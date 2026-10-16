# bafu-dev

BAFU LCI process datasets and the source for the GitHub Pages site.

## Terms of Use

The files contained in this repository may only be used following the specific BAFU terms of use, which you can find in the root directories of the data folders. The document `BAFU-2025_Context and Content.pdf` can be downloaded with the BAFU:20XY data at [https://nexus.openlca.org/databases](https://nexus.openlca.org/databases). For more general info on the database itself, see [https://www.bafu.admin.ch/en/life-cycle-assessment](https://www.bafu.admin.ch/en/life-cycle-assessment).


## Repository layout

- `raw_data/<dataset>/ecoSpold files/nexus_version_<n>/` — process data sets in EcoSpold1 format (`process_<uuid>.xml`), one folder per dataset version (e.g. `bafu_2026_v1`, `bafu_2026_v2`, `bafu_2027_v1`); each raw format may have multiple nexus subversions
- `raw_data/<dataset>/openlca_ilcd_export/nexus_version_<n>/ILCD/` — the same data sets in ILCD format (`processes/<uuid>.xml`), plus flows, flow properties, unit groups, sources, contacts and LCIA methods; likewise per nexus subversion
- `site/` — static site generator and page templates
- `index.html`, `assets/` (generated, at the repo root) — version-independent landing page
- `pages/<dataset>/process/<uuid>/` (generated) — one page per process and dataset version

Do not edit generated output by hand; regenerate instead.

Every process exists in all raw formats with the same UUID. The GitHub Pages site serves the repository root, so each raw XML file is directly reachable under the Pages URL.

## Website

Published at `https://cswh.github.io/bafu-dev/` (GitHub Pages, served from the `main` branch root).

- The landing page at `https://cswh.github.io/bafu-dev/` is version-independent: it lists the processes of all existing BAFU versions with search, filtering (BAFU version, location, reference unit, category, subcategory), column sorting and pagination. A BAFU version column shows the dataset each process belongs to, and a version overview at the top filters the list per version.
- Each process has a dedicated, shareable page, namespaced by dataset version:
  `https://cswh.github.io/bafu-dev/pages/<dataset>/process/<uuid>/`
  e.g. `https://cswh.github.io/bafu-dev/pages/bafu_2026_v1/process/0004e814-c18d-42e2-a3f7-ce1fa51a3c2c/`
- A process page shows the raw XML of every available raw format of that dataset side by side (e.g. EcoSpold1 nexus v1, ILCD nexus v1 and ILCD nexus v2), plus direct links to the raw files.
- The exchanges table lists every exchange of the EcoSpold1 file as reference and one row per raw format (EcoSpold1, ILCD nexus v1, ILCD nexus v2, ...), with a Source column indicating the origin of each row. It supports full-text filtering, dropdown filters (source, direction, sphere) and column sorting; a raw button per row shows the raw `<exchange>` XML fetched from the corresponding raw file.

## Regenerating the site

After adding or changing data under `raw_data/`, run:

```bash
python3 site/generate.py
```

The generator automatically detects every `raw_data/bafu_<year>_v<number>/` folder and, within it, every `nexus_version_<n>` subfolder of the EcoSpold and ILCD raw formats. It builds the root landing page and all `pages/<dataset>/process/<uuid>/` pages; output for dataset versions that no longer exist is removed. Commit and push the result to publish it.
