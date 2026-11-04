# -*- coding: utf-8 -*-
"""
End-to-end smoke test on the downloaded data, stdlib only (no pandas needed).

Checks one month per year:
  * header parses to 109 named columns after dropping the stray trailing comma
  * row count / delay-field population
  * availability of the 5 delay-cause fields (needed for research question 3)
  * a mini aggregation: on-time rate by carrier and by departure hour block
"""
import csv
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MANIFEST = os.path.join(ROOT, "data", "bts", "manifest.json")

CAUSE = ["CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay"]
NUM = ["DepDelay", "ArrDelay", "TaxiOut", "TaxiIn", "Distance"]


def load_month(key, limit=None):
    mf = json.load(open(MANIFEST, encoding="utf-8"))
    rec = mf["files"][key]
    path = os.path.join(ROOT, rec["csv_file"].replace("/", os.sep))
    with open(path, "r", encoding="latin-1", newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        cols = header[:-1] if header[-1] == "" else header      # drop stray trailing field
        idx = {c: i for i, c in enumerate(cols)}
        rows = []
        for r in rdr:
            rows.append(r[:-1])
            if limit and len(rows) >= limit:
                break
    return cols, idx, rows


def main():
    report = {}
    for key in ("2023-06", "2024-06", "2025-06"):
        cols, idx, rows = load_month(key)
        print("=" * 72)
        print(f"{key}   rows_loaded={len(rows):,}   columns={len(cols)}")

        # ---- delay-cause population
        pop = {}
        for c in CAUSE:
            i = idx[c]
            filled = sum(1 for r in rows if r[i] not in ("", "NULL"))
            pop[c] = filled
        print("  delay-cause fields present in", len(CAUSE), "cols ->",
              "ALL FILLED" if all(v > 0 for v in pop.values()) else "MISSING SOME")
        for c, v in pop.items():
            print(f"    {c:20s} {v:>8,}  ({v/len(rows)*100:5.1f}% of flights)")

        # ---- cancellation code coverage
        cc = Counter(r[idx["CancellationCode"]] for r in rows)
        print("  CancellationCode:", dict(cc.most_common(6)))

        # ---- on-time rate overall + by carrier
        arr15 = Counter(r[idx["ArrDel15"]] for r in rows)
        print("  ArrDel15:", dict(arr15))
        by_carrier = defaultdict(lambda: [0, 0])
        for r in rows:
            v = r[idx["ArrDel15"]]
            if v in ("0.00", "0", "1.00", "1"):
                d = by_carrier[r[idx["Reporting_Airline"]]]
                d[0] += 1
                d[1] += 1 if v in ("1.00", "1") else 0
        rank = sorted(((n, t, dl / t) for n, (t, dl) in by_carrier.items() if t > 2000),
                      key=lambda x: -x[2])[:5]
        print("  worst 5 carriers by ArrDel15 rate (>=2000 flts):")
        for n, t, rate in rank:
            print(f"    {n:>4}  n={t:>7,}  late={rate*100:5.1f}%")

        # ---- on-time rate by departure hour block
        blk = defaultdict(lambda: [0, 0])
        for r in rows:
            v = r[idx["ArrDel15"]]
            if v in ("0.00", "0", "1.00", "1"):
                b = blk[r[idx["DepTimeBlk"]]]
                b[0] += 1
                b[1] += 1 if v in ("1.00", "1") else 0
        print("  by departure block (first 6):")
        for k2 in sorted(blk)[:6]:
            t, d = blk[k2]
            print(f"    {k2:10s} n={t:>7,}  late={d/t*100:5.1f}%")

        report[key] = {"columns": len(cols), "rows": len(rows),
                       "cause_populated": all(v > 0 for v in pop.values())}

    print("=" * 72)
    print("SMOKE TEST", "PASSED" if all(v["cause_populated"] for v in report.values()) else "FAILED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
