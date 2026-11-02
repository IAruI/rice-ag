#!/usr/bin/env python3
"""Weekly early-warning brief for rice.ag/brief/.

Run after fetch_prices.py:  python3 pipeline/brief.py            (pulls NOAA ONI, then builds)
                            python3 pipeline/brief.py --no-fetch (rebuild from stored data only)

Five signals that moved Thai rice prices in the past, each read the same way every week:
  1. El Nino (NOAA Oceanic Nino Index)          data/raw/oni.json, pulled here
  2. Thai white rice 5% export price (FOB)      prices.json series th_5
  3. Thai white paddy price (DIT, baht)         prices.json series dit_paddy
  4. Baht vs US dollar                          data/raw/fx.json
  5. India's rice export policy                 data/brief_notes.json, edited by hand (no clean data feed exists)

Writes src/static/data/brief.json, which build.py renders into /brief/ and /th/brief/.
The rules that turn each number into "up / steady / down" are constants below and are
printed on the page, so readers can see exactly how a signal was decided.
"""
import argparse, datetime as dt, json, sys, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'raw'
OUT = ROOT / 'src' / 'static' / 'data'
NOTES = ROOT / 'data' / 'brief_notes.json'
ONI_URL = 'https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt'
EPOCH = dt.date(1970, 1, 1)
SEASONS = ['DJF', 'JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ']  # centre month = index + 1

# Signal rules (shown on the page)
PRICE_MOVE = 3.0   # % change over 4 weeks that counts as a real move for rice prices
FX_MOVE = 2.0      # % change over 4 weeks for USD/THB
EL_NINO = 0.5      # ONI threshold, NOAA definition


# ---------------------------------------------------------------- ONI
def parse_oni(text):
    """NOAA oni.ascii.txt -> {'YYYY-MM': anomaly}, keyed by the season's centre month."""
    out = {}
    for line in text.splitlines():
        p = line.split()
        if len(p) != 4 or p[0] not in SEASONS:
            continue
        m = SEASONS.index(p[0]) + 1
        out[f'{int(p[1]):04d}-{m:02d}'] = round(float(p[3]), 2)
    if len(out) < 12:
        raise ValueError(f'ONI file parsed to only {len(out)} rows; layout may have changed')
    return out


def fetch_oni(store):
    import requests
    r = requests.get(ONI_URL, headers={'User-Agent': 'rice.ag brief (+https://rice.ag/brief/)'}, timeout=60)
    r.raise_for_status()
    pts = parse_oni(r.text)
    s = store['series'].setdefault('ONI', {})
    n = sum(1 for k, v in pts.items() if s.get(k) != v)
    s.update(pts)  # NOAA revises recent seasons; take its latest numbers
    return n


def oni_category(v):
    a = abs(v)
    if a < EL_NINO:
        return 'neutral'
    size = 'very_strong' if a >= 2.0 else 'strong' if a >= 1.5 else 'moderate' if a >= 1.0 else 'weak'
    return f"{'el_nino' if v > 0 else 'la_nina'}_{size}"


def season_label(month_key):
    y, m = map(int, month_key.split('-'))
    return SEASONS[m - 1], y


# ---------------------------------------------------------------- series helpers
def points_from_prices(series, field):
    """prices.json series -> sorted [(date, value)] for 'v' (USD) or 'thb'."""
    vals = series.get(field) or []
    return [(EPOCH + dt.timedelta(days=d), v) for d, v in zip(series['d'], vals) if v is not None]


def at_or_before(pts, day, max_gap):
    best = None
    for d, v in pts:
        if d > day:
            break
        best = (d, v)
    if best and (day - best[0]).days <= max_gap:
        return best
    return None


def changes(pts):
    """Latest value plus % change vs ~1 week, ~4 weeks and ~1 year earlier."""
    if not pts:
        return None
    last_d, last_v = pts[-1]
    out = {'date': last_d.isoformat(), 'value': last_v}
    for key, days, gap in (('chg_1w', 7, 6), ('chg_4w', 28, 10), ('chg_52w', 364, 20)):
        ref = at_or_before(pts, last_d - dt.timedelta(days=days), gap)
        out[key] = round((last_v / ref[1] - 1) * 100, 1) if ref and ref[1] else None
    return out


def move_signal(chg, threshold):
    if chg is None:
        return 'unknown'
    return 'up' if chg >= threshold else 'down' if chg <= -threshold else 'steady'


# ---------------------------------------------------------------- build
def build(prices, fx_store, oni_store, notes, now=None):
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0, tzinfo=None)
    bkk_day = (now + dt.timedelta(hours=7)).date()
    week_of = bkk_day - dt.timedelta(days=bkk_day.weekday())
    S = prices.get('series', {})
    ind = []

    # 1. El Nino
    oni = oni_store.get('series', {}).get('ONI', {})
    if oni:
        keys = sorted(oni)
        last, prev = keys[-1], keys[-2] if len(keys) > 1 else None
        v = oni[last]
        season, year = season_label(last)
        cat = oni_category(v)
        ind.append({'id': 'oni', 'value': v, 'season': season, 'year': year, 'category': cat,
                    'prev': oni[prev] if prev else None,
                    'signal': 'up' if v >= EL_NINO else 'steady',
                    'history': [[k, oni[k]] for k in keys[-24:]]})
    else:
        ind.append({'id': 'oni', 'signal': 'unknown'})

    # 2. Thai 5% FOB (USD and baht)
    if 'th_5' in S:
        usd = changes(points_from_prices(S['th_5'], 'v'))
        thb = changes(points_from_prices(S['th_5'], 'thb'))
        ind.append({'id': 'fob', **usd, 'thb': thb['value'] if thb else None,
                    'signal': move_signal(usd['chg_4w'], PRICE_MOVE),
                    'history': [[d.isoformat(), v] for d, v in points_from_prices(S['th_5'], 'v')[-26:]]})
    else:
        ind.append({'id': 'fob', 'signal': 'unknown'})

    # 3. Thai white paddy (baht per tonne)
    if 'dit_paddy' in S:
        pad = changes(points_from_prices(S['dit_paddy'], 'thb'))
        ind.append({'id': 'paddy', **pad, 'signal': move_signal(pad['chg_4w'], PRICE_MOVE),
                    'history': [[d.isoformat(), v] for d, v in points_from_prices(S['dit_paddy'], 'thb')[-90:]]})
        # paddy as a share of the export price, both in baht: how much of the export price reaches the farm gate
        fob_thb = points_from_prices(S.get('th_5', {'d': []}), 'thb')
        ref = at_or_before(fob_thb, dt.date.fromisoformat(pad['date']), 14)
        if ref:
            ind[-1]['share_of_fob'] = round(pad['value'] / ref[1] * 100, 1)
    else:
        ind.append({'id': 'paddy', 'signal': 'unknown'})

    # 4. Baht (USD/THB; up = weaker baht = higher baht prices for the same dollar price)
    thb = fx_store.get('series', {}).get('THB', {})
    if thb:
        pts = [(dt.date.fromisoformat(d), v) for d, v in sorted(thb.items())]
        fx = changes(pts)
        ind.append({'id': 'fx', **fx, 'signal': move_signal(fx['chg_4w'], FX_MOVE)})
    else:
        ind.append({'id': 'fx', 'signal': 'unknown'})

    # 5. India export policy (hand-edited)
    india = notes.get('india', {})
    status = india.get('status', 'unknown')
    ind.append({'id': 'india', 'status': status,
                'signal': {'open': 'steady', 'watch': 'up', 'restricted': 'up'}.get(status, 'unknown'),
                **{k: india.get(k) for k in ('note_en', 'note_th', 'updated', 'source_name', 'source_url')}})

    ups = sum(1 for i in ind if i['signal'] == 'up')
    downs = sum(1 for i in ind if i['signal'] == 'down')
    known = sum(1 for i in ind if i['signal'] != 'unknown')
    return {'generated': now.isoformat() + 'Z', 'week_of': week_of.isoformat(),
            'summary': {'up': ups, 'down': downs, 'known': known},
            'rules': {'price_move_pct': PRICE_MOVE, 'fx_move_pct': FX_MOVE, 'el_nino': EL_NINO},
            'note_en': notes.get('note_en'), 'note_th': notes.get('note_th'),
            'indicators': ind}


def load(p, default):
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-fetch', action='store_true')
    a = ap.parse_args()
    oni_store = load(RAW / 'oni.json', {'series': {}, 'status': {}})
    if not a.no_fetch:
        st = oni_store.setdefault('status', {})
        st['last_attempt'] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + 'Z'
        try:
            n = fetch_oni(oni_store)
            st['last_ok'], st['last_error'] = st['last_attempt'], None
            print(f'oni   ok, {n} new/changed points')
        except Exception as e:  # keep last good data; the page shows the season it is from
            st['last_error'] = f'{type(e).__name__}: {e}'[:300]
            print(f'oni   FAILED: {st["last_error"]}', file=sys.stderr)
            traceback.print_exc()
        oni_store['series']['ONI'] = dict(sorted(oni_store['series'].get('ONI', {}).items()))
        RAW.mkdir(parents=True, exist_ok=True)
        (RAW / 'oni.json').write_text(json.dumps(oni_store, indent=0, sort_keys=True), encoding='utf-8')
    brief = build(load(OUT / 'prices.json', {}), load(RAW / 'fx.json', {}), oni_store, load(NOTES, {}))
    brief['oni_status'] = oni_store.get('status', {})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'brief.json').write_text(json.dumps(brief, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f"brief: {brief['summary']['up']} up, {brief['summary']['down']} down, of {brief['summary']['known']} signals")


if __name__ == '__main__':
    main()
