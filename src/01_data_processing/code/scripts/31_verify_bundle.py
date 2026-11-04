# -*- coding: utf-8 -*-
"""
Final acceptance check for the consolidated hand-off bundle.

1. every expected file is in 交付包_成员1/ and inside 交付包_成员1.zip
2. every headline number quoted in the plain-language guide matches the data
3. the guide really is usable without code (no missing cross-references)
"""
import os
import re
import sys
import zipfile

import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BUNDLE = os.path.join(ROOT, "交付包_成员1")
ZIP_PATH = os.path.join(ROOT, "交付包_成员1.zip")
ANA = os.path.join(ROOT, "data", "bts", "analysis")
GLOB = os.path.join(ROOT, "data", "bts", "clean", "otp_*.parquet").replace("\\", "/")

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label)
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))


EXPECTED = [
    "00_先读我_讲解文档.md", "01_素材包_六要素.md",
    "02_数据字典.md", "02_数据字典.csv",
    "03_图表三件套.md", "04_英文图注.md", "07_文件总清单.md",
    "08_附_数据下载与口径说明.md",
] + [f"05_图片/fig{i}_{n}.png" for i, n in enumerate(
    ["delay_distribution", "month_weekday_heatmap", "hourly_pattern",
     "monthly_trend", "airline_ranking", "worst_airports", "delay_causes",
     "airport_cause_profile"], 1)] + [
    "06_数据/otp_2023.parquet", "06_数据/otp_2024.parquet",
    "06_数据/otp_2025.parquet", "06_数据/clean_summary.json"]

print("=" * 76)
print("1) BUNDLE FOLDER")
print("=" * 76)
check("bundle folder exists", os.path.isdir(BUNDLE))
found = set()
for dp, _d, fs in os.walk(BUNDLE):
    for f in fs:
        found.add(os.path.relpath(os.path.join(dp, f), BUNDLE).replace("\\", "/"))
for rel in EXPECTED:
    check(f"present: {rel}", rel in found)
check("no unexpected extra files", found == set(EXPECTED),
      f"extra={sorted(found - set(EXPECTED))}")

print()
print("=" * 76)
print("2) ZIP CONTENTS")
print("=" * 76)
check("zip exists", os.path.exists(ZIP_PATH),
      f"{os.path.getsize(ZIP_PATH)/2**20:.0f} MB" if os.path.exists(ZIP_PATH) else "")
with zipfile.ZipFile(ZIP_PATH) as z:
    bad = z.testzip()
    check("zip passes integrity test", bad is None, str(bad))
    names = {n.split("交付包_成员1/", 1)[-1] for n in z.namelist()
             if not n.endswith("/")}
    for rel in EXPECTED:
        check(f"in zip: {rel}", rel in names)

print()
print("=" * 76)
print("3) PLAIN-LANGUAGE GUIDE — numbers must match the data")
print("=" * 76)
guide_path = os.path.join(BUNDLE, "00_先读我_讲解文档.md")
g = open(guide_path, encoding="utf-8").read()
print(f"  guide size: {len(g):,} chars, {g.count(chr(10))+1:,} lines")

con = duckdb.connect()
con.execute("PRAGMA threads=6")
r = con.execute(f"""
    SELECT count(*), count(*) FILTER (WHERE ArrDel15 IS NOT NULL),
           count(*) FILTER (WHERE Cancelled=1), count(*) FILTER (WHERE Diverted=1),
           count(*) FILTER (WHERE ArrDel15=1),
           avg(ArrDel15) FILTER (WHERE ArrDel15 IS NOT NULL),
           avg(ArrDelay) FILTER (WHERE ArrDel15 IS NOT NULL),
           median(ArrDelay) FILTER (WHERE ArrDel15 IS NOT NULL),
           count(*) FILTER (WHERE ArrDelay > 180)
    FROM read_parquet('{GLOB}')
""").fetchone()

quote = {
    "total flights 20,928,579": ("20,928,579", r[0] == 20928579),
    "operated 20,588,134": ("20,588,134", r[1] == 20588134),
    "cancelled 287,134": ("287,134", r[2] == 287134),
    "diverted 53,309": ("53,309", r[3] == 53309),
    "delayed 4,371,303": ("4,371,303", r[4] == 4371303),
    "delay rate 21.23 / 21.2": ("21.23", abs(r[5] * 100 - 21.23) < 0.01),
    "mean +7.4": ("+7.4", abs(r[6] - 7.4) < 0.05),
    "median -6": ("−6 分钟", r[7] == -6.0),
    "long tail 296,358": ("296,358", r[8] == 296358),
}
for label, (token, data_ok) in quote.items():
    check(f"guide quotes {label} and data agrees", token in g and data_ok,
          f"in_doc={token in g} data_ok={data_ok}")

# cause shares
ct = pd.read_csv(os.path.join(ANA, "causes_total.csv")).set_index("cause")
for cause, pct in [("LateAircraftDelay", 39.9), ("CarrierDelay", 34.4),
                   ("NASDelay", 19.7), ("WeatherDelay", 5.9),
                   ("SecurityDelay", 0.2)]:
    actual = ct.loc[cause, "share"] * 100
    tok = f"{pct}"
    check(f"guide quotes {cause} {pct}% and data agrees ({actual:.1f}%)",
          tok in g and abs(actual - pct) < 0.06)

# monthly / weekday / hourly
mo = pd.read_csv(os.path.join(ANA, "monthly.csv"))
check("guide quotes Jul-2024 peak 29.6%",
      "29.6" in g and abs(mo.delay_rate.max() * 100 - 29.6) < 0.05)
check("guide quotes Oct-2024 trough 13.2%",
      "13.2" in g and abs(mo.delay_rate.min() * 100 - 13.2) < 0.05)

mw = pd.read_csv(os.path.join(ANA, "month_weekday.csv"))
mw["r"] = mw.delay_rate * 100
check("guide quotes worst cell 32.5% (Jul Sun)",
      "32.5" in g and abs(mw.r.max() - 32.5) < 0.05
      and int(mw.loc[mw.r.idxmax(), "Month"]) == 7
      and int(mw.loc[mw.r.idxmax(), "DayOfWeek"]) == 7)
check("guide quotes best cell 12.1% (Oct Tue)",
      "12.1" in g and abs(mw.r.min() - 12.1) < 0.05
      and int(mw.loc[mw.r.idxmin(), "Month"]) == 10
      and int(mw.loc[mw.r.idxmin(), "DayOfWeek"]) == 2)

hov = pd.read_csv(os.path.join(ANA, "hourly.csv"))
h = hov.groupby("CRSDepHour").apply(
    lambda x: (x.delay_rate * x.flights).sum() / x.flights.sum(),
    include_groups=False) * 100
check("guide quotes 05:00 = 8.9%", "8.9%" in g and abs(h.loc[5] - 8.9) < 0.05)
check("guide quotes 19:00 = 30.5% (3yr avg)",
      "30.5%" in g and abs(h.loc[19] - 30.5) < 0.05)

# December holiday window
dec = con.execute(f"""
    SELECT round(100.0*avg(ArrDel15) FILTER (WHERE DayofMonth BETWEEN 1 AND 17),1),
           round(100.0*avg(ArrDel15) FILTER (WHERE DayofMonth BETWEEN 18 AND 31),1),
           round(100.0*avg(ArrDel15) FILTER (WHERE DayofMonth = 25),1),
           round(100.0*avg(ArrDel15) FILTER (WHERE DayofMonth = 28),1)
    FROM read_parquet('{GLOB}') WHERE Month = 12
""").fetchone()
check(f"guide Dec 1-17 = 18.7%", "18.7%" in g and abs(dec[0] - 18.7) < 0.05)
check(f"guide Dec 18-31 = 24.3%", "24.3%" in g and abs(dec[1] - 24.3) < 0.05)
check(f"guide Dec 25 = 11.4%", "11.4%" in g and abs(dec[2] - 11.4) < 0.05)
check(f"guide Dec 28 = 33.3%", "33.3%" in g and abs(dec[3] - 33.3) < 0.05)

# figure references in the guide must exist in the bundle
# (findall returns the capture group only, so re-attach the folder prefix)
refs = {"05_图片/" + m for m in
        re.findall(r"`05_图片/(fig\d_[a-z_]+\.png)`", g)}
check("every figure the guide references exists in the bundle",
      refs.issubset(found), f"missing={sorted(refs - found)}")
check("guide references all 8 figures", len(refs) == 8, f"{len(refs)} referenced")

# no leftover stale figure names anywhere in the bundle docs
STALE = ["fig3_airline_ranking", "fig4_worst_airports", "fig5_delay_causes",
         "fig6_hourly_pattern", "fig7_monthly_trend"]
for rel in EXPECTED:
    if not rel.endswith(".md"):
        continue
    txt = open(os.path.join(BUNDLE, rel), encoding="utf-8").read()
    hits = [s for s in STALE if s in txt]
    check(f"no stale figure names in {rel}", not hits, str(hits))

print()
print("=" * 76)
print(f"RESULT: {'BUNDLE OK — ALL CHECKS PASSED' if not fails else f'{len(fails)} FAILURES'}")
for f in fails:
    print("   FAIL:", f)
print("=" * 76)
sys.exit(0 if not fails else 1)
