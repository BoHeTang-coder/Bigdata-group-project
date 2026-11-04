# -*- coding: utf-8 -*-
"""
Probe how DuckDB reads the BTS CSV: trailing-comma column, sniffed types,
and the edge cases the cleaning step must handle (hhmm '2400', empty strings,
delay-field nulls for cancelled/diverted flights).
"""
import sys

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

GLOB = "data/bts/extracted/*/*.csv"
SAMPLE = "data/bts/extracted/2023/On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_2023_6.csv"

con = duckdb.connect()
con.execute("PRAGMA threads=6")

print("=" * 72)
print("1) default auto-detected schema (first 12 rows only, to read the header)")
print("=" * 72)
desc = con.execute(
    f"DESCRIBE SELECT * FROM read_csv('{SAMPLE}', header=true, encoding='latin-1')"
).fetchall()
print(f"column count = {len(desc)}")
for i, (name, typ, *rest) in enumerate(desc[:8]):
    print(f"  [{i:3d}] {name!r:42s} {typ}")
print(f"  ...")
for i, (name, typ, *rest) in enumerate(desc[-4:], start=len(desc) - 4):
    print(f"  [{i:3d}] {name!r:42s} {typ}")

print()
print("=" * 72)
print("2) read everything as VARCHAR, check the trailing column")
print("=" * 72)
desc2 = con.execute(
    f"DESCRIBE SELECT * FROM read_csv('{SAMPLE}', header=true, encoding='latin-1', all_varchar=true)"
).fetchall()
print(f"column count = {len(desc2)}")
print("first 3:", [d[0] for d in desc2[:3]])
print("last 3 :", [d[0] for d in desc2[-3:]])

print()
print("=" * 72)
print("3) type variety of the hhmm time fields (are they quoted?)")
print("=" * 72)
for col in ["CRSDepTime", "DepTime", "WheelsOff", "CRSArrTime", "ArrTime", "FlightDate"]:
    row = con.execute(
        f'SELECT "{col}" FROM read_csv(\'{SAMPLE}\', header=true, encoding=\'latin-1\', '
        f"all_varchar=true) WHERE \"{col}\" IS NOT NULL LIMIT 3"
    ).fetchall()
    print(f"  {col:12s} -> {[r[0] for r in row]}")

print()
print("=" * 72)
print("4) edge cases on one full month")
print("=" * 72)
q = f"""
WITH t AS (
  SELECT * FROM read_csv('{SAMPLE}', header=true, encoding='latin-1', all_varchar=true)
)
SELECT
  count(*)                                                AS rows,
  count(*) FILTER (WHERE "DepTime"   = '2400')            AS deptime_2400,
  count(*) FILTER (WHERE "ArrTime"   = '2400')            AS arrtime_2400,
  count(*) FILTER (WHERE "CRSDepTime"= '2400')            AS crsdep_2400,
  count(*) FILTER (WHERE "DepTime" IS NULL)               AS deptime_null,
  count(*) FILTER (WHERE "DepDelay" = '')                 AS depdelay_empty,
  count(*) FILTER (WHERE "ArrDelay" = '')                 AS arrdelay_empty,
  count(*) FILTER (WHERE "Cancelled" = '1.00')            AS cancelled,
  count(*) FILTER (WHERE "Diverted"  = '1.00')            AS diverted,
  count(*) FILTER (WHERE "CancellationCode" = '')         AS cancelcode_empty,
  count(DISTINCT "CancellationCode")                      AS cancelcode_distinct
FROM t
"""
for k, v in zip([d[0] for d in con.execute(q).description], con.execute(q).fetchone()):
    print(f"  {k:22s} {v:,}")

print()
print("=" * 72)
print("5) distinct values of the small categorical columns")
print("=" * 72)
for col, lim in [("Cancelled", 5), ("Diverted", 5), ("CancellationCode", 8),
                 ("DepDel15", 5), ("ArrDel15", 5), ("DistanceGroup", 12)]:
    vals = con.execute(
        f'SELECT "{col}", count(*) c FROM read_csv(\'{SAMPLE}\', header=true, '
        f"encoding='latin-1', all_varchar=true) GROUP BY 1 ORDER BY c DESC LIMIT {lim}"
    ).fetchall()
    print(f"  {col:20s} {[(v[0], v[1]) for v in vals]}")
