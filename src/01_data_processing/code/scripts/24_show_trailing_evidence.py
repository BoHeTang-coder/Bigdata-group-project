# -*- coding: utf-8 -*-
"""Show the raw evidence behind change #1, and what breaks if you ignore it."""
import os
import sys

import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SAMPLE = os.path.join(
    ROOT, "data", "bts", "extracted", "2023",
    "On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_2023_6.csv")

with open(SAMPLE, "r", encoding="latin-1") as f:
    header = f.readline().rstrip("\n")
    data = f.readline().rstrip("\n")

print("=" * 76)
print("1) THE RAW BYTES  (end of the header line)")
print("=" * 76)
print(f"  ...{header[-60:]!r}")
print(f"  header ends with a comma? {header.endswith(',')}")
print(f"  commas in header line   : {header.count(',')}")
print()
print("  (end of the first data line)")
print(f"  ...{data[-60:]!r}")
print(f"  data line ends with a comma? {data.endswith(',')}")
print(f"  commas in data line     : {data.count(',')}   "
      f"(more than the header, because quoted city names contain commas)")

print()
print("=" * 76)
print("2) HOW MANY 'FIELDS' DOES A STANDARD PARSER SEE?")
print("=" * 76)
import csv
with open(SAMPLE, "r", encoding="latin-1", newline="") as f:
    r = csv.reader(f)
    h = next(r)
    d = next(r)
print(f"  csv.reader -> header has {len(h)} fields, last one = {h[-1]!r}")
print(f"  csv.reader -> data   has {len(d)} fields, last one = {d[-1]!r}")

print()
print("=" * 76)
print("3) WHAT pandas AND duckdb NAME THAT EXTRA COLUMN IF YOU DON'T DROP IT")
print("=" * 76)
pdf = pd.read_csv(SAMPLE, encoding="latin-1", nrows=5)
print(f"  pandas  : {pdf.shape[1]} columns; first = {pdf.columns[0]!r}; "
      f"last = {pdf.columns[-1]!r}")
print(f"            last column all-NaN? {pdf.iloc[:, -1].isna().all()}")

con = duckdb.connect()
desc = con.execute(
    f"DESCRIBE SELECT * FROM read_csv('{SAMPLE.replace(chr(92), '/')}', "
    f"header=true, encoding='latin-1')").fetchall()
print(f"  duckdb  : {len(desc)} columns; first = {desc[0][0]!r}; "
      f"last = {desc[-1][0]!r}  (type {desc[-1][1]})")

print()
print("=" * 76)
print("4) WHY IT MATTERS — a naive 'row count of non-null values' would differ")
print("=" * 76)
n_all, n_real = pdf.shape[1], pdf.shape[1] - 1
print(f"  columns reported by a naive reader : {n_all}")
print(f"  columns that actually carry data   : {n_real}")
print(f"  -> every downstream 'number of fields' claim would be off by one,")
print(f"     and the data dictionary would document a column that does not exist.")
