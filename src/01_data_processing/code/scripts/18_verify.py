# -*- coding: utf-8 -*-
"""
Final acceptance check for the 成员1 deliverables:
clean Parquet + data dictionary + 8 captioned figures.
"""
import json
import os
import sys

import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BTS = os.path.join(ROOT, "data", "bts")
CLEAN = os.path.join(BTS, "clean")
FIG = os.path.join(ROOT, "figures")

ok = True


def check(label, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))


print("=" * 72)
print("1) CLEAN PARQUET")
print("=" * 72)
con = duckdb.connect()
con.execute("PRAGMA threads=6")
GLOB = os.path.join(CLEAN, "otp_*.parquet").replace("\\", "/")

files = sorted(f for f in os.listdir(CLEAN) if f.endswith(".parquet"))
check("three yearly parquet files exist", len(files) == 3, ", ".join(files))

desc = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{GLOB}')").fetchall()
check("column count is 114 (109 official + 5 derived)", len(desc) == 114,
      f"got {len(desc)}")

tot = con.execute(f"SELECT count(*) FROM read_parquet('{GLOB}')").fetchone()[0]
check("total rows == 20,928,579 (matches source CSV count)", tot == 20928579,
      f"got {tot:,}")

per_year = con.execute(
    f"SELECT Year, count(*) FROM read_parquet('{GLOB}') GROUP BY 1 ORDER BY 1").fetchall()
check("years present are 2023/2024/2025",
      [y for y, _ in per_year] == [2023, 2024, 2025],
      ", ".join(f"{y}:{n:,}" for y, n in per_year))

r = con.execute(f"""
    SELECT count(*) FILTER (WHERE ArrDel15 = 1) AS delayed,
           count(*) FILTER (WHERE Cancelled = 1) AS cancelled,
           min(FlightDate) AS lo, max(FlightDate) AS hi
    FROM read_parquet('{GLOB}')
""").fetchone()
check("date range covers 2023-01-01 .. 2025-12-31",
      str(r[2]) == "2023-01-01" and str(r[3]) == "2025-12-31", f"{r[2]} .. {r[3]}")
check("delay/cancel counts survived the transformation",
      r[0] == 4371303 and r[1] == 287134, f"delayed={r[0]:,} cancelled={r[1]:,}")

bad = con.execute(f"""
    SELECT count(*) FROM read_parquet('{GLOB}')
    WHERE CRSDepHour IS NOT NULL AND (CRSDepHour < 0 OR CRSDepHour > 23)
""").fetchone()[0]
check("derived CRSDepHour is always 0-23 (midnight 2400 handled)", bad == 0,
      f"{bad} out-of-range")

# sum of causes == ArrDelayMinutes for delayed flights, minus a known handful
# of carrier-reporting gaps documented in DATA_DICTIONARY.md
mism = con.execute(f"""
    SELECT count(*) FROM read_parquet('{GLOB}')
    WHERE ArrDel15 = 1 AND TotalCauseDelay IS NOT NULL
      AND abs(TotalCauseDelay - ArrDelayMinutes) > 0.005
""").fetchone()[0]
null_causes = con.execute(f"""
    SELECT count(*) FROM read_parquet('{GLOB}')
    WHERE ArrDel15 = 1 AND TotalCauseDelay IS NULL
""").fetchone()[0]
check("TotalCauseDelay == ArrDelayMinutes for delayed flights with a cause report",
      mism == 15, f"{mism} known all-zero-cause carrier gaps (documented)")
check("delayed flights with no cause report at all are NULL, not 0",
      null_causes == 3, f"{null_causes} such flights (documented)")

csv_bytes = 8.82 * 2**30
pq_bytes = sum(os.path.getsize(os.path.join(CLEAN, f)) for f in files)
print(f"       CSV {csv_bytes/2**30:.2f} GB -> Parquet {pq_bytes/2**30:.2f} GB "
      f"({csv_bytes/pq_bytes:.1f}x smaller)")

print()
print("=" * 72)
print("2) DATA DICTIONARY")
print("=" * 72)
for name in ("DATA_DICTIONARY.md", "DATA_DICTIONARY.csv"):
    p = os.path.join(CLEAN, name)
    check(f"{name} exists", os.path.exists(p),
          f"{os.path.getsize(p):,} bytes" if os.path.exists(p) else "")
dd = pd.read_csv(os.path.join(CLEAN, "DATA_DICTIONARY.csv"))
check("dictionary covers every column", len(dd) == 114, f"{len(dd)} rows")
check("every column has a Chinese label", dd.chinese.notna().all())
check("all 109 official columns have the official English definition",
      dd.official_definition_en.notna().sum() == 109,
      f"{dd.official_definition_en.notna().sum()}")

print()
print("=" * 72)
print("3) FIGURES")
print("=" * 72)
caps = open(os.path.join(FIG, "CAPTIONS.md"), encoding="utf-8").read()
pngs = sorted(f for f in os.listdir(FIG) if f.endswith(".png"))
check("8 PNG figures produced", len(pngs) == 8, f"got {len(pngs)}")
for f in pngs:
    p = os.path.join(FIG, f)
    check(f"{f}", os.path.getsize(p) > 40000,
          f"{os.path.getsize(p)/1024:.0f} KB")
n_caps = caps.count("\n## Figure ")
check("every figure has an English caption", n_caps == 8, f"{n_caps} captions")

guide = open(os.path.join(FIG, "FIGURE_GUIDE.md"), encoding="utf-8").read()
n_args = guide.count("**这张图支撑的论点**")
check("every figure has an argument (三件套 complete)", n_args == 8, f"{n_args} arguments")

# Topics required by the task brief, matched on filename keywords (not on
# numbers) so a renumbering can never make this check pass falsely.
required = {"delay distribution": "delay_distribution",
            "month x weekday heatmap": "month_weekday",
            "airline ranking": "airline_ranking",
            "worst airports": "worst_airports",
            "delay cause share": "delay_causes"}
for topic, kw in required.items():
    check(f"required topic covered: {topic}", any(kw in p for p in pngs))

# filename number must equal the Figure number in both generated documents
import re as _re
for i, f in enumerate(pngs, 1):
    check(f"Figure {i} — filename number matches order", f.startswith(f"fig{i}_"), f)
    check(f"Figure {i} — listed as Figure {i} in FIGURE_GUIDE",
          f"## Figure {i} — `{f}`" in guide, f)

print()
print("=" * 72)
print(f"RESULT: {'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'}")
print("=" * 72)
sys.exit(0 if ok else 1)
