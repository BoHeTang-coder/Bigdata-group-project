# -*- coding: utf-8 -*-
"""
Compute every aggregate the charts need, from the clean Parquet files.
Writes small CSVs to data/bts/analysis/ so plotting can iterate without
re-scanning 20.9M rows, and so teammates can reuse the numbers directly.

Delay-rate convention used everywhere:
    delay rate = mean(ArrDel15) over flights with ArrDel15 NOT NULL
    denominator = operated flights (ArrDel15 is NULL for cancelled/diverted)
"""
import json
import os
import sys
import time

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BTS = os.path.join(ROOT, "data", "bts")
CLEAN = os.path.join(BTS, "clean", "otp_*.parquet").replace("\\", "/")
OUT = os.path.join(BTS, "analysis")
CAUSES = ["CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay"]


def main():
    os.makedirs(OUT, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=6")
    con.execute("PRAGMA memory_limit='6GB'")

    t0 = time.time()
    P = f"read_parquet('{CLEAN}')"
    summary = {}

    def dump(name, sql):
        df = con.execute(sql).fetchdf()
        p = os.path.join(OUT, name)
        df.to_csv(p, index=False, encoding="utf-8-sig")
        print(f"  {name:34s} {len(df):>7,} rows")
        return df

    print("computing aggregates ...")

    # ---------------------------------------------------------------- overview
    ov = con.execute(f"""
        SELECT
            count(*)                                                   AS total_flights,
            count(*) FILTER (WHERE Cancelled = 1)                      AS cancelled,
            count(*) FILTER (WHERE Diverted  = 1)                      AS diverted,
            count(*) FILTER (WHERE ArrDel15 IS NOT NULL)               AS operated,
            count(*) FILTER (WHERE ArrDel15 = 1)                       AS delayed15,
            avg(ArrDel15) FILTER (WHERE ArrDel15 IS NOT NULL)          AS delay_rate,
            avg(ArrDelay) FILTER (WHERE ArrDelay IS NOT NULL
                                    AND Cancelled = 0 AND Diverted = 0) AS mean_arr_delay,
            median(ArrDelay) FILTER (WHERE ArrDelay IS NOT NULL
                                    AND Cancelled = 0 AND Diverted = 0) AS median_arr_delay,
            avg(DepDelay) FILTER (WHERE DepDelay IS NOT NULL
                                    AND Cancelled = 0)                 AS mean_dep_delay,
            sum(TotalCauseDelay)                                       AS total_cause_minutes,
            count(DISTINCT Reporting_Airline)                          AS n_carriers,
            count(DISTINCT Origin)                                     AS n_airports
        FROM {P}
    """).fetchdf()
    ov.to_json(os.path.join(OUT, "overview.json"), orient="records", indent=2)
    print("  overview.json")
    summary["overview"] = ov.to_dict("records")[0]

    # ------------------------------------------------- 1. delay distribution
    dump("delay_hist.csv", f"""
        SELECT
            CASE WHEN ArrDelay < -60 THEN -61
                 WHEN ArrDelay > 180 THEN 181
                 ELSE CAST(floor(ArrDelay) AS INTEGER) END AS bucket,
            count(*)                                      AS flights
        FROM {P}
        WHERE ArrDelay IS NOT NULL AND Cancelled = 0 AND Diverted = 0
        GROUP BY 1 ORDER BY 1
    """)

    # ------------------------------------------- 2. month x day-of-week matrix
    dump("month_weekday.csv", f"""
        SELECT Month, DayOfWeek,
               count(*) FILTER (WHERE ArrDel15 IS NOT NULL)  AS flights,
               avg(ArrDel15) FILTER (WHERE ArrDel15 IS NOT NULL) AS delay_rate,
               avg(ArrDelay) FILTER (WHERE ArrDelay IS NOT NULL
                                     AND Cancelled = 0 AND Diverted = 0) AS mean_arr_delay
        FROM {P} GROUP BY 1,2 ORDER BY 1,2
    """)

    # --------------------------------------------------- 3. airline ranking
    dump("airline.csv", f"""
        SELECT Reporting_Airline                                       AS carrier,
               count(*)                                                AS flights,
               avg(ArrDel15) FILTER (WHERE ArrDel15 IS NOT NULL)       AS delay_rate,
               avg(DepDelay) FILTER (WHERE DepDelay IS NOT NULL)       AS mean_dep_delay,
               avg(ArrDelay) FILTER (WHERE ArrDelay IS NOT NULL
                                     AND Cancelled = 0 AND Diverted = 0) AS mean_arr_delay,
               avg(Cancelled)                                          AS cancel_rate,
               avg(CASE WHEN ArrDelay > 0 THEN ArrDelay END)
                   FILTER (WHERE ArrDelay IS NOT NULL)                 AS mean_positive_delay
        FROM {P} GROUP BY 1 ORDER BY flights DESC
    """)

    # --------------------------------------------------- 4. airport ranking
    dump("airport.csv", f"""
        SELECT Origin                                          AS airport,
               any_value(OriginCityName)                       AS city,
               any_value(OriginState)                          AS state,
               count(*)                                        AS flights,
               avg(ArrDel15) FILTER (WHERE ArrDel15 IS NOT NULL) AS delay_rate,
               avg(DepDelay) FILTER (WHERE DepDelay IS NOT NULL) AS mean_dep_delay,
               avg(ArrDelay) FILTER (WHERE ArrDelay IS NOT NULL
                                     AND Cancelled = 0 AND Diverted = 0) AS mean_arr_delay,
               avg(Cancelled)                                  AS cancel_rate
        FROM {P} GROUP BY 1 HAVING count(*) >= 20000 ORDER BY delay_rate DESC
    """)

    # ------------------------------------------------------ 5. delay causes
    union = " UNION ALL ".join(
        f"SELECT Year, '{c}' AS cause, sum({c}) AS minutes FROM {P} GROUP BY Year"
        for c in CAUSES)
    dump("causes_by_year.csv", f"""
        SELECT Year, cause, minutes,
               minutes / sum(minutes) OVER (PARTITION BY Year) AS share
        FROM ({union}) ORDER BY Year, minutes DESC
    """)
    dump("causes_total.csv", f"""
        SELECT cause, minutes, minutes / sum(minutes) OVER () AS share
        FROM (SELECT cause, sum(minutes) AS minutes FROM ({union}) GROUP BY 1)
        ORDER BY minutes DESC
    """)

    # ----------------------------------------------------- 6. hourly pattern
    dump("hourly.csv", f"""
        SELECT Year, CRSDepHour,
               count(*)                                        AS flights,
               avg(ArrDel15) FILTER (WHERE ArrDel15 IS NOT NULL) AS delay_rate,
               avg(ArrDelay) FILTER (WHERE ArrDelay IS NOT NULL
                                     AND Cancelled = 0 AND Diverted = 0) AS mean_arr_delay
        FROM {P} WHERE CRSDepHour IS NOT NULL
        GROUP BY 1,2 ORDER BY 1,2
    """)

    # ----------------------------------------------------- 7. monthly trend
    dump("monthly.csv", f"""
        SELECT Year, Month,
               count(*)                                        AS flights,
               avg(ArrDel15) FILTER (WHERE ArrDel15 IS NOT NULL) AS delay_rate,
               avg(Cancelled)                                  AS cancel_rate,
               avg(ArrDelay) FILTER (WHERE ArrDelay IS NOT NULL
                                     AND Cancelled = 0 AND Diverted = 0) AS mean_arr_delay
        FROM {P} GROUP BY 1,2 ORDER BY 1,2
    """)

    # --------------------------------------- 8. airport x cause composition
    dump("airport_cause.csv", f"""
        WITH top AS (
            SELECT Origin FROM {P} GROUP BY 1 ORDER BY count(*) DESC LIMIT 12
        )
        SELECT t.Origin AS airport, c.cause, sum(c.minutes) AS minutes
        FROM (
            {" UNION ALL ".join(
                f"SELECT Origin, '{x}' AS cause, {x} AS minutes FROM {P} "
                f"WHERE Origin IN (SELECT Origin FROM top)" for x in CAUSES)}
        ) c
        JOIN top t ON t.Origin = c.Origin
        GROUP BY 1,2 ORDER BY 1,2
    """)

    # --------------------------------------------- carrier x cause composition
    dump("carrier_cause.csv", f"""
        SELECT Reporting_Airline AS carrier, cause, sum(minutes) AS minutes
        FROM (
            {" UNION ALL ".join(
                f"SELECT Reporting_Airline, '{x}' AS cause, {x} AS minutes FROM {P}"
                for x in CAUSES)}
        )
        GROUP BY 1,2 ORDER BY 1,2
    """)

    summary["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    summary["runtime_sec"] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, "aggregate_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\ndone in {time.time()-t0:.1f}s -> {OUT}")


if __name__ == "__main__":
    main()
