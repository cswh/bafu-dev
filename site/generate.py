#!/usr/bin/env python3
"""Generate the static GitHub Pages site for the BAFU 2026 v1 process datasets.

Reads the EcoSpold1 and ILCD process data sets, extracts index metadata,
and writes a static site into docs/:
  - index.html         landing page with search / filter / sort
  - assets/index.json  metadata for all processes
  - process/<uuid>/    one page per process with side-by-side raw XML
"""

import json
import os
import shutil
import uuid as uuidlib
import xml.etree.ElementTree as ET
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "bafu_2026_v1")
ECOSPOLD_DIR = os.path.join(DATA, "ecoSpold files", "nexus_version_1")
ILCD_DIR = os.path.join(DATA, "openlca_ilcd_export", "nexus_version_1", "ILCD", "processes")
DOCS = ROOT
BASE_PATH = "/bafu-dev/"

ECOSPOLD_REL = "data/bafu_2026_v1/ecoSpold files/nexus_version_1/process_{u}.xml"
ILCD_REL = "data/bafu_2026_v1/openlca_ilcd_export/nexus_version_1/ILCD/processes/{u}.xml"


def esc(s):
    return escape(s if s is not None else "")


def extract_ecospold(path):
    r = ET.parse(path).getroot()
    rf = r.find(".//referenceFunction")
    geo = r.find(".//geography")
    tp = r.find(".//timePeriod")
    ds = r.find(".//dataSetInformation")
    def rfget(k):
        return rf.get(k) if rf is not None else None
    def tpget(tag):
        if tp is None:
            return None
        el = tp.find(tag)
        return el.text if el is not None else None
    return {
        "name": rfget("name"),
        "unit": rfget("unit"),
        "category": rfget("category"),
        "subcategory": rfget("subCategory"),
        "location": geo.get("location") if geo is not None else None,
        "start": tpget("startDate"),
        "end": tpget("endDate"),
        "type": ds.get("type") if ds is not None else None,
        "infrastructure": rfget("infrastructureProcess"),
    }


def build_index():
    entries = []
    for fn in sorted(os.listdir(ECOSPOLD_DIR)):
        if not fn.endswith(".xml") or not fn.startswith("process_"):
            continue
        uid = fn[len("process_"):-len(".xml")]
        meta = extract_ecospold(os.path.join(ECOSPOLD_DIR, fn))
        entries.append({"uuid": uid, **meta})
    return entries


def page_shell(title, body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="{BASE_PATH}assets/style.css">
</head>
<body>
{body}
</body>
</html>
"""


def build_process_page(entry):
    uid = entry["uuid"]
    ecospold_src = ECOSPOLD_REL.format(u=uid)
    ilcd_src = ILCD_REL.format(u=uid)
    name = entry.get("name") or uid
    back = f'<a class="back" href="{BASE_PATH}index.html">&larr; All processes</a>'
    meta_rows = [
        ("Name", entry.get("name")),
        ("Location", entry.get("location")),
        ("Reference unit", entry.get("unit")),
        ("Category", entry.get("category")),
        ("Subcategory", entry.get("subcategory")),
        ("Start date", entry.get("start")),
        ("End date", entry.get("end")),
        ("UUID", uid),
    ]
    meta_html = "".join(
        f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in meta_rows
    )
    body = f"""
<header>
  {back}
  <h1>{esc(name)}</h1>
</header>
<main>
<section class="meta">
  <table>{meta_html}</table>
  <p class="links">
    <a href="{BASE_PATH}{ecospold_src}">EcoSpold1 raw XML</a>
    &middot;
    <a href="{BASE_PATH}{ilcd_src}">ILCD raw XML</a>
  </p>
</section>
<section class="compare">
  <div class="pane">
    <h2>EcoSpold1 (raw)</h2>
    <iframe src="{BASE_PATH}{ecospold_src}" title="EcoSpold1 raw XML"></iframe>
  </div>
  <div class="pane">
    <h2>ILCD (raw)</h2>
    <iframe src="{BASE_PATH}{ilcd_src}" title="ILCD raw XML"></iframe>
  </div>
</section>
</main>
"""
    return page_shell(name, body)


def write_site(index):
    assets = os.path.join(DOCS, "assets")
    proc_dir = os.path.join(DOCS, "process")
    for d in (assets, proc_dir):
        if os.path.exists(d):
            shutil.rmtree(d)
    os.makedirs(assets)
    os.makedirs(proc_dir)

    with open(os.path.join(assets, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)

    src_assets = os.path.join(ROOT, "site", "assets")
    for fn in os.listdir(src_assets):
        shutil.copy(os.path.join(src_assets, fn), os.path.join(assets, fn))
    shutil.copy(os.path.join(src_assets, "index.html"), os.path.join(DOCS, "index.html"))
    open(os.path.join(DOCS, ".nojekyll"), "w").close()

    for entry in index:
        uid = entry["uuid"]
        d = os.path.join(proc_dir, uid)
        os.makedirs(d)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_process_page(entry))


def main():
    index = build_index()
    print(f"index entries: {len(index)}")
    write_site(index)
    print("site written to repo root")


if __name__ == "__main__":
    main()
