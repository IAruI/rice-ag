#!/usr/bin/env python3
"""Offline tests for pipeline/fertilizer.py (no network)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
import fertilizer as F

# Pink Sheet layout: a header row naming commodities, a units row, then YYYYMmm rows
rows = [[None, 'Crude oil', 'Rice, Thai 5%', 'Phosphate rock', 'DAP', 'TSP', 'Urea ', 'Potassium chloride **'],
        [None, '($/bbl)', '($/mt)', '($/mt)', '($/mt)', '($/mt)', '($/mt)', '($/mt)'],
        ['2025M10', 60, 380, 150, 700, 600, 410, 350],
        ['2025M11', 61, 375, 151, 690, 0, 400, 349],
        ['2026M10', 62, 400, 160, 720, 610, 445, 355],
        ['notes', None, None, None, None, None, None, None]]
p = F.parse_pinksheet(rows)
assert set(p) == {'rock', 'dap', 'tsp', 'urea', 'kcl'}, p.keys()
assert p['urea'] == [('2025-10-01', 410.0), ('2025-11-01', 400.0), ('2026-10-01', 445.0)], p['urea']
assert len(p['tsp']) == 2, 'zero means missing'
try:
    F.parse_pinksheet([['x', 'Rice'], ['2025M10', 1]])
    raise AssertionError('should fail without urea')
except (StopIteration, ValueError):
    pass

items = [dict(shop='A', brand='Rabbit', brand_th='กระต่าย', npk=[46, 0, 0], size_kg=50, price=1000),
         dict(shop='B', brand='Stork', brand_th=None, npk=[46, 0, 0], size_kg=50, price=1100),
         dict(shop='B', brand='Stork', brand_th=None, npk=[46, 0, 0], size_kg=50, price=970),   # repeat on a promo sheet: dropped
         dict(shop='A', brand='Crown', brand_th=None, npk=[15, 15, 15], size_kg=50, price=1200),
         dict(shop='A', brand='Cow', brand_th=None, npk=[15, 15, 15], size_kg=50, price=1250),
         dict(shop='B', brand='Yaka', brand_th=None, npk=[15, 15, 15], size_kg=50, price=600),  # misread board: flagged
         dict(shop='B', brand='Thip', brand_th=None, npk=[15, 15, 15], size_kg=25, price=905),  # small bag: listed, not in median
         dict(shop='A', brand='Mix', brand_th=None, npk=[18, 46, 0], size_kg=50, price=1630),
         dict(shop='A', brand='Pot', brand_th=None, npk=[0, 0, 60], size_kg=50, price=930),
         dict(shop='A', brand='Lime', brand_th=None, size_kg=50, price=100)]
fs = {f['npk']: f for f in F.shop_formulas(items)}
assert fs['46-0-0']['count'] == 2 and fs['46-0-0']['median'] == 1050, fs['46-0-0']
t = fs['15-15-15']
assert t['count'] == 3 and t['median'] == 1225 and [i['flag'] for i in t['items'] if i['price'] == 600] == [True], t
assert any(i['size_kg'] == 25 and not i['flag'] for i in t['items'])
nc = F.nutrient_costs(list(fs.values()))
assert nc['N'][0]['npk'] == '46-0-0' and abs(nc['N'][0]['baht_per_kg'] - 1050 / 23) < 0.1
assert nc['K'][0]['baht_per_kg'] == round(930 / 30, 1)
p18 = nc['P'][0]
assert p18['npk'] == '18-46-0' and abs(p18['baht_per_kg'] - (1630 - 9 * 1050 / 23) / 23) < 0.1, p18

out = F.build({'items': items}, {'series': {'urea': {'2025-10-01': 410, '2026-10-01': 445}}},
              {'series': {'THB': {'2026-11-20': 34.0}, 'THB_monthly': {'2026-10-01': 33.6}}},
              {'series': {'dit_paddy': {'d': [20727], 'thb': [9700]}}})
assert out['world']['urea']['y1'] == round((445 / 410 - 1) * 100, 1) and out['world']['urea']['thb_bag'] == round(445 * 34 * 50 / 1000)
assert out['paddy']['kg_per_urea_bag'] == round(1050 / 9.7)
assert out['paddy']['world_hist'] and out['paddy']['world_hist'][0][0] == '2026-10-01', out['paddy']
print('fertilizer tests ok')

# fertpages: blend maths and rice defaults
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fertpages as P
px = {'46-0-0': 1100, '18-46-0': 1600, '0-0-60': 900}
b = P.blend((16, 20, 0), px, 100)
assert abs(b['dap'] - 43.5) < 0.1 and abs(b['urea'] - 17.8) < 0.1 and b['mop'] == 0 and abs(b['filler'] - 38.8) < 0.2, b
assert abs(b['cost'] - (17.78 * 22 + 43.48 * 32)) < 2, b
assert P.blend((46, 46, 46), px) is None, 'too concentrated'
assert P.blend((5, 40, 0), px) is None, 'less N than DAP brings'
assert P.blend((0, 0, 60), px)['mop'] == 100
r = P.rice_defaults({'formulas': [dict(npk='16-20-0', median=1000), dict(npk='15-15-15', median=1200), dict(npk='46-0-0', median=1100)]})
e = {(x['variety'], x['soil']): x for x in r['examples']}
assert e[('sensitive', 'clay')]['cost'] == round(25 * 1000 / 50 + 5 * 1100 / 50)
assert e[('nonsensitive', 'sand')]['basal_f'] == '15-15-15' and e[('nonsensitive', 'sand')]['cost'] == round(30 * 1200 / 50 + 10 * 1100 / 50)
print('fertpages tests ok')
