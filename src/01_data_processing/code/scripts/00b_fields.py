# -*- coding: utf-8 -*-
"""Extract the official BTS variable list from the saved DL_SelectFields form HTML."""
import re, json, os

here = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(here, "..", "probe_form.html"), encoding="utf-8").read()

inputs = re.findall(r'<input[^>]*type=["\']checkbox["\'][^>]*>', html, re.I)
CONTROL = {"chkAllVars", "chkAllGroups", "chkDownloadZip",
           "chkshowNull", "chkMergeSub", "chkDocument", "chkTermDef"}

fields = []
for tag in inputs:
    m = re.search(r'name="([^"]+)"', tag)
    if not m:
        continue
    n = m.group(1)
    if n in CONTROL:
        continue
    fields.append(n)

print("checkbox inputs total :", len(inputs))
print("control checkboxes    :", len([t for t in inputs if re.search(r'name="(chkAllVars|chkAllGroups|chkDownloadZip|chkshowNull|chkMergeSub|chkDocument|chkTermDef)"', t)]))
print("DATA fields           :", len(fields))
print()
for i, f in enumerate(fields, 1):
    print(f"{i:3d}. {f}")

with open(os.path.join(here, "bts_fields_form.json"), "w", encoding="utf-8") as fh:
    json.dump(fields, fh, indent=2)
print("\nsaved -> scripts/bts_fields_form.json")
