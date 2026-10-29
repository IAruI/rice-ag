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
