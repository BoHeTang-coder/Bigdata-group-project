# -*- coding: utf-8 -*-
"""
Extract the downloaded BTS prezip archives to CSV and verify them.

BTS quirks handled here
  * file encoding is latin-1 / CP1252 (accented city names)
  * every line ends with a stray comma -> csv.reader yields 110 fields,
    the last one empty; valid rows therefore have exactly COLS+1 fields
  * the archive also contains readme.html

Output : data/bts/extracted/<year>/<name>.csv
Updates: data/bts/manifest.json with row_count / malformed_rows

Usage:
    python scripts/02_extract.py             # extract + verify everything
    python scripts/02_extract.py --verify    # verify only (CSV must exist)
    python scripts/02_extract.py --force     # re-extract from zip
"""
import argparse
import csv
import json
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BTS = os.path.join(ROOT, "data", "bts")
RAW = os.path.join(BTS, "raw")
OUT = os.path.join(BTS, "extracted")
MANIFEST = os.path.join(BTS, "manifest.json")

ENCODING = "latin-1"
COLS = 109


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def verify_csv(path, expected_cols=COLS):
    """Return (data_rows, header_cols, malformed_rows)."""
    n = bad = 0
    with open(path, "r", encoding=ENCODING, newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        hcols = len(header)
        want = expected_cols + 1          # + trailing empty field
        for row in rdr:
            n += 1
            if len(row) != want:
                bad += 1
    return n, hcols, bad


def work(item):
    """Runs in a worker process: extract one zip, then verify its CSV."""
    key, rec, do_extract, force = item
    if not rec.get("ok"):
        return key, rec
    zpath = os.path.join(ROOT, rec["file"].replace("/", os.sep))
    if not os.path.exists(zpath):
        return key, {**rec, "extract_ok": False, "error": "zip missing"}

    year = rec["year"]
    out_dir = os.path.join(OUT, str(year))
    os.makedirs(out_dir, exist_ok=True)

    with zipfile.ZipFile(zpath) as zf:
        member = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
        csv_path = os.path.join(out_dir, os.path.basename(member))
        if do_extract and (force or not os.path.exists(csv_path)):
            zf.extract(member, out_dir)

    rows, hcols, bad = verify_csv(csv_path, rec.get("csv_columns", COLS))
    return key, {
        **rec,
        "extract_ok": True,
        "csv_file": os.path.relpath(csv_path, ROOT).replace("\\", "/"),
        "csv_bytes": os.path.getsize(csv_path),
        "row_count": rows,
        "parsed_columns": hcols,
        "malformed_rows": bad,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="do not extract, only verify")
    ap.add_argument("--force", action="store_true", help="re-extract even if csv exists")
    ap.add_argument("--jobs", type=int, default=min(6, (os.cpu_count() or 4)))
    a = ap.parse_args()

    mf = json.load(open(MANIFEST, encoding="utf-8"))
    items = sorted((k, v) for k, v in mf["files"].items() if v.get("ok"))
    log(f"{len(items)} archives -> {OUT}  (jobs={a.jobs})")

    t0 = time.time()
    payload = [(k, v, not a.verify, a.force) for k, v in items]
    # Threads (not processes): zip extraction is zlib and releases the GIL.
    with ThreadPoolExecutor(a.jobs) as ex:
        futs = [ex.submit(work, p) for p in payload]
        for fu in as_completed(futs):
            k, rec = fu.result()
            mf["files"][k] = rec
            if rec.get("extract_ok"):
                log(f"{k}  rows={rec['row_count']:>9,}  cols={rec['parsed_columns']}  "
                    f"bad={rec['malformed_rows']}  ({rec['csv_bytes']/2**20:.0f} MB)")
            else:
                log(f"{k}  EXTRACT FAILED  {rec.get('error')}")

    ok = [v for v in mf["files"].values() if v.get("extract_ok")]
    total_rows = sum(v.get("row_count", 0) for v in ok)
    total_bytes = sum(v.get("csv_bytes", 0) for v in ok)
    total_bad = sum(v.get("malformed_rows", 0) for v in ok)
    mf["extract_summary"] = {
        "months_ok": len(ok), "total_rows": total_rows,
        "total_csv_bytes": total_bytes,
        "total_csv_gb": round(total_bytes / 2**30, 2),
        "malformed_rows": total_bad,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(mf, f, indent=2, ensure_ascii=False)

    log("-" * 64)
    log(f"done in {(time.time()-t0)/60:.1f} min | rows={total_rows:,} | "
        f"csv={total_bytes/2**30:.2f} GB | malformed={total_bad}")


if __name__ == "__main__":
    sys.exit(main())
