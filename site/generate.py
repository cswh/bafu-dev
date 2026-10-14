#!/usr/bin/env python3
"""Generate the static GitHub Pages site for the BAFU process datasets.

Scans all dataset versions under data/ (e.g. bafu_2026_v1, bafu_2026_v2,
bafu_2027_v1), extracts index metadata from the EcoSpold1 files, and writes
a static site at the repository root:
  - <dataset>/index.html    landing page with search / filter / sort
  - <dataset>/assets/*      styles, scripts, index.json
  - <dataset>/process/<uuid>/  one page per process with side-by-side raw XML

The repo-root index.html redirects to the latest dataset version.
"""

import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = ROOT
BASE_PATH = "/bafu-dev/"

ECOSPOLD_REL = "data/{d}/ecoSpold files/nexus_version_1/process_{u}.xml"
ILCD_REL = "data/{d}/openlca_ilcd_export/nexus_version_1/ILCD/processes/{u}.xml"

VERSION_RE = re.compile(r"^bafu_(\d{4})_v(\d+)$")


def esc(s):
    return escape(s if s is not None else "")


def dataset_dirs():
    dirs = []
    for fn in sorted(os.listdir(DATA)):
        if not os.path.isdir(os.path.join(DATA, fn)) or not VERSION_RE.match(fn):
            continue
        eco = os.path.join(DATA, fn, "ecoSpold files")
        if os.path.isdir(eco):
            dirs.append(fn)
    return dirs


def dataset_label(ds):
    m = VERSION_RE.match(ds)
    if not m:
        return ds
    return f"BAFU {m.group(1)} v{m.group(2)}"


def dataset_sort_key(ds):
    m = VERSION_RE.match(ds)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


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


def build_index(dataset):
    eco_dir = os.path.join(DATA, dataset, "ecoSpold files", "nexus_version_1")
    entries = []
    for fn in sorted(os.listdir(eco_dir)):
        if not fn.endswith(".xml") or not fn.startswith("process_"):
            continue
        uid = fn[len("process_"):-len(".xml")]
        meta = extract_ecospold(os.path.join(eco_dir, fn))
        entries.append({"uuid": uid, "dataset": dataset, **meta})
    return entries


def page_shell(title, body, dataset):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="{BASE_PATH}{dataset}/assets/style.css">
<link rel="stylesheet" href="{BASE_PATH}{dataset}/assets/process.css">
</head>
<body>
{body}
</body>
</html>
"""


def build_process_page(entry):
    uid = entry["uuid"]
    ds = entry["dataset"]
    ecospold_src = ECOSPOLD_REL.format(d=ds, u=uid)
    ilcd_src = ILCD_REL.format(d=ds, u=uid)
    name = entry.get("name") or uid
    back = f'<a class="back" href="{BASE_PATH}{ds}/index.html">&larr; {esc(dataset_label(ds))} &middot; all processes</a>'
    meta_rows = [
        ("Name", entry.get("name")),
        ("BAFU version", dataset_label(ds)),
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
    return page_shell(name, body, ds)


def write_dataset_site(dataset, index, all_versions):
    out = os.path.join(OUT, dataset)
    assets = os.path.join(out, "assets")
    proc_dir = os.path.join(out, "process")
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

    versions_html = "".join(
        f'<a href="{BASE_PATH}{d}/index.html"{(" class=\"current\"" if d == dataset else "")}>{esc(dataset_label(d))}</a>'
        for d in all_versions
    )
    nav = f'<nav class="versions">{versions_html}</nav>'
    landing = open(os.path.join(src_assets, "index.html"), encoding="utf-8").read()
    landing = landing.replace('href="/bafu-dev/assets/', f'href="{BASE_PATH}{dataset}/assets/')
    landing = landing.replace('src="/bafu-dev/assets/', f'src="{BASE_PATH}{dataset}/assets/')
    landing = landing.replace("<!--VERSIONS-->", nav)
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(landing)

    for entry in index:
        uid = entry["uuid"]
        d = os.path.join(proc_dir, uid)
        os.makedirs(d)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_process_page(entry))


def write_root_redirect(latest):
    body = (
        f'<meta http-equiv="refresh" content="0; url={BASE_PATH}{latest}/index.html">'
        f'<link rel="canonical" href="{BASE_PATH}{latest}/index.html">'
        f'<p>Moved to <a href="{BASE_PATH}{latest}/index.html">{esc(dataset_label(latest))}</a></p>'
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BAFU process datasets</title>
{body}
</head>
</html>
"""
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


def main():
    datasets = sorted(dataset_dirs(), key=dataset_sort_key)
    if not datasets:
        raise SystemExit("no dataset versions found under data/")
    latest = datasets[-1]
    for ds in datasets:
        index = build_index(ds)
        print(f"{ds}: {len(index)} processes")
        write_dataset_site(ds, index, datasets)
    write_root_redirect(latest)
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    # remove generated output of dataset versions that no longer exist
    for fn in os.listdir(ROOT):
        if VERSION_RE.match(fn) and fn not in datasets:
            shutil.rmtree(os.path.join(ROOT, fn))
    print(f"site written; latest dataset: {latest}")


if __name__ == "__main__":
    main()
