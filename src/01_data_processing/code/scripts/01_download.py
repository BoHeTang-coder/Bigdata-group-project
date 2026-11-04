# -*- coding: utf-8 -*-
"""
BTS TranStats - On-Time Performance (Reporting Carrier, 1987-present)
Robust parallel downloader for the official PREZIP monthly archives.

Source UI : https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ
Backend   : https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{Y}_{M}.zip

Features: resume via HTTP Range, exponential-backoff retry, zip integrity check,
SHA-256 + row count, resumable manifest (safe to re-run).
"""
import hashlib
import json
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----------------------------------------------------------------------------
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
BASE = ("https://transtats.bts.gov/PREZIP/"
        "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{y}_{m}.zip")
YEARS = (2023, 2024, 2025)
MONTHS = range(1, 13)

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RAW = os.path.join(ROOT, "data", "bts", "raw")
MANIFEST = os.path.join(ROOT, "data", "bts", "manifest.json")

WORKERS = 8          # tuned: per-connection throughput saturates ~0.4 MiB/s aggregate
MAX_RETRY = 6
CHUNK = 1 << 20      # 1 MiB
TIMEOUT = 180

_ssl = ssl.create_default_context()
_lock = threading.Lock()
_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ----------------------------------------------------------------------------
def load_manifest():
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"source": BASE, "years": list(YEARS), "files": {}}


def save_manifest(mf):
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    tmp = MANIFEST + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(mf, f, indent=2, ensure_ascii=False)
    os.replace(tmp, MANIFEST)


def build_jobs():
    out = []
    for y in YEARS:
        for m in MONTHS:
            key = f"{y}-{m:02d}"
            out.append({
                "key": key, "year": y, "month": m,
                "url": BASE.format(y=y, m=m),
                "dir": os.path.join(RAW, str(y)),
                "name": os.path.basename(BASE.format(y=y, m=m)),
            })
    return out


# ----------------------------------------------------------------------------
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def remote_size(url):
    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl) as r:
        return int(r.headers.get("Content-Length") or 0), r.headers.get("Accept-Ranges")


def download_once(url, dest, expect=None):
    """Stream url -> dest (.part then rename). Supports resume via Range."""
    part = dest + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    headers = {"User-Agent": UA, "Accept-Encoding": "identity"}
    mode = "wb"
    if have:
        headers["Range"] = f"bytes={have}-"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl) as r:
        if have and r.status == 200:      # server ignored Range -> restart
            log(f"    resume not supported, restarting {os.path.basename(dest)}")
            have, mode = 0, "wb"
        elif have and r.status == 206:
            mode = "ab"
        total = None
        cr = r.headers.get("Content-Length")
        if cr:
            total = have + int(cr)
        with open(part, mode) as f:
            done = have
            while True:
                chunk = r.read(CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
    os.replace(part, dest)
    return total


def fetch(job, mf):
    key, dest = job["key"], os.path.join(job["dir"], job["name"])
    os.makedirs(job["dir"], exist_ok=True)

    rec = mf["files"].get(key, {})
    if rec.get("ok") and os.path.exists(dest) and os.path.getsize(dest) == rec.get("bytes"):
        log(f"{key}  cached  ({rec['bytes']/2**20:.1f} MB)")
        return key, rec

    last = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            size = download_once(job["url"], dest)
            with zipfile.ZipFile(dest) as zf:
                bad = zf.testzip()
                if bad:
                    raise zipfile.BadZipFile(f"corrupt member {bad}")
                members = zf.namelist()
                with zf.open(members[0]) as fh:
                    header = fh.readline().decode("utf-8", "replace").strip()
            ncol = len([c for c in header.split(",") if c != ""])
            rec = {
                "ok": True, "year": job["year"], "month": job["month"],
                "url": job["url"], "file": os.path.relpath(dest, ROOT).replace("\\", "/"),
                "bytes": os.path.getsize(dest),
                "sha256": sha256_file(dest),
                "zip_members": members,
                "csv_columns": ncol,
                "csv_header": header,
                "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            with _lock:
                mf["files"][key] = rec
                save_manifest(mf)
            log(f"{key}  OK      {rec['bytes']/2**20:6.1f} MB  cols={ncol}")
            return key, rec
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            wait = min(60, 3 * 2 ** (attempt - 1))
            log(f"{key}  retry {attempt}/{MAX_RETRY} in {wait}s  <- {last}")
            time.sleep(wait)
    with _lock:
        mf["files"][key] = {"ok": False, "year": job["year"], "month": job["month"],
                            "url": job["url"], "error": last}
        save_manifest(mf)
    log(f"{key}  FAILED  {last}")
    return key, {"ok": False, "error": last}


# ----------------------------------------------------------------------------
def main():
    jobs = build_jobs()
    mf = load_manifest()
    mf.setdefault("files", {})
    log(f"target: {len(jobs)} monthly archives -> {RAW}")

    t0 = time.time()
    failures = []
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(fetch, j, mf): j for j in jobs}
        for fu in as_completed(futs):
            k, rec = fu.result()
            if not rec.get("ok"):
                failures.append((k, rec.get("error")))

    ok = [v for v in mf["files"].values() if v.get("ok")]
    total = sum(v["bytes"] for v in ok)
    mf["summary"] = {
        "months_ok": len(ok), "months_failed": len(failures),
        "total_bytes": total, "total_gb": round(total / 2**30, 3),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    save_manifest(mf)

    log("-" * 64)
    log(f"done in {(time.time()-t0)/60:.1f} min | ok={len(ok)}/{len(jobs)} | {total/2**30:.2f} GB")
    for k, e in failures:
        log(f"  FAILED {k}: {e}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
