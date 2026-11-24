#!/usr/bin/env python3
"""Watch DIT for new "recommended retail price of chemical fertilizer" announcements.

They are scanned PDFs, so reading them is a manual step (tools/dit_fert_ocr.py). This only notices that a new one
exists and records it in data/raw/dit_watch.json; the fertilizer page then says a newer official list is out.
"""
import datetime as dt, html, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / 'data' / 'raw' / 'dit_watch.json'
KNOWN = ROOT / 'data' / 'dit_fert.json'
URL = 'https://www.dit.go.th/th/law/act/prices-goods-services-2542/'
TITLE = 'ราคาจำหน่ายปลีกแนะนำปุ๋ยเคมี'


def find(page):
    """[(no, be_year, pdf_url)] for every fertilizer recommended-price announcement linked on the page."""
    page = html.unescape(page)
    out = []
    for m in re.finditer(r'ฉบับที่\s*(\d+)\s*พ\.ศ\.\s*(\d{4})[^<]{0,80}?' + TITLE, page):
        pdf = re.search(r'href="([^"]+\.pdf)"', page[m.end():m.end() + 3000], re.I)
        if pdf:
            u = pdf.group(1)
            out.append((int(m.group(1)), int(m.group(2)), u if u.startswith('http') else 'https://www.dit.go.th' + u))
    seen, res = set(), []
    for x in out:
        if x[:2] not in seen:
            seen.add(x[:2]); res.append(x)
    return res


def update(get):
    try:
        known = {(a['no'], int(a['date'][:4]) + 543) for a in json.loads(KNOWN.read_text(encoding='utf-8'))['announcements']}
    except Exception:
        known = set()
    st = {'checked': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    try:
        found = find(get(URL).content.decode('utf-8', 'replace'))
        st.update(ok=True, found=[dict(no=n, year=y, url=u) for n, y, u in found],
                  new=[dict(no=n, year=y, url=u) for n, y, u in found if (n, y) not in known and y >= 2569])
        print(f'dit_watch: {len(found)} fertilizer announcements listed, {len(st["new"])} not yet read')
    except Exception as e:
        old = {}
        try:
            old = json.loads(STORE.read_text(encoding='utf-8'))
        except Exception:
            pass
        st.update(ok=False, error=f'{type(e).__name__}: {e}'[:300], new=old.get('new', []), found=old.get('found', []))
        print(f'dit_watch: FAILED {st["error"]}')
    STORE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')
    return st
