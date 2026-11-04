# -*- coding: utf-8 -*-
"""Check the individual null rates that feed the dictionary's missingness table."""
import sys

import duckdb

sys.stdout.reconfigure(encoding="utf-8")
c = duckdb.connect()
c.execute("PRAGMA threads=6")
P = "read_parquet('data/bts/clean/otp_*.parquet')"

cols = ["ArrTime", "ArrDelay", "ArrDelayMinutes", "ArrDel15", "ArrivalDelayGroups",
        "TaxiIn", "WheelsOn", "ActualElapsedTime", "AirTime", "CRSElapsedTime",
        "FirstDepTime", "TotalAddGTime", "LongestAddGTime", "Tail_Number",
        "DepTime", "DepDelay", "DepDel15", "TaxiOut", "WheelsOff", "DepTimeBlk"]
q = ("SELECT " + ", ".join(
    f'round(100.0*count(*) FILTER (WHERE "{x}" IS NULL)/count(*),3) AS "{x}"'
    for x in cols) + f" FROM {P}")
r = c.execute(q).fetchdf().iloc[0]
for k, v in r.items():
    print(f"{k:22s} {v:8.3f}%")

print()
share = c.execute(
    f"SELECT round(100.0*count(*) FILTER (WHERE Cancelled=1 OR Diverted=1)/count(*),3),"
    f" round(100.0*avg(Cancelled),3), round(100.0*count(*) FILTER (WHERE Diverted=1)/count(*),3)"
    f" FROM {P}").fetchone()
print(f"cancelled+diverted : {share[0]}%   cancelled: {share[1]}%   diverted: {share[2]}%")
