"""Fertilizer sub-pages for rice.ag: one page per formula, blend-your-own, rice cost per rai.

Everything is computed at build time from src/static/data/fertilizer.json (see pipeline/fertilizer.py),
so the numbers are in the HTML search engines read. The calculators on the pages redo the same maths in JS.
"""
BAG = 50

# Common Thai names and what each formula is used for. Rice uses follow the Rice Department's
# Rice Knowledge Bank (rkb.ricethailand.go.th); anything not listed there is described only by its make-up.
INFO = {
    '46-0-0': dict(en='Urea', th='ยูเรีย', world='urea',
                   use_en='The cheapest common source of nitrogen. In rice it is the standard top-dressing, applied at maximum tillering and at panicle initiation.',
                   use_th='แหล่งไนโตรเจนที่ถูกที่สุดในบรรดาปุ๋ยทั่วไป ในนาข้าวใช้เป็นปุ๋ยแต่งหน้า ใส่ช่วงข้าวแตกกอสูงสุดและช่วงกำเนิดช่อดอก'),
    '21-0-0': dict(en='Ammonium sulfate', th='แอมโมเนียมซัลเฟต',
                   use_en='Nitrogen plus about 24% sulfur. The Rice Department lists it as an alternative rice top-dressing at roughly twice the urea rate.',
                   use_th='ไนโตรเจนพร้อมกำมะถันราว 24% กรมการข้าวระบุให้ใช้แต่งหน้าแทนยูเรียได้ ในอัตราราวสองเท่าของยูเรีย'),
    '0-0-60': dict(en='Potash (potassium chloride, MOP)', th='โพแทสเซียมคลอไรด์', world='kcl',
                   use_en='The cheapest source of potassium, and a base for blending NPK.', use_th='แหล่งโพแทสเซียมที่ถูกที่สุด และเป็นแม่ปุ๋ยสำหรับผสมสูตร'),
    '18-46-0': dict(en='DAP (diammonium phosphate)', th='ไดแอมโมเนียมฟอสเฟต', world='dap',
                    use_en='The main source of phosphate, and the usual base for blending 16-20-0 and other rice formulas.',
                    use_th='แหล่งฟอสเฟตหลัก และเป็นแม่ปุ๋ยสำหรับผสมสูตร 16-20-0 และสูตรนาข้าวอื่น ๆ'),
    '16-20-0': dict(en='Ammonium phosphate (rice starter)', th='แอมโมเนียมฟอสเฟต (สูตรรองพื้นนาข้าว)',
                    use_en='The Rice Department\'s recommended basal fertilizer for rice on clay soils, 25-35 kg per rai.',
                    use_th='ปุ๋ยรองพื้นนาข้าวในดินเหนียวตามคำแนะนำของกรมการข้าว อัตรา 25-35 กก./ไร่'),
    '16-16-8': dict(en='Rice basal NPK', th='สูตรรองพื้นนาดินทราย',
                    use_en='The Rice Department\'s recommended basal fertilizer for rice on loam and sandy soils.',
                    use_th='ปุ๋ยรองพื้นนาข้าวในดินร่วนและดินทรายตามคำแนะนำของกรมการข้าว'),
    '15-15-15': dict(en='Balanced NPK', th='สูตรเสมอ',
                     use_en='A balanced compound. The Rice Department lists it as a basal option for rice on loam and sandy soils; also widely used on vegetables and fruit.',
                     use_th='ปุ๋ยสูตรเสมอ กรมการข้าวระบุเป็นทางเลือกปุ๋ยรองพื้นนาข้าวในดินร่วนและดินทราย ใช้มากกับผักและไม้ผลด้วย'),
    '16-16-16': dict(en='Balanced NPK', th='สูตรเสมอ', use_en='A balanced compound used on vegetables, fruit and field crops.',
                     use_th='ปุ๋ยสูตรเสมอ ใช้กับผัก ไม้ผล และพืชไร่'),
    '13-13-21': dict(en='High-potash NPK', th='สูตรโพแทสสูง',
                     use_en='A compound with extra potassium. The Rice Department lists it for rice on loam and sandy soils at 30-45 kg per rai; also used for fruit fill.',
                     use_th='ปุ๋ยที่มีโพแทสเซียมสูง กรมการข้าวระบุให้ใช้กับนาข้าวในดินร่วนและดินทราย อัตรา 30-45 กก./ไร่ ใช้กับไม้ผลช่วงบำรุงผลด้วย'),
    '16-8-8': dict(en='Nitrogen-rich NPK', th='สูตรไนโตรเจนสูง', use_en='A nitrogen-heavy compound, often sold as a rice or urea substitute.',
                   use_th='ปุ๋ยที่มีไนโตรเจนสูง มักขายเป็นปุ๋ยนาข้าวหรือปุ๋ยใช้แทนยูเรีย'),
    '8-24-24': dict(en='Phosphate and potash NPK', th='สูตรฟอสเฟตและโพแทสสูง', use_en='Low nitrogen, high phosphate and potash; used for flowering and fruiting.',
                    use_th='ไนโตรเจนต่ำ ฟอสเฟตและโพแทสสูง ใช้ช่วงออกดอกและติดผล'),
    '15-0-0': dict(en='Calcium nitrate', th='แคลเซียมไนเตรต', use_en='Nitrogen with calcium, mostly for vegetables and fruit.',
                   use_th='ไนโตรเจนพร้อมแคลเซียม ใช้กับผักและไม้ผลเป็นหลัก'),
}

STRAIGHTS = {'N': ('46-0-0', 46), 'P': ('18-46-0', 46), 'K': ('0-0-60', 60)}
BLEND_TARGETS = ['16-20-0', '16-16-8', '15-15-15', '16-8-8', '13-13-21', '16-16-16', '20-8-20', '8-24-24']


def npk(key):
    return tuple(int(x) for x in key.split('-'))


def blend(target, prices, amount=100):
    """kg of urea, DAP, potash and filler to make `amount` kg of a target N-P-K, and the cost.
    DAP supplies all the phosphate (and some nitrogen), urea the rest of the nitrogen, potash the potassium.
    prices: baht per 50 kg bag for '46-0-0', '18-46-0', '0-0-60'. Returns None if the target is too concentrated."""
    n, p, k = target
    dap = amount * p / 46
    urea = (amount * n / 100 - dap * 0.18) / 0.46
    mop = amount * k / 60
    if urea < 0:  # more nitrogen from DAP than the target wants: not possible with these three
        return None
    filler = amount - dap - urea - mop
    if filler < -0.01:
        return None
    parts = [('46-0-0', urea), ('18-46-0', dap), ('0-0-60', mop)]
    if any(prices.get(f) is None for f, kg in parts if kg > 0):
        return None
    cost = sum(kg * prices[f] / BAG for f, kg in parts if kg > 0)
    return dict(urea=round(urea, 1), dap=round(dap, 1), mop=round(mop, 1), filler=round(max(filler, 0), 1),
                cost=round(cost), per_bag=round(cost * BAG / amount))


def blend_table(F):
    by = {f['npk']: f for f in F.get('formulas', [])}
    prices = {k: by[k]['median'] for k in ('46-0-0', '18-46-0', '0-0-60') if k in by}
    rows = []
    for t in BLEND_TARGETS:
        b = blend(npk(t), prices, BAG)
        if not b:
            continue
        shop = by.get(t)
        rows.append(dict(npk=t, **b, shop=shop['median'] if shop else None,
                         saving=shop['median'] - b['per_bag'] if shop else None))
    saved = [r for r in rows if r['saving'] is not None]
    return dict(prices=prices, rows=rows, best=max(saved, key=lambda r: r['saving']) if saved else None)


def formula_pages(F):
    """Which formulas get their own page: every formula seen at 3 or more brands, plus the straights and rice formulas."""
    keep = {'46-0-0', '16-20-0', '15-15-15', '0-0-60', '21-0-0', '18-46-0', '16-8-8', '13-13-21', '16-16-16', '8-24-24'}
    return [f for f in F.get('formulas', []) if f['count'] >= 3 or f['npk'] in keep]


def formula_fill(f, F, lang):
    """Facts for one formula page."""
    th = lang == 'th'
    info = INFO.get(f['npk'], {})
    n, p, k = f['n'], f['p'], f['k']
    kg = dict(n=BAG * n / 100, p=BAG * p / 100, k=BAG * k / 100)
    by = {x['npk']: x for x in F.get('formulas', [])}
    prices = {x: by[x]['median'] for x in ('46-0-0', '18-46-0', '0-0-60') if x in by}
    b = blend((n, p, k), prices, BAG) if f['npk'] not in ('46-0-0', '18-46-0', '0-0-60') else None
    w = (F.get('world') or {}).get(info.get('world', ''))
    gap = f['median'] - w['thb_bag'] if w and w.get('thb_bag') else None
    name = (info.get('th') if th else info.get('en')) or ''
    if th:
        lead = f"ปุ๋ยสูตร {f['npk']}{(' (' + name + ')') if name else ''} กระสอบ 50 กก. ราคาหน้าร้านราว {f['median']:,} บาท"
        lead += f" ช่วง {f['low']:,}–{f['high']:,} บาท จาก {f['count']} ยี่ห้อ" if f['count'] > 1 else ''
        lead += f" คิดเป็นธาตุอาหาร 1 กก. ราว {f['per_nutrient']:.1f} บาท" if f.get('per_nutrient') else ''
    else:
        lead = f"A 50 kg bag of {f['npk']}{(' (' + name + ')') if name else ''} costs about {f['median']:,} baht at Thai shops"
        lead += f", {f['low']:,}–{f['high']:,} baht across {f['count']} brands" if f['count'] > 1 else ''
        lead += f"; that is about {f['per_nutrient']:.1f} baht per kg of nutrient." if f.get('per_nutrient') else '.'
    return dict(f=f, info=info, name=name, kg=kg, blend=b, world=w, gap=gap, lead=lead,
                use=(info.get('use_th') if th else info.get('use_en')))


# ---------------------------------------------------------------- rice: fertilizer cost per rai
# Rice Department, Rice Knowledge Bank: basal 16-20-0 (clay) or 16-16-8 (loam/sand); top-dress urea.
# Photoperiod-sensitive rice (e.g. Hom Mali): basal 25, urea 5 kg/rai. Non-sensitive: basal 30, urea 10 kg/rai.
RICE_PLAN = {
    'sensitive': {'basal': 25, 'top': 5},
    'nonsensitive': {'basal': 30, 'top': 10},
}
RICE_SOIL = {'clay': ['16-20-0', '18-20-0', '20-20-0', '16-8-8'], 'sand': ['16-16-8', '15-15-15', '13-13-21', '16-20-0']}


def rice_defaults(F):
    by = {f['npk']: f['median'] for f in F.get('formulas', [])}
    opts = {soil: [(x, by[x]) for x in lst if x in by] for soil, lst in RICE_SOIL.items()}
    top = [(x, by[x]) for x in ('46-0-0', '21-0-0') if x in by]
    examples = []
    for variety in ('sensitive', 'nonsensitive'):
        for soil in ('clay', 'sand'):
            if not opts[soil] or not top:
                continue
            bf, bp = opts[soil][0]
            tf, tp = top[0]
            plan = RICE_PLAN[variety]
            cost = plan['basal'] * bp / BAG + plan['top'] * tp / BAG
            examples.append(dict(variety=variety, soil=soil, basal_f=bf, basal_kg=plan['basal'], top_f=tf, top_kg=plan['top'],
                                 cost=round(cost)))
    return dict(opts=opts, top=top, plan=RICE_PLAN, examples=examples)


# ---------------------------------------------------------------- rice vs urea, since 1960
def affordability(F, prices):
    """Tonnes of urea one tonne of Thai 5% white rice buys, month by month (both World Bank / TREA USD prices)."""
    import datetime, statistics
    th5 = (prices.get('series') or {}).get('th_5') or {}
    urea = dict(((F.get('world') or {}).get('urea') or {}).get('hist') or [])
    if not th5.get('d') or not urea:
        return None
    epoch = datetime.date(1970, 1, 1)
    rice = {}
    for t, v in zip(th5['d'], th5['v']):
        if v:
            m = (epoch + datetime.timedelta(days=int(t))).strftime('%Y-%m-01')
            rice.setdefault(m, []).append(v)
    pts = [[m, round(statistics.mean(rice[m]) / u, 3)] for m, u in sorted(urea.items()) if m in rice and u]
    if len(pts) < 24:
        return None
    vals = sorted(v for _, v in pts)
    cur = pts[-1][1]
    rank = sum(1 for v in vals if v <= cur) / len(vals)  # share of months since 1960 with a ratio at or below today's
    return dict(hist=pts, current=cur, date=pts[-1][0], median=round(statistics.median(vals), 2),
                low=min(pts, key=lambda p: p[1]), high=max(pts, key=lambda p: p[1]), pct=round(rank * 100))


# ---------------------------------------------------------------- brands
BRANDS = {  # slug: shop-sheet brand name (only brands named clearly on the boards, with 6+ prices)
    'rabbit': 'Rabbit', 'crown': 'Crown', 'openbill-stork': 'Openbill Stork', 'yara': 'Sailboat / Yara',
    'thip': 'Thip', 'cow-head': 'Cow Head', 'cow-head-plough': 'Cow Head & Plough'}


def brand_pages(F):
    """One entry per brand: every formula it was seen at, and how far its price sits from that formula's median."""
    med = {f['npk']: f['median'] for f in F.get('formulas', [])}
    out = []
    for slug, name in BRANDS.items():
        rows, prem = [], []
        for f in F.get('formulas', []):
            for i in f['items']:
                if i['brand'] == name:
                    d = (i['price'] / f['median'] - 1) * 100 if i['size_kg'] == BAG and f['count'] > 1 else None
                    if d is not None and not i['flag']:
                        prem.append(d)
                    rows.append(dict(npk=f['npk'], price=i['price'], size_kg=i['size_kg'], median=med.get(f['npk']), shop=i['shop'],
                                     diff=round(d, 1) if d is not None else None, flag=i['flag'], count=f['count']))
        if len(rows) < 3:
            continue
        th = next((i['brand_th'] for f in F.get('formulas', []) for i in f['items'] if i['brand'] == name and i['brand_th']), None)
        full = [r['price'] for r in rows if r['size_kg'] == BAG]
        out.append(dict(slug=slug, en=name, th=th or name, rows=sorted(rows, key=lambda r: r['npk']),
                        n=len(rows), nf=len({r['npk'] for r in rows}), low=min(full) if full else None, high=max(full) if full else None,
                        premium=round(sum(prem) / len(prem), 1) if len(prem) >= 2 else None))
    return out


def faq(F, lang, blendt=None, rice=None, afford=None):
    """Questions people search, answered from today's numbers. Used for the page and FAQPage JSON-LD."""
    th = lang == 'th'
    by = {f['npk']: f for f in F.get('formulas', [])}
    out = []
    u = by.get('46-0-0')
    if u:
        out.append(('ปุ๋ยยูเรีย 46-0-0 ราคากระสอบละเท่าไร' if th else 'How much is a bag of urea (46-0-0) in Thailand?',
                    (f"ราคาหน้าร้านราว {u['median']:,} บาทต่อกระสอบ 50 กก. (พบ {u['low']:,}–{u['high']:,} บาท) ราคาแนะนำของแต่ละจังหวัดดูได้ที่กรมการค้าภายใน" if th else
                     f"About {u['median']:,} baht for a 50 kg bag at shops ({u['low']:,}–{u['high']:,} baht seen). Each province's recommended retail price is published by the Department of Internal Trade.")))
    a = by.get('16-20-0')
    if a:
        out.append(('ปุ๋ย 16-20-0 ใช้กับอะไร ราคาเท่าไร' if th else 'What is 16-20-0 used for, and what does it cost?',
                    (f"เป็นปุ๋ยรองพื้นนาข้าวในดินเหนียวตามคำแนะนำของกรมการข้าว อัตรา 25-35 กก./ไร่ ราคาหน้าร้านราว {a['median']:,} บาทต่อกระสอบ" if th else
                     f"It is the Rice Department's recommended basal fertilizer for rice on clay soils, at 25-35 kg per rai. Shops charge about {a['median']:,} baht a bag.")))
    n = (F.get('nutrients') or {}).get('N') or []
    if n:
        out.append(('ปุ๋ยสูตรไหนให้ไนโตรเจนถูกที่สุด' if th else 'Which fertilizer gives the cheapest nitrogen?',
                    (f"ตอนนี้ {n[0]['npk']} ให้ไนโตรเจนราว {n[0]['baht_per_kg']:.1f} บาทต่อกก. รองลงมาคือ " + ', '.join(f"{x['npk']} {x['baht_per_kg']:.1f}" for x in n[1:3]) + " บาท" if th else
                     f"Right now {n[0]['npk']}, at about {n[0]['baht_per_kg']:.1f} baht per kg of nitrogen, then " + ', '.join(f"{x['npk']} at {x['baht_per_kg']:.1f}" for x in n[1:3]) + '.')))
    if blendt and blendt.get('best'):
        b = blendt['best']
        out.append(('ผสมปุ๋ยใช้เองถูกกว่าซื้อสำเร็จไหม' if th else 'Is it cheaper to blend your own fertilizer?',
                    (f"มักถูกกว่า ที่ราคาวันนี้ สูตร {b['npk']} ผสมจากยูเรีย DAP และโพแทส ถูกกว่าซื้อสำเร็จราว {b['saving']:,} บาทต่อกระสอบ ยังไม่รวมค่าแรงผสม" if th else
                     f"Usually. At today's prices, mixing {b['npk']} from urea, DAP and potash costs about {b['saving']:,} baht a bag less than buying it ready-made, before mixing labour.")))
    if rice and rice.get('examples'):
        c = [e['cost'] for e in rice['examples']]
        out.append(('ใส่ปุ๋ยนาข้าว ต้นทุนไร่ละเท่าไร' if th else 'How much does fertilizer for rice cost per rai?',
                    (f"ตามอัตราที่กรมการข้าวแนะนำ ค่าปุ๋ยเคมีราว {min(c):,}–{max(c):,} บาทต่อไร่ต่อฤดู ขึ้นกับพันธุ์ข้าวและชนิดดิน" if th else
                     f"At the Rice Department's recommended rates, about {min(c):,}–{max(c):,} baht per rai per season, depending on variety and soil.")))
    if afford:
        out.append(('ตอนนี้ปุ๋ยแพงเมื่อเทียบกับราคาข้าวไหม' if th else 'Is fertilizer expensive compared with rice right now?',
                    (f"ใช่ ข้าวขาว 5% 1 ตันซื้อยูเรียได้ {afford['current']:.2f} ตัน ต่ำกว่าค่ากลางตั้งแต่ปี 2503 ที่ {afford['median']:.2f} ตัน มีเพียงราว {afford['pct']}% ของเดือนตั้งแต่ปี 2503 ที่ต่ำกว่าหรือเท่านี้" if th else
                     f"Yes. A tonne of Thai 5% rice buys {afford['current']:.2f} tonnes of urea, against a median of {afford['median']:.2f} since 1960; only about {afford['pct']}% of months since 1960 were as low or lower.")))
    out.append(('ร้านขายปุ๋ยแพงเกินไป แจ้งได้ที่ไหน' if th else 'Where can I report a shop overcharging for fertilizer?',
                ('ตรวจราคาแนะนำของจังหวัดที่เว็บไซต์กรมการค้าภายใน และแจ้งสำนักงานพาณิชย์จังหวัด หรือสายด่วน 1569' if th else
                 "Check your province's recommended price on the Department of Internal Trade website, then contact the provincial commerce office or the 1569 hotline.")))
    return out


# ---------------------------------------------------------------- world benchmark pages
WORLD_PAGES = [  # slug, World Bank series id, the World Bank's own name for the series
    dict(slug='urea', key='urea', wb='Urea, E. Europe', thai='46-0-0',
         en='Urea', th='ยูเรีย', title_en='Urea price', title_th='ราคายูเรียตลาดโลก'),
    dict(slug='dap', key='dap', wb='DAP', thai='18-46-0', en='DAP (diammonium phosphate)', th='DAP (ไดแอมโมเนียมฟอสเฟต)',
         title_en='DAP price', title_th='ราคา DAP ตลาดโลก'),
    dict(slug='potash', key='kcl', wb='Potassium chloride', thai='0-0-60', en='Potash (potassium chloride)', th='โพแทสเซียมคลอไรด์',
         title_en='Potash price', title_th='ราคาโพแทสตลาดโลก'),
    dict(slug='tsp', key='tsp', wb='TSP', thai=None, en='TSP (triple superphosphate)', th='TSP (ทริปเปิลซูเปอร์ฟอสเฟต)',
         title_en='TSP price', title_th='ราคา TSP ตลาดโลก'),
    dict(slug='phosphate-rock', key='rock', wb='Phosphate rock', thai=None, en='Phosphate rock', th='หินฟอสเฟต',
         title_en='Phosphate rock price', title_th='ราคาหินฟอสเฟตตลาดโลก'),
]


def world_fill(wp, F):
    """Facts for one world benchmark page, from fertilizer.json."""
    import statistics
    w = (F.get('world') or {}).get(wp['key'])
    if not w or len(w.get('hist') or []) < 24:
        return None
    h = w['hist']
    d = dict(h)
    last_d, last_v = h[-1]
    y, m = int(last_d[:4]), int(last_d[5:7])
    m1 = d.get(f"{y if m > 1 else y - 1}-{(m - 1 or 12):02d}-01")
    years = {}
    for a, v in h:
        years.setdefault(int(a[:4]), []).append(v)
    yrows = [dict(year=yy, avg=round(statistics.mean(v)), lo=round(min(v)), hi=round(max(v)), months=len(v)) for yy, v in sorted(years.items(), reverse=True)]
    for i, r in enumerate(yrows[:-1]):
        r['chg'] = round((r['avg'] / yrows[i + 1]['avg'] - 1) * 100, 1)
    hi = max(h, key=lambda p: p[1]); lo = min(h, key=lambda p: p[1])
    th_f = next((f for f in F.get('formulas', []) if f['npk'] == wp['thai']), None) if wp['thai'] else None
    return dict(wp=wp, w=w, date=last_d, usd=last_v, m1=round((last_v / m1 - 1) * 100, 1) if m1 else None, y1=w.get('y1'),
                ath=hi, atl=lo, first=h[0][0], months=list(reversed(h[-24:])), years=yrows, thai=th_f,
                avg10=round(statistics.mean(v for a, v in h if int(a[:4]) > y - 10)))


def seasonality(F, key, start=2006, end=None):
    """Average % gap between each calendar month and its year's average, over complete years [start, end].
    Small, noisy numbers: shown with the spread so nobody reads more into them than is there."""
    import statistics
    h = ((F.get('world') or {}).get(key) or {}).get('hist') or []
    years = {}
    for d, v in h:
        years.setdefault(int(d[:4]), {})[int(d[5:7])] = v
    full = sorted(y for y, ms in years.items() if len(ms) == 12 and y >= start and (end is None or y <= end))
    if len(full) < 8:
        return None
    dev = {m: [] for m in range(1, 13)}
    for y in full:
        avg = statistics.mean(years[y].values())
        for m, v in years[y].items():
            dev[m].append((v / avg - 1) * 100)
    rows = [dict(m=m, avg=round(statistics.mean(dev[m]), 1), below=sum(1 for x in dev[m] if x < 0)) for m in range(1, 13)]
    lo = min(rows, key=lambda r: r['avg']); hi = max(rows, key=lambda r: r['avg'])
    return dict(rows=rows, years=len(full), first=full[0], last=full[-1], low=lo, high=hi)


def season_svg(s, lang):
    """A 12-bar chart of the monthly pattern (bars below zero = cheaper than the year's average)."""
    if not s:
        return ''
    TH = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
    EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    W, H, L, T, B = 760, 260, 70, 16, 34
    m = max(abs(r['avg']) for r in s['rows']) or 1
    m = (int(m) // 2 + 1) * 2
    bw = (W - L - 10) / 12
    Y = lambda v: T + (1 - (v + m) / (2 * m)) * (H - T - B)
    o = [f'<svg class="px-svg px-static" viewBox="0 0 {W} {H}" role="img" aria-label="{"รูปแบบราคาตามเดือน" if lang == "th" else "Price pattern by month"}">']
    for v in (-m, 0, m):
        o.append(f'<line class="px-grid" x1="{L}" x2="{W - 10}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                 f'<text class="px-tick" x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{(format(v, "+d") if v else "0")}%</text>')
    for i, r in enumerate(s['rows']):
        x = L + i * bw + bw * 0.15
        y0, y1 = Y(0), Y(r['avg'])
        cls = 'fs-lo' if r['avg'] < 0 else 'fs-hi'
        o.append(f'<rect class="{cls}" x="{x:.1f}" y="{min(y0, y1):.1f}" width="{bw * 0.7:.1f}" height="{abs(y1 - y0):.1f}"><title>{(TH if lang == "th" else EN)[i]} {r["avg"]:+.1f}%</title></rect>')
        o.append(f'<text class="px-tick fs-m" x="{x + bw * 0.35:.1f}" y="{H - 10}" text-anchor="middle">{(TH if lang == "th" else EN)[i]}</text>')
    o.append('</svg>')
    return ''.join(o)


# ---------------------------------------------------------------- Thai prices from every source (fert_local)

SRC = {'dit': ('DIT recommended price (77 provinces)', 'ราคาแนะนำ กรมการค้าภายใน (77 จังหวัด)'),
       'coop': ('Tha Bo co-op, Nong Khai', 'สหกรณ์การเกษตรท่าบ่อ หนองคาย'),
       'report': ('Provincial commerce office and news checks', 'สำนักงานพาณิชย์จังหวัดและข่าว'),
       'survey': ('rice.ag shop survey', 'สำรวจหน้าร้านของ rice.ag')}
BRAND_NAMES = {'rabbit': ('Rabbit', 'กระต่าย'), 'cow-plough': ('Cow Head & Plough', 'หัววัวคันไถ'), 'top-one': ('Top One', 'ท็อปวัน'),
               'rung-arun': ('Rung Arun', 'รุ่งอรุณ'), 'crown': ('Crown', 'มงกุฎ'), 'yara': ('Yara', 'ยาร่า'), 'entec': ('Entec', 'เอ็นเทค'),
               'other': ('Other brand', 'ยี่ห้ออื่น')}


def bname(slug, lang, extra=None):
    n = (extra or {}).get(slug) or BRAND_NAMES.get(slug)
    if not n:
        return slug
    return n[1] if lang == 'th' else n[0]


def tracker_svg(points, lang, label=''):
    """Thai bag prices for one formula, every source on one time axis. points from fert_local.tracker."""
    import datetime as _dt
    pts = [p for p in points if p.get('low')]
    if len(pts) < 2:
        return ''
    d = lambda s: _dt.date.fromisoformat(s[:10])
    t0 = min(d(p['date']) for p in pts).replace(day=1)
    t1 = max(_dt.date.today(), max(d(p['date']) for p in pts))
    W, H, M = 760, 330, dict(l=70, r=20, t=34, b=40)
    lo = min(p['low'] for p in pts); hi = max(p.get('high') or p['low'] for p in pts)
    pad = max(40, (hi - lo) * 0.1); lo -= pad; hi += pad
    step = 100 if hi - lo < 900 else 200
    ticks = list(range(int(lo // step + 1) * step, int(hi) + 1, step))
    span = (t1 - t0).days or 1
    X = lambda t: M['l'] + (t - t0).days / span * (W - M['l'] - M['r'])
    Y = lambda v: M['t'] + (1 - (v - lo) / (hi - lo)) * (H - M['t'] - M['b'])
    o = [f'<svg class="px-svg px-static fl-track" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">']
    for v in ticks:
        o.append(f'<line class="px-grid" x1="{M["l"]}" x2="{W - M["r"]}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                 f'<text class="px-tick" x="{M["l"] - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:,}</text>')
    mon_th = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
    m = t0; every = 1 if span < 400 else 3
    while m <= t1:
        if (m.month - 1) % every == 0:
            lab = mon_th[m.month - 1] if lang == 'th' else m.strftime('%b')
            if m.month == 1 or m == t0:
                lab += f" {(m.year + 543) % 100 if lang == 'th' else m.year}" if lang == 'th' else f' {m.year}'
            o.append(f'<text class="px-tick" x="{X(m):.1f}" y="{H - 14}" text-anchor="middle">{lab}</text>')
        m = (m.replace(day=28) + _dt.timedelta(days=4)).replace(day=1)
    o.append(f'<line class="px-axis" x1="{M["l"]}" x2="{W - M["r"]}" y1="{H - M["b"]}" y2="{H - M["b"]}"/>')
    o.append(f'<text class="px-tick" x="4" y="20">{"บาท/กระสอบ 50 กก." if lang == "th" else "baht per 50 kg bag"}</text>')
    style = {'dit': 1, 'report': 2, 'coop': 3, 'survey': 4}
    for p in pts:
        x = X(d(p['date'])); k = style[p['src']]; h = p.get('high') or p['low']
        tip = f"{p['date']} · {bname(p['src'], lang, {s: v for s, v in SRC.items()})}: {p['low']:,}{('–' + format(h, ',')) if h != p['low'] else ''}"
        if p['src'] == 'dit':
            o.append(f'<rect class="fl-dit" x="{x - 6:.1f}" y="{Y(h):.1f}" width="12" height="{max(2, Y(p["low"]) - Y(h)):.1f}" style="fill:var(--s{k})"><title>{tip}</title></rect>')
        elif p['src'] == 'report':
            o.append(f'<g style="stroke:var(--s{k})"><title>{tip}</title><line class="fl-rng" x1="{x:.1f}" x2="{x:.1f}" y1="{Y(h):.1f}" y2="{Y(p["low"]):.1f}"/>'
                     f'<circle r="3" cx="{x:.1f}" cy="{Y((p["low"] + h) / 2):.1f}" style="fill:var(--s{k})"/></g>')
        elif p['src'] == 'coop':
            o.append(f'<circle class="fl-coop" r="5" cx="{x:.1f}" cy="{Y(p["low"]):.1f}" style="fill:var(--s{k})"><title>{tip}</title></circle>')
        else:
            o.append(f'<path d="M{x:.1f} {Y(p["low"]) - 7:.1f}l7 7-7 7-7-7z" style="fill:var(--s{k})"><title>{tip}</title></path>')
    o.append('</svg>')
    used = [s for s in ('dit', 'report', 'coop', 'survey') if any(p['src'] == s for p in pts)]
    legend = ''.join(f'<li><i style="background:var(--s{style[s]})"></i>{SRC[s][1] if lang == "th" else SRC[s][0]}</li>' for s in used)
    return ''.join(o) + f'<ul class="px-key">{legend}</ul>'


def province_pages(F):
    L = F.get('local') or {}
    return (L.get('dit') or {}).get('provinces') or []


def province_fill(row, F, lang):
    """Context for /fertilizer/province/<slug>/."""
    L = F['local']; dit = L['dit']; rows = dit['provinces']
    th = lang == 'th'
    order = ['46-0-0', '16-20-0', '15-15-15', '21-0-0', '0-0-60', '18-46-0']
    table = []
    for f in order:
        bs = row['prices'].get(f)
        if not bs:
            continue
        nat = dit['national'][f]
        items = sorted(bs.items(), key=lambda kv: kv[1])
        table.append(dict(npk=f, items=[dict(brand=b, name=bname(b, lang), price=p) for b, p in items],
                          low=items[0][1], high=items[-1][1], nat_low=nat['low'], nat_high=nat['high']))
    deltas = sorted({r['delta'] for r in rows})
    rank = sum(1 for r in rows if r['delta'] < row['delta']) + 1
    same = [r for r in rows if r['region'] == row['region'] and r['slug'] != row['slug']]
    reports = [r for r in L.get('reports', []) if r.get('province') == row['slug']]
    coop = L.get('coop') if (L.get('coop') or {}).get('province') == row['slug'] else None
    urea = next((t for t in table if t['npk'] == '46-0-0'), None)
    name = row['th'] if th else row['en']
    lead = ((f"ราคาจำหน่ายปลีกแนะนำของกรมการค้าภายใน จ.{name}: ยูเรีย 46-0-0 กระสอบละ {urea['low']:,}–{urea['high']:,} บาท แล้วแต่ยี่ห้อ"
             if th else f"DIT recommended retail price for {name}: urea 46-0-0 at {urea['low']:,}–{urea['high']:,} baht a bag, depending on brand")
            if urea else '')
    return dict(row=row, name=name, table=table, rank=rank, n=len(rows), cheapest_delta=deltas[0], dearest_delta=deltas[-1],
                region=sorted(same, key=lambda r: r['delta'])[:12], reports=reports, coop=coop, lead=lead)
