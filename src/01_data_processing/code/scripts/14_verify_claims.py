# -*- coding: utf-8 -*-
"""Verify the causal claims used in the figure captions before shipping them."""
import os
import sys

import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
P = f"read_parquet('{os.path.join(ROOT, 'data/bts/clean/otp_*.parquet').replace(chr(92), '/')}')"

con = duckdb.connect()
con.execute("PRAGMA threads=6")

print("=" * 72)
print("A) WORST CANCELLATION DAYS OVERALL")
print("=" * 72)
q = f"""
SELECT FlightDate, count(*) AS flights, sum(Cancelled) AS cancelled,
       round(100.0*avg(Cancelled), 2) AS cancel_pct,
       round(100.0*avg(ArrDel15), 1)  AS delay_pct
FROM {P} GROUP BY 1 ORDER BY cancel_pct DESC LIMIT 12
"""
print(con.execute(q).fetchdf().to_string(index=False))

print()
print("=" * 72)
print("B) JANUARY 2024 DAILY CANCELLATION PATTERN")
print("=" * 72)
q = f"""
SELECT FlightDate, sum(Cancelled) AS cancelled, round(100.0*avg(Cancelled),2) AS cancel_pct
FROM {P} WHERE Year=2024 AND Month=1 GROUP BY 1 ORDER BY 2 DESC LIMIT 8
"""
print(con.execute(q).fetchdf().to_string(index=False))

print()
print("=" * 72)
print("C) JULY 2024 DAILY CANCELLATION PATTERN (CrowdStrike was 2024-07-19)")
print("=" * 72)
q = f"""
SELECT FlightDate, sum(Cancelled) AS cancelled, round(100.0*avg(Cancelled),2) AS cancel_pct,
       round(100.0*avg(ArrDel15),1) AS delay_pct
FROM {P} WHERE Year=2024 AND Month=7 GROUP BY 1 ORDER BY 2 DESC LIMIT 10
"""
print(con.execute(q).fetchdf().to_string(index=False))

print()
print("=" * 72)
print("D) AIRPORT CAUSE PROFILE (shares, %) - check the fig8 caption claim")
print("=" * 72)
d = pd.read_csv(os.path.join(ROOT, "data/bts/analysis/airport_cause.csv"))
piv = d.pivot(index="airport", columns="cause", values="minutes").fillna(0)
share = (piv.div(piv.sum(axis=1), axis=0) * 100).round(1)
share = share[["WeatherDelay", "NASDelay", "LateAircraftDelay", "CarrierDelay", "SecurityDelay"]]
print(share.sort_values("WeatherDelay", ascending=False).to_string())
