# -*- coding: utf-8 -*-
"""
Cross-check every headline number quoted in 素材包_成员1交付.md against the
actual clean data, so the writing member never inherits a transcription error.
"""
import os
import re
import sys

import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BTS = os.path.join(ROOT, "data", "bts")
GLOB = os.path.join(BTS, "clean", "otp_*.parquet").replace("\\", "/")
ANA = os.path.join(BTS, "analysis")

con = duckdb.connect()
con.execute("PRAGMA threads=6")
fails = []


def expect(label, actual, claimed, tol=0.05):
    good = abs(actual - claimed) <= tol
    if not good:
        fails.append((label, actual, claimed))
    print(f"  [{'OK ' if good else 'BAD'}] {label:46s} actual={actual:>16,.2f}  "
          f"doc={claimed:>16,.2f}")


print("=" * 78)
print("HEADLINE TOTALS")
print("=" * 78)
r = con.execute(f"""
    SELECT count(*),
           count(*) FILTER (WHERE ArrDel15 IS NOT NULL),
           count(*) FILTER (WHERE Cancelled=1),
           count(*) FILTER (WHERE Diverted=1),
           count(*) FILTER (WHERE ArrDel15=1),
           avg(ArrDel15) FILTER (WHERE ArrDel15 IS NOT NULL),
           avg(ArrDelay) FILTER (WHERE ArrDel15 IS NOT NULL),
           median(ArrDelay) FILTER (WHERE ArrDel15 IS NOT NULL),
           sum(TotalCauseDelay)
    FROM read_parquet('{GLOB}')
""").fetchone()
expect("total flights", r[0], 20928579, 0)
expect("operated flights (delay-rate denominator)", r[1], 20588134, 0)
expect("cancelled", r[2], 287134, 0)
expect("diverted", r[3], 53309, 0)
expect("delayed >=15 min", r[4], 4371303, 0)
expect("delay rate %", r[5] * 100, 21.23, 0.005)
expect("mean arrival delay (min)", r[6], 7.4, 0.05)
expect("median arrival delay (min)", r[7], -6.0, 0)
expect("total cause minutes", r[8], 311427461, 1)
expect("cancel rate %", r[2] / r[0] * 100, 1.37, 0.005)
expect("diverted rate %", r[3] / r[0] * 100, 0.25, 0.005)

print()
print("=" * 78)
print("DELAY CAUSE SHARES")
print("=" * 78)
ct = pd.read_csv(os.path.join(ANA, "causes_total.csv"))
want = {"LateAircraftDelay": (124146659, 39.9), "CarrierDelay": (107011714, 34.4),
        "NASDelay": (61415753, 19.7), "WeatherDelay": (18313928, 5.9),
        "SecurityDelay": (539407, 0.2)}
for _, row in ct.iterrows():
    m, s = want[row.cause]
    expect(f"{row.cause} minutes", row.minutes, m, 1)
    expect(f"{row.cause} share %", row.share * 100, s, 0.05)

print()
print("=" * 78)
print("AIRLINES / AIRPORTS / TIME PATTERNS")
print("=" * 78)
al = pd.read_csv(os.path.join(ANA, "airline.csv")).set_index("carrier")
for c, v in [("F9", 29.3), ("B6", 27.8), ("NK", 25.2), ("9E", 14.9),
             ("YX", 16.5), ("DL", 17.8)]:
    expect(f"airline {c} delay rate %", al.loc[c, "delay_rate"] * 100, v, 0.05)

ap = pd.read_csv(os.path.join(ANA, "airport.csv")).set_index("airport")
for a, v in [("FLL", 27.3), ("MIA", 27.0), ("SFB", 26.8), ("MCO", 25.9),
             ("PBI", 24.1), ("DFW", 26.7)]:
    expect(f"airport {a} delay rate %", ap.loc[a, "delay_rate"] * 100, v, 0.05)

mo = pd.read_csv(os.path.join(ANA, "monthly.csv"))
expect("peak month delay rate % (2024-07)",
       mo.delay_rate.max() * 100, 29.6, 0.05)
expect("lowest month delay rate %", mo.delay_rate.min() * 100, 13.2, 0.05)

ho = pd.read_csv(os.path.join(ANA, "hourly.csv"))
h = ho.groupby("CRSDepHour").apply(
    lambda g: (g.delay_rate * g.flights).sum() / g.flights.sum(),
    include_groups=False) * 100
expect("05:00 delay rate % (3-yr avg)", h.loc[5], 8.9, 0.05)
expect("19:00 delay rate % (3-yr avg)", h.loc[19], 30.5, 0.05)
expect("worst single hour-year cell % (2025 19:00)",
       ho.delay_rate.max() * 100, 32.6, 0.05)
expect("worst cell really is 2025 hour 19",
       (int(ho.loc[ho.delay_rate.idxmax(), "Year"]),
        int(ho.loc[ho.delay_rate.idxmax(), "CRSDepHour"])) == (2025, 19), 1, 0)

mw = pd.read_csv(os.path.join(ANA, "month_weekday.csv"))
dow = mw.groupby("DayOfWeek").apply(
    lambda g: (g.delay_rate * g.flights).sum() / g.flights.sum(),
    include_groups=False) * 100
expect("Tuesday delay rate % (best)", dow.loc[2], 17.9, 0.05)

print()
print("=" * 78)
print("CROWDSTRIKE DAY 2024-07-19")
print("=" * 78)
d = con.execute(f"""
    SELECT round(100.0*avg(Cancelled),2), round(100.0*avg(ArrDel15),1)
    FROM read_parquet('{GLOB}') WHERE FlightDate = DATE '2024-07-19'
""").fetchone()
expect("2024-07-19 cancel %", d[0], 16.5, 0.05)
expect("2024-07-19 delay %", d[1], 58.3, 0.05)

print()
print("=" * 78)
print("DOC/SLIDE CROSS-CHECK: every number quoted in the package")
print("=" * 78)
pkg = open(os.path.join(ROOT, "素材包_成员1交付.md"), encoding="utf-8").read()
for token in ["20,928,579", "20,588,134", "21.23", "287,134", "53,309",
              "4,371,303", "311,427,461", "124,146,659", "107,011,714",
              "61,415,753", "18,313,928", "539,407", "15.9", "0.98 GB",
              "8.82 GB", "0.56 GB", "109", "114", "300 dpi"]:
    present = token in pkg
    if not present:
        fails.append((f"token {token} missing from package", 0, 1))
    print(f"  [{'OK ' if present else 'BAD'}] quoted in package: {token}")

print()
print("=" * 78)
print(f"RESULT: {'ALL NUMBERS MATCH THE DATA' if not fails else f'{len(fails)} MISMATCHES'}")
for f in fails:
    print("   MISMATCH:", f)
print("=" * 78)
sys.exit(0 if not fails else 1)
