#!/usr/bin/env python3
"""Tha Bo Agricultural Cooperative (Nong Khai) fertilizer price list -> data/raw/coop_thabo.json.

The co-op posts its shop prices on https://www.coopthabo.com/thabo-2 with an "update วันที่ ..." line, about monthly.
Each new list is kept under its own date, so the page builds a small price history.
Called from pipeline/fertilizer.py; a failure keeps the stored lists and is reported in status.
"""
import datetime as dt, html, json, re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / 'data' / 'raw' / 'coop_thabo.json'
URL = 'https://www.coopthabo.com/thabo-2'
TH_MONTHS = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม', 'สิงหาคม',
             'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
HEADINGS = [('ปุ๋ยตรากระต่าย', 'rabbit'), ('ปุ๋ยตราหัววัว', 'cow-plough'), ('ปุ๋ยตรายาร่า', 'yara')]
ITEM = re.compile(r'สูตร\s*(ต็อบวัน|ท็อบวัน|ท็อปวัน|เอ็นเทค)?\s*(\d{1,2})\s*-\s*(\d{1,2})\s*-\s*(\d{1,2})(?!\d)(.*?)ราคา\s*(.*?)(?:บาท|(?=สูตร)|$)')


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        elif tag in ('br', 'p', 'div', 'li', 'tr'):
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.parts.append(d)


def to_text(page):
    if '<' in page:
        p = _Text(); p.feed(page); page = ''.join(p.parts)
    return re.sub(r'\s+', ' ', html.unescape(page).replace('\xa0', ' '))


def parse(page):
    """Returns (date 'YYYY-MM-DD' or None, [{brand, npk, price, size_kg, out}])."""
    t = to_text(page)
    date = None
    m = re.search(r'update\s*วันที่\s*(\d{1,2})\s*(' + '|'.join(TH_MONTHS) + r')\s*(\d{4})', t)
    if m:
        y = int(m.group(3)); y = y - 543 if y > 2400 else y
        date = f'{y}-{TH_MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}'
    start = t.find('ปุ๋ยตรากระต่าย')
    end = t.find('อาหารปลา', start)
    t = t[start:end if end > 0 else None] if start >= 0 else t
    # cut into brand sections by heading; text after Yara's last line (15-0-0) is unlabelled photos -> 'other'
    marks = sorted((t.find(h), b) for h, b in HEADINGS if t.find(h) >= 0)
    items = []
    for i, (pos, brand) in enumerate(marks):
        seg = t[pos:marks[i + 1][0] if i + 1 < len(marks) else None]
        if brand == 'yara':
            cut = re.search(r'15\s*-\s*0\s*-\s*0\s*ราคา[^สูตร]*', seg)
            if cut:
                items += _items(seg[:cut.end()], 'yara')
                items += _items(seg[cut.end():], 'other')
                continue
        items += _items(seg, brand)
    return date, items


def _items(seg, brand):
    out = []
    for m in ITEM.finditer(seg):
        tag, n, p, k, mid, price = m.groups()
        b = 'top-one' if tag in ('ต็อบวัน', 'ท็อบวัน', 'ท็อปวัน') else 'entec' if tag == 'เอ็นเทค' else brand
        size = 25 if re.search(r'25\s*(กก|ก\.ก|กิโล)', mid + price) else 50
        oos = 'สินค้าหมด' in price
        num = re.search(r'\d[\d,]{2,}', re.sub(r'\(.*?\)', '', price))
        val = int(num.group().replace(',', '')) if num and not oos else None
        if val is None and not oos:
            continue
        out.append(dict(brand=b, npk=f'{int(n)}-{int(p)}-{int(k)}', price=val, size_kg=size, out=oos))
    return out


def load():
    try:
        return json.loads(STORE.read_text(encoding='utf-8'))
    except Exception:
        return {'lists': {}, 'status': {}}


def update(get):
    """get(url) -> response with .text. Stores a new list when the co-op's update date changes."""
    store = load(); st = store.setdefault('status', {})
    st['last_attempt'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        date, items = parse(get(URL).content.decode('utf-8', 'replace'))
        if not items or not date:
            raise ValueError(f'no price list found (date={date}, items={len(items)})')
        new = date not in store['lists']
        store['lists'][date] = items
        st['last_ok'] = st['last_attempt']; st['last_error'] = None
        print(f'coop: Tha Bo list {date}, {len(items)} items{" (new)" if new else ""}')
    except Exception as e:
        st['last_error'] = f'{type(e).__name__}: {e}'[:300]
        print(f'coop: FAILED {st["last_error"]}')
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding='utf-8')
    return store
