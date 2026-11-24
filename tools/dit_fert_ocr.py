#!/usr/bin/env python3
"""Read a DIT "recommended retail price of chemical fertilizer" announcement (scanned PDF) into data/dit_fert.json.

The Office of the Central Committee on Prices (สำนักงาน กกร., Department of Internal Trade) publishes these as
scanned tables: 77 provinces x formulas x brands, baht per 50 kg bag. They are images, so this needs
tesseract with the Thai language pack and poppler (pdftoppm). Run it by hand when a new announcement appears
(pipeline/dit_watch.py flags new ones on the site):

    python3 tools/dit_fert_ocr.py ANNOUNCEMENT.pdf --no 9 --date 2026-06-26 --url https://www.dit.go.th/media/... \
        --layout "A=dist|46-0-0:rung-arun,top-one,cow-plough,rabbit|18-46-0:top-one,rung-arun,crown|0-0-60:rabbit,cow-plough,top-one,rung-arun,crown" \
        --layout "B=dist|21-0-0:rabbit,cow-plough,top-one,rung-arun,crown|15-15-15:rabbit,cow-plough,top-one,rung-arun,crown|16-20-0:rabbit,cow-plough,top-one"

--layout gives each table's columns left to right, as printed in the header (check one page by eye; the column
order of brands changes between announcements). "dist" is the distance column, when the table has one.
Pages are assigned to tables in order: the first table runs until its last province, then the next starts.

How the numbers are checked: every price in a row is the brand's ex-depot price plus one delivery amount for that
province. So each table solves for one base price per column and one delta per province, OCR misreads are replaced
by base + delta, and the two tables must agree on every province's delta. The script refuses to write if they don't.
"""
import argparse, io, json, re, subprocess, sys, tempfile, difflib
from collections import Counter
from pathlib import Path

try:                      # only the OCR needs these; solve() and the tests run without them
    import numpy as np
    from PIL import Image
except ImportError:
    np = Image = None

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'dit_fert.json'
PROV = json.loads((ROOT / 'data' / 'provinces.json').read_text(encoding='utf-8'))
TH = [p[0] for p in PROV]
SLUG = {p[0]: p[2] for p in PROV}
ALIAS = {'ลำพน': 'ลำพูน', 'ตาก': 'ตาก', 'ตัง': 'ตรัง'}   # names tesseract mangles most


def groups(idx, gap=12):
    out = []
    for i in idx:
        if out and i - out[-1][-1] <= gap:
            out[-1].append(i)
        else:
            out.append([i])
    return [int(sum(g) / len(g)) for g in out]


def tess(img, lang, psm, wl=None):
    args = ['tesseract', 'stdin', 'stdout', '-l', lang, '--psm', str(psm)]
    if wl:
        args += ['-c', 'tessedit_char_whitelist=' + wl]
    b = io.BytesIO(); img.save(b, 'PNG')
    rows = subprocess.run(args + ['tsv'], input=b.getvalue(), capture_output=True).stdout.decode().splitlines()[1:]
    return [r.split('\t')[-1] for r in rows if r.split('\t')[-1].strip()]


def deskew(im):
    sm = im.resize((im.width // 4, im.height // 4))
    best = (0, 0.0)
    for ang in np.arange(-2, 2.01, 0.05):
        b = np.array(sm.rotate(ang, fillcolor=255)) < 128
        sc = (b.sum(1).astype(float) ** 2).sum()
        if sc > best[0]:
            best = (sc, float(ang))
    return im.rotate(best[1], fillcolor=255, resample=Image.BICUBIC)


def read_page(path):
    """Cells of one table page: [(name_text, [cell_text, ...]), ...]."""
    im = Image.open(path).convert('L')
    if im.height > im.width:          # some issues are scanned portrait with the table turned sideways
        im = im.rotate(-90, expand=True)
    im = deskew(im)
    a = np.array(im); dark = a < 128
    H = groups(np.where(dark.sum(1) > 0.25 * a.shape[1])[0])
    body = [(H[i], H[i + 1]) for i in range(len(H) - 1) if 40 < H[i + 1] - H[i] < 80]
    # a column rule is dark through (nearly) the full height of most rows; stacked digits never are
    light = a < 180
    cnt = np.zeros(a.shape[1])
    for y0, y1 in body:
        f = light[y0 + 5:y1 - 5].mean(0)
        cnt += np.maximum.reduce([np.roll(f, k) for k in (-2, -1, 0, 1, 2)]) > 0.8
    V = []
    for v in groups(np.where(cnt > 0.5 * len(body))[0]):
        if not V or v - V[-1] >= 60:
            V.append(v)
    rows = [(H[i], H[i + 1]) for i in range(len(H) - 1) if 40 < H[i + 1] - H[i] < 80]
    out = []
    for y0, y1 in rows:
        name = ' '.join(tess(im.crop((V[1] + 4, y0 + 4, V[2] - 4, y1 - 4)), 'tha', 7))
        cells = []
        for c in range(2, len(V) - 1):
            t = ''.join(tess(im.crop((V[c] + 4, y0 + 4, V[c + 1] - 4, y1 - 4)), 'eng', 7, '0123456789,-')).replace(',', '')
            cells.append(int(t) if re.fullmatch(r'\d{1,4}', t) else None)
        out.append((name, cells))
    return out


def match(raw):
    n = re.sub(r'[^฀-๿]', '', raw).replace('ํา', 'ำ')
    if not n:
        return None
    for a, t in ALIAS.items():
        if n.startswith(a):
            return t
    best = max(TH, key=lambda t: difflib.SequenceMatcher(None, n, t).ratio())
    return best if difflib.SequenceMatcher(None, n, best).ratio() > 0.6 else None


def parse_layout(s):
    name, spec = s.split('=', 1)
    cols = []
    for part in spec.split('|'):
        if part == 'dist':
            cols.append(('dist', None))
        else:
            f, brands = part.split(':')
            cols += [(f, b) for b in brands.split(',')]
    return name, cols


def solve(rows, cols):
    """rows: [(province, cells)]. Returns base {formula: {brand: price}}, {province: (delta, km)}, fixes."""
    R = []
    for th, cells in rows:
        if len(cells) == len(cols) and sum(isinstance(v, int) and v > 99 for v in cells) >= 3 and th not in [r[0] for r in R]:
            R.append((th, cells))
    num = [i for i, (f, b) in enumerate(cols) if f != 'dist']
    # a dash ("not sold") can OCR as a stray digit; no 50 kg bag costs under 100 baht
    R = [(t, [(v if (i not in num or not isinstance(v, int) or v >= 100) else None) for i, v in enumerate(c)]) for t, c in R]
    sold = {i for i in num if sum(isinstance(c[i], int) for _, c in R) >= 0.5 * len(R)}
    ref = next((c for t, c in R if t == 'กรุงเทพมหานคร'), None) or max((c for t, c in R), key=lambda c: sum(isinstance(v, int) for v in c))
    base = {i: (ref[i] if i in sold else None) for i in num}
    for _ in range(6):
        D = {}
        for th, cells in R:
            diffs = [cells[i] - base[i] for i in num if isinstance(cells[i], int) and base[i] is not None]
            D[th] = Counter(diffs).most_common(1)[0][0] if diffs else None
        for i in num:
            cand = [cells[i] - D[th] for th, cells in R if isinstance(cells[i], int) and D[th] is not None]
            base[i] = Counter(cand).most_common(1)[0][0] if cand and i in sold else None
    fixes = sum(1 for th, cells in R for i in num if base[i] is not None and cells[i] != base[i] + D[th])
    di = next((i for i, (f, b) in enumerate(cols) if f == 'dist'), None)
    prov = {th: (D[th], cells[di] if di is not None else None) for th, cells in R}
    out = {}
    for i in num:
        if base[i] is not None:
            f, b = cols[i]
            out.setdefault(f, {})[b] = base[i]
    return out, prov, fixes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf'); ap.add_argument('--no', type=int, required=True); ap.add_argument('--date', required=True)
    ap.add_argument('--url', default=''); ap.add_argument('--layout', action='append', required=True)
    ap.add_argument('--first-page', type=int, default=3)
    a = ap.parse_args()
    layouts = [parse_layout(s) for s in a.layout]
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['pdftoppm', '-r', '300', '-f', str(a.first_page), '-png', a.pdf, f'{tmp}/p'], check=True)
        pages = sorted(Path(tmp).glob('p-*.png'))
        tables = [[] for _ in layouts]
        from concurrent.futures import ThreadPoolExecutor   # tesseract runs in subprocesses, so threads parallelise
        with ThreadPoolExecutor(max_workers=6) as ex:
            read = list(ex.map(read_page, pages))
        cur = 0
        for p, cells in zip(pages, read):
            rows = [(match(n), c) for n, c in cells]
            rows = [(t, c) for t, c in rows if t]
            width = Counter(len(c) for _, c in rows).most_common(1)[0][0] if rows else 0
            fits = [i for i, (_, cols) in enumerate(layouts) if len(cols) == width]
            if fits and cur not in fits:            # tables differ in column count; follow the page's width
                cur = fits[0]
            print(f'{p.name}: {len(rows)} provinces, {width} columns -> table {layouts[cur][0]}', file=sys.stderr)
            tables[cur] += rows
    base, deltas, kms = {}, {}, {}
    for (name, cols), rows in zip(layouts, tables):
        b, prov, fixes = solve(rows, cols)
        print(f'table {name}: {len(prov)} provinces, {fixes} OCR cells corrected', file=sys.stderr)
        base.update(b)
        for th, (d, km) in prov.items():
            if th in deltas and deltas[th] != d:
                sys.exit(f'delta mismatch for {th}: {deltas[th]} vs {d}. Check the layout and the scan.')
            deltas[th] = d
            if km is not None:
                kms.setdefault(th, []).append(km)
    missing = [t for t in TH if t not in deltas]
    if missing:
        sys.exit(f'missing provinces: {missing}')
    prov = {}
    for th in TH:
        k = kms.get(th, [])
        km = k[0] if len(set(k)) == 1 else (min(k, key=lambda x: abs(x - 50 * deltas[th] - 100)) if k else None)
        prov[SLUG[th]] = [deltas[th], km]
    store = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {'announcements': []}
    ann = [x for x in store['announcements'] if x['no'] != a.no or x['date'][:4] != a.date[:4]]
    ann.append(dict(no=a.no, date=a.date, url=a.url, base=base, prov=prov))
    store['announcements'] = sorted(ann, key=lambda x: x['date'])
    OUT.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'wrote {OUT}: No.{a.no} {a.date}, {len(base)} formulas, {len(prov)} provinces')


if __name__ == '__main__':
    main()
