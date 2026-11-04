# -*- coding: utf-8 -*-
"""Is December really a secondary delay peak, or is it a holiday-window effect?"""
import os
import sys

import duckdb

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
GLOB = os.path.join(ROOT, "data", "bts", "clean", "otp_*.parquet").replace("\\", "/")
con = duckdb.connect()
con.execute("PRAGMA threads=6")

print("=" * 74)
print("A) DECEMBER BY DAY-OF-MONTH (all 3 years pooled)")
print("=" * 74)
rows = con.execute(f"""
    SELECT DayofMonth,
           round(100.0*avg(ArrDel15), 1) AS delay_pct,
           count(*) AS flights
    FROM read_parquet('{GLOB}') WHERE Month = 12
    GROUP BY 1 ORDER BY 1
""").fetchall()
for d, p, n in rows:
    bar = "#" * int(p)
    print(f"  Dec {d:2d}  {p:5.1f}%  {bar}")

print()
print("=" * 74)
print("B) DEC vs the rest of the year, split by holiday window")
print("=" * 74)
r = con.execute(f"""
    SELECT
      round(100.0*avg(ArrDel15) FILTER (WHERE Month=12 AND DayofMonth BETWEEN 18 AND 31),1) AS dec_holiday,
      round(100.0*avg(ArrDel15) FILTER (WHERE Month=12 AND DayofMonth BETWEEN 1 AND 17),1)  AS dec_early,
      round(100.0*avg(ArrDel15) FILTER (WHERE Month IN (6,7)),1)                            AS jun_jul,
      round(100.0*avg(ArrDel15) FILTER (WHERE Month IN (9,10,11)),1)                        AS autumn,
      round(100.0*avg(ArrDel15),1)                                                          AS all_year
    FROM read_parquet('{GLOB}')
""").fetchone()
print(f"  Dec 18-31 (holiday) : {r[0]}%")
print(f"  Dec 1-17            : {r[1]}%")
print(f"  Jun-Jul             : {r[2]}%")
print(f"  Sep-Nov (autumn)    : {r[3]}%")
print(f"  all year            : {r[4]}%")

print()
print("=" * 74)
print("C) SAME TEST FOR THE OTHER SUSPECT WINDOWS")
print("=" * 74)
r = con.execute(f"""
    SELECT
      round(100.0*avg(ArrDel15) FILTER (WHERE Month=1),1)  AS jan,
      round(100.0*avg(ArrDel15) FILTER (WHERE Month=3),1)  AS mar,
      round(100.0*avg(ArrDel15) FILTER (WHERE Month=5),1)  AS may,
      round(100.0*avg(ArrDel15) FILTER (WHERE Month=8),1)  AS aug,
      round(100.0*avg(ArrDel15) FILTER (WHERE Month=12),1) AS dec,
      round(100.0*avg(ArrDel15) FILTER (WHERE Month=11),1) AS nov
    FROM read_parquet('{GLOB}')
""").fetchone()
print(f"  Jan={r[0]}%  Mar={r[1]}%  May={r[2]}%  Aug={r[3]}%  Dec={r[4]}%  Nov={r[5]}%")
