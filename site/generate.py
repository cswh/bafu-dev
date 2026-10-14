#!/usr/bin/env python3
"""Generate the static GitHub Pages site for the BAFU process datasets.

Scans all dataset versions under raw_data/ (e.g. bafu_2026_v1,
bafu_2026_v2, bafu_2027_v1) and for each version discovers the raw
formats: every EcoSpold nexus version under "ecoSpold files/" and every
ILCD nexus version under "openlca_ilcd_export/". Output structure:

  index.html                       version-independent landing page
  assets/*                         styles, scripts, index.json
  pages/<dataset>/process/<uuid>/  one page per process with side-by-side
                                   raw XML of every available raw format
"""

import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA = os.path.join(ROOT, "raw_data")
PAGES = os.path.join(ROOT, "pages")
OUT = ROOT
BASE_PATH = "/bafu-dev/"

VERSION_RE = re.compile(r"^bafu_(\d{4})_v(\d+)$")
NEXUS_RE = re.compile(r"^nexus_version_(\d+)$")


def esc(s):
    return escape(s if s is not None else "")


def dataset_dirs():
    dirs = []
    for fn in sorted(os.listdir(RAW_DATA)):
        if os.path.isdir(os.path.join(RAW_DATA, fn)) and VERSION_RE.match(fn):
            dirs.append(fn)
    return sorted(dirs, key=dataset_sort_key)


def dataset_label(ds):
    m = VERSION_RE.match(ds)
    return f"BAFU {m.group(1)} v{m.group(2)}" if m else ds


def dataset_sort_key(ds):
    m = VERSION_RE.match(ds)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def nexus_versions(path):
    if not os.path.isdir(path):
        return []
    out = []
    for fn in sorted(os.listdir(path)):
        m = NEXUS_RE.match(fn)
        if m and os.path.isdir(os.path.join(path, fn)):
            out.append(int(m.group(1)))
    return sorted(out)


def raw_formats(dataset):
    """Return list of (key, title, relpath_template) for each raw format."""
    eco_base = os.path.join(RAW_DATA, dataset, "ecoSpold files")
    ilcd_base = os.path.join(RAW_DATA, dataset, "openlca_ilcd_export")
    formats = []
    for nv in nexus_versions(eco_base):
        key = f"ecospold{nv}"
        title = f"EcoSpold1 (nexus v{nv})"
        rel = f"raw_data/{dataset}/ecoSpold files/nexus_version_{nv}/process_{{u}}.xml"
        formats.append((key, title, rel))
    for nv in nexus_versions(ilcd_base):
        key = f"ilcd{nv}"
        title = f"ILCD (nexus v{nv})"
        rel = f"raw_data/{dataset}/openlca_ilcd_export/nexus_version_{nv}/ILCD/processes/{{u}}.xml"
        formats.append((key, title, rel))
    return formats


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


def build_index(dataset, formats):
    eco = [f for f in formats if f[0].startswith("ecospold")]
    if not eco:
        return []
    nv = eco[0][0].replace("ecospold", "")
    eco_dir = os.path.join(RAW_DATA, dataset, "ecoSpold files", f"nexus_version_{nv}")
    entries = []
    for fn in sorted(os.listdir(eco_dir)):
        if not fn.endswith(".xml") or not fn.startswith("process_"):
            continue
        uid = fn[len("process_"):-len(".xml")]
        meta = extract_ecospold(os.path.join(eco_dir, fn))
        entries.append({"uuid": uid, "dataset": dataset, **meta})
    return entries


def page_shell(title, body, stylesheet):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="{stylesheet}">
</head>
<body>
{body}
</body>
</html>
"""


def build_process_page(entry, formats):
    uid = entry["uuid"]
    ds = entry["dataset"]
    name = entry.get("name") or uid
    back = f'<a class="back" href="{BASE_PATH}index.html">&larr; all processes</a>'
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
    raw_links = " &middot; ".join(
        f'<a href="{BASE_PATH}{rel.format(u=uid)}">{esc(title)}</a>'
        for _, title, rel in formats
    )
    panes = "".join(
        f'<div class="pane"><h2>{esc(title)}</h2>'
        f'<iframe src="{BASE_PATH}{rel.format(u=uid)}" title="{esc(title)} raw XML"></iframe></div>'
        for _, title, rel in formats
    )
    cls = "many" if len(formats) > 3 else ("three" if len(formats) == 3 else "two")
    body = f"""
<header>
  {back}
  <h1>{esc(name)}</h1>
</header>
<main>
<section class="meta">
  <table>{meta_html}</table>
  <p class="links">{raw_links}</p>
</section>
<section class="compare {cls}">
{panes}
</section>
</main>
"""
    return page_shell(name, body, f"{BASE_PATH}assets/process.css")


def write_root_site(datasets, indexes):
    assets = os.path.join(OUT, "assets")
    if os.path.exists(assets):
        shutil.rmtree(assets)
    os.makedirs(assets)

    all_entries = []
    for ds in datasets:
        all_entries.extend(indexes[ds])
    with open(os.path.join(assets, "index.json"), "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False)

    src_assets = os.path.join(ROOT, "site", "assets")
    for fn in os.listdir(src_assets):
        shutil.copy(os.path.join(src_assets, fn), os.path.join(assets, fn))

    versions_html = "".join(
        f'<a href="{BASE_PATH}index.html?dataset={d}" data-dataset="{d}">{esc(dataset_label(d))}</a>'
        for d in datasets
    )
    landing = open(os.path.join(src_assets, "index.html"), encoding="utf-8").read()
    landing = landing.replace("<!--VERSIONS-->", f'<nav class="versions">{versions_html}</nav>')
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(landing)


def write_process_pages(dataset, index, formats):
    proc_dir = os.path.join(PAGES, dataset, "process")
    if os.path.exists(proc_dir):
        shutil.rmtree(proc_dir)
    os.makedirs(proc_dir)
    for entry in index:
        uid = entry["uuid"]
        d = os.path.join(proc_dir, uid)
        os.makedirs(d)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_process_page(entry, formats))


def cleanup_stale(datasets):
    if not os.path.isdir(PAGES):
        return
    for fn in os.listdir(PAGES):
        if VERSION_RE.match(fn) and fn not in datasets:
            shutil.rmtree(os.path.join(PAGES, fn))


def main():
    os.makedirs(PAGES, exist_ok=True)
    datasets = dataset_dirs()
    if not datasets:
        raise SystemExit("no dataset versions found under raw_data/")
    indexes = {}
    for ds in datasets:
        formats = raw_formats(ds)
        indexes[ds] = build_index(ds, formats)
        write_process_pages(ds, indexes[ds], formats)
        fmt_names = ", ".join(f[1] for f in formats)
        print(f"{ds}: {len(indexes[ds])} processes; formats: {fmt_names}")
    write_root_site(datasets, indexes)
    cleanup_stale(datasets)
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print(f"site written; datasets: {', '.join(datasets)}")


if __name__ == "__main__":
    main()
