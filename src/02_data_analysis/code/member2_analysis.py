"""CS5488 member 2: reproducible airport clustering and flight-delay rule mining.

The five predeparture rule dimensions are season, scheduled departure period,
week type, distance band, reporting airline, and origin state. Rules use up to
three dimensions and are selected only on 2023-24; 2025 is held out.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import time
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler


EXPECTED = {
    2023: (6_847_899, "9b3df5081e4cf9e2e00364db8ccf49fed17a4be08dccee01099836b48e35963b"),
    2024: (7_079_061, "94bacd0732a5c70c5d997acfee916e6727f83729cb9ae6c09061344666aebabf"),
    2025: (7_001_619, "a399e0b8571beee130c8d9a4fe2d36322a3e1d11a26ffb056ae3a9e1bcbc424a"),
}
REQUIRED_COLUMNS = {
    "Year", "Month", "DayOfWeek", "FlightDate", "Origin", "OriginCityName",
    "OriginState", "Reporting_Airline", "CRSDepHour", "Distance", "Cancelled",
    "Diverted", "ArrDel15", "ArrDelayMinutes", "LateAircraftDelay",
    "WeatherDelay", "TotalCauseDelay",
}
CLUSTER_FEATURES = [
    "delay_rate", "cancel_rate", "mean_delayed_min", "late_share", "weather_share"
]
RULE_DIMENSIONS = [
    "season", "dep_period", "week_type", "distance_band", "airline", "origin_state"
]


def source_expr(data_dir: Path) -> str:
    paths = [data_dir / f"otp_{year}.parquet" for year in EXPECTED]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError("Missing Parquet files: " + ", ".join(missing))
    quoted = ["'" + str(p.resolve()).replace("'", "''") + "'" for p in paths]
    return "read_parquet([" + ", ".join(quoted) + "])"


def file_audit(db: duckdb.DuckDBPyConnection, data_dir: Path, source: str) -> pd.DataFrame:
    """Verify downloaded assets, schema and row totals before analysis."""
    available = {row[0] for row in db.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()}
    absent = REQUIRED_COLUMNS - available
    if absent:
        raise ValueError("Required columns missing: " + ", ".join(sorted(absent)))
    actual_rows = dict(db.execute(f"SELECT Year, count(*) FROM {source} GROUP BY Year").fetchall())
    if set(actual_rows) != set(EXPECTED):
        raise ValueError(f"Unexpected years: {actual_rows}")
    records = []
    for year, (expected_rows, expected_hash) in EXPECTED.items():
        path = data_dir / f"otp_{year}.parquet"
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                h.update(block)
        digest = h.hexdigest()
        count = actual_rows[year]
        if digest != expected_hash or count != expected_rows:
            raise ValueError(f"Asset check failed for {path.name}: rows={count}, sha256={digest}")
        records.append({"year": year, "rows": count, "bytes": path.stat().st_size,
                        "sha256": digest, "verified": True})
    return pd.DataFrame(records)


def annual_overview(db: duckdb.DuckDBPyConnection, source: str) -> pd.DataFrame:
    result = db.execute(f"""
        SELECT Year AS year, count(*) AS scheduled,
               count(*) FILTER (WHERE Cancelled=1) AS cancelled,
               count(*) FILTER (WHERE Diverted=1) AS diverted,
               count(*) FILTER (WHERE Cancelled=0 AND Diverted=0 AND ArrDel15 IS NULL)
                   AS executed_missing_arrdel15,
               count(*) FILTER (WHERE Cancelled=0 AND Diverted=0 AND ArrDel15 IS NOT NULL)
                   AS delay_denominator,
               count(*) FILTER (WHERE Cancelled=0 AND Diverted=0 AND ArrDel15=1)
                   AS delayed
        FROM {source} GROUP BY Year ORDER BY Year
    """).df()
    result["delay_rate"] = result.delayed / result.delay_denominator
    result["cancel_rate"] = result.cancelled / result.scheduled
    if not (result.scheduled.sum() == 20_928_579 and
            result.delay_denominator.sum() == 20_588_134 and
            result.delayed.sum() == 4_371_303):
        raise ValueError("Annual totals no longer match the verified release")
    return result


def airport_profiles(db: duckdb.DuckDBPyConnection, source: str) -> pd.DataFrame:
    profiles = db.execute(f"""
        SELECT Origin AS airport, min(OriginCityName) AS city,
               count(*) AS scheduled,
               count(*) FILTER (WHERE Cancelled=0 AND Diverted=0 AND ArrDel15 IS NOT NULL)
                   AS delay_denominator,
               count(*) FILTER (WHERE Cancelled=0 AND Diverted=0 AND ArrDel15=1) AS delayed,
               count(*) FILTER (WHERE Cancelled=1) AS cancelled,
               sum(ArrDelayMinutes) FILTER (WHERE ArrDel15=1) AS delayed_arrival_minutes,
               sum(LateAircraftDelay) AS late_minutes,
               sum(WeatherDelay) AS weather_minutes,
               sum(TotalCauseDelay) AS cause_minutes
        FROM {source} GROUP BY Origin
    """).df()
    profiles["delay_rate"] = profiles.delayed / profiles.delay_denominator
    profiles["cancel_rate"] = profiles.cancelled / profiles.scheduled
    profiles["mean_delayed_min"] = profiles.delayed_arrival_minutes / profiles.delayed
    profiles["late_share"] = profiles.late_minutes / profiles.cause_minutes
    profiles["weather_share"] = profiles.weather_minutes / profiles.cause_minutes
    return profiles.sort_values("scheduled", ascending=False).reset_index(drop=True)


def cluster_airports(profiles: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Use an explicit minimum volume and report threshold sensitivity."""
    eligible = profiles.loc[profiles.scheduled >= 30_000].dropna(subset=CLUSTER_FEATURES).copy()
    if len(eligible) != 101:
        raise ValueError(f"Unexpected number of eligible airports: {len(eligible)}")
    scaler = StandardScaler()
    X = scaler.fit_transform(eligible[CLUSTER_FEATURES])
    candidates = []
    for k in range(2, 7):
        model = KMeans(n_clusters=k, n_init=50, random_state=5488)
        labels = model.fit_predict(X)
        candidates.append({"k": k, "silhouette": silhouette_score(X, labels),
                           "smallest_cluster": int(np.bincount(labels).min())})
    diagnostics = pd.DataFrame(candidates)
    allowed = diagnostics.loc[diagnostics.smallest_cluster >= 5]
    best_k = int(allowed.sort_values("silhouette", ascending=False).iloc[0].k)
    model = KMeans(n_clusters=best_k, n_init=50, random_state=5488)
    eligible["cluster"] = model.fit_predict(X) + 1
    eligible.to_csv(out / "airport_clusters.csv", index=False)

    summary = eligible.groupby("cluster").agg(
        airports=("airport", "size"), scheduled=("scheduled", "sum"),
        delay_denominator=("delay_denominator", "sum"), delayed=("delayed", "sum"),
        cancelled=("cancelled", "sum"), delay_rate=("delay_rate", "mean"),
        cancel_rate=("cancel_rate", "mean"), mean_delayed_min=("mean_delayed_min", "mean"),
        late_share=("late_share", "mean"), weather_share=("weather_share", "mean"),
    ).reset_index()
    summary["flight_weighted_delay_rate"] = summary.delayed / summary.delay_denominator
    summary["flight_weighted_cancel_rate"] = summary.cancelled / summary.scheduled
    summary.to_csv(out / "cluster_summary.csv", index=False)

    # Refit on alternate volume thresholds; compare common airports, not numeric labels.
    base = eligible.set_index("airport")["cluster"]
    threshold_rows = []
    for threshold in (20_000, 30_000, 50_000):
        q = profiles.loc[profiles.scheduled >= threshold].dropna(subset=CLUSTER_FEATURES)
        xx = StandardScaler().fit_transform(q[CLUSTER_FEATURES])
        labels = KMeans(n_clusters=best_k, n_init=50, random_state=5488).fit_predict(xx)
        alternate = pd.Series(labels, index=q.airport)
        common = base.index.intersection(alternate.index)
        threshold_rows.append({"minimum_scheduled": threshold, "airports": len(q),
                               "flight_coverage": q.scheduled.sum() / profiles.scheduled.sum(),
                               "silhouette": silhouette_score(xx, labels),
                               "smallest_cluster": int(np.bincount(labels).min()),
                               "ari_vs_30000": adjusted_rand_score(base[common], alternate[common])})
    sensitivity = pd.DataFrame(threshold_rows)
    sensitivity.to_csv(out / "cluster_sensitivity.csv", index=False)
    diagnostics.to_csv(out / "cluster_k_diagnostics.csv", index=False)

    pca = PCA(n_components=2, random_state=5488)
    xy = pca.fit_transform(X)
    fig, ax = plt.subplots(figsize=(9, 6))
    for cluster, group in eligible.groupby("cluster"):
        idx = eligible.index.get_indexer(group.index)
        ax.scatter(xy[idx, 0], xy[idx, 1], s=np.sqrt(group.scheduled) / 8,
                   alpha=.7, label=f"Group {cluster} ({len(group)} airports)")
    for _, row in eligible.nlargest(10, "scheduled").iterrows():
        idx = eligible.index.get_loc(row.name)
        ax.annotate(row.airport, xy[idx], xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.set(xlabel=f"PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)",
           ylabel=f"PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)",
           title="Departure-airport profiles, 2023–2025")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out / "airport_clusters.png", dpi=250)
    plt.close(fig)
    return eligible, summary, diagnostics


def build_rule_cube(db: duckdb.DuckDBPyConnection, source: str) -> pd.DataFrame:
    """One scan creates a small transaction cube for exhaustive 1-3-item mining."""
    cube = db.execute(f"""
        SELECT Year AS year,
               CASE WHEN Month IN (12,1,2) THEN 'winter'
                    WHEN Month IN (3,4,5) THEN 'spring'
                    WHEN Month IN (6,7,8) THEN 'summer' ELSE 'autumn' END AS season,
               CASE WHEN CRSDepHour BETWEEN 0 AND 5 THEN 'overnight'
                    WHEN CRSDepHour BETWEEN 6 AND 11 THEN 'morning'
                    WHEN CRSDepHour BETWEEN 12 AND 17 THEN 'afternoon'
                    ELSE 'evening' END AS dep_period,
               CASE WHEN DayOfWeek IN (6,7) THEN 'weekend' ELSE 'weekday' END AS week_type,
               CASE WHEN Distance < 500 THEN 'short'
                    WHEN Distance < 1000 THEN 'medium' ELSE 'long' END AS distance_band,
               Reporting_Airline AS airline, OriginState AS origin_state,
               count(*) AS n, count(*) FILTER (WHERE ArrDel15=1) AS delayed
        FROM {source}
        WHERE Cancelled=0 AND Diverted=0 AND ArrDel15 IS NOT NULL
          AND CRSDepHour BETWEEN 0 AND 23
          AND Month BETWEEN 1 AND 12 AND DayOfWeek BETWEEN 1 AND 7
          AND Distance IS NOT NULL AND Reporting_Airline IS NOT NULL
          AND OriginState IS NOT NULL
        GROUP BY ALL
    """).df()
    return cube


def mine_rules(cube: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Enumerate observed itemsets, select on training only, attach 2025 results."""
    train = cube.loc[cube.year.isin([2023, 2024])]
    test = cube.loc[cube.year == 2025]
    n_train, d_train = int(train.n.sum()), int(train.delayed.sum())
    n_test, d_test = int(test.n.sum()), int(test.delayed.sum())
    rows = []
    total_candidates = 0
    for size in (1, 2, 3):
        for dims in itertools.combinations(RULE_DIMENSIONS, size):
            a = train.groupby(list(dims), dropna=False)[["n", "delayed"]].sum().reset_index()
            b = test.groupby(list(dims), dropna=False)[["n", "delayed"]].sum().reset_index()
            both = a.merge(b, on=list(dims), how="left", suffixes=("_train", "_test"))
            both[["n_test", "delayed_test"]] = both[["n_test", "delayed_test"]].fillna(0)
            total_candidates += len(both)
            for row in both.itertuples(index=False):
                values = [getattr(row, d) for d in dims]
                nt, dt = int(row.n_train), int(row.delayed_train)
                ns, ds = int(row.n_test), int(row.delayed_test)
                joint_support = dt / n_train
                if joint_support < .005 or nt < 50_000:
                    continue
                confidence = dt / nt
                lift = confidence / (d_train / n_train)
                if lift < 1.20:
                    continue
                rule = " & ".join(f"{d}={v}" for d, v in zip(dims, values))
                risk_unexposed_train = (d_train - dt) / (n_train - nt)
                risk_unexposed_test = (d_test - ds) / (n_test - ns) if ns < n_test else np.nan
                rows.append({
                    "antecedent": rule, "item_count": size,
                    "train_antecedent_n": nt, "train_delayed_n": dt,
                    "train_antecedent_coverage": nt / n_train,
                    "train_support": joint_support, "train_confidence": confidence,
                    "train_lift": lift,
                    "train_risk_difference_pp": 100 * (confidence - risk_unexposed_train),
                    "test_antecedent_n": ns, "test_delayed_n": ds,
                    "test_support": ds / n_test,
                    "test_confidence": ds / ns if ns else np.nan,
                    "test_lift": (ds / ns) / (d_test / n_test) if ns else np.nan,
                    "test_risk_difference_pp": 100 * ((ds / ns) - risk_unexposed_test) if ns else np.nan,
                })
    result = pd.DataFrame(rows).sort_values(["train_lift", "train_support"], ascending=False)
    result.to_csv(out / "association_rules.csv", index=False)
    meta = pd.DataFrame([{"candidate_itemsets": total_candidates,
                          "selected_rules": len(result),
                          "min_joint_support": .005, "min_train_antecedent_n": 50_000,
                          "min_train_lift": 1.20,
                          "train_flights": n_train, "test_flights": n_test,
                          "train_delay_baseline": d_train / n_train,
                          "test_delay_baseline": d_test / n_test}])
    meta.to_csv(out / "rule_mining_audit.csv", index=False)
    return result, meta


def summer_evening_validation(db: duckdb.DuckDBPyConnection, source: str, out: Path) -> pd.DataFrame:
    """Previously observed temporal finding, separate from mined top rules."""
    table = db.execute(f"""
        SELECT Year AS year,
               CASE WHEN Month BETWEEN 6 AND 8 THEN 1 ELSE 0 END AS summer,
               CASE WHEN CRSDepHour BETWEEN 18 AND 23 THEN 1 ELSE 0 END AS evening,
               count(*) AS n, count(*) FILTER (WHERE ArrDel15=1) AS delayed
        FROM {source}
        WHERE Cancelled=0 AND Diverted=0 AND ArrDel15 IS NOT NULL
        GROUP BY ALL ORDER BY ALL
    """).df()
    table["delay_rate"] = table.delayed / table.n
    table.to_csv(out / "summer_evening_by_year.csv", index=False)
    return table


def stratified_evening_validation(db: duckdb.DuckDBPyConnection, source: str,
                                  out: Path) -> pd.DataFrame:
    """Within summer, compare evening with other hours in the same month/airport/airline.

    This is a descriptive stratified comparison, not a causal estimate. Strata
    with fewer than 30 flights in either timing group are excluded.
    """
    data = db.execute(f"""
        SELECT Year AS y, Month AS m, Origin AS airport,
               Reporting_Airline AS airline,
               CAST(CRSDepHour BETWEEN 18 AND 23 AS INTEGER) AS evening,
               count(*) AS n, count(*) FILTER (WHERE ArrDel15=1) AS delayed
        FROM {source}
        WHERE Month BETWEEN 6 AND 8 AND Cancelled=0 AND Diverted=0
          AND ArrDel15 IS NOT NULL AND CRSDepHour BETWEEN 0 AND 23
        GROUP BY ALL
    """).df()
    rows = []
    for year, group in data.groupby("y"):
        table = group.pivot_table(index=["m", "airport", "airline"], columns="evening",
                                  values=["n", "delayed"], aggfunc="sum").fillna(0)
        table.columns = [f"{metric}_{flag}" for metric, flag in table.columns]
        table = table.loc[(table.n_1 >= 30) & (table.n_0 >= 30)].copy()
        table["risk_difference"] = table.delayed_1 / table.n_1 - table.delayed_0 / table.n_0
        exposed_total = int(group.loc[group.evening == 1, "n"].sum())
        rows.append({
            "year": int(year), "eligible_strata": len(table),
            "evening_flights_covered": int(table.n_1.sum()),
            "evening_coverage": float(table.n_1.sum() / exposed_total),
            "exposed_weighted_risk_difference_pp":
                float(100 * np.average(table.risk_difference, weights=table.n_1)),
            "fraction_strata_positive": float((table.risk_difference > 0).mean()),
        })
    result = pd.DataFrame(rows)
    result.to_csv(out / "stratified_evening_check.csv", index=False)
    return result


def rule_plots(rules: pd.DataFrame, out: Path) -> None:
    short_names = {
        "season=summer": "Summer", "dep_period=evening": "evening",
        "distance_band=medium": "500–999 mi", "distance_band=long": "1,000+ mi",
        "distance_band=short": "<500 mi", "week_type=weekend": "weekend",
        "week_type=weekday": "weekday", "airline=WN": "WN", "origin_state=FL": "Florida",
    }

    def display_rule(rule: str) -> str:
        return " + ".join(short_names.get(part, part) for part in rule.split(" & "))

    shown = rules.head(8).iloc[::-1].copy()
    shown["display"] = shown.antecedent.map(display_rule)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh(shown.display, shown.train_lift, label="2023–24", color="#3867a6")
    ax.scatter(shown.test_lift, shown.display, label="2025", color="#d45d39", zorder=3)
    ax.axvline(1, color="black", linewidth=.8)
    ax.set(xlabel="Lift for arrival delay >=15 min", title="Top mined rules: 2023–24 ranking and 2025 temporal check")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out / "association_rules.png", dpi=250)
    plt.close(fig)

    shown = rules.head(7)
    fig, ax = plt.subplots(figsize=(10, 6.5))
    points = ax.scatter(shown.train_support * 100, shown.train_confidence * 100,
                        c=shown.train_lift, s=100 + 50 * shown.item_count,
                        cmap="viridis", edgecolor="white")
    for row in shown.itertuples():
        label = display_rule(row.antecedent)
        ax.annotate(label, (row.train_support * 100, row.train_confidence * 100),
                    xytext=(5, 4), textcoords="offset points", fontsize=7)
    ax.set(xlabel="Support (% of all executed flights)",
           ylabel="Confidence (% delayed given conditions)",
           title="Mined flight-delay rules, 2023–2024")
    ax.set_xlim(0.4, 3.5)
    ax.set_ylim(34, 46)
    fig.colorbar(points, ax=ax, label="Lift")
    fig.tight_layout()
    fig.savefig(out / "rule_support_confidence.png", dpi=250)
    plt.close(fig)


def analyze(data_dir: Path, output_dir: Path) -> dict:
    data_dir, out = Path(data_dir), Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    db = duckdb.connect()
    db.execute("SET threads=4")
    source = source_expr(data_dir)
    times = []
    last = time.perf_counter()

    def mark(stage: str) -> None:
        nonlocal last
        now = time.perf_counter()
        times.append({"stage": stage, "seconds": round(now - last, 3)})
        last = now

    audit = file_audit(db, data_dir, source)
    audit.to_csv(out / "data_audit.csv", index=False)
    mark("file hashes, schema and row audit")
    yearly = annual_overview(db, source)
    yearly.to_csv(out / "yearly_overview.csv", index=False)
    mark("annual overview")
    airports = airport_profiles(db, source)
    airports.to_csv(out / "airport_profiles_all.csv", index=False)
    mark("airport-level aggregation")
    eligible, cluster_summary, k_diag = cluster_airports(airports, out)
    mark("clustering, sensitivity and PCA")
    cube = build_rule_cube(db, source)
    cube.to_csv(out / "rule_cube.csv", index=False)
    mark("transaction cube aggregation")
    rules, rule_meta = mine_rules(cube, out)
    mark("exhaustive rule mining")
    summer_evening_validation(db, source, out)
    mark("temporal-rule validation")
    stratified_evening_validation(db, source, out)
    mark("within-stratum robustness check")
    rule_plots(rules, out)
    mark("rule figures")
    pd.DataFrame(times).to_csv(out / "runtime_profile.csv", index=False)
    summary = {
        "scheduled": int(yearly.scheduled.sum()),
        "delay_denominator": int(yearly.delay_denominator.sum()),
        "delayed": int(yearly.delayed.sum()),
        "airports_total": len(airports), "airports_clustered": len(eligible),
        "clustered_flight_coverage": float(eligible.scheduled.sum() / yearly.scheduled.sum()),
        "selected_k": int(k_diag.sort_values("silhouette", ascending=False).iloc[0].k),
        "candidate_itemsets": int(rule_meta.candidate_itemsets.iloc[0]),
        "selected_rules": len(rules),
    }
    (out / "analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(pd.DataFrame(times).to_string(index=False))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.data_dir, args.output_dir)


if __name__ == "__main__":
    main()
