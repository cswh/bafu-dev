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

OLCA = "{http://openlca.org/ilcd-extensions}"


def loc(tag):
    return tag.split("}")[-1]


def find1(el, name, from_depth=0):
    for e in el.iter():
        if loc(e.tag) == name:
            return e
    return None


def findall_loc(el, name):
    return [e for e in el.iter() if loc(e.tag) == name]

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


def load_ilcd_context(ilcd_base):
    """Load flow and unit lookup tables for an ILCD export."""
    flows = {}
    fdir = os.path.join(ilcd_base, "flows")
    if os.path.isdir(fdir):
        for fn in os.listdir(fdir):
            try:
                r = ET.parse(os.path.join(fdir, fn)).getroot()
            except ET.ParseError:
                continue
            u = find1(r, "UUID")
            if u is None:
                continue
            nm = find1(r, "baseName")
            typ = find1(r, "typeOfDataSet")
            loc_el = find1(r, "locationOfSupply")
            classes = findall_loc(r, "class") + findall_loc(r, "category")
            flows[u.text] = {
                "name": nm.text if nm is not None else None,
                "type": typ.text if typ is not None else None,
                "loc": loc_el.text if loc_el is not None else None,
                "cat": [c.text for c in classes if c.text],
            }
    units = {}
    udir = os.path.join(ilcd_base, "unitgroups")
    if os.path.isdir(udir):
        for fn in os.listdir(udir):
            try:
                r = ET.parse(os.path.join(udir, fn)).getroot()
            except ET.ParseError:
                continue
            for un in findall_loc(r, "unit"):
                uid = un.get(OLCA + "unitId")
                nm = find1(un, "name")
                if uid and nm is not None:
                    units[uid] = nm.text
    return {"flows": flows, "units": units}


def eco_direction(ex):
    for child in ex:
        t = loc(child.tag)
        if t in ("inputGroup", "outputGroup"):
            return "Input" if t == "inputGroup" else "Output"
    return None


def parse_eco_exchanges(path):
    r = ET.parse(path).getroot()
    out = []
    for i, ex in enumerate(findall_loc(r, "exchange")):
        a = ex.attrib
        out.append({
            "name": a.get("name"),
            "unit": a.get("unit"),
            "amount": a.get("meanValue"),
            "category": a.get("category"),
            "subcategory": a.get("subCategory"),
            "location": a.get("location"),
            "direction": eco_direction(ex),
            "cas": a.get("CASNumber"),
            "infrastructure": a.get("infrastructureProcess"),
            "uncertainty": a.get("uncertaintyType"),
            "sd95": a.get("standardDeviation95"),
            "comment": a.get("generalComment"),
            "number": a.get("number"),
            "index": i,
        })
    return out


def parse_ilcd_exchanges(path, ctx):
    r = ET.parse(path).getroot()
    flows, units = ctx["flows"], ctx["units"]
    out = []
    for i, ex in enumerate(findall_loc(r, "exchange")):
        ref = find1(ex, "referenceToFlowDataSet")
        flow = flows.get(ref.get("refObjectId")) if ref is not None else None
        d = find1(ex, "exchangeDirection")
        mean = find1(ex, "meanAmount")
        res = find1(ex, "resultingAmount")
        unc = find1(ex, "uncertaintyDistributionType")
        sd = find1(ex, "relativeStandardDeviation95In")
        comment = find1(ex, "generalComment")
        out.append({
            "name": flow["name"] if flow else None,
            "unit": units.get(ex.get(OLCA + "unitId")),
            "amount": ex.get(OLCA + "amount") or (mean.text if mean is not None else None),
            "mean_amount": mean.text if mean is not None else None,
            "resulting_amount": res.text if res is not None else None,
            "category": flow["cat"] if flow else None,
            "type": flow["type"] if flow else None,
            "location": flow["loc"] if flow else None,
            "direction": d.text if d is not None else None,
            "uncertainty": unc.text if unc is not None else None,
            "sd95": sd.text if sd is not None else None,
            "comment": comment.text if comment is not None else None,
            "flow_uuid": ref.get("refObjectId") if ref is not None else None,
            "index": i,
        })
    return out


def num_eq(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-12
    except (TypeError, ValueError):
        return a == b


def match_exchanges(eco, ilcd):
    """Match each EcoSpold1 exchange (reference) to an ILCD exchange.
    Greedy: prefer (direction, name, amount) then (direction, name) then name."""
    used = [False] * len(ilcd)
    pairs = []
    for e in eco:
        best, best_score = None, -1
        for i, x in enumerate(ilcd):
            if used[i]:
                continue
            score = -1
            same_dir = x["direction"] == e["direction"]
            same_name = x["name"] == e["name"]
            same_amount = num_eq(x["amount"], e["amount"])
            if same_dir and same_name and same_amount:
                score = 3
            elif same_dir and same_name:
                score = 2
            elif same_name:
                score = 1
            elif same_dir and same_amount:
                score = 0
            if score > best_score:
                best, best_score = i, score
        if best is not None:
            used[best] = True
            pairs.append((e, ilcd[best], best_score))
        else:
            pairs.append((e, None, -1))
    orphans = [ilcd[i] for i in range(len(ilcd)) if not used[i]]
    # second pass: match remaining exchanges by direction + amount + name similarity
    import difflib
    still = [(i, p) for i, p in enumerate(pairs) if p[1] is None]
    for pi, (e, _, _) in still:
        best, best_score = None, 0.0
        for oi, x in enumerate(orphans):
            if x["direction"] != e["direction"]:
                continue
            if not num_eq(x["amount"], e["amount"]):
                continue
            sim = difflib.SequenceMatcher(None, (e["name"] or ""), (x["name"] or "")).ratio()
            if sim > best_score:
                best, best_score = oi, sim
        if best is not None and best_score >= 0.5:
            x = orphans.pop(best)
            pairs[pi] = (e, x, 1)
    orphans2 = [x for x in orphans]
    return pairs, orphans2


def biosphere_or_technosphere(eco_ex, ilcd_ex):
    if ilcd_ex and ilcd_ex.get("type"):
        t = ilcd_ex["type"]
        if "Elementary" in t:
            return "Biosphere"
        return "Technosphere"
    cat = (eco_ex.get("category") or "").lower()
    if cat in ("resources", "emissions to air", "emissions to water", "emissions to soil", "emissions"):
        return "Biosphere"
    return "Technosphere"


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


def fmt_val(v):
    if v is None:
        return '<span class="missing">&mdash;</span>'
    if isinstance(v, list):
        return esc(" / ".join(v))
    return esc(v)


def flag(a, b, cmp=None):
    ok = (a == b) if cmp is None else cmp(a, b)
    cls = "ok" if ok else "diff"
    return ok, cls


def build_exchange_table(eco, ilcd):
    pairs, orphans = match_exchanges(eco, ilcd)
    rows = []
    for idx, (e, x, score) in enumerate(pairs):
        bs = biosphere_or_technosphere(e, x)
        matched = x is not None
        cells = []
        # name
        ok, cls = flag(e["name"], x["name"] if x else None)
        cells.append(f'<td class="{cls}">{fmt_val(e["name"])}<div class="ilcd">{fmt_val(x["name"] if x else None)}</div></td>')
        # direction
        ok, cls = flag(e["direction"], x["direction"] if x else None)
        cells.append(f'<td class="{cls}">{fmt_val(e["direction"])}<div class="ilcd">{fmt_val(x["direction"] if x else None)}</div></td>')
        # amount
        ok_amt, cls = (True, "ok") if not matched else flag(e["amount"], x["amount"], num_eq)
        cells.append(f'<td class="{cls}">{fmt_val(e["amount"])}<div class="ilcd">{fmt_val(x["amount"] if x else None)}</div></td>')
        # unit
        ok_unit, cls = (True, "ok") if not matched else flag(e["unit"], x["unit"])
        cells.append(f'<td class="{cls}">{fmt_val(e["unit"])}<div class="ilcd">{fmt_val(x["unit"] if x else None)}</div></td>')
        # category / compartment
        eco_cat = (e.get("category") or "") + ((" / " + e["subcategory"]) if e.get("subcategory") else "")
        ilcd_cat = " / ".join(x["category"]) if x and x.get("category") else ""
        ok_cat, cls = (True, "ok") if not matched else flag(eco_cat, ilcd_cat)
        cells.append(f'<td class="{cls}">{esc(eco_cat)}<div class="ilcd">{fmt_val(ilcd_cat)}</div></td>')
        # location
        ok_loc, cls = (True, "ok") if not matched else flag(e["location"], x["location"])
        cells.append(f'<td class="{cls}">{fmt_val(e["location"])}<div class="ilcd">{fmt_val(x["location"] if x else None)}</div></td>')
        # biosphere/technosphere
        cells.append(f'<td>{bs}</td>')
        # detail link
        cells.append(f'<td><button class="detail-btn" data-ex="{idx}">raw</button></td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    for x in orphans:
        cells = [
            f'<td class="missing">no EcoSpold1 counterpart<div class="ilcd">{fmt_val(x["name"])}</div></td>',
            f'<td>{fmt_val(x["direction"])}</td>',
            f'<td>{fmt_val(x["amount"])}</td>',
            f'<td>{fmt_val(x["unit"])}</td>',
            f'<td>{fmt_val(" / ".join(x["category"]) if x.get("category") else "")}</td>',
            f'<td>{fmt_val(x["location"])}</td>',
            '<td>?</td>',
            '<td></td>',
        ]
        rows.append('<tr class="orphan">' + "".join(cells) + "</tr>")
    unmatched = sum(1 for _, x, _ in pairs if x is None)
    summary = f"{len(pairs)} EcoSpold1 exchanges, {len(pairs) - unmatched} matched in ILCD, {unmatched} unmatched, {len(orphans)} ILCD-only"
    detail_data = []
    for e, x, _ in pairs:
        detail_data.append({"eco": e["index"], "ilcd": x["index"] if x else None})
    for x in orphans:
        detail_data.append({"eco": None, "ilcd": x["index"]})
    return rows, summary, detail_data


def build_process_page(entry, formats, eco_exchanges, ilcd_exchanges, ilcd_ctx):
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
    ex_rows, ex_summary, ex_details = build_exchange_table(eco_exchanges, ilcd_exchanges)
    details_json = json.dumps(ex_details, ensure_ascii=False)
    eco_fmt_url = next((f for f in formats if f[0].startswith("ecospold")), None)
    ilcd_fmt_url = next((f for f in formats if f[0].startswith("ilcd")), None)
    eco_url_json = json.dumps(BASE_PATH + eco_fmt_url[2].format(u=uid)) if eco_fmt_url else "null"
    ilcd_url_json = json.dumps(BASE_PATH + ilcd_fmt_url[2].format(u=uid)) if ilcd_fmt_url else "null"
    ex_table = "".join(ex_rows)
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
<section class="exchanges">
  <h2>Exchanges (EcoSpold1 reference vs ILCD)</h2>
  <p class="ex-summary">{esc(ex_summary)}</p>
  <p class="legend">Each cell shows the <strong>EcoSpold1</strong> value on top and the <strong>ILCD</strong> value below; <span class="ok">green</span> = identical, <span class="diff">red</span> = different, <span class="missing">&mdash;</span> = missing.</p>
  <div class="tbl-wrap"><table class="ex-table">
    <thead><tr><th>Flow name</th><th>Direction</th><th>Amount</th><th>Unit</th><th>Category / compartment</th><th>Location</th><th>Sphere</th><th>Raw</th></tr></thead>
    <tbody>{ex_table}</tbody>
  </table></div>
  <div id="ex-detail" class="ex-detail" hidden>
    <button id="ex-detail-close">&times;</button>
    <div class="panes">
      <div><h3>EcoSpold1 exchange (raw)</h3><pre id="detail-eco"></pre></div>
      <div><h3>ILCD exchange (raw)</h3><pre id="detail-ilcd"></pre></div>
    </div>
  </div>
</section>
<section class="compare {cls}">
{panes}
</section>
<script>
(function() {{
  var details = {details_json};
  var box = document.getElementById("ex-detail");
  var ecoEl = document.getElementById("detail-eco");
  var ilcdEl = document.getElementById("detail-ilcd");
  var ecoUrl = {eco_url_json};
  var ilcdUrl = {ilcd_url_json};
  var cache = {{}};
  function extractNth(xmlText, tagName, n) {{
    var doc = new DOMParser().parseFromString(xmlText, "application/xml");
    var els = doc.getElementsByTagName(tagName);
    return els.length > n ? new XMLSerializer().serializeToString(els[n]) : null;
  }}
  function load(url, n, tagName, target) {{
    if (n === null || n === undefined) {{ target.textContent = "(no counterpart in this format)"; return Promise.resolve(); }}
    if (cache[url]) {{ target.textContent = extractNth(cache[url], tagName, n) || "(exchange not found)"; return Promise.resolve(); }}
    return fetch(url).then(function(r) {{ return r.text(); }}).then(function(t) {{
      cache[url] = t;
      target.textContent = extractNth(t, tagName, n) || "(exchange not found)";
    }}).catch(function() {{ target.textContent = "(failed to load raw file)"; }});
  }}
  document.querySelectorAll(".detail-btn").forEach(function(btn) {{
    btn.addEventListener("click", function() {{
      var d = details[parseInt(this.getAttribute("data-ex"), 10)];
      ecoEl.textContent = "loading...";
      ilcdEl.textContent = "loading...";
      load(ecoUrl, d.eco, "exchange", ecoEl);
      load(ilcdUrl, d.ilcd, "exchange", ilcdEl);
      box.hidden = false;
    }});
  }});
  document.getElementById("ex-detail-close").addEventListener("click", function() {{ box.hidden = true; }});
}})();
</script>
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
    eco_fmt = next((f for f in formats if f[0].startswith("ecospold")), None)
    ilcd_fmt = next((f for f in formats if f[0].startswith("ilcd")), None)
    ilcd_ctx = None
    if ilcd_fmt:
        ilcd_base = os.path.join(RAW_DATA, dataset, "openlca_ilcd_export", "nexus_version_1", "ILCD")
        if os.path.isdir(ilcd_base):
            ilcd_ctx = load_ilcd_context(ilcd_base)
    for entry in index:
        uid = entry["uuid"]
        eco_ex = []
        ilcd_ex = []
        if eco_fmt:
            eco_path = os.path.join(ROOT, eco_fmt[2].format(u=uid))
            if os.path.exists(eco_path):
                eco_ex = parse_eco_exchanges(eco_path)
        if ilcd_fmt and ilcd_ctx:
            ilcd_path = os.path.join(ROOT, ilcd_fmt[2].format(u=uid))
            if os.path.exists(ilcd_path):
                ilcd_ex = parse_ilcd_exchanges(ilcd_path, ilcd_ctx)
        d = os.path.join(proc_dir, uid)
        os.makedirs(d)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_process_page(entry, formats, eco_ex, ilcd_ex, ilcd_ctx))


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
