"""Thai retail fertilizer prices from every source we have, merged for the site.

Sources (all baht per 50 kg bag):
  dit      data/dit_fert.json        DIT recommended retail price, 77 provinces x brands, a few times a year (official ceiling)
  coop     data/raw/coop_thabo.json  Tha Bo co-op (Nong Khai) shop list, about monthly, pulled automatically
  reports  data/fert_reports.json    provincial commerce office checks and news, logged by hand with links
  survey   data/fertilizer_shops.json  rice.ag's own shop-board survey
"""
import datetime as dt, json, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORMULAS = ['46-0-0', '16-20-0', '15-15-15', '0-0-60', '21-0-0', '18-46-0']   # the six DIT lists


def _load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except Exception:
        return default


def provinces():
    return [dict(th=t, en=e, slug=s, region=r) for t, e, s, r in _load(ROOT / 'data' / 'provinces.json', [])]


def dit_prices(ann, slug):
    """{formula: {brand: price}} for one province in one announcement."""
    d = (ann['prov'].get(slug) or [None])[0]
    if d is None:
        return {}
    return {f: {b: p + d for b, p in bs.items()} for f, bs in ann['base'].items()}


def dit_block(store, provs):
    anns = sorted(store.get('announcements', []), key=lambda a: a['date'])
    if not anns:
        return None
    cur, prev = anns[-1], (anns[-2] if len(anns) > 1 else None)
    deltas = [v[0] for v in cur['prov'].values() if v and v[0] is not None]
    nat = {}
    for f, bs in cur['base'].items():
        prices = sorted(p + d for p in bs.values() for d in deltas)
        cheapest = min(bs, key=bs.get)
        nat[f] = dict(low=prices[0], high=prices[-1], median=round(statistics.median(prices)),
                      cheapest_brand=cheapest, brands=len(bs),
                      prev_low=(min(p + v[0] for p in prev['base'].get(f, {}).values() for v in prev['prov'].values() if v[0] is not None)
                                if prev and prev['base'].get(f) else None))
    rows = []
    for p in provs:
        v = cur['prov'].get(p['slug'])
        if not v:
            continue
        pr = dit_prices(cur, p['slug'])
        rows.append(dict(p, delta=v[0], km=v[1], prices=pr,
                         cheap={f: min(bs.values()) for f, bs in pr.items() if bs}))
    rows.sort(key=lambda r: r['delta'])
    hist = [dict(no=a['no'], date=a['date'], url=a.get('url'),
                 low={f: min(bs.values()) + min(v[0] for v in a['prov'].values()) for f, bs in a['base'].items() if bs},
                 high={f: max(bs.values()) + max(v[0] for v in a['prov'].values()) for f, bs in a['base'].items() if bs})
            for a in anns]
    return dict(no=cur['no'], date=cur['date'], url=cur.get('url'), national=nat, provinces=rows, history=hist,
                brands=sorted({b for bs in cur['base'].values() for b in bs}))


def coop_block(store):
    lists = store.get('lists', {})
    if not lists:
        return None
    ds = sorted(lists)
    cur = lists[ds[-1]]
    prev = {(x['brand'], x['npk']): x['price'] for x in lists[ds[-2]]} if len(ds) > 1 else {}
    items = []
    for x in cur:
        if x['size_kg'] != 50:
            continue
        p = prev.get((x['brand'], x['npk']))
        items.append(dict(x, chg=(x['price'] - p) if p and x['price'] else None))
    return dict(date=ds[-1], name_en='Tha Bo Agricultural Cooperative', name_th='สหกรณ์การเกษตรท่าบ่อ จำกัด',
                province='nong-khai', area_en='Tha Bo, Nong Khai', area_th='อ.ท่าบ่อ จ.หนองคาย',
                url='https://www.coopthabo.com/thabo-2', items=items, dates=ds, status=store.get('status', {}))


def tracker(dit, coop_store, reports, survey_formulas, survey):
    """Per formula: dated points from every source, oldest first. Each point: date, low, high, src, label."""
    out = {f: [] for f in FORMULAS}
    if dit:
        for h in dit['history']:
            for f, lo in h['low'].items():
                if f in out:
                    out[f].append(dict(date=h['date'], low=lo, high=h['high'][f], src='dit', ref=f"No.{h['no']}"))
    for d, items in sorted(coop_store.get('lists', {}).items()):
        for f in out:
            ps = [x['price'] for x in items if x['npk'] == f and x['price'] and x['size_kg'] == 50]
            if ps:
                out[f].append(dict(date=d, low=min(ps), high=max(ps), src='coop', ref='Tha Bo'))
    for r in reports:
        for p in r['prices']:
            if p['npk'] in out:
                out[p['npk']].append(dict(date=r['date'], low=p['low'], high=p['high'], src='report', ref=r.get('province') or 'national',
                                          url=r.get('url')))
    m = (survey or {}).get('month')
    for f in survey_formulas:
        if f['npk'] in out and m:
            out[f['npk']].append(dict(date=f'{m}-15' if len(m) == 7 else m, low=f['median'], high=f['median'], src='survey', ref='rice.ag'))
    for f in out:
        out[f].sort(key=lambda x: x['date'])
    return out


def build(survey_formulas, survey):
    provs = provinces()
    dit = dit_block(_load(ROOT / 'data' / 'dit_fert.json', {}), provs)
    coop_store = _load(ROOT / 'data' / 'raw' / 'coop_thabo.json', {})
    coop = coop_block(coop_store)
    rep = _load(ROOT / 'data' / 'fert_reports.json', {})
    reports = sorted(rep.get('reports', []), key=lambda r: r['date'], reverse=True)
    watch = _load(ROOT / 'data' / 'raw' / 'dit_watch.json', {})
    track = tracker(dit, coop_store, reports, survey_formulas, survey)
    # newest dated price we hold for each formula, any source
    latest = {}
    for f, pts in track.items():
        if pts:
            latest[f] = pts[-1]
    fresh = []
    if coop:
        fresh.append(dict(src='coop', date=coop['date']))
    if (survey or {}).get('month'):
        fresh.append(dict(src='survey', date=survey['month']))
    if reports:
        fresh.append(dict(src='report', date=reports[0]['date']))
    if dit:
        fresh.append(dict(src='dit', date=dit['date']))
    return dict(dit=dit, coop=coop, reports=reports, brand_names=rep.get('brands', {}), tracker=track, latest=latest,
                fresh=sorted(fresh, key=lambda x: x['date'], reverse=True),
                dit_new=[n for n in watch.get('new', [])], dit_checked=watch.get('checked'))
