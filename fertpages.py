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
