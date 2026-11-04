"""Server-rendered price content for rice.ag.

Everything here is computed at build time from src/static/data/prices.json, so the
numbers are in the HTML that search engines read (prices.js still draws the
interactive charts on the homepage and replaces the table with the same numbers).

- stats(): latest value, date, frequency and 1-month / 1-year change for a series
  (same rules as prices.js, so the server table and the JS table agree)
- HUBS: one page per origin country and per rice type, at /prices/<slug>/
- market_verdict(): the plain-language "how is rice doing" paragraph on the homepage
- svg_chart(): a static multi-line chart for the hub pages (no JavaScript needed)

To add a hub page: add an entry to HUBS. Its series ids come from pipeline/catalog.py.
"""
import datetime, json, math
from pathlib import Path

ROOT = Path(__file__).parent
EPOCH = datetime.date(1970, 1, 1)
TH_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
TH_MONTHS_LONG = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม', 'สิงหาคม',
                  'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
SRCNAME = {'trea': 'TREA', 'fao': 'FAO', 'wb': 'World Bank', 'usda': 'USDA', 'dit': 'DIT'}
SRCNAME_TH = dict(SRCNAME, dit='กรมการค้าภายใน', wb='ธนาคารโลก')
STALE_DAYS = 120  # older than this, a row says the source publishes late


# ---------------------------------------------------------------- data

def load_prices():
    try:
        return json.loads((ROOT / 'src/static/data/prices.json').read_text(encoding='utf-8'))
    except Exception:
        return {'series': {}, 'groups': [], 'sources': {}}


def load_india():
    try:
        return json.loads((ROOT / 'data/brief_notes.json').read_text(encoding='utf-8')).get('india', {})
    except Exception:
        return {}


def day(n):
    return EPOCH + datetime.timedelta(days=int(n))


def freq_of(s):
    d = s['d']; n = len(d)
    if n < 3:
        return 'monthly'
    gap = (d[-1] - d[max(0, n - 10)]) / min(9, n - 1)
    return 'daily' if gap < 4 else 'weekly' if gap < 12 else 'monthly'


def _tol(s):
    return {'daily': 7, 'weekly': 14}.get(freq_of(s), 45)


def _at(s, t, tol, arr):
    d = s['d']
    if not d or d[0] > t:
        return None
    lo, hi = 0, len(d) - 1
    while lo < hi:
        mid = (lo + hi + 1) >> 1
        if d[mid] <= t: lo = mid
        else: hi = mid - 1
    return arr[lo] if t - d[lo] <= tol and arr[lo] else None


def change(s, days, arr=None):
    arr = arr or s['v']
    prev = _at(s, s['d'][-1] - days, max(_tol(s), days * 0.25), arr)
    return (arr[-1] / prev - 1) * 100 if prev else None


def stats(data, sid):
    s = data['series'].get(sid)
    if not s or not s.get('d'):
        return None
    last = day(s['d'][-1])
    thb = s.get('thb') or []
    # Thai domestic prices are set in baht, so their % changes are in baht (USD moves add FX noise)
    base = thb if thb and not s['market']['en'].startswith('Export') else None
    return dict(id=sid, s=s, en=s['en'], th=s['th'], usd=s['v'][-1], thb=thb[-1] if thb else None,
                date=last, freq=freq_of(s), m1=change(s, 30, base), y1=change(s, 365, base),
                m1_thb=change(s, 30, thb) if thb else None, y1_thb=change(s, 365, thb) if thb else None,
                stale=(datetime.date.today() - last).days > STALE_DAYS,
                paddy=s.get('basis') == 'paddy', export=s['market']['en'].startswith('Export'),
                src=s.get('src', []))


# ---------------------------------------------------------------- formatting

def num(v):
    return f'{v:,.0f}' if v is not None else '–'


def pct(v):
    if v is None:
        return '–'
    return '0.0%' if round(v, 1) == 0 else f'{v:+.1f}%'


def fdate(d, lang='en', monthly=False):
    if monthly:
        return f'{TH_MONTHS_LONG[d.month - 1]} {d.year + 543}' if lang == 'th' else d.strftime('%B %Y')
    return f'{d.day} {TH_MONTHS[d.month - 1]} {d.year + 543}' if lang == 'th' else d.strftime('%-d %b %Y').lstrip('0')


def move(v, lang):
    """'up 3.8%' / 'ขึ้น 3.8%'; tiny moves read as unchanged."""
    if v is None:
        return None
    if abs(v) < 0.05:
        return 'ทรงตัว' if lang == 'th' else 'unchanged'
    if lang == 'th':
        return f"{'เพิ่มขึ้น' if v > 0 else 'ลดลง'} {abs(v):.1f}%"
    return f"{'up' if v > 0 else 'down'} {abs(v):.1f}%"


def when(st, lang):
    return fdate(st['date'], lang, monthly=st['freq'] == 'monthly')


def srcnames(st, lang):
    names = SRCNAME_TH if lang == 'th' else SRCNAME
    return ', '.join(names.get(k, k) for k in st['src'])


# ---------------------------------------------------------------- sentences

def price_sentence(st, lang, baht=False):
    """One factual sentence: price, basis, date, 1-month and 1-year moves."""
    if not st:
        return ''
    name = st['th'] if lang == 'th' else st['en']
    m1 = move(st['m1_thb'] if baht else st['m1'], lang)
    y1 = move(st['y1_thb'] if baht else st['y1'], lang)
    d = when(st, lang)
    monthly = st['freq'] == 'monthly'
    if lang == 'th':
        price = f"{num(st['thb'])} บาทต่อตัน (ราว {num(st['usd'])} ดอลลาร์)" if baht and st['thb'] else f"{num(st['usd'])} ดอลลาร์สหรัฐต่อตัน"
        basis = 'ราคาส่งออก FOB' if st['export'] else 'ราคาในประเทศ'
        out = f"{name} {basis} {price} {'ในเดือน' if monthly else 'ณ วันที่'} {d}"
        moves = [x for x in (m1 and f'{m1} ในรอบเดือน', y1 and f'{y1} ในรอบปี') if x]
        out += (' ' + ' และ'.join(moves)) if moves else ''
        if st['stale']:
            out += f" ตัวเลขนี้เป็นข้อมูลล่าสุดที่เผยแพร่ ({srcnames(st, lang)} เผยแพร่ช้ากว่าปัจจุบันหลายเดือน)"
        return out
    basis = 'FOB export' if st['export'] else 'domestic price'
    price = (f"฿{num(st['thb'])} per tonne ({basis}, about ${num(st['usd'])})" if baht and st['thb']
             else f"${num(st['usd'])} per tonne ({basis})")
    out = f"{name} was {price} {'in' if monthly else 'on'} {d}"
    moves = [x for x in (m1 and f'{m1} over the month', y1 and f'{y1} over the year') if x]
    out += (', ' + ' and '.join(moves)) if moves else ''
    out += '.'
    if st['stale']:
        out += f" This is the latest published figure: {srcnames(st, lang)} releases these prices several months late."
    return out


def direction(v, lang):
    if v is None:
        return 'ไม่ชัดเจน' if lang == 'th' else 'unclear'
    if v >= 2: return 'ปรับขึ้น' if lang == 'th' else 'rising'
    if v <= -2: return 'ปรับลง' if lang == 'th' else 'falling'
    return 'ทรงตัว' if lang == 'th' else 'steady'


def market_verdict(data, brief, lang):
    """The homepage summary: where prices are, which way they are moving, what to watch.
    Returns a list of sentences (empty if there is no data)."""
    th5, vn5, paddy = (stats(data, k) for k in ('th_5', 'vn_5', 'dit_paddy'))
    if not th5:
        return []
    out = []
    dirn = direction(th5['m1'], lang)
    if lang == 'th':
        out.append(f"ราคาส่งออกข้าว{dirn}ในเดือนนี้")
    else:
        out.append(f"Rice export prices are {dirn} this month.")
    out.append(price_sentence(th5, lang).rstrip('.') + ('' if lang == 'th' else '.'))
    if vn5:
        if lang == 'th':
            out.append(f"ข้าวขาว 5% เวียดนาม {num(vn5['usd'])} ดอลลาร์ต่อตันในเดือน{fdate(vn5['date'], 'th', True)} ({move(vn5['y1'], 'th') or '–'} ในรอบปี)")
        else:
            out.append(f"Viet Nam 5% was ${num(vn5['usd'])} in {fdate(vn5['date'], 'en', True)} ({move(vn5['y1'], 'en') or 'n/a'} on the year).")
    if paddy and paddy['thb']:
        if lang == 'th':
            out.append(f"ข้าวเปลือกเจ้าในไทย {num(paddy['thb'])} บาทต่อตัน ณ {fdate(paddy['date'], 'th')} ({move(paddy['y1_thb'], 'th') or '–'} ในรอบปี)")
        else:
            out.append(f"Thai white paddy was ฿{num(paddy['thb'])} per tonne on {fdate(paddy['date'])} ({move(paddy['y1_thb'], 'en') or 'n/a'} on the year).")
    oni = next((i for i in (brief or {}).get('indicators', []) if i.get('id') == 'oni'), None)
    if oni and oni.get('value') is not None:
        v = oni['value']
        if v >= 0.5:
            out.append(f"เอลนีโญยังมีกำลัง (ONI {v:.2f}) เป็นความเสี่ยงต่อผลผลิตข้าวในเอเชียฤดูหน้า" if lang == 'th' else
                       f"El Niño is active (ONI {v:.2f}), a risk to next season's Asian harvests.")
        elif v <= -0.5:
            out.append(f"อยู่ในภาวะลานีญา (ONI {v:.2f}) ซึ่งมักเอื้อต่อปริมาณฝนในเอเชีย" if lang == 'th' else
                       f"La Niña conditions (ONI {v:.2f}) usually mean ample monsoon rain in Asia.")
    st = load_india().get('status')
    if st in ('open', 'watch', 'restricted'):
        out.append({'open': {'en': "India's rice exports are open.", 'th': 'อินเดียส่งออกข้าวได้ตามปกติ'},
                    'watch': {'en': 'India may restrict rice exports: watch closely.', 'th': 'อินเดียอาจจำกัดการส่งออกข้าว ควรจับตา'},
                    'restricted': {'en': 'India is restricting rice exports.', 'th': 'อินเดียกำลังจำกัดการส่งออกข้าว'}}[st][lang])
    return out


# ---------------------------------------------------------------- static chart

def _nice(lo, hi, n=5):
    span = hi - lo or 1
    step = 10 ** math.floor(math.log10(span / n))
    err = span / n / step
    step *= 10 if err >= 7.5 else 5 if err >= 3.5 else 2 if err >= 1.5 else 1
    v, out = math.ceil(lo / step) * step, []
    while v <= hi + 1e-9:
        out.append(v); v += step
    return out


def svg_chart(data, ids, baht=False, years=5, label='', lang='en'):
    """A static, accessible multi-line SVG of the last `years` years (USD, or baht)."""
    S = data['series']
    ids = [i for i in ids if i in S and S[i].get('d')]
    if not ids:
        return ''
    W, H, M = 760, 340, dict(l=74, r=34, t=26, b=34)
    tmax = max(S[i]['d'][-1] for i in ids)
    tmin = tmax - int(years * 365.25)
    lines = []
    for k, sid in enumerate(ids):
        s = S[sid]; arr = s.get('thb') if baht else s['v']
        if not arr:
            continue
        pts = [(t, v) for t, v in zip(s['d'], arr) if t >= tmin and v]
        if len(pts) > 260:  # bucket-average long daily series to keep the HTML small
            b = math.ceil(len(pts) / 260)
            pts = [(pts[j + len(pts[j:j + b]) // 2][0], sum(v for _, v in pts[j:j + b]) / len(pts[j:j + b]))
                   for j in range(0, len(pts), b)]
        if pts:
            lines.append((k, sid, pts))
    if not lines:
        return ''
    lo = min(v for _, _, p in lines for _, v in p); hi = max(v for _, _, p in lines for _, v in p)
    pad = (hi - lo) * 0.08 or 10
    ticks = _nice(max(0, lo - pad), hi + pad)
    lo, hi = min(max(0, lo - pad), ticks[0]), max(hi + pad, ticks[-1])
    X = lambda t: M['l'] + (t - tmin) / ((tmax - tmin) or 1) * (W - M['l'] - M['r'])
    Y = lambda v: M['t'] + (1 - (v - lo) / ((hi - lo) or 1)) * (H - M['t'] - M['b'])
    o = [f'<svg class="px-svg px-static" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">']
    for v in ticks:
        o.append(f'<line class="px-grid" x1="{M["l"]}" x2="{W - M["r"]}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                 f'<text class="px-tick" x="{M["l"] - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{num(v)}</text>')
    y0 = day(tmin).year + 1
    for yr in range(y0, day(tmax).year + 1):
        t = (datetime.date(yr, 1, 1) - EPOCH).days
        o.append(f'<text class="px-tick" x="{X(t):.1f}" y="{H - 8}" text-anchor="middle">{yr + 543 if lang == "th" else yr}</text>')
    o.append(f'<line class="px-axis" x1="{M["l"]}" x2="{W - M["r"]}" y1="{H - M["b"]}" y2="{H - M["b"]}"/>')
    unit = ('บาท/ตัน' if lang == 'th' else 'THB/t') if baht else ('USD/ตัน' if lang == 'th' else 'USD/t')
    o.append(f'<text class="px-tick" x="4" y="12">{unit}</text>')
    for k, sid, pts in lines:
        d = ''.join(f"{'L' if j else 'M'}{X(t):.1f} {Y(v):.1f}" for j, (t, v) in enumerate(pts))
        o.append(f'<path class="px-line" style="stroke:var(--s{k + 1})" d="{d}"/>')
        t, v = pts[-1]
        o.append(f'<circle class="px-dot" r="3.5" cx="{X(t):.1f}" cy="{Y(v):.1f}" style="fill:var(--s{k + 1})"/>')
    o.append('</svg>')
    legend = ''.join(f'<li><i style="background:var(--s{k + 1})"></i>{(S[sid]["th"] if lang == "th" else S[sid]["en"])}</li>'
                     for k, sid, _ in lines)
    return ''.join(o) + f'<ul class="px-key">{legend}</ul>'


# ---------------------------------------------------------------- hub pages
# title/desc may use {p} (primary price, USD), {pt} (primary price, baht) and {d} (its date).

HUBS = [
    dict(slug='thailand', kind='origin', primary='th_5',
         series=['th_5', 'th_hm', 'th_jas', 'th_glu', 'th_pb', 'th_100b', 'th_25', 'th_15', 'th_a1s', 'th_hmbrk'],
         chart=['th_5', 'th_hm', 'th_jas', 'th_glu', 'th_pb', 'th_a1s'],
         name={'en': 'Thailand', 'th': 'ไทย'},
         h1={'en': 'Thai rice prices today', 'th': 'ราคาข้าวไทยวันนี้'},
         title={'en': 'Thai rice price today: white 5% ${p}/t, Hom Mali, jasmine, glutinous | rice.ag',
                'th': 'ราคาข้าวไทยวันนี้: ข้าวขาว 5% {p} ดอลลาร์/ตัน หอมมะลิ ข้าวหอม ข้าวเหนียว | rice.ag'},
         desc={'en': 'Thai rice export prices updated weekly: white rice 5% ${p}/t FOB Bangkok ({d}), plus Hom Mali, Pathum jasmine, glutinous, parboiled and broken rice, with history back to 1960. Free CSV.',
               'th': 'ราคาส่งออกข้าวไทยอัปเดตทุกสัปดาห์: ข้าวขาว 5% {p} ดอลลาร์/ตัน FOB กรุงเทพฯ ({d}) พร้อมข้าวหอมมะลิ ข้าวหอมปทุมธานี ข้าวเหนียว ข้าวนึ่ง และปลายข้าว ข้อมูลย้อนหลังถึงปี 2503 ดาวน์โหลด CSV ฟรี'},
         body={'en': ["Thailand is one of the world's two or three largest rice exporters, and one of the few that publishes a full set of export quotes every week: the Thai Rice Exporters Association (TREA) posts FOB Bangkok prices each Wednesday, and this page shows them alongside FAO and World Bank history.",
                      "Thai prices tend to sit above Viet Nam, India and Pakistan for the same grade, because of quality, a stronger currency and a smaller exportable surplus. Hom Mali (Thai jasmine from the northeast) is a separate, premium market priced per crop year."],
               'th': ['ไทยเป็นหนึ่งในสองถึงสามประเทศผู้ส่งออกข้าวรายใหญ่ที่สุดของโลก และเป็นหนึ่งในไม่กี่ประเทศที่เผยแพร่ราคาส่งออกครบทุกชนิดทุกสัปดาห์ สมาคมผู้ส่งออกข้าวไทย (TREA) ประกาศราคา FOB กรุงเทพฯ ทุกวันพุธ หน้านี้แสดงราคาดังกล่าวพร้อมข้อมูลย้อนหลังจาก FAO และธนาคารโลก',
                      'ราคาข้าวไทยมักสูงกว่าเวียดนาม อินเดีย และปากีสถานในข้าวเกรดเดียวกัน เพราะคุณภาพ ค่าเงินที่แข็งกว่า และปริมาณส่วนเกินเพื่อส่งออกที่น้อยกว่า ข้าวหอมมะลิจากภาคอีสานเป็นตลาดพรีเมียมแยกต่างหาก และกำหนดราคาตามปีการผลิต']},
         drivers={'en': ["The baht: exporters price in dollars, so a stronger baht pushes dollar quotes up.",
                         "India's export policy: when India restricts exports, buyers turn to Thailand and Viet Nam.",
                         "Harvest timing: the main crop is cut from November to January, when paddy supply peaks.",
                         "Rainfall and El Niño, which affect the second crop and next year's planting."],
                  'th': ['ค่าเงินบาท: ผู้ส่งออกเสนอราคาเป็นดอลลาร์ บาทแข็งจึงดันราคาดอลลาร์ขึ้น',
                         'นโยบายส่งออกของอินเดีย: เมื่ออินเดียจำกัดการส่งออก ผู้ซื้อหันมาซื้อจากไทยและเวียดนาม',
                         'ช่วงเก็บเกี่ยว: ข้าวนาปีเก็บเกี่ยวช่วงพฤศจิกายนถึงมกราคม ซึ่งข้าวเปลือกออกสู่ตลาดมากที่สุด',
                         'ปริมาณฝนและเอลนีโญ ที่กระทบข้าวนาปรังและการเพาะปลูกปีถัดไป']}),
    dict(slug='thailand-paddy', kind='origin', primary='dit_paddy', baht=True,
         series=['dit_paddy', 'dit_paddy_supan', 'dit_paddy_hm', 'dit_paddy_pathum', 'dit_paddy_glu', 'dit_w5', 'dit_hm', 'dit_glu'],
         chart=['dit_paddy', 'dit_paddy_hm', 'dit_paddy_pathum', 'dit_paddy_glu'],
         name={'en': 'Thai paddy', 'th': 'ข้าวเปลือกไทย'},
         h1={'en': 'Thai paddy prices today', 'th': 'ราคาข้าวเปลือกวันนี้'},
         title={'en': 'Thai paddy price today: white paddy ฿{pt}/t, Hom Mali, glutinous, Pathum | rice.ag',
                'th': 'ราคาข้าวเปลือกวันนี้: ข้าวเปลือกเจ้า {pt} บาท/ตัน หอมมะลิ ข้าวเหนียว ปทุมธานี | rice.ag'},
         desc={'en': 'Daily Thai paddy and wholesale rice prices from the Department of Internal Trade: white paddy ฿{pt} per tonne ({d}), Hom Mali, Pathum Thani and glutinous paddy, Bangkok wholesale. Baht and US dollars.',
               'th': 'ราคาข้าวเปลือกและข้าวสารขายส่งรายวันจากกรมการค้าภายใน: ข้าวเปลือกเจ้า {pt} บาท/ตัน ({d}) ข้าวเปลือกหอมมะลิ ปทุมธานี ข้าวเหนียว และราคาขายส่ง กทม. เป็นบาทและดอลลาร์'},
         body={'en': ["These are Thailand's official daily paddy (unmilled rice) and Bangkok wholesale prices, published by the Department of Internal Trade on business days. Paddy prices are what mills and traders pay farmers, so they move before export prices do.",
                      "A tonne of paddy mills to roughly 0.6 to 0.7 tonnes of rice, so paddy is always cheaper per tonne than milled rice. Prices assume standard moisture; wet paddy straight from the harvester is bought at a discount."],
               'th': ['ราคาข้าวเปลือกและราคาข้าวสารขายส่งในกรุงเทพฯ รายวันอย่างเป็นทางการของไทย จากกรมการค้าภายใน ประกาศทุกวันทำการ ราคาข้าวเปลือกคือราคาที่โรงสีและพ่อค้าจ่ายให้เกษตรกร จึงมักเคลื่อนไหวก่อนราคาส่งออก',
                      'ข้าวเปลือก 1 ตันสีได้ข้าวสารราว 0.6–0.7 ตัน ราคาข้าวเปลือกต่อตันจึงต่ำกว่าข้าวสารเสมอ ราคาเป็นราคาที่ความชื้นมาตรฐาน ข้าวเปลือกสดจากรถเกี่ยวจะถูกหักราคาตามความชื้น']},
         drivers={'en': ["Export demand: when Thai FOB quotes rise, mills bid more for paddy within days or weeks.",
                         "Harvest pressure: prices usually dip as the main crop arrives from November.",
                         "Moisture and quality deductions at the mill, which these reference prices do not show.",
                         "Government support schemes for farmers, which can set a floor in some seasons."],
                  'th': ['ความต้องการส่งออก: เมื่อราคา FOB ไทยขึ้น โรงสีจะเสนอซื้อข้าวเปลือกสูงขึ้นภายในไม่กี่วันหรือสัปดาห์',
                         'ข้าวออกสู่ตลาดมาก: ราคามักอ่อนตัวเมื่อข้าวนาปีเริ่มเก็บเกี่ยวตั้งแต่พฤศจิกายน',
                         'การหักความชื้นและคุณภาพที่โรงสี ซึ่งราคาอ้างอิงเหล่านี้ไม่ได้แสดง',
                         'มาตรการช่วยเหลือเกษตรกรของรัฐ ที่อาจเป็นราคาขั้นต่ำในบางฤดู']}),
    dict(slug='vietnam', kind='origin', primary='vn_5', series=['vn_5', 'vn_25', 'vn_jas'], chart=['vn_5', 'vn_25', 'vn_jas'],
         name={'en': 'Vietnam', 'th': 'เวียดนาม'},
         h1={'en': 'Vietnam rice prices today', 'th': 'ราคาข้าวเวียดนามวันนี้'},
         title={'en': 'Vietnam rice price today: 5% broken ${p}/t FOB, 25%, jasmine | rice.ag',
                'th': 'ราคาข้าวเวียดนามวันนี้: ข้าวขาว 5% {p} ดอลลาร์/ตัน FOB 25% และข้าวหอม | rice.ag'},
         desc={'en': 'Vietnamese rice export prices: white rice 5% broken ${p}/t FOB ({d}), 25% broken and jasmine, with history back to 1997 and comparison with Thai and Indian prices. Free CSV.',
               'th': 'ราคาส่งออกข้าวเวียดนาม: ข้าวขาว 5% {p} ดอลลาร์/ตัน FOB ({d}) ข้าวขาว 25% และข้าวหอม ข้อมูลย้อนหลังถึงปี 2540 เทียบกับราคาข้าวไทยและอินเดีย ดาวน์โหลด CSV ฟรี'},
         body={'en': ["Viet Nam is one of the world's top three rice exporters, shipping mostly from the Mekong Delta, where farmers grow up to three crops a year. The Philippines is by far its largest buyer.",
                      "The 5% broken grade is the usual benchmark and is often the cheapest of the major Asian origins after India. Vietnamese fragrant varieties now compete directly with Thai jasmine."],
               'th': ['เวียดนามเป็นหนึ่งในสามผู้ส่งออกข้าวรายใหญ่ที่สุดของโลก ส่งออกส่วนใหญ่จากสามเหลี่ยมปากแม่น้ำโขง ซึ่งปลูกข้าวได้ถึงปีละสามรอบ ฟิลิปปินส์เป็นผู้ซื้อรายใหญ่ที่สุดอย่างทิ้งห่าง',
                      'ข้าวขาว 5% เป็นเกรดอ้างอิงหลัก และมักถูกที่สุดในบรรดาผู้ส่งออกรายใหญ่ของเอเชียรองจากอินเดีย ข้าวหอมของเวียดนามแข่งขันโดยตรงกับข้าวหอมไทยแล้ว']},
         drivers={'en': ["Philippine import policy and tariffs, since the Philippines buys a large share of Vietnamese exports.",
                         "Mekong Delta harvests, with the big winter-spring crop arriving in February and March.",
                         "Competition from Indian and Thai quotes for the same buyers."],
                  'th': ['นโยบายนำเข้าและภาษีของฟิลิปปินส์ ซึ่งซื้อข้าวเวียดนามในสัดส่วนสูง',
                         'การเก็บเกี่ยวในสามเหลี่ยมปากแม่น้ำโขง โดยข้าวรอบใหญ่ฤดูหนาว-ใบไม้ผลิออกช่วงกุมภาพันธ์ถึงมีนาคม',
                         'การแข่งขันด้านราคากับอินเดียและไทยในกลุ่มผู้ซื้อเดียวกัน']}),
    dict(slug='india', kind='origin', primary='in_5', series=['in_5', 'in_25', 'in_pb5', 'in_basmati'], chart=['in_5', 'in_25', 'in_pb5', 'in_basmati'],
         name={'en': 'India', 'th': 'อินเดีย'}, india=True,
         h1={'en': 'India rice export prices', 'th': 'ราคาส่งออกข้าวอินเดีย'},
         title={'en': 'India rice export price: 5% white ${p}/t, parboiled, basmati, export policy | rice.ag',
                'th': 'ราคาส่งออกข้าวอินเดีย: ข้าวขาว 5% {p} ดอลลาร์/ตัน ข้าวนึ่ง บาสมาติ และนโยบายส่งออก | rice.ag'},
         desc={'en': "Indian rice export prices: white rice 5% ${p}/t FOB ({d}), 25% broken, parboiled 5% and Pusa basmati, plus the current status of India's rice export policy. History back to 1995.",
               'th': 'ราคาส่งออกข้าวอินเดีย: ข้าวขาว 5% {p} ดอลลาร์/ตัน FOB ({d}) ข้าวขาว 25% ข้าวนึ่ง 5% และบาสมาติปูซา พร้อมสถานะนโยบายส่งออกข้าวของอินเดียล่าสุด ข้อมูลย้อนหลังถึงปี 2538'},
         body={'en': ["India is the world's largest rice exporter, with roughly 40% of global trade in recent years, so its export policy moves prices everywhere. It restricted broken rice in 2022 and banned non-basmati white rice exports in July 2023, and lifted those curbs in 2024 and 2025.",
                      "The Indian quotes here come from USDA, which publishes them a few months late. For direction in between, watch Thai and Vietnamese quotes and the policy status below."],
               'th': ['อินเดียเป็นผู้ส่งออกข้าวรายใหญ่ที่สุดของโลก ครองสัดส่วนราว 40% ของการค้าข้าวโลกในช่วงหลายปีที่ผ่านมา นโยบายส่งออกของอินเดียจึงกระทบราคาข้าวทั่วโลก อินเดียจำกัดการส่งออกปลายข้าวในปี 2565 ห้ามส่งออกข้าวขาวที่ไม่ใช่บาสมาติในเดือนกรกฎาคม 2566 และยกเลิกมาตรการเหล่านี้ในปี 2567 และ 2568',
                      'ราคาข้าวอินเดียในหน้านี้มาจาก USDA ซึ่งเผยแพร่ช้ากว่าปัจจุบันหลายเดือน ระหว่างนั้นให้ดูทิศทางจากราคาข้าวไทยและเวียดนาม และสถานะนโยบายด้านล่าง']},
         drivers={'en': ["Export policy: bans, duties and minimum export prices have repeatedly reset world prices.",
                         "The monsoon, which waters most of the kharif (main) crop.",
                         "Government stocks and minimum support prices paid to farmers.",
                         "The rupee against the dollar."],
                  'th': ['นโยบายส่งออก: การห้ามส่งออก ภาษีส่งออก และราคาส่งออกขั้นต่ำ เคยเปลี่ยนระดับราคาข้าวโลกมาแล้วหลายครั้ง',
                         'มรสุม ซึ่งเป็นแหล่งน้ำหลักของข้าวฤดูหลัก (kharif)',
                         'สต็อกข้าวของรัฐบาลและราคาประกันขั้นต่ำที่จ่ายให้เกษตรกร',
                         'ค่าเงินรูปีเทียบดอลลาร์']}),
    dict(slug='pakistan', kind='origin', primary='pk_5', series=['pk_5', 'pk_25', 'pk_pb5', 'pk_basmati'], chart=['pk_5', 'pk_25', 'pk_pb5', 'pk_basmati'],
         name={'en': 'Pakistan', 'th': 'ปากีสถาน'},
         h1={'en': 'Pakistan rice export prices', 'th': 'ราคาส่งออกข้าวปากีสถาน'},
         title={'en': 'Pakistan rice price: 5% white ${p}/t FOB, basmati, parboiled | rice.ag',
                'th': 'ราคาข้าวปากีสถาน: ข้าวขาว 5% {p} ดอลลาร์/ตัน FOB บาสมาติ ข้าวนึ่ง | rice.ag'},
         desc={'en': 'Pakistani rice export prices: white rice 5% ${p}/t FOB ({d}), 25% broken, parboiled and Super Kernel basmati, with history back to 1997. Free CSV download.',
               'th': 'ราคาส่งออกข้าวปากีสถาน: ข้าวขาว 5% {p} ดอลลาร์/ตัน FOB ({d}) ข้าวขาว 25% ข้าวนึ่ง และบาสมาติซูเปอร์เคอร์เนล ข้อมูลย้อนหลังถึงปี 2540 ดาวน์โหลด CSV ฟรี'},
         body={'en': ["Pakistan is one of the world's largest rice exporters, selling both long-grain non-basmati rice, mostly from Sindh, and basmati, mostly from Punjab. It competes with India for buyers in Africa, the Middle East and Asia.",
                      "Non-basmati quotes come from USDA and lag by a few months; the basmati line uses FAO's monthly series."],
               'th': ['ปากีสถานเป็นหนึ่งในผู้ส่งออกข้าวรายใหญ่ของโลก ขายทั้งข้าวเมล็ดยาวที่ไม่ใช่บาสมาติ ซึ่งปลูกมากในแคว้นสินธ์ และข้าวบาสมาติ ซึ่งปลูกมากในแคว้นปัญจาบ แข่งขันกับอินเดียในตลาดแอฟริกา ตะวันออกกลาง และเอเชีย',
                      'ราคาข้าวที่ไม่ใช่บาสมาติมาจาก USDA ซึ่งช้ากว่าปัจจุบันหลายเดือน ส่วนบาสมาติใช้ข้อมูลรายเดือนของ FAO']},
         drivers={'en': ["Indian export policy and Indian prices for the same grades.",
                         "Monsoon rain and flooding in Sindh and Punjab.",
                         "The rupee and freight costs to Africa and the Gulf."],
                  'th': ['นโยบายส่งออกและราคาข้าวเกรดเดียวกันของอินเดีย',
                         'ฝนมรสุมและน้ำท่วมในแคว้นสินธ์และปัญจาบ',
                         'ค่าเงินรูปีและค่าขนส่งไปแอฟริกาและอ่าวเปอร์เซีย']}),
    dict(slug='united-states', kind='origin', primary='us_lg', series=['us_lg'], chart=['us_lg', 'th_5'],
         name={'en': 'United States', 'th': 'สหรัฐอเมริกา'},
         h1={'en': 'US rice export prices', 'th': 'ราคาส่งออกข้าวสหรัฐอเมริกา'},
         title={'en': 'US rice price: long grain No.2 ${p}/t FOB, vs Asian prices, CBOT rough rice | rice.ag',
                'th': 'ราคาข้าวสหรัฐฯ: ข้าวเมล็ดยาว No.2 {p} ดอลลาร์/ตัน FOB เทียบราคาเอเชีย | rice.ag'},
         desc={'en': 'US long grain No.2, 4% broken export price ${p}/t FOB ({d}) compared with Thai 5%, plus how to convert CBOT rough rice futures to a per-tonne price.',
               'th': 'ราคาส่งออกข้าวเมล็ดยาวสหรัฐฯ No.2 4% {p} ดอลลาร์/ตัน FOB ({d}) เทียบกับข้าวขาว 5% ของไทย และวิธีแปลงราคาฟิวเจอร์สข้าวเปลือก CBOT เป็นราคาต่อตัน'},
         body={'en': ["US long-grain rice comes mostly from Arkansas and the Mississippi Delta; California grows medium-grain. US export prices usually sit well above Asian origins, and the main buyers are in the Americas, especially Mexico, Central America and Haiti.",
                      "Chicago's CBOT rough rice futures are for unmilled long-grain paddy in dollars per hundredweight. We can't republish them, but the homepage has a converter that turns a CBOT quote into dollars per tonne."],
               'th': ['ข้าวเมล็ดยาวของสหรัฐฯ ปลูกมากในรัฐอาร์คันซอและลุ่มแม่น้ำมิสซิสซิปปี ส่วนแคลิฟอร์เนียปลูกข้าวเมล็ดกลาง ราคาส่งออกข้าวสหรัฐฯ มักสูงกว่าข้าวเอเชียมาก ผู้ซื้อหลักอยู่ในทวีปอเมริกา โดยเฉพาะเม็กซิโก อเมริกากลาง และเฮติ',
                      'ฟิวเจอร์สข้าวเปลือก CBOT ของชิคาโกเป็นราคาข้าวเปลือกเมล็ดยาวเป็นดอลลาร์ต่อ 100 ปอนด์ เรานำราคามาเผยแพร่ซ้ำไม่ได้ แต่หน้าแรกมีตัวแปลงราคา CBOT เป็นดอลลาร์ต่อตัน']},
         drivers={'en': ["US planted area, which shifts with soybean and cotton returns.",
                         "Demand from Mexico, Central America and the Caribbean.",
                         "The gap to cheaper Asian rice, which limits how far US prices can rise."],
                  'th': ['พื้นที่ปลูกข้าวในสหรัฐฯ ซึ่งเปลี่ยนตามผลตอบแทนของถั่วเหลืองและฝ้าย',
                         'ความต้องการจากเม็กซิโก อเมริกากลาง และแคริบเบียน',
                         'ส่วนต่างกับข้าวเอเชียที่ถูกกว่า ซึ่งจำกัดว่าราคาสหรัฐฯ จะขึ้นได้แค่ไหน']}),
    # ---- by rice type
    dict(slug='white-rice-5-percent', kind='type', primary='th_5', series=['th_5', 'vn_5', 'in_5', 'pk_5', 'uy_5', 'us_lg'],
         chart=['th_5', 'vn_5', 'in_5', 'pk_5', 'uy_5', 'us_lg'],
         name={'en': 'White rice 5%', 'th': 'ข้าวขาว 5%'},
         h1={'en': 'White rice 5% broken: export prices by country', 'th': 'ราคาข้าวขาว 5% ตามประเทศผู้ส่งออก'},
         title={'en': 'White rice 5% broken price today: Thailand ${p}/t, Vietnam, India, Pakistan | rice.ag',
                'th': 'ราคาข้าวขาว 5% วันนี้: ไทย {p} ดอลลาร์/ตัน เวียดนาม อินเดีย ปากีสถาน | rice.ag'},
         desc={'en': 'The world benchmark rice grade compared across origins: Thai 5% ${p}/t FOB ({d}), Vietnam, India, Pakistan, Uruguay and US long grain, with 1-month and 1-year changes.',
               'th': 'ข้าวเกรดอ้างอิงของโลกเทียบตามประเทศ: ไทย 5% {p} ดอลลาร์/ตัน FOB ({d}) เวียดนาม อินเดีย ปากีสถาน อุรุกวัย และข้าวเมล็ดยาวสหรัฐฯ พร้อมการเปลี่ยนแปลงรอบ 1 เดือนและ 1 ปี'},
         body={'en': ["Long-grain white rice with up to 5% broken kernels is the most traded grade in the world, and the one analysts quote when they talk about 'the rice price'. Thai 5% is the oldest benchmark, with World Bank data back to 1960.",
                      "The spread between origins matters as much as the level: when Indian or Vietnamese rice is much cheaper than Thai, price-sensitive buyers switch."],
               'th': ['ข้าวขาวเมล็ดยาวที่มีข้าวหักไม่เกิน 5% เป็นเกรดที่ซื้อขายมากที่สุดในโลก และเป็นเกรดที่นักวิเคราะห์ใช้เมื่อพูดถึง "ราคาข้าว" ข้าวขาว 5% ของไทยเป็นราคาอ้างอิงที่เก่าแก่ที่สุด มีข้อมูลธนาคารโลกย้อนหลังถึงปี 2503',
                      'ส่วนต่างราคาระหว่างประเทศสำคัญพอ ๆ กับระดับราคา เมื่อข้าวอินเดียหรือเวียดนามถูกกว่าข้าวไทยมาก ผู้ซื้อที่อ่อนไหวต่อราคาจะเปลี่ยนแหล่งซื้อ']},
         drivers={'en': ["India's export policy, the biggest single swing factor since 2022.",
                         "Import demand from the Philippines, Indonesia and West Africa.",
                         "El Niño and monsoon rainfall across South and Southeast Asia.",
                         "Exchange rates of the exporting countries against the dollar."],
                  'th': ['นโยบายส่งออกของอินเดีย ปัจจัยที่เปลี่ยนแปลงราคามากที่สุดตั้งแต่ปี 2565',
                         'ความต้องการนำเข้าของฟิลิปปินส์ อินโดนีเซีย และแอฟริกาตะวันตก',
                         'เอลนีโญและฝนมรสุมในเอเชียใต้และเอเชียตะวันออกเฉียงใต้',
                         'ค่าเงินของประเทศผู้ส่งออกเทียบกับดอลลาร์']}),
    dict(slug='jasmine-rice', kind='type', primary='th_hm', series=['th_hm', 'th_jas', 'vn_jas', 'dit_hm', 'dit_paddy_hm'],
         chart=['th_hm', 'th_jas', 'vn_jas'],
         name={'en': 'Jasmine & Hom Mali', 'th': 'ข้าวหอมมะลิและข้าวหอม'},
         h1={'en': 'Jasmine rice prices: Thai Hom Mali and fragrant rice', 'th': 'ราคาข้าวหอมมะลิและข้าวหอม'},
         title={'en': 'Jasmine rice price per ton today: Thai Hom Mali ${p}/t, Pathum, Vietnam jasmine | rice.ag',
                'th': 'ราคาข้าวหอมมะลิวันนี้: ส่งออก {p} ดอลลาร์/ตัน ข้าวหอมปทุมธานี ข้าวเปลือกหอมมะลิ | rice.ag'},
         desc={'en': 'Thai Hom Mali export price ${p}/t FOB ({d}), Pathum Thani fragrant, Vietnamese jasmine, plus Hom Mali paddy and Bangkok wholesale prices in baht.',
               'th': 'ราคาส่งออกข้าวหอมมะลิไทย {p} ดอลลาร์/ตัน FOB ({d}) ข้าวหอมปทุมธานี ข้าวหอมเวียดนาม พร้อมราคาข้าวเปลือกหอมมะลิและราคาขายส่ง กทม. เป็นบาท'},
         body={'en': ["Thai Hom Mali (Khao Dawk Mali 105 and RD15) is grown mainly in the northeast, once a year in the wet season, because the varieties flower by day length. That single crop, and its aroma, keep it at more than twice the price of ordinary white rice.",
                      "Pathum Thani fragrant rice can be grown year-round and is cheaper; Vietnamese fragrant varieties compete with both. The US, China, Hong Kong and West Africa are major buyers of Thai jasmine."],
               'th': ['ข้าวหอมมะลิไทย (ขาวดอกมะลิ 105 และ กข15) ปลูกมากในภาคอีสาน ปีละครั้งในฤดูนาปี เพราะเป็นพันธุ์ไวต่อช่วงแสง ผลผลิตเพียงรอบเดียวต่อปีและความหอมทำให้ราคาสูงกว่าข้าวขาวทั่วไปมากกว่าสองเท่า',
                      'ข้าวหอมปทุมธานีปลูกได้ทั้งปีและราคาถูกกว่า ข้าวหอมเวียดนามแข่งกับทั้งสองชนิด ผู้ซื้อข้าวหอมมะลิไทยรายใหญ่ได้แก่ สหรัฐฯ จีน ฮ่องกง และแอฟริกาตะวันตก']},
         drivers={'en': ["The size of the northeast's wet-season crop, which depends on rainfall.",
                         "New-crop arrivals from November, often priced separately from old crop.",
                         "Competition from cheaper Vietnamese and Cambodian fragrant rice."],
                  'th': ['ขนาดผลผลิตนาปีภาคอีสาน ซึ่งขึ้นกับปริมาณฝน',
                         'ข้าวใหม่ที่ออกตั้งแต่พฤศจิกายน ซึ่งมักแยกราคาจากข้าวเก่า',
                         'การแข่งขันจากข้าวหอมเวียดนามและกัมพูชาที่ราคาถูกกว่า']}),
    dict(slug='basmati-rice', kind='type', primary='pk_basmati', series=['pk_basmati', 'in_basmati'], chart=['pk_basmati', 'in_basmati', 'th_hm'],
         name={'en': 'Basmati', 'th': 'บาสมาติ'},
         h1={'en': 'Basmati rice export prices', 'th': 'ราคาส่งออกข้าวบาสมาติ'},
         title={'en': 'Basmati rice price per ton: Pakistan Super Kernel ${p}/t, India Pusa basmati | rice.ag',
                'th': 'ราคาข้าวบาสมาติต่อตัน: ปากีสถาน {p} ดอลลาร์/ตัน และอินเดีย | rice.ag'},
         desc={'en': 'Basmati export prices: Pakistan Super Kernel ${p}/t FOB ({d}) and India Pusa basmati, compared with Thai Hom Mali, with history back to 2000.',
               'th': 'ราคาส่งออกข้าวบาสมาติ: ปากีสถานซูเปอร์เคอร์เนล {p} ดอลลาร์/ตัน FOB ({d}) และอินเดียปูซา เทียบกับข้าวหอมมะลิไทย ข้อมูลย้อนหลังถึงปี 2543'},
         body={'en': ["Basmati is an extra-long, aromatic rice grown only in the Indo-Gangetic plains of India and Pakistan. It is usually aged before sale and sold mainly to the Gulf, Iran, the UK, the EU and the US.",
                      "India's line here is USDA's Pusa basmati quote, which is published late; Pakistan's comes from FAO monthly data."],
               'th': ['บาสมาติเป็นข้าวเมล็ดยาวพิเศษที่มีกลิ่นหอม ปลูกได้เฉพาะที่ราบลุ่มแม่น้ำสินธุ-คงคาในอินเดียและปากีสถาน มักบ่มให้เก่าก่อนขาย และขายไปยังกลุ่มประเทศอ่าวอาหรับ อิหร่าน สหราชอาณาจักร สหภาพยุโรป และสหรัฐฯ เป็นหลัก',
                      'ราคาอินเดียในหน้านี้เป็นราคาบาสมาติปูซาจาก USDA ซึ่งเผยแพร่ช้า ส่วนปากีสถานใช้ข้อมูลรายเดือนของ FAO']},
         drivers={'en': ["Demand from Iran and the Gulf states, the largest buyers.",
                         "Minimum export prices India has set for basmati at times.",
                         "Crop size in Punjab (both countries) and the rupee."],
                  'th': ['ความต้องการจากอิหร่านและกลุ่มประเทศอ่าวอาหรับ ซึ่งเป็นผู้ซื้อรายใหญ่ที่สุด',
                         'ราคาส่งออกขั้นต่ำที่อินเดียเคยกำหนดสำหรับบาสมาติ',
                         'ขนาดผลผลิตในแคว้นปัญจาบของทั้งสองประเทศ และค่าเงินรูปี']}),
    dict(slug='parboiled-rice', kind='type', primary='th_pb', series=['th_pb', 'in_pb5', 'pk_pb5'], chart=['th_pb', 'in_pb5', 'pk_pb5'],
         name={'en': 'Parboiled', 'th': 'ข้าวนึ่ง'},
         h1={'en': 'Parboiled rice export prices', 'th': 'ราคาส่งออกข้าวนึ่ง'},
         title={'en': 'Parboiled rice price per ton: Thai ${p}/t, India, Pakistan | rice.ag',
                'th': 'ราคาข้าวนึ่งต่อตัน: ไทย {p} ดอลลาร์/ตัน อินเดีย ปากีสถาน | rice.ag'},
         desc={'en': 'Parboiled rice export prices: Thai parboiled 100% ${p}/t FOB ({d}), India and Pakistan parboiled 5%, with 1-month and 1-year changes and history.',
               'th': 'ราคาส่งออกข้าวนึ่ง: ข้าวนึ่งไทย 100% {p} ดอลลาร์/ตัน FOB ({d}) ข้าวนึ่ง 5% ของอินเดียและปากีสถาน พร้อมการเปลี่ยนแปลงรอบเดือนและรอบปี'},
         body={'en': ["Parboiled rice is soaked and steamed in the husk before milling, which makes it firmer, more nutritious and less likely to break. The biggest markets are West Africa, South Africa, the Middle East and Bangladesh.",
                      "India dominates the trade; it put a 20% duty on parboiled exports in 2023, which lifted Thai and Pakistani parboiled prices until it was removed in 2024."],
               'th': ['ข้าวนึ่งคือข้าวเปลือกที่แช่น้ำและนึ่งก่อนสี ทำให้เมล็ดแข็งขึ้น มีคุณค่าทางอาหารมากขึ้น และหักน้อยลง ตลาดใหญ่ที่สุดคือแอฟริกาตะวันตก แอฟริกาใต้ ตะวันออกกลาง และบังกลาเทศ',
                      'อินเดียครองตลาดนี้ ในปี 2566 อินเดียเก็บภาษีส่งออกข้าวนึ่ง 20% ทำให้ราคาข้าวนึ่งไทยและปากีสถานสูงขึ้นจนกระทั่งยกเลิกภาษีในปี 2567']},
         drivers={'en': ["Indian export duties and supply.",
                         "Import demand from Nigeria, Benin, South Africa and Saudi Arabia.",
                         "Paddy prices, since parboiling adds a processing step before milling."],
                  'th': ['ภาษีส่งออกและปริมาณข้าวของอินเดีย',
                         'ความต้องการนำเข้าจากไนจีเรีย เบนิน แอฟริกาใต้ และซาอุดีอาระเบีย',
                         'ราคาข้าวเปลือก เพราะการนึ่งเป็นขั้นตอนเพิ่มก่อนการสี']}),
    dict(slug='broken-rice', kind='type', primary='th_a1s', series=['th_a1s', 'th_hmbrk', 'th_25', 'vn_25', 'in_25', 'pk_25'],
         chart=['th_a1s', 'th_hmbrk', 'th_25', 'vn_25'],
         name={'en': 'Broken rice', 'th': 'ปลายข้าว'},
         h1={'en': 'Broken rice prices: A1 Super and 25% grades', 'th': 'ราคาปลายข้าว: เอ1 ซุปเปอร์ และข้าวขาว 25%'},
         title={'en': 'Broken rice price per ton: Thai A1 Super ${p}/t, Hom Mali brokens, 25% grades | rice.ag',
                'th': 'ราคาปลายข้าวต่อตัน: เอ1 ซุปเปอร์ {p} ดอลลาร์/ตัน ปลายข้าวหอมมะลิ ข้าวขาว 25% | rice.ag'},
         desc={'en': 'Broken rice export prices: Thai A1 Super 100% brokens ${p}/t FOB ({d}), Hom Mali brokens, and 25% broken white rice from Thailand, Vietnam, India and Pakistan.',
               'th': 'ราคาส่งออกปลายข้าว: ปลายข้าวเอ1 ซุปเปอร์ {p} ดอลลาร์/ตัน FOB ({d}) ปลายข้าวหอมมะลิ และข้าวขาว 25% จากไทย เวียดนาม อินเดีย และปากีสถาน'},
         body={'en': ["Broken rice is the kernels that break during milling. A1 Super is the standard 100% broken export grade, sold for food in West Africa and for rice flour, noodles, brewing and animal feed elsewhere.",
                      "Grades like white rice 25% are whole rice with a high share of brokens, priced between 5% rice and pure brokens. Read how brokens are classified in our broken rice grading guide."],
               'th': ['ปลายข้าวคือเมล็ดที่หักระหว่างการสี เอ1 ซุปเปอร์เป็นเกรดปลายข้าว 100% มาตรฐานสำหรับส่งออก ใช้เป็นอาหารในแอฟริกาตะวันตก และใช้ทำแป้งข้าว เส้นก๋วยเตี๋ยว เบียร์ และอาหารสัตว์ในตลาดอื่น',
                      'ข้าวขาว 25% คือข้าวที่มีสัดส่วนข้าวหักสูง ราคาอยู่ระหว่างข้าว 5% กับปลายข้าวล้วน อ่านวิธีจำแนกข้าวหักได้ในคู่มือการจำแนกข้าวหักของเรา']},
         drivers={'en': ["Feed and ethanol demand in China and elsewhere, which competes with maize prices.",
                         "West African food demand, especially Senegal.",
                         "India's broken rice export policy (it banned broken rice exports from 2022 until 2025)."],
                  'th': ['ความต้องการใช้ทำอาหารสัตว์และเอทานอลในจีนและที่อื่น ซึ่งแข่งกับราคาข้าวโพด',
                         'ความต้องการบริโภคในแอฟริกาตะวันตก โดยเฉพาะเซเนกัล',
                         'นโยบายส่งออกปลายข้าวของอินเดีย (ห้ามส่งออกปลายข้าวตั้งแต่ปี 2565 จนถึงปี 2568)']}),
    dict(slug='glutinous-rice', kind='type', primary='th_glu', series=['th_glu', 'dit_glu', 'dit_paddy_glu'], chart=['th_glu'],
         name={'en': 'Glutinous (sticky)', 'th': 'ข้าวเหนียว'},
         h1={'en': 'Glutinous (sticky) rice prices', 'th': 'ราคาข้าวเหนียว'},
         title={'en': 'Sticky rice price per ton: Thai glutinous 10% ${p}/t FOB, paddy & wholesale | rice.ag',
                'th': 'ราคาข้าวเหนียววันนี้: ส่งออก {p} ดอลลาร์/ตัน ข้าวเหนียว กข.6 และข้าวเปลือกเหนียว | rice.ag'},
         desc={'en': 'Thai glutinous (sticky) rice prices: export 10% ${p}/t FOB ({d}), RD6 Bangkok wholesale and long-grain glutinous paddy in baht, with history.',
               'th': 'ราคาข้าวเหนียวไทย: ส่งออกข้าวเหนียว 10% {p} ดอลลาร์/ตัน FOB ({d}) ข้าวสารเหนียว กข.6 ขายส่ง กทม. และข้าวเปลือกเหนียวเมล็ดยาว เป็นบาท พร้อมข้อมูลย้อนหลัง'},
         body={'en': ["Glutinous or sticky rice is the everyday staple of northern and northeastern Thailand and Laos, and is used across Asia for desserts and snacks. Thailand is the main exporter.",
                      "Much of the crop is eaten by the farm families who grow it, so a poor season in the northeast tightens the marketable surplus quickly."],
               'th': ['ข้าวเหนียวเป็นอาหารหลักประจำวันของภาคเหนือและภาคอีสานของไทยและลาว และใช้ทำขนมและของว่างทั่วเอเชีย ไทยเป็นผู้ส่งออกหลัก',
                      'ผลผลิตส่วนใหญ่ถูกบริโภคในครัวเรือนของเกษตรกรเอง ปีที่ภาคอีสานผลผลิตไม่ดี ข้าวส่วนเกินที่ขายได้จึงลดลงเร็ว']},
         drivers={'en': ["Wet-season rainfall in northern and northeastern Thailand.",
                         "Demand from China, Laos and Thai food processors.",
                         "How much farmers keep for their own use after a weak harvest."],
                  'th': ['ฝนฤดูนาปีในภาคเหนือและภาคอีสาน',
                         'ความต้องการจากจีน ลาว และผู้ผลิตอาหารในไทย',
                         'ปริมาณที่เกษตรกรเก็บไว้บริโภคเองหลังปีที่ผลผลิตไม่ดี']}),
]

HUB_BY_SLUG = {h['slug']: h for h in HUBS}


def hub_fill(h, data, lang):
    """Title, description and the facts that go into a hub page, with numbers filled in."""
    st = stats(data, h['primary'])
    rows = [x for x in (stats(data, k) for k in h['series']) if x]
    fmt = dict(p=num(st['usd']) if st else '–', pt=num(st['thb']) if st and st['thb'] else '–',
               d=when(st, lang) if st else '')
    title = h['title'][lang].format(**fmt)
    desc = h['desc'][lang].format(**fmt)
    lead = price_sentence(st, lang, baht=h.get('baht')) if st else ''
    return dict(title=title, desc=desc, lead=lead, rows=rows, primary=st,
                chart=svg_chart(data, h['chart'], baht=h.get('baht', False), lang=lang,
                                label=h['h1'][lang]))


def dataset_ld(h, data, lang, url, base_url, org_id):
    rows = [x for x in (stats(data, k) for k in h['series']) if x]
    start = min((day(x['s']['d'][0]) for x in rows), default=None)
    return {"@type": "Dataset", "name": h['h1'][lang], "url": base_url + url,
            "description": h['desc'][lang].split(':')[0], "isAccessibleForFree": True, "inLanguage": lang,
            "temporalCoverage": f"{start.isoformat() if start else '1960-01-01'}/..",
            "variableMeasured": [x['en'] for x in rows],
            "creator": {"@id": org_id},
            "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": base_url + "/static/data/prices.csv"}]}
