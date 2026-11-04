# -*- coding: utf-8 -*-
"""
Data-quality audit on one sample month (stdlib only).
Validates the caveats documented in data/bts/README.md against the real data.
"""
import csv
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MANIFEST = os.path.join(ROOT, "data", "bts", "manifest.json")
KEY = "2023-06"
CAUSE = ["CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay"]


def f(x):
    return float(x) if x not in ("", "NULL") else None


def main():
    mf = json.load(open(MANIFEST, encoding="utf-8"))
    path = os.path.join(ROOT, mf["files"][KEY]["csv_file"].replace("/", os.sep))
    print(f"sample month: {KEY}")
    print(f"file: {os.path.relpath(path, ROOT)}\n")

    with open(path, "r", encoding="latin-1", newline="") as fh:
        rdr = csv.reader(fh)
        header = next(rdr)[:-1]
        I = {c: i for i, c in enumerate(header)}

        n = 0
        cause_when_del15 = cause_when_not_del15 = 0
        del15_no_cause = cause_without_del15 = 0
        sum_eq = sum_ne = sum_na = 0
        maxdiff = 0.0
        cancelled = diverted = 0
        arrdelay_null_cancelled = arrdelay_null_operated = 0
        keys = Counter()
        carriers = Counter()
        origins = set()
        dests = set()
        cause_totals = Counter()

        for r in rdr:
            r = r[:-1]
            n += 1
            g = r.__getitem__
            isdel = g(I["ArrDel15"]) in ("1.00", "1")
            causes = [f(g(I[c])) for c in CAUSE]
            filled = [c for c in causes if c is not None]
            if isdel:
                cause_when_del15 += 1
                if not filled:
                    del15_no_cause += 1
            else:
                cause_when_not_del15 += 1
                if filled:
                    cause_without_del15 += 1

            adm = f(g(I["ArrDelayMinutes"]))
            if isdel and len(filled) == 5:
                s = sum(filled)
                if adm is None:
                    sum_na += 1
                elif abs(s - adm) < 0.005:
                    sum_eq += 1
                else:
                    sum_ne += 1
                    maxdiff = max(maxdiff, abs(s - adm))
                for c, v in zip(CAUSE, causes):
                    cause_totals[c] += v

            cancelled += g(I["Cancelled"]) in ("1.00", "1")
            diverted += g(I["Diverted"]) in ("1.00", "1")
            ad = f(g(I["ArrDelay"]))
            if g(I["Cancelled"]) in ("1.00", "1"):
                arrdelay_null_cancelled += ad is None
            else:
                arrdelay_null_operated += ad is None

            keys[(g(I["FlightDate"]), g(I["Reporting_Airline"]),
                  g(I["Flight_Number_Reporting_Airline"]), g(I["Origin"]),
                  g(I["Dest"]), g(I["CRSDepTime"]))] += 1
            carriers[g(I["Reporting_Airline"])] += 1
            origins.add(g(I["Origin"]))
            dests.add(g(I["Dest"]))

    print(f"rows                                   : {n:,}")
    print(f"Cancelled=1                            : {cancelled:,} ({cancelled/n*100:.2f}%)")
    print(f"Diverted=1                             : {diverted:,} ({diverted/n*100:.2f}%)")
    print(f"distinct reporting carriers            : {len(carriers)}")
    print(f"distinct origin airports               : {len(origins)}")
    print(f"distinct destination airports          : {len(dests)}")
    print()
    print("--- CAVEAT 2: cause fields only for ArrDel15=1 ---")
    print(f"ArrDel15=1 total                       : {cause_when_del15:,}")
    print(f"  ...of which ALL 5 causes non-null    : {cause_when_del15 - del15_no_cause:,}")
    print(f"  ...of which causes are null          : {del15_no_cause:,}")
    print(f"ArrDel15=0 total                       : {cause_when_not_del15:,}")
    print(f"  ...but causes populated (violations) : {cause_without_del15:,}")
    print()
    print("--- CAVEAT 2b: sum(5 causes) vs ArrDelayMinutes ---")
    print(f"exact match (within 0.005)             : {sum_eq:,}")
    print(f"mismatch                               : {sum_ne:,}  (max abs diff {maxdiff:.2f})")
    print(f"ArrDelayMinutes missing                : {sum_na:,}")
    if sum_eq + sum_ne:
        print(f"-> match rate {sum_eq/(sum_eq+sum_ne)*100:.3f}%")
    print()
    print("--- CAVEAT 4: ArrDelay null for cancelled ---")
    print(f"ArrDelay null when Cancelled=1         : {arrdelay_null_cancelled:,} / {cancelled:,}")
    print(f"ArrDelay null when NOT cancelled       : {arrdelay_null_operated:,} / {n-cancelled:,}")
    print()
    print("--- CAVEAT 6: duplicate key check ---")
    dup = {k: v for k, v in keys.items() if v > 1}
    print(f"duplicate (date,carrier,fltnum,orig,dest,CRSDepTime) keys: {len(dup):,}")
    if dup:
        for k, v in list(dup.items())[:3]:
            print("   ", k, "x", v)
    print()
    print("--- cause share among delayed flights ---")
    tot = sum(cause_totals.values())
    for c, v in cause_totals.most_common():
        print(f"  {c:20s} {v:>14,.0f} min  {v/tot*100:5.1f}%")


if __name__ == "__main__":
    main()
