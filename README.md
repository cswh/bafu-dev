# bafu-dev

BAFU 2026 v1 LCI process datasets and the source for the GitHub Pages site.

## Repository layout

- `data/bafu_2026_v1/ecoSpold files/nexus_version_1/` — 11,947 process data sets in EcoSpold1 format (`process_<uuid>.xml`)
- `data/bafu_2026_v1/openlca_ilcd_export/nexus_version_1/ILCD/` — the same data sets in ILCD format (`processes/<uuid>.xml`), plus flows, flow properties, unit groups, sources, contacts and LCIA methods
- `site/` — static site generator and page templates
- `index.html`, `assets/`, `process/` — generated GitHub Pages output (do not edit by hand; regenerate instead)

Every process exists in both formats with the same UUID. The GitHub Pages site serves the repository root, so each raw XML file is directly reachable under the Pages URL.

## Website

Published at `https://cswh.github.io/bafu-dev/` (GitHub Pages, served from the `main` branch root).

- The landing page lists all processes with search, filtering (location, reference unit, category, subcategory), column sorting and pagination.
- Each process has a dedicated, shareable page at
  `https://cswh.github.io/bafu-dev/process/<uuid>/`
  showing its raw EcoSpold1 and raw ILCD XML side by side, plus direct links to both raw files.

## Regenerating the site

After adding or changing data under `data/`, run:

```bash
python3 site/generate.py
```

This rebuilds `assets/index.json`, all `process/<uuid>/index.html` pages and the landing page from the current data. Commit and push the result to publish it.
