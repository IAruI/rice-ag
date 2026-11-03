# rice.ag

Free rice grain scanner, rice prices and rice knowledge site. Live at https://rice.ag (Netlify project `rice-ag`).

## Editing content
Every push to `main` rebuilds and publishes the site automatically (about a minute).

| What | Where |
|---|---|
| Page text, English | `src/pages/en/*.html` |
| Page text, Thai | `src/pages/th/*.html` (keep EN and TH in step) |
| Page titles, descriptions (SEO), page list | `PAGES` in `build.py` |
| Buttons, labels, scanner/calculator text (EN + TH) | `src/i18n.json` |
| Header, footer, `<head>` | `src/templates/base.html` |
| Scanner and calculator layout | `src/pages/shared/` |
| Styles | `src/static/css/site.css` |
| Images | `src/static/img/` |
| Scanner engine (image analysis) | `src/static/js/engine.js` |
| Scanner UI | `src/static/js/app.js` |
| Prices page layout and text | `src/pages/shared/prices.html` |
| Prices charts and table | `src/static/js/prices.js` |
| Which price series are shown, and their sources | `pipeline/catalog.py` |

Page files are Jinja templates: use `{{ prefix }}/path/` for internal links so they work in both languages.

To add a page: create `src/pages/en/<name>.html` and `src/pages/th/<name>.html`, then add an entry to `PAGES` in `build.py`.

## Run locally
    pip install -r requirements.txt
    python3 build.py
    python3 -m http.server 8000 --directory dist

## Testing the scanner
`tests/gen.py` makes synthetic rice photos with known answers; `node tests/batch.js` reports accuracy (needs `sharp`). Keep iPhone Safari's canvas memory limit in mind: one canvas, 2000 px max on phones.

## Rice prices (/prices/)
A GitHub Action (`.github/workflows/prices.yml`) runs `pipeline/fetch_prices.py` every day at 17:37 Bangkok time. It pulls:

| Source | What | How often |
|---|---|---|
| Thai Rice Exporters Association | Thai FOB quotes (weekly page + monthly archive from 2018) | Wednesdays |
| FAO GIEWS FPMA (JSON API) | Viet Nam, US, Uruguay, Pakistan FOB; Thai history from 1989 | weekly / monthly |
| World Bank Pink Sheet (xlsx) | Thai 5%, 25%, A1; Viet Nam 5%, back to 1960 | monthly |
| Thai Department of Internal Trade | Paddy and Bangkok wholesale prices (THB) | daily |
| ECB via frankfurter.dev | USD/THB to convert DIT prices | daily |

Raw history lives in `data/raw/*.json` and is only ever added to. A source that fails keeps its old data, and the failure is shown on the page. The page reads `src/static/data/prices.json`; `prices.csv` is the download. The Action commits both, and the push makes Netlify rebuild.

- Run it by hand: GitHub > Actions > Update rice prices > Run workflow (tick *backfill* to re-pull all history).
- Locally: `pip install -r pipeline/requirements.txt && python3 pipeline/fetch_prices.py`
- Parser tests (offline, no network): `python3 tests/test_prices.py`
- Add or remove a line on the charts: edit `pipeline/catalog.py`.
- CBOT rough rice is an embedded TradingView chart, not stored data: CME's licence doesn't allow republishing its prices.
- TREA's weekly page shows grade names as an image, so rows are matched by position. If TREA adds or removes a row, the pull stops with an error instead of mislabelling prices; update `TREA_WEEKLY_ROWS` in `fetch_prices.py`.

## Price pages and SEO (Nov 2026)
`pricepages.py` turns `prices.json` into HTML at build time, so the numbers are in the page source that search engines read:
- **Homepage**: "How rice is doing" summary (generated from Thai 5%, Viet Nam 5%, Thai paddy, El Niño and India's status), the latest-prices table, and a title carrying the Thai and Vietnam 5% prices. `prices.js` still draws the interactive charts.
- **Hub pages** at `/prices/<slug>/` (EN + TH): one per origin (Thailand, Thai paddy, Vietnam, India, Pakistan, US) and per type (white 5%, jasmine, basmati, parboiled, broken, glutinous). Each has the latest price in its title, a static 5-year chart, the table, hand-written context and Dataset schema. Edit or add hubs in `HUBS` in `pricepages.py`.
- Tests (offline): `python3 tests/test_pricepages.py`

## Analytics
Cloudflare Web Analytics (cookieless, filters most bots). Create a site in Cloudflare > Analytics & Logs > Web Analytics, copy the token, and set it as `CF_ANALYTICS_TOKEN` in Netlify > Site configuration > Environment variables. Next deploy adds the beacon to every page; with no token, nothing is added.

## Weekly brief (/brief/)
`pipeline/brief.py` runs in the same daily Action, after the prices. It pulls NOAA's Oceanic Niño Index into `data/raw/oni.json`, reads the Thai 5% FOB, Thai white paddy and USD/THB series already stored, and writes `src/static/data/brief.json`. `build.py` renders that into `/brief/` and `/th/brief/` (template: `src/pages/shared/brief.html`).

- Signal rules (what counts as up / steady / down) are constants at the top of `pipeline/brief.py` and are printed on the page.
- **India's export policy is edited by hand** in `data/brief_notes.json`: set `status` to `open`, `watch` or `restricted`, update `updated` and the EN/TH notes, push. Pushing that file re-runs the Action and the site rebuilds. Optional top-level `note_en` / `note_th` show as an editor's note above the cards.
- Tests (offline): `python3 tests/test_brief.py`
