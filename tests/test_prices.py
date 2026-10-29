#!/usr/bin/env python3
"""Offline test of pipeline/fetch_prices.py against copies of each source's real page layout
(captured Oct 2026). Run: python3 tests/test_prices.py"""
import datetime as dt, io, json, shutil, sys, tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'pipeline'))
import fetch_prices as fp  # noqa: E402

# --- TREA weekly page: grade names are an image in a rowspan cell; tables nested in a layout table
TREA_WEEKLY = """<html><body><form><table><tr><td><table><tr><td>Item</td><td>30 Sep 2026</td><td>7 Oct 2026</td>
<td>14 Oct 2026</td><td>21 Oct 2026</td><td>28 Oct 2026</td></tr>
<tr><td rowspan="9"><img src="price_eng-1.jpg.jpg"></td><td>1239</td><td>1236</td><td>1238</td><td>1236</td><td>1230</td></tr>
<tr><td>1178</td><td>1175</td><td>1177</td><td>1190</td><td>1184</td></tr>
<tr><td>469</td><td>468</td><td>478</td><td>477</td><td>475</td></tr>
<tr><td>687</td><td>686</td><td>703</td><td>717</td><td>759</td></tr>
<tr><td>480</td><td>485</td><td>495</td><td>500</td><td>498</td></tr>
<tr><td><font>474</font></td><td>479</td><td>489</td><td>494</td><td>492</td></tr>
<tr><td>455</td><td>460</td><td>472</td><td>478</td><td>478</td></tr>
<tr><td>389</td><td>397</td><td>416</td><td>424</td><td>431</td></tr>
<tr><td>829</td><td>841</td><td>843</td><td>841</td><td>883</td></tr></table></td></tr>
<tr><td></td></tr><tr><td><table><tr><td rowspan="2"><img src="x.jpg"></td><td>489</td><td>500</td><td>510</td><td>515</td><td>512</td></tr>
<tr><td>483</td><td>494</td><td>504</td><td>509</td><td>NQ</td></tr></table></td></tr>
<tr><td>Unit : U.S. Dollars per metric ton ( milled rice basis ), F.O.B. prices</td></tr>
<tr><td>Exchange Rates of US DOLLAR*</td></tr>
<tr><td><table><tr><td>Item</td><td>23 Sep 2026</td><td>30 Sep 2026</td><td>7 Oct 2026</td><td>14 Oct 2026</td><td>21 Oct 2026</td></tr>
<tr><td><img src="price_eng-3.jpg"></td><td>32.9256</td><td>33.3061</td><td>33.3992</td><td>33.3223</td><td>33.3971</td></tr></table></td></tr>
</table></form></body></html>"""

TREA_AVG = """<html><body><table><tr><td>Item</td>{m}<td>Avg.</td></tr>
<tr><td>Thai Hom Mali Rice Premium Quality (crop 2024/25)</td><td>1,334</td><td>1,331</td><td>1,300</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td>1,306</td></tr>
<tr><td>Thai Hom Mali Rice Premium Quality (crop 2025/26)</td><td>1,203</td><td>1,200</td><td>1,175</td><td>1,210</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td>1,209</td></tr>
<tr><td>White Rice 5%</td><td>408</td><td>409</td><td>381</td><td>403</td><td>440</td><td>494</td><td>467</td><td></td><td></td><td></td><td></td><td></td><td>429</td></tr>
<tr><td>Remark : FOB Prices quoted include a single white woven polypropylene (PP) bag each of 50 kg.</td></tr>
</table></body></html>""".replace('{m}', ''.join(f'<td>{m}</td>' for m in fp.MONTHS))

DIT_HTML = """<html><body><div><h2>ประเภท : ขายส่ง สินค้า : ราคาขายส่งข้าว ผลิตภัณฑ์ข้าวและกระสอบป่าน {name} {unit}</h2></div>
<table><tr><th>วันที่</th><th>ราคา ต่ำสุด - สูงสุด (บาท)</th><th>ราคาเฉลี่ย (บาท)</th></tr>
<tr><td>27 ต.ค. 2569</td><td>{lo} - {hi}</td><td>{avg}</td></tr>
<tr><td>28 ต.ค. 2569</td><td>{lo} - {hi}</td><td>{avg}</td></tr>
<tr><td>ราคาเฉลี่ย</td><td>{lo} - {hi}</td><td>{avg}</td></tr></table></body></html>"""


def fao_json(uuid):
    pts = [{'price_value': 419.06, 'price_value_dollar': 419.06, 'date': '2026-09-01', 'periodicity': 'monthly'},
           {'price_value': 441.42, 'price_value_dollar': 441.42, 'date': '2026-08-01', 'periodicity': 'monthly'}]
    if uuid.startswith('eb6de409'):
        pts += [{'price_value': 480.0, 'price_value_dollar': 480.0, 'date': '2026-09-25', 'periodicity': 'weekly'},
                {'price_value': 470.0, 'price_value_dollar': 470.0, 'date': '2000-01-07', 'periodicity': 'weekly'}]
    return {'uuid': uuid, 'datapoints': pts}


def wb_xlsx():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Monthly Prices'
    ws.append(['World Bank Commodity Price Data (The Pink Sheet)'])
    ws.append(['monthly prices in nominal US dollars, 1960 to present'])
    ws.append(['(monthly series are available only in nominal US dollars)'])
    ws.append(['Updated on October 02, 2026'])
    ws.append([None, 'Crude oil, average', 'Rice, Thai 5% ', 'Rice, Thai 25% ', 'Rice, Thai A.1', 'Rice, Viet Namese 5%'])
    ws.append([None, '($/bbl)', '($/mt)', '($/mt)', '($/mt)', '($/mt)'])
    ws.append(['1960M01', 1.6, 104.5, '…', '…', '…'])
    ws.append(['2026M09', 70, 482, 461, 473.2, 418.5])
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


class R:
    def __init__(self, body, ctype='text/html'):
        self.content = body if isinstance(body, bytes) else body.encode('utf-8')
        self.text = self.content.decode('utf-8', 'replace')

    def raise_for_status(self):
        pass

    def json(self):
        return json.loads(self.text)


def fake_get(url, headers=None, timeout=None, params=None):
    if 'price_eng.html' in url:
        return R(TREA_WEEKLY)
    if 'AVG%20prices%202026' in url:
        return R(TREA_AVG)
    if 'AVG%20prices' in url:
        raise fp.requests.HTTPError('404')
    if 'FpmaSeriePrice' in url:
        return R(json.dumps(fao_json(url.rstrip('/').split('/')[-1])))
    if 'commodity-markets' in url:
        return R('<a href="https://thedocs.worldbank.org/x/CMO-Historical-Data-Monthly.xlsx">xls</a>')
    if url.endswith('.xlsx'):
        return R(wb_xlsx())
    if 'frankfurter' in url:
        y = url.split('/v1/')[1][:4]
        return R(json.dumps({'rates': {f'{y}-10-27': {'THB': 33.77}, f'{y}-10-28': {'THB': 33.775}} if y == '2026' else {}}))
    raise AssertionError(url)


def fake_post(url, headers=None, timeout=None, data=None):
    code = data['proname']
    if code in ('R11007', 'R11029', 'R11018'):
        return R(DIT_HTML.format(name='ข้าวขาว 5%', unit='บาท/100 กก.', lo=1550, hi=1560, avg='1,555.00'))
    return R(DIT_HTML.format(name='ข้าวเปลือกเจ้า', unit='บาท/ตัน', lo=8600, hi=9700, avg='9,150.00'))


def main():
    tmp = Path(tempfile.mkdtemp())
    fp.RAW, fp.OUT = tmp / 'raw', tmp / 'out'
    fp.TODAY = dt.date(2026, 10, 29)
    with mock.patch.object(fp.requests, 'get', fake_get), mock.patch.object(fp.requests, 'post', fake_post), \
            mock.patch.object(sys, 'argv', ['x']):
        fp.main()
        out = json.loads((fp.OUT / 'prices.json').read_text())
        S = out['series']
        epoch = dt.date(1970, 1, 1)
        day = lambda s, i: (epoch + dt.timedelta(days=S[s]['d'][i])).isoformat()

        # TREA weekly rows mapped by position
        assert S['th_5']['v'][-1] == 492 and day('th_5', -1) == '2026-10-28', S['th_5']['v'][-5:]
        assert S['th_hm']['v'][-1] == 1184
        assert S['th_glu']['v'][-1] == 883
        assert S['th_pb']['v'][-1] == 509 and day('th_pb', -1) == '2026-10-21', 'NQ must be skipped'
        # splice: weekly TREA from 2026-09-30, then FAO weekly earlier, then WB 1960
        assert '2026-09-25' in [day('th_5', i) for i in range(len(S['th_5']['d']))]
        assert day('th_5', 0) == '1960-01-01' and S['th_5']['v'][0] == 104.5
        assert S['th_5']['src'] == ['trea', 'fao', 'wb'], S['th_5']['src']
        # TREA monthly archive -> newest Hom Mali crop chosen per month (before weekly starts)
        hm = {day('th_hm', i): S['th_hm']['v'][i] for i in range(len(S['th_hm']['d']))}
        assert hm['2026-01-01'] == 1203, hm
        # WB Viet Nam only fills dates before FAO's first point ('…' cells are skipped, later WB points dropped)
        assert S['vn_5']['v'][-1] == 419.1 and S['vn_5']['src'] == ['fao'], S['vn_5']
        # DIT: THB -> USD at the day's rate; /100 kg -> /t
        assert S['dit_paddy']['thb'][-1] == 9150 and abs(S['dit_paddy']['v'][-1] - 9150 / 33.775) < 0.1
        assert S['dit_w5']['thb'][-1] == 15550 and abs(S['dit_w5']['v'][-1] - 15550 / 33.775) < 0.1
        assert all(out['sources'][k]['last_ok'] for k in out['sources']), out['sources']

        # second run with a broken TREA page: history kept, error recorded, others still OK
        global TREA_WEEKLY
        good = TREA_WEEKLY
        TREA_WEEKLY = good.replace('<tr><td>829</td>', '<tr><td>x</td>')
        fp.main()
        out2 = json.loads((fp.OUT / 'prices.json').read_text())
        assert out2['sources']['trea']['last_error'] and 'expected 11' in out2['sources']['trea']['last_error']
        assert out2['series']['th_5']['v'][-1] == 492, 'stored history must survive a failed pull'
        assert out2['sources']['fao']['last_error'] is None
        TREA_WEEKLY = good
    print('all price pipeline tests passed;', len(S), 'series')
    shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
