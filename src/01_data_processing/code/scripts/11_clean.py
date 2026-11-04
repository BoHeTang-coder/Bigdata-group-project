# -*- coding: utf-8 -*-
"""
Clean the BTS On-Time Performance CSVs into typed Parquet, one file per year.

Cleaning decisions (all documented in data/bts/clean/DATA_DICTIONARY.md):
  * drop the stray trailing-comma column (`column109`) that BTS appends
  * empty strings -> NULL (DuckDB already does this for us)
  * hhmm time strings ("0800", and "2400" for midnight) -> SMALLINT
  * Cancelled / Diverted / DepDel15 / ArrDel15  "0.00"/"1.00" -> TINYINT 0/1
  * keep ALL rows, including cancelled and diverted flights. Their delay
    fields are legitimately NULL; filtering is the analyst's choice.
  * add a small set of clearly-named derived columns (prefix-free, documented)

Output: data/bts/clean/otp_<year>.parquet   (ZSTD)
        data/bts/clean/clean_summary.json
"""
import json
import os
import sys
import time

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BTS = os.path.join(ROOT, "data", "bts")
EXTRACTED = os.path.join(BTS, "extracted")
OUTDIR = os.path.join(BTS, "clean")
SCHEMA = os.path.join(BTS, "docs", "schema_check.json")

# ---------------------------------------------------------------- type maps
HHMM = ["CRSDepTime", "DepTime", "WheelsOff", "WheelsOn", "CRSArrTime", "ArrTime",
        "FirstDepTime"] + [f"Div{i}{s}" for i in range(1, 6)
                           for s in ("WheelsOn", "WheelsOff")]

FLAG01 = ["Cancelled", "Diverted", "DepDel15", "ArrDel15"]

SMALLINT = ["Year", "Quarter", "Month", "DayofMonth", "DayOfWeek",
            "OriginWac", "DestWac", "DistanceGroup",
            "DepartureDelayGroups", "ArrivalDelayGroups", "DivAirportLandings"]

INTEGER = ["DOT_ID_Reporting_Airline", "Flight_Number_Reporting_Airline",
           "OriginAirportID", "OriginAirportSeqID", "OriginCityMarketID",
           "DestAirportID", "DestAirportSeqID", "DestCityMarketID"] + \
          [f"Div{i}{s}" for i in range(1, 6) for s in ("AirportID", "AirportSeqID")]

DOUBLE = ["DepDelay", "DepDelayMinutes", "TaxiOut", "TaxiIn",
          "ArrDelay", "ArrDelayMinutes",
          "CRSElapsedTime", "ActualElapsedTime", "AirTime", "Flights", "Distance",
          "CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay",
          "LateAircraftDelay", "TotalAddGTime", "LongestAddGTime",
          "DivReachedDest",
          "DivActualElapsedTime", "DivArrDelay", "DivDistance"] + \
         [f"Div{i}{s}" for i in range(1, 6) for s in ("TotalGTime", "LongestGTime")]

VARCHAR = ["Reporting_Airline", "IATA_CODE_Reporting_Airline", "Tail_Number",
           "Origin", "OriginCityName", "OriginState", "OriginStateFips",
           "OriginStateName", "Dest", "DestCityName", "DestState",
           "DestStateFips", "DestStateName", "DepTimeBlk", "ArrTimeBlk",
           "CancellationCode"] + \
          [f"Div{i}{s}" for i in range(1, 6) for s in ("Airport", "TailNum")]

DATE = ["FlightDate"]

DERIVED = ["CRSDepHour", "CRSArrHour", "Route", "IsWeekend", "TotalCauseDelay"]


def build_select(cols):
    """cols = the 109 official CSV columns, in order."""
    tmap = {}
    for c in HHMM:
        tmap[c] = "SMALLINT"
    for c in FLAG01:
        tmap[c] = "FLAG"
    for c in SMALLINT:
        tmap[c] = "SMALLINT"
    for c in INTEGER:
        tmap[c] = "INTEGER"
    for c in DOUBLE:
        tmap[c] = "DOUBLE"
    for c in VARCHAR:
        tmap[c] = "VARCHAR"
    for c in DATE:
        tmap[c] = "DATE"

    missing = [c for c in cols if c not in tmap]
    if missing:
        raise SystemExit(f"unclassified columns: {missing}")
    extra = [c for c in tmap if c not in cols]
    if extra:
        raise SystemExit(f"type map has columns not in CSV: {extra}")

    parts = []
    for c in cols:
        q = f'"{c}"'
        t = tmap[c]
        if t == "FLAG":
            # "0.00"/"1.00" -> 0/1 ; NULL stays NULL
            parts.append(f'TRY_CAST(TRY_CAST({q} AS DOUBLE) AS TINYINT) AS "{c}"')
        elif t == "DATE":
            parts.append(f'TRY_CAST({q} AS DATE) AS "{c}"')
        else:
            parts.append(f'TRY_CAST({q} AS {t}) AS "{c}"')

    # ---- derived columns (named clearly, documented in the data dictionary)
    parts.append('TRY_CAST(floor(TRY_CAST("CRSDepTime" AS INTEGER)/100) % 24 AS TINYINT) '
                 'AS "CRSDepHour"')
    parts.append('TRY_CAST(floor(TRY_CAST("CRSArrTime" AS INTEGER)/100) % 24 AS TINYINT) '
                 'AS "CRSArrHour"')
    parts.append('("Origin" || \'-\' || "Dest") AS "Route"')
    parts.append('(TRY_CAST("DayOfWeek" AS INTEGER) IN (6,7)) AS "IsWeekend"')
    # Sum of the five cause fields. If a carrier reported none of them at all
    # (all NULL) we keep NULL instead of pretending the delay had zero cause.
    all_null = " AND ".join(f'"{c}" IS NULL' for c in
                            ["CarrierDelay", "WeatherDelay", "NASDelay",
                             "SecurityDelay", "LateAircraftDelay"])
    total = " + ".join(f'COALESCE(TRY_CAST("{c}" AS DOUBLE),0)' for c in
                       ["CarrierDelay", "WeatherDelay", "NASDelay",
                        "SecurityDelay", "LateAircraftDelay"])
    parts.append(f'(CASE WHEN {all_null} THEN NULL ELSE ({total}) END) AS "TotalCauseDelay"')
    return ",\n    ".join(parts)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    cols = json.load(open(SCHEMA, encoding="utf-8"))["csv_columns"]
    print(f"official columns: {len(cols)}")

    con = duckdb.connect()
    con.execute("PRAGMA threads=6")
    con.execute("PRAGMA memory_limit='6GB'")
    con.execute("PRAGMA preserve_insertion_order=false")   # lower memory

    sel = build_select(cols)
    summary = {"columns_kept": len(cols), "derived_columns": DERIVED, "years": {}}
    t_all = time.time()

    for year in (2023, 2024, 2025):
        src = os.path.join(EXTRACTED, str(year), "*.csv").replace("\\", "/")
        dst = os.path.join(OUTDIR, f"otp_{year}.parquet").replace("\\", "/")
        t0 = time.time()
        print(f"\n[{year}] reading {src}")

        def run(parallel):
            con.execute(f"""
                COPY (
                    SELECT
                        {sel}
                    FROM read_csv('{src}', header=true, encoding='latin-1',
                                  all_varchar=true, sample_size=-1,
                                  parallel={'true' if parallel else 'false'})
                ) TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 1000000)
            """)

        try:
            run(True)
        except duckdb.NotImplementedException as e:
            # Some monthly files trip DuckDB's parallel CSV reader; it tells us
            # to re-read single-threaded. Retry rather than lose the year.
            print(f"[{year}] parallel reader unsupported -> retrying single-threaded")
            run(False)

        n, = con.execute(f"SELECT count(*) FROM read_parquet('{dst}')").fetchone()
        size = os.path.getsize(dst)
        dt = time.time() - t0
        summary["years"][str(year)] = {"rows": n, "parquet_bytes": size}
        print(f"[{year}] rows={n:,}  parquet={size/2**30:.2f} GB  ({dt/60:.1f} min)")

    con.close()
    summary["total_rows"] = sum(v["rows"] for v in summary["years"].values())
    summary["total_bytes"] = sum(v["parquet_bytes"] for v in summary["years"].values())
    summary["total_gb"] = round(summary["total_bytes"] / 2**30, 3)
    summary["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    with open(os.path.join(OUTDIR, "clean_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 64)
    print(f"TOTAL rows={summary['total_rows']:,}  parquet={summary['total_gb']} GB  "
          f"({(time.time()-t_all)/60:.1f} min)")


if __name__ == "__main__":
    main()
