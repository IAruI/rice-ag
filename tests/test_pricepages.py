"""Offline checks for pricepages.py: every hub points at real series, and change() matches prices.js."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pricepages as pp
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
from catalog import SERIES

for h in pp.HUBS:
    for sid in h['series'] + h['chart'] + [h['primary']]:
        assert sid in SERIES, f"hub {h['slug']} uses unknown series {sid}"
    for k in ('title', 'desc', 'h1', 'name', 'body', 'drivers'):
        assert set(h[k]) == {'en', 'th'}, f"hub {h['slug']} {k} needs en and th"
assert len({h['slug'] for h in pp.HUBS}) == len(pp.HUBS), 'duplicate hub slug'

# weekly series: 1-month change uses the point ~30 days back
s = {'d': [0, 7, 14, 21, 28, 35], 'v': [100, 101, 102, 103, 104, 110], 'market': {'en': 'Export, FOB'}}
assert pp.freq_of(s) == 'weekly'
assert abs(pp.change(s, 30) - 10.0) < 1e-9, pp.change(s, 30)
assert pp.change(s, 365) is None
assert pp.pct(0.01) == '0.0%' and pp.pct(2.345) == '+2.3%' and pp.pct(None) == '–'
print('pricepages tests ok;', len(pp.HUBS), 'hubs')
