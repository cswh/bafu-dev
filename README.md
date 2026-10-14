# bafu-dev

BAFU LCI process datasets and the source for the GitHub Pages site.

## Repository layout

- `data/<dataset>/ecoSpold files/nexus_version_1/` — process data sets in EcoSpold1 format (`process_<uuid>.xml`), one folder per dataset version (e.g. `bafu_2026_v1`, `bafu_2026_v2`, `bafu_2027_v1`)
- `data/<dataset>/openlca_ilcd_export/nexus_version_1/ILCD/` — the same data sets in ILCD format (`processes/<uuid>.xml`), plus flows, flow properties, unit groups, sources, contacts and LCIA methods
- `site/` — static site generator and page templates
- `<dataset>/` (generated, at the repo root) — GitHub Pages output per dataset version: `index.html`, `assets/`, `process/`
- `index.html` (generated, at the repo root) — redirects to the latest dataset version

Do not edit generated output by hand; regenerate instead.

Every process exists in both formats with the same UUID. The GitHub Pages site serves the repository root, so each raw XML file is directly reachable under the Pages URL.

## Website

Published at `https://cswh.github.io/bafu-dev/` (GitHub Pages, served from the `main` branch root).

- `https://cswh.github.io/bafu-dev/` redirects to the latest dataset version.
- Each dataset version has its own landing page, e.g.
  `https://cswh.github.io/bafu-dev/bafu_2026_v1/`,
  with an overview of (and navigation between) all existing BAFU versions.
- The landing page lists all processes of all dataset versions with search, filtering (BAFU version, location, reference unit, category, subcategory), column sorting and pagination. A BAFU version column shows the dataset each process belongs to.
- Each process has a dedicated, shareable page, namespaced by dataset version:
  `https://cswh.github.io/bafu-dev/<dataset>/process/<uuid>/`
  e.g. `https://cswh.github.io/bafu-dev/bafu_2026_v1/process/0004e814-c18d-42e2-a3f7-ce1fa51a3c2c/`
  It shows the raw EcoSpold1 and raw ILCD XML of that process side by side, plus direct links to both raw files.

## Regenerating the site

After adding or changing data under `data/`, run:

```bash
python3 site/generate.py
```

The generator automatically detects every `data/bafu_<year>_v<number>/` folder, builds each version's landing page and all `process/<uuid>/` pages, and rewrites the root redirect to the newest version. Output for dataset versions that no longer exist is removed. Commit and push the result to publish it.
