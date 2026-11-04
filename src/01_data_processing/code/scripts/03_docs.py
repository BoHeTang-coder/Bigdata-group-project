# -*- coding: utf-8 -*-
"""
Pull the official field dictionary (readme.html) out of a prezip archive and
convert it to Markdown, then verify the CSV header == form field list (1:1).

Outputs
  data/bts/docs/readme_<file>.html      original BTS documentation
  data/bts/docs/BTS_Ontime_field_dictionary.md
  data/bts/docs/schema_check.json
"""
import html as htmlmod
import json
import os
import re
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "data", "bts", "docs")
MANIFEST = os.path.join(ROOT, "data", "bts", "manifest.json")
FORM_FIELDS = os.path.join(ROOT, "scripts", "bts_fields_form.json")


def strip_tags(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</tr>|</div>|</li>", "\n", s, flags=re.I)
    s = re.sub(r"</t[dh]>", "\t", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = htmlmod.unescape(s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def main():
    os.makedirs(DOCS, exist_ok=True)
    mf = json.load(open(MANIFEST, encoding="utf-8"))

    # newest completed archive
    keys = sorted(k for k, v in mf["files"].items() if v.get("ok")
                  and "readme.html" in (v.get("zip_members") or []))
    key = keys[-1]
    rec = mf["files"][key]
    zpath = os.path.join(ROOT, rec["file"].replace("/", os.sep))
    print(f"source archive: {key}  ({rec['file']})")

    with zipfile.ZipFile(zpath) as zf:
        raw = zf.read("readme.html")
    out_html = os.path.join(DOCS, f"readme_{key.replace('-', '_')}.html")
    with open(out_html, "wb") as f:
        f.write(raw)

    txt = raw.decode("latin-1", "replace")
    md = strip_tags(txt)
    md_path = os.path.join(DOCS, "BTS_Ontime_field_dictionary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# BTS On-Time Performance - official field dictionary\n\n"
                f"> Extracted verbatim from `readme.html` inside the official "
                f"PREZIP archive `{os.path.basename(zpath)}`\n"
                f"> Source: https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ\n\n"
                f"```\n{md}\n```\n")
    print(f"wrote {os.path.relpath(md_path, ROOT)}  ({len(md):,} chars)")
    print(f"wrote {os.path.relpath(out_html, ROOT)}")

    # ---- schema cross-check -------------------------------------------------
    form = json.load(open(FORM_FIELDS, encoding="utf-8"))
    csv_cols = [c.strip('"') for c in rec["csv_header"].split(",") if c.strip('"')]
    check = {
        "source_archive": key,
        "form_field_count": len(form),
        "csv_column_count": len(csv_cols),
        "counts_match": len(form) == len(csv_cols),
        "form_fields": form,
        "csv_columns": csv_cols,
    }
    with open(os.path.join(DOCS, "schema_check.json"), "w", encoding="utf-8") as f:
        json.dump(check, f, indent=2, ensure_ascii=False)

    print(f"\nform fields = {len(form)}   csv columns = {len(csv_cols)}   "
          f"match = {check['counts_match']}")
    print("\ncsv columns:")
    for i, c in enumerate(csv_cols, 1):
        print(f"  {i:3d}. {c}")


if __name__ == "__main__":
    main()
