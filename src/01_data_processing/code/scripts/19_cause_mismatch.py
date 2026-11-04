# -*- coding: utf-8 -*-
"""Inspect the handful of flights where sum(causes) != ArrDelayMinutes."""
import os
import sys

import duckdb

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
GLOB = os.path.join(ROOT, "data", "bts", "clean", "otp_*.parquet").replace("\\", "/")

con = duckdb.connect()
con.execute("PRAGMA threads=6")

df = con.execute(f"""
    SELECT FlightDate, Reporting_Airline, Flight_Number_Reporting_Airline,
           Origin, Dest, ArrDelay, ArrDelayMinutes, TotalCauseDelay,
           CarrierDelay, WeatherDelay, NASDelay, SecurityDelay, LateAircraftDelay,
           Cancelled, Diverted,
           round(TotalCauseDelay - ArrDelayMinutes, 2) AS diff
    FROM read_parquet('{GLOB}')
    WHERE ArrDel15 = 1 AND abs(TotalCauseDelay - ArrDelayMinutes) > 0.005
    ORDER BY abs(TotalCauseDelay - ArrDelayMinutes) DESC
""").fetchdf()

print(f"mismatching flights: {len(df)}")
print()
print(df.to_string(index=False))

n_all = con.execute(
    f"SELECT count(*) FROM read_parquet('{GLOB}') WHERE ArrDel15 = 1").fetchone()[0]
print()
print(f"share of delayed flights: {len(df):,} / {n_all:,} = {len(df)/n_all*100:.6f}%")
