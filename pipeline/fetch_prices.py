#!/usr/bin/env python3
"""Daily rice price pull for rice.ag/prices.

Run:  python3 pipeline/fetch_prices.py            (normal daily run)
      python3 pipeline/fetch_prices.py --backfill (re-pull full history)

Each source writes into data/raw/<source>.json, merging new points into what is
already stored, so a failed or partial run never deletes history. After the pulls,
assemble() builds src/static/data/prices.json (what the page reads) and
src/static/data/prices.csv (download). Every source's last success / last error is
recorded in the JSON so the page can show stale data honestly.
"""
import argparse, csv, datetime as dt, io, json, re, sys, time, traceback
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'raw'
OUT = ROOT / 'src' / 'static' / 'data'
UA = {'User-Agent': 'rice.ag price tracker (+https://rice.ag/prices/)'}
TODAY = dt.date.today()

sys.path.insert(0, str(Path(__file__).parent))
from catalog import SOURCES, SERIES, GROUPS  # noqa: E402


# ---------------------------------------------------------------- storage
def load_raw(src):
    p = RAW / f'{src}.json'
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))
    return {'series': {}, 'status': {}}


def save_raw(src, store):
    RAW.mkdir(parents=True, exist_ok=True)
    for k in store['series']:
        store['series'][k] = dict(sorted(store['series'][k].items()))
    (RAW / f'{src}.json').write_text(json.dumps(store, ensure_ascii=False, indent=0, sort_keys=True), encoding='utf-8')


def merge(store, sid, points):
    """points: iterable of (iso_date, value). Returns number of new or changed points."""
    s = store['series'].setdefault(sid, {})
    n = 0
    for d, v in points:
        if v is None:
            continue
        v = round(float(v), 4)
        if s.get(d) != v:
            s[d] = v
            n += 1
    return n


def get(url, **kw):
    """GET with retries on network errors and 5xx; a 4xx (e.g. a year page that doesn't exist) fails at once."""
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=60, **kw)
            r.raise_for_status()
            return r
        except requests.HTTPError as e:
            status = getattr(e.response, 'status_code', 0) or 0
            if status < 500 or attempt == 2:
                raise
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 2:
                raise
        time.sleep(5 * (attempt + 1))


def num(s):
    s = (s or '').strip().replace(',', '')
    try:
        return float(s)
    except ValueError:
        return None


def sane_usd(v, lo=80, hi=4000):
    if v is None or not (lo <= v <= hi):
        raise ValueError(f'value {v} outside sane USD/t range {lo}-{hi}; source layout may have changed')
    return v


# ---------------------------------------------------------------- TREA
TREA = 'http://www.thairiceexporters.or.th'
# Row order of the weekly table on price_eng.html. The grade names there are an image,
# so rows are mapped by position; if the row count changes we stop rather than guess.
TREA_WEEKLY_ROWS = ['hm_prem_old', 'hm_prem_new', 'hm_brk_a1s', 'jasmine', 'w100b', 'w5', 'w25',
                    'a1s', 'glu10', 'pb_prem', 'pb100']
MONTHS = {m: i + 1 for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])}


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def fetch_trea(store, backfill):
    added = 0
    # weekly quotes (last 5 Wednesdays)
    soup = BeautifulSoup(get(f'{TREA}/price_eng.html').content, 'html.parser')
    hdr = None
    for tr in soup.find_all('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all(['td', 'th'], recursive=False)]
        if cells and cells[0] == 'Item' and any(re.match(r'\d{1,2} [A-Z][a-z]{2} \d{4}$', c) for c in cells[1:]):
            hdr = tr
            break
    if hdr is None:
        raise ValueError('TREA weekly table header not found')
    dates = [dt.datetime.strptime(c.get_text(' ', strip=True), '%d %b %Y').date().isoformat()
             for c in hdr.find_all(['td', 'th'], recursive=False)[1:]]
    rows = []
    for tr in hdr.find_all_next('tr'):
        txt = tr.get_text(' ', strip=True)
        if txt.startswith('Item') or 'Exchange Rates' in txt:
            break
        vals = [c.get_text(' ', strip=True) for c in tr.find_all(['td', 'th'], recursive=False)]
        nums = [v for v in vals if re.fullmatch(r'[\d,]+(\.\d+)?|NQ|-', v)]
        if len(nums) == len(dates):
            rows.append([num(v) for v in nums])
    if len(rows) != len(TREA_WEEKLY_ROWS):
        raise ValueError(f'TREA weekly table has {len(rows)} price rows, expected {len(TREA_WEEKLY_ROWS)}')
    for key, vals in zip(TREA_WEEKLY_ROWS, rows):
        added += merge(store, f'w:{key}', [(d, sane_usd(v)) for d, v in zip(dates, vals) if v is not None])

    # monthly averages archive (labelled text tables from 2018 on)
    years = range(2018, TODAY.year + 1) if backfill else range(TODAY.year - 1, TODAY.year + 1)
    for y in years:
        try:
            r = get(f'{TREA}/database/AVG%20prices%20{y}.html')
        except requests.HTTPError:
            continue
        soup = BeautifulSoup(r.content, 'html.parser')
        for tr in soup.find_all('tr'):
            cells = [c.get_text(' ', strip=True) for c in tr.find_all(['td', 'th'], recursive=False)]
            if len(cells) < 13 or not cells[0] or cells[0] == 'Item' or cells[0].startswith(('Remark', 'Last updated')):
                continue
            label = re.sub(r'\s+', ' ', cells[0])
            pts = []
            for m in range(12):
                v = num(cells[1 + m])
                if v is not None:
                    pts.append((f'{y}-{m + 1:02d}-01', sane_usd(v)))
            added += merge(store, f'm:{slug(label)}', pts)
    # Hom Mali rows are split by crop year; keep the newest crop that has a price each month.
    for kind in ('premium-quality', '100'):
        best = {}
        for sid, pts in store['series'].items():
            m = re.match(rf'm:thai-hom-mali-rice-{kind}-crop-(\d{{4}})-\d\d$', sid)
            if m:
                for d, v in pts.items():
                    if d not in best or int(m.group(1)) > best[d][0]:
                        best[d] = (int(m.group(1)), v)
        added += merge(store, f'm:hom-mali-{kind}-latest-crop', [(d, v) for d, (_, v) in best.items()])
    return added


# ---------------------------------------------------------------- FAO FPMA
FPMA = 'https://fpma.fao.org/giews/v4/global/price_module/api/v1'


def fetch_fao(store, backfill):
    added = 0
    for uuid in SOURCES['fao']['series']:
        j = get(f'{FPMA}/FpmaSeriePrice/{uuid}/').json()
        by = {'weekly': [], 'monthly': []}
        for p in j.get('datapoints', []):
            v = p.get('price_value_dollar') or p.get('price_value')
            if v is not None and p.get('periodicity') in by:
                by[p['periodicity']].append((p['date'][:10], sane_usd(float(v))))
        for per, pts in by.items():
            if pts:
                added += merge(store, f'{per[0]}:{uuid}', pts)
    return added


# ---------------------------------------------------------------- World Bank Pink Sheet
WB_PAGE = 'https://www.worldbank.org/en/research/commodity-markets'
WB_FALLBACK = ('https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/'
               'related/CMO-Historical-Data-Monthly.xlsx')


def fetch_wb(store, backfill):
    import openpyxl
    url = WB_FALLBACK
    try:
        m = re.search(r'href="([^"]+CMO-Historical-Data-Monthly\.xlsx)"', get(WB_PAGE).text)
        if m:
            url = m.group(1)
    except requests.RequestException:
        pass
    wb = openpyxl.load_workbook(io.BytesIO(get(url).content), read_only=True, data_only=True)
    rows = list(wb['Monthly Prices'].iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(rows) if r and any(isinstance(c, str) and c.startswith('Rice, Thai 5') for c in r))
    cols = {i: c.strip() for i, c in enumerate(rows[hi]) if isinstance(c, str) and c.startswith('Rice')}
    if not cols:
        raise ValueError('no rice columns in Pink Sheet')
    added = 0
    for i, name in cols.items():
        pts = []
        for r in rows[hi + 2:]:
            if not r or not isinstance(r[0], str) or not re.fullmatch(r'\d{4}M\d\d', r[0]):
                continue
            if isinstance(r[i], (int, float)) and r[i] > 0:  # the Pink Sheet uses 0 for some missing months
                pts.append((f'{r[0][:4]}-{r[0][5:]}-01', sane_usd(float(r[i]), lo=30)))
        added += merge(store, slug(name), pts)
    return added


# ---------------------------------------------------------------- Thai DIT (domestic, THB)
DIT = 'https://pricelist.dit.go.th/main_price.php?seltime=day'
TH_MONTHS = {m: i + 1 for i, m in enumerate(['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'])}


def th_date(s):
    d, m, y = s.split()
    return dt.date(int(y) - 543, TH_MONTHS[m], int(d)).isoformat()


def be(d):
    return f'{d.day:02d}/{d.month:02d}/{d.year + 543}'


def fetch_dit(store, backfill):
    added = 0
    for code, meta in SOURCES['dit']['series'].items():
        have = store['series'].get(code)
        start = dt.date(2015, 1, 1) if backfill or not have else dt.date.fromisoformat(max(have)) - dt.timedelta(days=21)
        r = requests.post(DIT, headers=UA, timeout=90, data={
            'day1': be(start), 'day2': be(TODAY), 'protype': '2', 'progroup': meta['group'],
            'proname': code, 'seltime': 'day'})
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')
        h2 = next((h.get_text(' ', strip=True) for h in soup.find_all('h2') if 'สินค้า' in h.get_text()), '')
        if 'บาท/ตัน' in h2:
            factor = 1
        elif 'บาท/100 กก' in h2:
            factor = 10
        else:
            raise ValueError(f'DIT {code}: unknown unit in "{h2[-40:]}"')
        pts = []
        for tr in soup.find_all('tr'):
            tds = [td.get_text(' ', strip=True) for td in tr.find_all('td')]
            if len(tds) == 3 and re.match(r'\d{1,2} \S+ \d{4}$', tds[0]):
                v = num(tds[2])
                if v:
                    thb_t = v * factor
                    if not 2000 <= thb_t <= 150000:
                        raise ValueError(f'DIT {code}: {thb_t} THB/t looks wrong')
                    pts.append((th_date(tds[0]), thb_t))
        added += merge(store, code, pts)
    return added


# ---------------------------------------------------------------- FX (ECB via frankfurter)
FX_FROM = 1999  # first year of ECB THB reference rates; needed to show older Thai export prices in baht


def fetch_fx(store, backfill):
    have = store['series'].get('THB', {})
    years_have = {d[:4] for d in have}
    recent = {TODAY.year, TODAY.year - 1 if TODAY.month == 1 else TODAY.year}
    years = [y for y in range(FX_FROM, TODAY.year + 1) if backfill or str(y) not in years_have or y in recent]
    added = 0
    for y in years:
        j = get(f'https://api.frankfurter.dev/v1/{y}-01-01..{min(dt.date(y, 12, 31), TODAY)}',
                params={'base': 'USD', 'symbols': 'THB'}).json()
        added += merge(store, 'THB', [(d, r['THB']) for d, r in j.get('rates', {}).items()])
    return added


FETCHERS = {'trea': fetch_trea, 'fao': fetch_fao, 'wb': fetch_wb, 'dit': fetch_dit, 'fx': fetch_fx}


# ---------------------------------------------------------------- assemble
def to_usd(points, fx):
    """THB/t -> USD/t using the most recent FX rate on or before each date."""
    dates = sorted(fx)
    out, j = {}, 0
    for d in sorted(points):
        while j + 1 < len(dates) and dates[j + 1] <= d:
            j += 1
        if dates and dates[j] <= d:
            out[d] = points[d] / fx[dates[j]]
    return out


def fx_lookup(fx):
    dates = sorted(fx)
    import bisect

    def at(d):  # rate on d, or the latest before it within 10 days
        i = bisect.bisect_right(dates, d) - 1
        if i >= 0 and (dt.date.fromisoformat(d) - dt.date.fromisoformat(dates[i])).days <= 10:
            return fx[dates[i]]
        return None
    return at


def assemble(stores):
    fx = stores['fx']['series'].get('THB', {})
    fx_at = fx_lookup(fx)
    baht_series = {sid for g in GROUPS if g.get('unit') == 'THB' for sid in g['series'] + g.get('table_extra', [])}
    epoch = dt.date(1970, 1, 1)
    series_out, csv_rows = {}, []
    for sid, meta in SERIES.items():
        merged, used, srclast = {}, [], {}
        for src, raw_id in meta['from']:  # priority order; lower priority only fills earlier history
            pts = dict(stores[src]['series'].get(raw_id, {}))
            if not pts:
                continue
            if meta.get('currency') == 'THB':
                pts = to_usd(pts, fx)
            cut = min(merged) if merged else None
            add = {d: v for d, v in pts.items() if cut is None or d < cut}
            if add:
                merged.update(add)
                used.append(src)
                srclast[src] = max(srclast.get(src, ''), max(add))
        if not merged:
            continue
        ds = sorted(merged)
        rec = {k: meta[k] for k in ('en', 'th', 'origin', 'basis', 'market', 'note_en', 'note_th') if k in meta}
        rec['src'] = sorted(set(used), key=used.index)
        rec['srclast'] = {k: (dt.date.fromisoformat(v) - epoch).days for k, v in srclast.items()}
        rec['d'] = [(dt.date.fromisoformat(d) - epoch).days for d in ds]
        rec['v'] = [round(merged[d], 1) for d in ds]
        if meta.get('currency') == 'THB':
            raw = stores[meta['from'][0][0]]['series'][meta['from'][0][1]]
            rec['thb'] = [round(raw.get(d)) if raw.get(d) is not None else None for d in ds]
        elif sid in baht_series:  # USD export quote shown in baht at that day's ECB rate
            rec['thb'] = [round(merged[d] * r) if (r := fx_at(d)) else None for d in ds]
        series_out[sid] = rec
        csv_rows += [(d, sid, meta['en'], round(merged[d], 1)) for d in ds]

    sources_out = {}
    for k, s in SOURCES.items():
        st = stores[k].get('status', {})
        sources_out[k] = {f: s[f] for f in ('name', 'url', 'terms', 'freq', 'sched_en', 'sched_th') if f in s}
        sources_out[k].update({f: st.get(f) for f in ('last_ok', 'last_attempt', 'last_error')})
    OUT.mkdir(parents=True, exist_ok=True)
    data = {'generated': dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
            'groups': GROUPS, 'series': series_out, 'sources': sources_out,
            'fx': {'date': max(fx), 'usd_thb': fx[max(fx)]} if fx else None}
    (OUT / 'prices.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    with open(OUT / 'prices.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['date', 'series_id', 'series', 'usd_per_tonne'])
        w.writerows(sorted(csv_rows))
    return len(series_out), len(csv_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backfill', action='store_true')
    ap.add_argument('--only', help='comma-separated source ids to pull (others are only re-assembled)')
    ap.add_argument('--no-fetch', action='store_true', help='rebuild prices.json from stored data only')
    a = ap.parse_args()
    only = set(a.only.split(',')) if a.only else set(FETCHERS)
    stores, ok = {}, 0
    for src, fn in FETCHERS.items():
        store = load_raw(src)
        stores[src] = store
        if a.no_fetch or src not in only:
            continue
        st = store.setdefault('status', {})
        st['last_attempt'] = dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        try:
            n = fn(store, a.backfill or not store['series'])
            st['last_ok'] = st['last_attempt']
            st['last_error'] = None
            ok += 1
            print(f'{src:5s} ok, {n} new/changed points')
        except Exception as e:  # one broken source must not stop the others
            st['last_error'] = f'{type(e).__name__}: {e}'[:300]
            print(f'{src:5s} FAILED: {st["last_error"]}', file=sys.stderr)
            traceback.print_exc()
        save_raw(src, store)
    ns, npts = assemble(stores)
    print(f'assembled {ns} series, {npts} points')
    if not a.no_fetch and ok == 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
