#!/usr/bin/env python3
"""Fertilizer prices for rice.ag/fertilizer/.

Run after fetch_prices.py:  python3 pipeline/fertilizer.py             (pulls World Bank, then builds)
                            python3 pipeline/fertilizer.py --no-fetch  (rebuild from stored data only)

Inputs
  data/fertilizer_shops.json   Thai shop-board survey, edited by hand (no clean public feed exists)
  data/raw/fert_wb.json        World Bank Pink Sheet fertilizer history (urea, DAP, TSP, potash, phosphate rock), USD/t, monthly
  data/raw/fx.json             USD/THB (pulled by fetch_prices.py)
  src/static/data/prices.json  Thai paddy price (for "kg of paddy to buy a bag")

Writes src/static/data/fertilizer.json, which build.py renders into /fertilizer/ and /th/fertilizer/.
A failure here never touches the rice prices.
"""
import argparse, datetime as dt, io, json, re, statistics, sys, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'raw'
SHOPS = ROOT / 'data' / 'fertilizer_shops.json'
OUT = ROOT / 'src' / 'static' / 'data' / 'fertilizer.json'

# Pink Sheet column header (start of text) -> our id
WB_COLS = {'Urea': 'urea', 'DAP': 'dap', 'TSP': 'tsp', 'Potassium chloride': 'kcl', 'Phosphate rock': 'rock'}
WORLD = {'urea': ('Urea (46-0-0)', 'ยูเรีย (46-0-0)', 46, 0, 0),
         'dap': ('DAP (18-46-0)', 'ไดแอมโมเนียมฟอสเฟต DAP (18-46-0)', 18, 46, 0),
         'kcl': ('Potash, potassium chloride (0-0-60)', 'โพแทสเซียมคลอไรด์ (0-0-60)', 0, 0, 60),
         'tsp': ('Triple superphosphate (0-46-0)', 'ทริปเปิลซูเปอร์ฟอสเฟต (0-46-0)', 0, 46, 0),
         'rock': ('Phosphate rock', 'หินฟอสเฟต', None, None, None)}
OUTLIER = 0.35        # a board price this far from the same formula's median is shown but left out of the median
BAG = 50              # kg, the standard Thai bag


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except Exception:
        return default


# ---------------------------------------------------------------- World Bank

def parse_pinksheet(rows):
    """rows: the 'Monthly Prices' sheet as lists. Returns {id: [(YYYY-MM-01, usd), ...]}."""
    hi = next(i for i, r in enumerate(rows) if r and any(isinstance(c, str) and c.strip().startswith('Urea') for c in r))
    cols = {}
    for i, c in enumerate(rows[hi]):
        if not isinstance(c, str):
            continue
        for head, key in WB_COLS.items():
            if c.strip().startswith(head) and key not in cols.values():
                cols[i] = key
    if 'urea' not in cols.values():
        raise ValueError('no urea column in Pink Sheet')
    out = {k: [] for k in cols.values()}
    for r in rows[hi + 1:]:
        if not r or not isinstance(r[0], str) or not re.fullmatch(r'\d{4}M\d\d', r[0]):
            continue
        for i, key in cols.items():
            v = r[i] if i < len(r) else None
            if isinstance(v, (int, float)) and 20 < v < 5000:
                out[key].append((f'{r[0][:4]}-{r[0][5:]}-01', round(float(v), 2)))
    return out


def fetch_world(store):
    sys.path.insert(0, str(ROOT / 'pipeline'))
    import openpyxl
    from fetch_prices import get, WB_PAGE, WB_FALLBACK
    url = WB_FALLBACK
    try:
        m = re.search(r'href="([^"]+CMO-Historical-Data-Monthly\.xlsx)"', get(WB_PAGE).text)
        if m:
            url = m.group(1)
    except Exception:
        pass
    wb = openpyxl.load_workbook(io.BytesIO(get(url).content), read_only=True, data_only=True)
    parsed = parse_pinksheet(list(wb['Monthly Prices'].iter_rows(values_only=True)))
    n = 0
    for key, pts in parsed.items():
        s = store['series'].setdefault(key, {})
        for d, v in pts:
            if s.get(d) != v:
                s[d] = v; n += 1
    return n


# ---------------------------------------------------------------- shop survey

def npk_key(npk):
    return '-'.join(str(x) for x in npk)


def shop_formulas(items):
    """One entry per formula: median price per 50 kg bag across brands and shops, with outliers flagged."""
    seen, rows = set(), []
    for it in items:
        if not it.get('npk') or not it.get('price') or not it.get('size_kg'):
            continue
        # the printed and promo sheets repeat board prices for the same brand; keep the board price
        k = (it['shop'], it['brand'], npk_key(it['npk']), it['size_kg'])
        if k in seen:
            continue
        seen.add(k)
        rows.append(dict(it, per50=it['price'] if it['size_kg'] == BAG else None))
    by = {}
    for r in rows:
        by.setdefault(npk_key(r['npk']), []).append(r)
    out = []
    for key, rs in by.items():
        full = [r for r in rs if r['per50']]  # small bags cost more per kg, so only 50 kg bags set the formula price
        if not full:
            continue
        med0 = statistics.median(r['per50'] for r in full)
        for r in rs:
            r['flag'] = bool(r['per50']) and len(full) >= 3 and abs(r['per50'] / med0 - 1) > OUTLIER
        good = [r['per50'] for r in full if not r['flag']] or [r['per50'] for r in full]
        n, p, k = rs[0]['npk']
        med = statistics.median(good)
        out.append(dict(npk=key, n=n, p=p, k=k, nutrients=n + p + k, count=len(full), shops=len({r['shop'] for r in full}),
                        median=round(med), low=min(good), high=max(good),
                        per_kg=round(med / BAG, 2),
                        per_nutrient=round(med / (BAG * (n + p + k) / 100), 1) if n + p + k else None,
                        items=sorted(({'brand': r['brand'], 'brand_th': r['brand_th'], 'price': r['price'], 'size_kg': r['size_kg'],
                                       'per50': r['per50'], 'shop': r['shop'], 'flag': r['flag']} for r in rs),
                                     key=lambda x: (x['size_kg'] != BAG, x['per50'] or x['price']))))
    # straight fertilizers and the common rice formulas first, then by how many brands carry it
    lead = ['46-0-0', '16-20-0', '15-15-15', '0-0-60', '21-0-0', '18-46-0', '16-8-8', '13-13-21', '16-16-16']
    out.sort(key=lambda f: (lead.index(f['npk']) if f['npk'] in lead else 99, -f['count'], f['npk']))
    return out


def nutrient_costs(formulas):
    """Baht per kg of nutrient (N, P2O5, K2O).
    Straight fertilizers: the whole price buys one nutrient.
    Phosphate (N-P-0 formulas): credit the nitrogen at the cheapest urea price, the rest of the price buys the P."""
    res = {'N': [], 'P': [], 'K': []}
    for f in formulas:
        parts = [(x, v) for x, v in (('N', f['n']), ('P', f['p']), ('K', f['k'])) if v]
        if len(parts) == 1:
            x, v = parts[0]
            res[x].append(dict(npk=f['npk'], baht_per_kg=round(f['median'] / (BAG * v / 100), 1), median=f['median'], method='straight'))
    urea = next((r for r in res['N'] if r['npk'] == '46-0-0'), None)
    if urea:
        for f in formulas:
            if f['n'] and f['p'] and not f['k']:
                left = f['median'] - BAG * f['n'] / 100 * urea['baht_per_kg']
                if left > 0:
                    res['P'].append(dict(npk=f['npk'], baht_per_kg=round(left / (BAG * f['p'] / 100), 1), median=f['median'],
                                         method='n_credit'))
    return {k: sorted(v, key=lambda r: r['baht_per_kg']) for k, v in res.items()}


# ---------------------------------------------------------------- assemble

def last(series):
    if not series:
        return None, None
    d = max(series)
    return d, series[d]


def build(shops, wb_store, fx_store, prices):
    fx_d, fx = last(fx_store.get('series', {}).get('THB', {}))
    formulas = shop_formulas(shops.get('items', []))
    world = {}
    for key, s in wb_store.get('series', {}).items():
        if key not in WORLD or not s:
            continue
        pts = sorted(s.items())
        d, v = pts[-1]
        yr = dict(pts).get(f'{int(d[:4]) - 1}{d[4:]}')
        en, th, n, p, k = WORLD[key]
        world[key] = dict(en=en, th=th, date=d, usd=v, y1=round((v / yr - 1) * 100, 1) if yr else None,
                          thb_bag=round(v * fx * BAG / 1000) if fx else None,
                          hist=[[a, b] for a, b in pts])
    # kg of paddy a farmer sells to buy one 50 kg bag of urea
    paddy = (prices.get('series') or {}).get('dit_paddy') or {}
    paddy_kg = (paddy.get('thb') or [None])[-1]
    paddy_kg = paddy_kg / 1000 if paddy_kg else None
    urea_shop = next((f for f in formulas if f['npk'] == '46-0-0'), None)
    per_bag = round(urea_shop['median'] / paddy_kg) if urea_shop and paddy_kg else None
    # history from world urea (no freight, duty or margin) against monthly average paddy, so the trend is like-for-like
    hist = []
    if 'urea' in world and paddy.get('d'):
        epoch = dt.date(1970, 1, 1)
        month_paddy = {}
        for t, v in zip(paddy['d'], paddy.get('thb') or []):
            if v:
                m = (epoch + dt.timedelta(days=int(t))).strftime('%Y-%m-01')
                month_paddy.setdefault(m, []).append(v / 1000)
        fxm = fx_store.get('series', {}).get('THB_monthly', {})
        for d, usd in world['urea']['hist']:
            if d in month_paddy and fxm.get(d):
                hist.append([d, round(usd * fxm[d] * BAG / 1000 / statistics.mean(month_paddy[d]), 1)])
    return dict(generated=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                survey=shops.get('survey', {}), market=shops.get('market', []), formulas=formulas, nutrients=nutrient_costs(formulas),
                world=world, fx=dict(date=fx_d, thb=fx), paddy=dict(baht_per_kg=round(paddy_kg, 2) if paddy_kg else None,
                                                                    kg_per_urea_bag=per_bag, world_hist=hist),
                status=wb_store.get('status', {}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-fetch', action='store_true')
    a = ap.parse_args()
    store = load(RAW / 'fert_wb.json', {'series': {}, 'status': {}})
    store.setdefault('series', {}); st = store.setdefault('status', {})
    if not a.no_fetch:
        st['last_attempt'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        try:
            n = fetch_world(store)
            st['last_ok'] = st['last_attempt']; st['last_error'] = None
            print(f'fertilizer: World Bank ok, {n} new/changed points')
        except Exception as e:  # keep the old data and say so on the page
            st['last_error'] = f'{type(e).__name__}: {e}'[:300]
            print(f'fertilizer: World Bank FAILED: {st["last_error"]}', file=sys.stderr)
            traceback.print_exc()
        (RAW / 'fert_wb.json').write_text(json.dumps(store, separators=(',', ':')), encoding='utf-8')
    out = build(load(SHOPS, {}), store, load(RAW / 'fx.json', {}), load(OUT.parent / 'prices.json', {}))
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f"fertilizer: {len(out['formulas'])} formulas, world series: {', '.join(out['world']) or 'none yet'}")


if __name__ == '__main__':
    main()
