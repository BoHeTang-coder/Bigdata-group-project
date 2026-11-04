# -*- coding: utf-8 -*-
"""
Verify the claim behind change #1: the trailing-comma column (column109) is
ALWAYS empty, in every one of the 20,928,579 rows.

Earlier verification only proved that every row parses to exactly 110 fields
(len(row) == 109+1). That is a statement about the NUMBER of fields, not about
their CONTENT. This script checks the content.
"""
import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
EXTRACTED = os.path.join(ROOT, "data", "bts", "extracted")
ENCODING = "latin-1"


def scan(path, name):
    rows = nonempty_last = wrong_len = 0
    samples = []
    with open(path, "r", encoding=ENCODING, newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        for row in rdr:
            rows += 1
            if len(row) != 110:
                wrong_len += 1
                continue
            if row[-1] != "":
                nonempty_last += 1
                if len(samples) < 3:
                    samples.append(row[-1])
    return name, rows, nonempty_last, wrong_len, len(header), header[-1], samples


files = []
for y in ("2023", "2024", "2025"):
    d = os.path.join(EXTRACTED, y)
    for f in sorted(os.listdir(d)):
        if f.endswith(".csv"):
            files.append((os.path.join(d, f), f"{y}/{f[:70]}..."))

print(f"scanning {len(files)} CSV files, every row ...\n")
tot_rows = tot_nonempty = tot_wrong = 0
with ThreadPoolExecutor(6) as ex:
    futs = [ex.submit(scan, p, n) for p, n in files]
    for fu in as_completed(futs):
        name, rows, nonempty, wrong, hlen, hlast, samples = fu.result()
        tot_rows += rows
        tot_nonempty += nonempty
        tot_wrong += wrong
        flag = "OK " if (nonempty == 0 and wrong == 0) else "BAD"
        print(f"  [{flag}] {name:74s} rows={rows:>8,} "
              f"nonempty_last={nonempty} wrong_len={wrong} hdr_fields={hlen} "
              f"hdr_last={hlast!r}")
        if samples:
            print(f"          sample non-empty values: {samples}")

print()
print("=" * 74)
print(f"TOTAL rows scanned      : {tot_rows:,}")
print(f"rows with non-empty 110th field : {tot_nonempty:,}")
print(f"rows not parsing to 110 fields  : {tot_wrong:,}")
print()
if tot_nonempty == 0 and tot_wrong == 0:
    print("CLAIM VERIFIED: the trailing-comma column is empty in every row,")
    print("and every row has exactly 109 real fields + 1 empty field.")
else:
    print("CLAIM REFUTED — investigate before trusting the cleaning step.")
    sys.exit(1)
