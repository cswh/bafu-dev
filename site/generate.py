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


def sentier_dirs(dataset):
    out = []
    sdir = os.path.join(RAW_DATA, dataset, "sentier_dev")
    if not os.path.isdir(sdir):
        return out
    for fn in sorted(os.listdir(sdir)):
        if os.path.isdir(os.path.join(sdir, fn)):
            out.append(os.path.join(sdir, fn))
    return out


_SENTIER_CACHE = {}


def load_sentier(dataset):
    """Load sentier_dev registry for a dataset. Returns dict or None."""
    if dataset in _SENTIER_CACHE:
        return _SENTIER_CACHE[dataset]
    dirs = sentier_dirs(dataset)
    result = None
    for d in dirs:
        reg = os.path.join(d, "registry")
        if not os.path.isdir(reg):
            continue
        try:
            import pyarrow.parquet as pq
        except ImportError:
            result = None
            break
        procs = pq.read_table(os.path.join(reg, "processes.parquet")).to_pylist()
        bios = pq.read_table(os.path.join(reg, "biosphere.parquet")).to_pylist()
        exch = pq.read_table(os.path.join(reg, "exchanges.parquet")).to_pylist()
        # reverse nomenclature map: EF3.1 (name, categories) -> BAFU source name
        rev = {}
        mdir = None
        for cand in os.listdir(d):
            if os.path.isdir(os.path.join(d, cand)) and cand.startswith("mappings"):
                mdir = os.path.join(d, cand)
                break
        if mdir:
            for sub in os.listdir(mdir):
                subp = os.path.join(mdir, sub)
                if not os.path.isdir(subp):
                    continue
                for fn in os.listdir(subp):
                    if not fn.startswith("biosphere-") or not fn.endswith(".json"):
                        continue
                    try:
                        mj = json.load(open(os.path.join(subp, fn), encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    for r in mj.get("replace", []):
                        t, sr = r.get("target"), r.get("source")
                        if t and sr:
                            rev.setdefault(
                                (str(t.get("name", "")).lower(), "::".join(str(c) for c in (t.get("context") or []))),
                                sr.get("name"),
                            )
        rev_name = {}
        for (nm, _ctx), v in rev.items():
            rev_name.setdefault(nm, v)
        bw2proc = {p["bw_id"]: p for p in procs}
        bw2bio = {b["bw_id"]: b for b in bios}
        uuid2bw = {p["code"]: p["bw_id"] for p in procs}
        ex_by_proc = {}
        for x in exch:
            ex_by_proc.setdefault(x["process_bw_id"], []).append(x)
        result = {
            "dir": d,
            "bw2proc": bw2proc,
            "bw2bio": bw2bio,
            "uuid2bw": uuid2bw,
            "ex_by_proc": ex_by_proc,
            "rev": rev,
            "rev_name": rev_name,
        }
        break
    _SENTIER_CACHE[dataset] = result
    return result


def sentier_exchange_rows(sent, uid):
    """Build display rows for one process from the sentier registry."""
    bw = sent["uuid2bw"].get(uid)
    if bw is None:
        return []
    rows = []
    for x in sent["ex_by_proc"].get(bw, []):
        db = x["input_database"]
        name = None
        cat = None
        loc = None
        ftype = None
        bafu_name = None
        if db.endswith("biosphere"):
            b = sent["bw2bio"].get(x["input_bw_id"])
            if b:
                name = b["name"]
                cat = b["categories"]
                ftype = b["type"]
                key = (str(b["name"]).lower(), str(b["categories"] or ""))
                bafu_name = sent["rev"].get((str(b["name"]).lower(), key[1]))
                if bafu_name is None:
                    bafu_name = sent["rev_name"].get(str(b["name"]).lower())
        else:
            p = sent["bw2proc"].get(x["input_bw_id"])
            if p:
                name = p["name"]
                loc = p["location"]
                cat = None
        if x["type"] == "production":
            direction = "Output"
        elif x["type"] == "technosphere":
            direction = "Input"
        elif ftype == "emission":
            direction = "Output"
        elif ftype == "natural resource":
            direction = "Input"
        else:
            direction = "Input"
        rows.append({
            "type": x["type"],
            "name": name,
            "bafu_name": bafu_name,
            "direction": direction,
            "amount": x["amount"],
            "unit": x["unit"],
            "cat": cat,
            "location": loc,
            "flow_type": ftype,
            "code": x["input_code"],
            "uncertainty": x.get("uncertainty_type"),
            "loc_p": x.get("loc"),
            "scale": x.get("scale"),
            "index": len(rows),
        })
    return rows


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
    # third pass: guess remaining by direction + similar name only (nomenclature renames)
    still2 = [(i, p) for i, p in enumerate(pairs) if p[1] is None]
    for pi, (e, _x, _s) in still2:
        best, best_score = None, 0.0
        for oi, x in enumerate(orphans):
            if x["direction"] != e["direction"]:
                continue
            sim = difflib.SequenceMatcher(None, (e["name"] or "").lower(), (x["name"] or "").lower()).ratio()
            if sim > best_score:
                best, best_score = oi, sim
        if best is not None and best_score >= 0.45:
            x = orphans.pop(best)
            pairs[pi] = (e, x, 0)
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


def build_exchange_rows(eco_ex, sources):
    """sources: list of dicts {key, label, exchanges, kind} where kind is 'ilcd' or 'sentier'.
    EcoSpold1 rows are the reference; every other source adds a row per exchange.
    Each row carries 'ref_idx': the 1-based index of the EcoSpold1 exchange it corresponds to (0 = unlinked)."""
    rows = []
    details = {}
    matched_counts = {}
    orphan_counts = {}
    for gi, e in enumerate(eco_ex):
        eco_cat = (e.get("category") or "") + ((" / " + e["subcategory"]) if e.get("subcategory") else "")
        eco_name = e["name"]
        d = {"eco": e["index"]}
        rows.append({
            "group": gi, "source": "EcoSpold1", "ref": True, "ref_idx": gi + 1,
            "name": e["name"], "direction": e["direction"], "amount": e["amount"],
            "unit": e["unit"], "cat": eco_cat, "location": e["location"],
            "sphere": biosphere_or_technosphere(e, None), "raw": ("eco", e["index"]),
        })
        for src in sources:
            key, label, exch = src["key"], src["label"], src["exchanges"]
            x = None
            for xx in exch:
                if xx.get("_matched_group") == gi:
                    x = xx
                    break
            if x is not None:
                matched_counts[label] = matched_counts.get(label, 0) + 1
                d[key] = x["index"]
                common = {
                    "group": gi, "source": label, "ref": False, "ref_idx": gi + 1,
                    "name": x["name"], "direction": x["direction"], "amount": x["amount"],
                    "unit": x["unit"], "location": x["location"],
                    "raw": (key, x["index"]),
                    "guess": x.get("_guessed", False),
                }
                if src["kind"] == "ilcd":
                    common["cat"] = " / ".join(x["category"]) if x.get("category") else ""
                    common["sphere"] = biosphere_or_technosphere(e, x)
                else:
                    common["cat"] = x.get("cat")
                    common["sphere"] = "Biosphere" if x.get("type") == "biosphere" else "Technosphere"
                    common["xtype"] = x.get("type")
                    common["bafu_name"] = x.get("bafu_name")
                rows.append(common)
            else:
                rows.append({
                    "group": gi, "source": label, "ref": False, "ref_idx": gi + 1,
                    "name": None, "direction": e["direction"], "amount": None,
                    "unit": None, "cat": None, "location": None,
                    "sphere": None, "raw": (key, None), "guess": False,
                })
        details[gi] = d
    for src in sources:
        key, label, exch = src["key"], src["label"], src["exchanges"]
        for x in exch:
            if x.get("_matched_group") is None:
                orphan_counts[label] = orphan_counts.get(label, 0) + 1
                common = {
                    "group": None, "source": label, "ref": False,
                    "name": x["name"], "direction": x["direction"], "amount": x["amount"],
                    "unit": x["unit"], "location": x["location"],
                    "ref_idx": 0,
                    "raw": (key, x["index"]), "guess": False,
                }
                if src["kind"] == "ilcd":
                    common["cat"] = " / ".join(x["category"]) if x.get("category") else ""
                    common["sphere"] = "Biosphere" if x.get("type") and "Elementary" in x["type"] else "Technosphere"
                else:
                    common["cat"] = x.get("cat")
                    common["sphere"] = "Biosphere" if x.get("type") == "biosphere" else "Technosphere"
                    common["xtype"] = x.get("type")
                    common["bafu_name"] = x.get("bafu_name")
                rows.append(common)
    parts = [f"{len(eco_ex)} EcoSpold1 exchanges"]
    for src in sources:
        m = matched_counts.get(src["label"], 0)
        o = orphan_counts.get(src["label"], 0)
        parts.append(f"{src['label']}: {m} matched, {len(eco_ex) - m} unmatched, {o} source-only")
    summary = "; ".join(parts)
    return rows, summary, details


def tag_sources(sources, eco_ex):
    """Attach matched group ids to each exchange of each source."""
    for src in sources:
        exch = src["exchanges"]
        pairs, orphans = match_exchanges(eco_ex, exch)
        for x in exch:
            x["_matched_group"] = None
            x["_guessed"] = False
        for gi, (e, x, score) in enumerate(pairs):
            if x is not None:
                x["_matched_group"] = gi
                x["_guessed"] = score <= 1


def tag_sources(sources, eco_ex):
    """Attach matched group ids to each exchange of each source."""
    for src in sources:
        exch = src["exchanges"]
        pairs, orphans = match_exchanges(eco_ex, exch)
        for x in exch:
            x["_matched_group"] = None
            x["_guessed"] = False
        for gi, (e, x, score) in enumerate(pairs):
            if x is not None:
                x["_matched_group"] = gi
                x["_guessed"] = score <= 1


def sentier_process_json(sent, uid):
    """JSON-like view of the sentier_dev data for one process."""
    bw = sent["uuid2bw"].get(uid)
    if bw is None:
        return None
    p = sent["bw2proc"][bw]
    rows = sentier_exchange_rows(sent, uid)
    return {
        "process": {k: p[k] for k in ("bw_id", "database", "code", "name", "reference_product", "unit", "location", "production_amount")},
        "exchanges": [
            {k: r[k] for k in ("type", "name", "bafu_name", "direction", "amount", "unit", "cat", "location", "flow_type", "code", "uncertainty", "loc_p", "scale") if r.get(k) is not None}
            for r in rows
        ],
    }


def build_process_page(entry, formats, eco_ex, sources, sentier_json=None):
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
    if sentier_json is not None:
        sentier_html = json.dumps(sentier_json, ensure_ascii=False, indent=1).replace("</", "<" + chr(92) + "/")
        panes += (
            '<div class="pane"><h2>sentier_dev (JSON-like view)</h2>'
            f'<pre class="jsonview">{sentier_html}</pre></div>'
        )
    cls = "many" if len(formats) > 3 else ("three" if len(formats) == 3 else "two")
    rows, ex_summary, details = build_exchange_rows(eco_ex, sources)
    rows_json = json.dumps([{**{k: r.get(k) for k in ("group","source","ref","ref_idx","guess","name","direction","amount","unit","cat","location","sphere","xtype","bafu_name")}, "raw": [r["raw"][0], r["raw"][1]]} for r in rows], ensure_ascii=False)
    details_json = json.dumps(details, ensure_ascii=False)
    source_urls = {}
    eco_fmt = next((f for f in formats if f[0].startswith("ecospold")), None)
    if eco_fmt:
        source_urls["eco"] = BASE_PATH + eco_fmt[2].format(u=uid)
    for i, f in enumerate(f for f in formats if f[0].startswith("ilcd")):
        source_urls[f[0]] = BASE_PATH + f[2].format(u=uid)
    urls_json = json.dumps(source_urls, ensure_ascii=False)
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
  <h2>Exchanges</h2>
  <p class="ex-summary">{esc(ex_summary)}</p>
  <div class="ex-controls">
    <input type="search" id="ex-q" placeholder="Filter by name, category, unit&hellip;" aria-label="Filter exchanges">
    <select id="ex-source" aria-label="Filter by source"><option value="">Source: all</option></select>
    <select id="ex-direction" aria-label="Filter by direction"><option value="">Direction: all</option><option>Input</option><option>Output</option></select>
    <select id="ex-sphere" aria-label="Filter by sphere"><option value="">Sphere: all</option><option>Biosphere</option><option>Technosphere</option></select>
    <select id="ex-sort" aria-label="Sort by">
      <option value="group">Sort: file order</option>
      <option value="name">Sort: name</option>
      <option value="source">Sort: source</option>
      <option value="direction">Sort: direction</option>
      <option value="amount">Sort: amount</option>
      <option value="unit">Sort: unit</option>
      <option value="cat">Sort: category</option>
      <option value="location">Sort: location</option>
      <option value="sphere">Sort: sphere</option>
    </select>
    <label><input type="checkbox" id="ex-desc"> descending</label>
  </div>
  <div class="tbl-wrap"><table class="ex-table" id="ex-table">
    <thead><tr>
      <th data-key="name">Flow name</th><th data-key="source">Source</th><th data-key="ref_idx">EcoSpold1 reference</th><th data-key="direction">Direction</th>
      <th data-key="amount">Amount</th><th data-key="unit">Unit</th><th data-key="cat">Category / compartment</th>
      <th data-key="location">Location</th><th data-key="sphere">Sphere</th><th>Raw</th>
    </tr></thead>
    <tbody></tbody>
  </table></div>
  <p class="ex-count" id="ex-count"></p>
  <div id="ex-detail" class="ex-detail" hidden>
    <button id="ex-detail-close">&times;</button>
    <div class="panes" id="detail-panes"></div>
  </div>
</section>
<section class="compare {cls}">
{panes}
</section>
<script src="{BASE_PATH}assets/exchanges.js"></script>
</main>
"""
    payload_json = json.dumps(
        {"rows": json.loads(rows_json), "details": json.loads(details_json), "urls": json.loads(urls_json)},
        ensure_ascii=False,
    ).replace("</", "<" + chr(92) + "/")
    payload = '<script type="application/json" id="ex-data">' + payload_json + '</script>'
    return page_shell(name, payload + body, f"{BASE_PATH}assets/process.css")


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
    ilcd_fmts = [f for f in formats if f[0].startswith("ilcd")]
    ctxs = {}
    for f in ilcd_fmts:
        nv = f[0].replace("ilcd", "")
        ilcd_base = os.path.join(RAW_DATA, dataset, "openlca_ilcd_export", f"nexus_version_{nv}", "ILCD")
        ctxs[f[0]] = load_ilcd_context(ilcd_base) if os.path.isdir(ilcd_base) else None
    sent = load_sentier(dataset)
    for entry in index:
        uid = entry["uuid"]
        eco_ex = []
        if eco_fmt:
            eco_path = os.path.join(ROOT, eco_fmt[2].format(u=uid))
            if os.path.exists(eco_path):
                eco_ex = parse_eco_exchanges(eco_path)
        sources = []
        for f in ilcd_fmts:
            path = os.path.join(ROOT, f[2].format(u=uid))
            exs = []
            if os.path.exists(path) and ctxs.get(f[0]):
                exs = parse_ilcd_exchanges(path, ctxs[f[0]])
            sources.append({"key": f[0], "label": f[1], "exchanges": exs, "kind": "ilcd"})
        if sent and sent["uuid2bw"].get(uid) is not None:
            sent_rows = sentier_exchange_rows(sent, uid)
            sources.append({"key": "sentier", "label": "sentier_dev (EF 3.1)", "exchanges": sent_rows, "kind": "sentier"})
        tag_sources(sources, eco_ex)
        d = os.path.join(proc_dir, uid)
        os.makedirs(d)
        sentier_json = sentier_process_json(sent, uid) if sent else None
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_process_page(entry, formats, eco_ex, sources, sentier_json))


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
