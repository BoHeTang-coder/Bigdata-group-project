# -*- coding: utf-8 -*-
"""Probe BTS TranStats: form structure + prezip availability for 2023-2025."""
import re, sys, urllib.request, urllib.error, concurrent.futures

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36"


def get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout)


def head(url, timeout=90):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, int(r.headers.get("Content-Length") or 0)
    except urllib.error.HTTPError as e:
        return e.code, 0
    except Exception as e:
        return "ERR:" + type(e).__name__, 0


FORM = "https://transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ&QO_fu146_anzr=b0-gvzr"

print("=" * 70)
print("[1] FORM PAGE")
print("=" * 70)
try:
    html = get(FORM).read().decode("utf-8", "replace")
    print("bytes:", len(html))
    for pat, tag in [
        (r'name="__VIEWSTATE"\s+value="([^"]{0,60})', "VIEWSTATE"),
        (r'name="__EVENTVALIDATION"\s+value="([^"]{0,60})', "EVENTVALIDATION"),
        (r'name="__VIEWSTATEGENERATOR"\s+value="([^"]{0,60})', "VIEWSTATEGENERATOR"),
    ]:
        m = re.search(pat, html)
        print(f"{tag}: {'FOUND' if m else 'missing'}")
    # table display name
    for m in re.finditer(r'<h[12][^>]*>(.*?)</h[12]>', html, re.S):
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if t:
            print("HEADING:", t[:120])
    # count field checkboxes
    boxes = re.findall(r'name="chk(?:Box)?([A-Za-z0-9_]+)"', html, re.I)
    print("checkbox-ish matches:", len(boxes), "unique:", len(set(boxes)))
    boxes2 = re.findall(r'<input[^>]+type=["\']checkbox["\'][^>]*>', html, re.I)
    print("raw <input type=checkbox>:", len(boxes2))
    # all input names
    names = re.findall(r'<input[^>]+name="([^"]+)"', html, re.I)
    from collections import Counter
    print("input names:", Counter(names).most_common(30))
    with open("probe_form.html", "w", encoding="utf-8") as f:
        f.write(html)
except Exception as e:
    print("FORM ERR", type(e).__name__, e)

print()
print("=" * 70)
print("[2] PREZIP AVAILABILITY 2023-2025")
print("=" * 70)
BASE = ("https://transtats.bts.gov/PREZIP/"
        "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{y}_{m}.zip")
jobs = [(y, m) for y in (2023, 2024, 2025) for m in range(1, 13)]
total = 0
with concurrent.futures.ThreadPoolExecutor(6) as ex:
    futs = {ex.submit(head, BASE.format(y=y, m=m)): (y, m) for y, m in jobs}
    res = {}
    for fu in concurrent.futures.as_completed(futs):
        y, m = futs[fu]
        res[(y, m)] = fu.result()
for y, m in jobs:
    st, ln = res[(y, m)]
    total += ln
    print(f"  {y}-{m:02d}  status={st}  bytes={ln:,}")
print(f"TOTAL: {total:,} bytes = {total/1024/1024/1024:.2f} GB")
