#!/usr/bin/env python3
"""Offline tests for the Thai fertilizer price sources: co-op parser, DIT watcher, DIT table solver, merge."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'pipeline'))
sys.path.insert(0, str(ROOT / 'tools'))

import coop_prices, dit_watch, fert_local


def test_coop_parse():
    date, items = coop_prices.parse((ROOT / 'tests/fixtures/coop_thabo.txt').read_text(encoding='utf-8'))
    assert date == '2026-11-16', date
    get = {(i['brand'], i['npk']): i for i in items}
    assert get[('rabbit', '46-0-0')]['price'] == 1020
    assert get[('rabbit', '16-20-0')]['price'] == 1130
    assert get[('cow-plough', '6-18-24')]['size_kg'] == 25
    assert get[('cow-plough', '0-0-50')]['out'] and get[('cow-plough', '0-0-50')]['price'] is None
    assert get[('yara', '16-16-16')]['price'] == 1480
    assert ('yara', '16-8-8') not in get                      # unlabelled photos after Yara are 'other'
    assert get[('top-one', '22-5-18')]['price'] == 1350
    assert get[('entec', '12-12-17')]['size_kg'] == 25
    assert not any(i['npk'] == '99-9-9' for i in items)      # script text ignored
    assert not any(i['npk'].startswith('21-0-') and i['npk'] != '21-0-0' for i in items)


def test_dit_watch_find():
    ent = lambda s: ''.join(f'&#x{ord(c):x};' if ord(c) > 127 else c for c in s)
    page = ('<div><a href="/x">' + ent('ประกาศสำนักงานคณะกรรมการกลางว่าด้วยราคาสินค้าและบริการ ฉบับที่ 9 พ.ศ. 2569 เรื่อง ราคาจำหน่ายปลีกแนะนำปุ๋ยเคมี')
            + '</a><span>337</span><a href="/media/dtyjro0q/20260627102448_6738.pdf">pdf</a></div>'
            + '<div>' + ent('ฉบับที่ 13 พ.ศ. 2560 เรื่อง ราคาจำหน่ายปลีกแนะนำก๊าซ') + '<a href="/media/a.pdf">x</a></div>')
    found = dit_watch.find(page)
    assert found == [(9, 2569, 'https://www.dit.go.th/media/dtyjro0q/20260627102448_6738.pdf')], found


def test_dit_solver_fixes_ocr():
    import dit_fert_ocr as T
    cols = T.parse_layout('A=dist|46-0-0:rabbit,cow-plough|0-0-60:rabbit')[1]
    base = [918, 898, 908]
    rows = []
    for i, th in enumerate(['กรุงเทพมหานคร', 'เชียงใหม่', 'ยะลา', 'ชัยนาท']):
        d = [0, 70, 139, 6][i]
        rows.append((th, [100 + i] + [b + d for b in base]))
    rows[1][1][1] = 4988          # leading 1 read as 4
    rows[2][1][3] = None          # unreadable cell
    rows[3][1][2] = 5             # a dash read as a digit
    out, prov, fixes = T.solve(rows, cols)
    assert out == {'46-0-0': {'rabbit': 918, 'cow-plough': 898}, '0-0-60': {'rabbit': 908}}, out
    assert prov['เชียงใหม่'] == (70, 101) and prov['ยะลา'][0] == 139
    assert fixes == 3, fixes


def test_merge():
    L = fert_local.build([dict(npk='46-0-0', median=1090, low=1050, high=1130)], dict(month='2026-11'))
    assert L['dit'] and len(L['dit']['provinces']) == 77
    nat = L['dit']['national']['46-0-0']
    assert nat['low'] < nat['median'] < nat['high']
    assert L['tracker']['46-0-0'][-1]['date'] >= L['tracker']['46-0-0'][0]['date']
    assert any(p['src'] == 'survey' and p['low'] == 1090 for p in L['tracker']['46-0-0'])
    slugs = {p['slug'] for p in fert_local.provinces()}
    for r in L['reports']:
        assert r['province'] is None or r['province'] in slugs, r['province']
        assert r['url'].startswith('https://')
        for p in r['prices']:
            assert 100 < p['low'] <= p['high'] < 3000, (r['date'], p)
            assert p.get('brand') is None or p['brand'] in json.loads((ROOT / 'data/fert_reports.json').read_text(encoding='utf-8'))['brands']


def test_dit_data_sane():
    d = json.loads((ROOT / 'data/dit_fert.json').read_text(encoding='utf-8'))
    for a in d['announcements']:
        assert len(a['prov']) == 77
        for f, bs in a['base'].items():
            for b, v in bs.items():
                assert 400 < v < 2500, (a['no'], f, b, v)
        ds = [v[0] for v in a['prov'].values()]
        assert min(ds) >= -50 and max(ds) <= 250, (min(ds), max(ds))


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn(); print('ok', name)
