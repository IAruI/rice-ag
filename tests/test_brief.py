#!/usr/bin/env python3
"""Offline test of pipeline/brief.py. Run: python3 tests/test_brief.py"""
import datetime as dt, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pipeline'))
import brief as b  # noqa: E402

ONI_TXT = """SEAS  YR   TOTAL   ANOM
 DJF 2026  26.15  -0.39
 JFM 2026  26.57  -0.21
 FMA 2026  27.34   0.11
 MAM 2026  28.09   0.46
 AMJ 2026  28.74   0.95
 MJJ 2026  29.02   1.39
 JJA 2026  29.09   1.80
 JAS 2026  29.12   2.16
 NDJ 2025  25.96  -0.60
 OND 2025  26.04  -0.61
 SON 2025  26.14  -0.57
 ASO 2025  26.33  -0.43
"""

def test_parse_oni():
    o = b.parse_oni(ONI_TXT)
    assert o['2026-08'] == 2.16 and o['2026-01'] == -0.39 and o['2025-12'] == -0.60, o
    assert b.season_label('2026-08') == ('JAS', 2026)
    assert b.oni_category(2.16) == 'el_nino_very_strong' and b.oni_category(-0.6) == 'la_nina_weak'
    assert b.oni_category(0.49) == 'neutral'

def test_build():
    E = dt.date(1970, 1, 1)
    days = [(dt.date(2026, 10, 1) + dt.timedelta(days=7 * i) - E).days for i in range(5)] 
    prices = {'series': {
        'th_5': {'d': days, 'v': [450, 455, 460, 470, 480], 'thb': [15000, 15200, 15400, 15800, 16000]},
        'dit_paddy': {'d': days, 'v': [0] * 5, 'thb': [9000, 9000, 9000, 9000, 9000]}}}
    fx = {'series': {'THB': {'2026-10-01': 33.0, '2026-10-29': 33.1}}}
    oni = {'series': {'ONI': b.parse_oni(ONI_TXT)}}
    notes = {'india': {'status': 'watch', 'note_en': 'x'}}
    r = b.build(prices, fx, oni, notes, now=dt.datetime(2026, 11, 2, 3, 0))
    I = {i['id']: i for i in r['indicators']}
    assert r['week_of'] == '2026-11-02'
    assert I['oni']['signal'] == 'up' and I['oni']['value'] == 2.16
    assert I['fob']['chg_4w'] == round((480 / 450 - 1) * 100, 1) and I['fob']['signal'] == 'up'
    assert I['paddy']['signal'] == 'steady' and I['paddy']['share_of_fob'] == 56.2
    assert I['fx']['signal'] == 'steady'
    assert I['india']['signal'] == 'up'
    assert r['summary'] == {'up': 3, 'down': 0, 'known': 5}, r['summary']

if __name__ == '__main__':
    test_parse_oni(); test_build(); print('brief tests ok')
