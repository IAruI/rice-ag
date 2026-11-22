#!/usr/bin/env python3
"""rice.ag static site builder. Usage: python3 build.py  -> dist/"""
import json, shutil, hashlib, datetime, os, re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pricepages as pp
import fertpages as fp

ROOT = Path(__file__).parent
SRC, DIST = ROOT / 'src', ROOT / 'dist'
BASE_URL = 'https://rice.ag'
TODAY = datetime.date.today().isoformat()
I18N = json.loads((SRC / 'i18n.json').read_text(encoding='utf-8'))

env = Environment(loader=FileSystemLoader([str(SRC / 'templates'), str(SRC / 'pages')]),
                  autoescape=select_autoescape(['html']), trim_blocks=True, lstrip_blocks=True)

# ---- weekly brief helpers (see pipeline/brief.py)
TH_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']

def fdate(iso, lang='en'):
    d = datetime.date.fromisoformat(str(iso)[:10])
    return f"{d.day} {TH_MONTHS[d.month - 1]} {d.year + 543}" if lang == 'th' else d.strftime('%-d %b %Y')

def spark(history, w=280, h=56):
    """Inline SVG line for [[date, value], ...]."""
    vals = [v for _, v in (history or []) if v is not None]
    if len(vals) < 2:
        return ''
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    pts = ' '.join(f"{i * w / (len(vals) - 1):.1f},{h - 4 - (v - lo) / rng * (h - 8):.1f}" for i, v in enumerate(vals))
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img" aria-hidden="true">'
            f'<polyline points="{pts}" fill="none" stroke="currentColor" stroke-width="2" vector-effect="non-scaling-stroke" '
            f'stroke-linejoin="round" stroke-linecap="round"/></svg>')

def onibars(history, w=280, h=56):
    """Bars above/below zero for the last ONI seasons; El Nino and La Nina bars coloured."""
    vals = [v for _, v in (history or [])]
    if not vals:
        return ''
    m = max(2.0, max(abs(v) for v in vals))
    bw = w / len(vals)
    mid = h / 2
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-hidden="true"><line x1="0" x2="{w}" y1="{mid}" y2="{mid}" class="bf-zero"/>']
    for i, v in enumerate(vals):
        bh = abs(v) / m * (mid - 2)
        cls = 'bf-warm' if v >= 0.5 else 'bf-cool' if v <= -0.5 else 'bf-neu'
        out.append(f'<rect x="{i * bw + 1:.1f}" y="{(mid - bh if v >= 0 else mid):.1f}" width="{max(bw - 2, 1):.1f}" height="{max(bh, .5):.1f}" rx="1.5" class="{cls}"/>')
    out.append('</svg>')
    return ''.join(out)

env.filters.update(fdate=fdate, spark=spark, onibars=onibars,
                   pxnum=pp.num, pxpct=pp.pct, pxkg=pp.kg,
                   pxdate=lambda d, lang='en': pp.fdate(d if isinstance(d, datetime.date) else datetime.date.fromisoformat(str(d)[:10]), lang),
                   pxsrc=lambda r, lang='en': pp.srcnames(r, lang))
PRICES = pp.load_prices()
env.globals.update(hubs=pp.HUBS)
# Cloudflare Web Analytics: set CF_ANALYTICS_TOKEN in Netlify (Site configuration > Environment variables).
# Empty = no analytics script on the site.
CF_ANALYTICS_TOKEN = os.environ.get('CF_ANALYTICS_TOKEN', '').strip()
env.globals.update(
    ONI_CAT={'en': {'neutral': 'Neutral', 'el_nino_weak': 'Weak El Niño', 'el_nino_moderate': 'Moderate El Niño',
                    'el_nino_strong': 'Strong El Niño', 'el_nino_very_strong': 'Very strong El Niño',
                    'la_nina_weak': 'Weak La Niña', 'la_nina_moderate': 'Moderate La Niña',
                    'la_nina_strong': 'Strong La Niña', 'la_nina_very_strong': 'Very strong La Niña'},
             'th': {'neutral': 'ภาวะปกติ', 'el_nino_weak': 'เอลนีโญกำลังอ่อน', 'el_nino_moderate': 'เอลนีโญกำลังปานกลาง',
                    'el_nino_strong': 'เอลนีโญกำลังแรง', 'el_nino_very_strong': 'เอลนีโญกำลังแรงมาก',
                    'la_nina_weak': 'ลานีญากำลังอ่อน', 'la_nina_moderate': 'ลานีญากำลังปานกลาง',
                    'la_nina_strong': 'ลานีญากำลังแรง', 'la_nina_very_strong': 'ลานีญากำลังแรงมาก'}},
    INDIA={'en': {'open': 'Exports open', 'watch': 'Watch: curbs possible', 'restricted': 'Exports restricted', 'unknown': 'Not checked'},
           'th': {'open': 'ส่งออกได้ตามปกติ', 'watch': 'จับตา: อาจจำกัดการส่งออก', 'restricted': 'จำกัดการส่งออก', 'unknown': 'ยังไม่ได้ตรวจ'}})

def load_brief():
    """A missing or broken brief.json only blanks /brief/; it never stops the rest of the site building."""
    try:
        return json.loads((SRC / 'static/data/brief.json').read_text(encoding='utf-8'))
    except Exception:
        return {}

def load_fert():
    """fertilizer.json plus the derived bits the page needs. Missing data blanks the page, never the build."""
    try:
        F = json.loads((SRC / 'static/data/fertilizer.json').read_text(encoding='utf-8'))
    except Exception:
        return {}
    by = {f['npk']: f for f in F.get('formulas', [])}
    F['key'] = [by[k] for k in ('46-0-0', '16-20-0', '15-15-15', '0-0-60', '21-0-0', '16-8-8', '13-13-21', '18-46-0') if k in by]
    F['urea'] = by.get('46-0-0')
    un = next((r for r in F.get('nutrients', {}).get('N', []) if r['npk'] == '46-0-0'), None)
    # yearly averages of the world series (complete years, plus the current year to date)
    years = {}
    for k in ('urea', 'dap', 'kcl'):
        for d, v in (F.get('world', {}).get(k, {}).get('hist') or []):
            years.setdefault(int(d[:4]), {}).setdefault(k, []).append(v)
    rows = []
    for y in sorted(years, reverse=True)[:12]:
        r = {'year': y, 'months': max(len(v) for v in years[y].values()), 'urea_chg': None}
        for k, v in years[y].items():
            r[k] = round(sum(v) / len(v))
        rows.append(r)
    for i, r in enumerate(rows[:-1]):
        prev = rows[i + 1]
        r['urea_chg'] = round((r['urea'] / prev['urea'] - 1) * 100, 1) if r.get('urea') and prev.get('urea') else None
    F['years'] = rows
    F['calc'] = {'formulas': {k: f['median'] for k, f in by.items()}, 'urea_n': un['baht_per_kg'] if un else None}
    sv = F.setdefault('survey', {})
    if sv.get('month'):
        y, m = map(int, sv['month'].split('-'))
        sv['month_th'] = f"{pp.TH_MONTHS_LONG[m - 1]} {y + 543}"
        sv['month_en'] = datetime.date(y, m, 1).strftime('%B %Y')
    return F

def fert_lead(F, lang):
    by = {f['npk']: f for f in F.get('formulas', [])}
    u, a, b = by.get('46-0-0'), by.get('16-20-0'), by.get('15-15-15')
    if not u:
        return ''
    w = (F.get('world') or {}).get('urea')
    if lang == 'th':
        out = f"ปุ๋ยยูเรีย 46-0-0 กระสอบ 50 กก. ราคาหน้าร้านราว {pp.num(u['median'])} บาท"
        out += f" ({pp.num(u['low'])}–{pp.num(u['high'])})" if u['count'] > 1 else ''
        out += f" สูตร 16-20-0 ราว {pp.num(a['median'])} บาท" if a else ''
        out += f" และ 15-15-15 ราว {pp.num(b['median'])} บาท" if b else ''
        out += f" ราคายูเรียตลาดโลก {pp.num(w['usd'])} ดอลลาร์ต่อตัน ({pp.fdate(datetime.date.fromisoformat(w['date']), 'th', True)})" if w else ''
        return out
    out = f"Urea (46-0-0) costs about {pp.num(u['median'])} baht for a 50 kg bag at Thai shops"
    out += f" ({pp.num(u['low'])}–{pp.num(u['high'])})" if u['count'] > 1 else ''
    out += f"; 16-20-0 about {pp.num(a['median'])} baht" if a else ''
    out += f" and 15-15-15 about {pp.num(b['median'])} baht" if b else ''
    out += '.'
    out += f" World urea was ${pp.num(w['usd'])} per tonne in {datetime.date.fromisoformat(w['date']).strftime('%B %Y')}." if w else ''
    return out

FERT = load_fert()

ORG = {"@type": "Organization", "@id": BASE_URL + "/#org", "name": "rice.ag", "url": BASE_URL + "/",
       "logo": BASE_URL + "/icon-512.png"}

PAGES = [
    dict(key='prices', path='/', src='shared/prices.html', section='prices', js=['prices.js'],
         title={'en': 'Rice prices today: Thai, Viet Nam, US export FOB & Thai paddy prices in USD/t | rice.ag',
                'th': 'ราคาข้าววันนี้: ราคาส่งออกข้าวไทย เวียดนาม สหรัฐฯ และราคาข้าวเปลือก (ดอลลาร์/ตัน) | rice.ag'},
         desc={'en': 'Free daily-updated rice price charts: Thai 5%, Hom Mali, jasmine, glutinous and parboiled export prices, Viet Nam, US, Uruguay and Pakistan FOB quotes, and Thai paddy prices, all in USD per tonne. Download the data.',
               'th': 'กราฟราคาข้าวอัปเดตทุกวัน ฟรี: ราคาส่งออกข้าวขาว 5% ข้าวหอมมะลิ ข้าวหอมไทย ข้าวเหนียว ข้าวนึ่ง ราคา FOB เวียดนาม สหรัฐฯ อุรุกวัย ปากีสถาน และราคาข้าวเปลือกไทย เป็นดอลลาร์ต่อตัน ดาวน์โหลดข้อมูลได้'}),
    dict(key='brief', path='/brief/', src='shared/brief.html', section='brief',
         title={'en': 'Weekly rice early-warning brief: El Niño, Thai export & paddy prices, baht, India policy | rice.ag',
                'th': 'สรุปสัญญาณเตือนตลาดข้าวรายสัปดาห์: เอลนีโญ ราคาส่งออกและข้าวเปลือก ค่าเงินบาท นโยบายอินเดีย | rice.ag'},
         desc={'en': 'Five signals that move Thai rice prices, read by the same rules every week: El Niño (ONI), Thai 5% FOB, Thai paddy in baht, USD/THB and India\'s rice export policy. Updated automatically.',
               'th': 'ห้าสัญญาณที่ขับเคลื่อนราคาข้าวไทย อ่านด้วยกฎเดียวกันทุกสัปดาห์: เอลนีโญ (ONI) ราคาส่งออกข้าวขาว 5% ราคาข้าวเปลือกเป็นบาท ค่าเงินบาท และนโยบายส่งออกข้าวของอินเดีย อัปเดตอัตโนมัติ'}),
    dict(key='home', path='/tools/', src='home', section='tools',
         title={'en': 'Free rice tools: grain scanner, moisture calculator & photo guide | rice.ag',
                'th': 'เครื่องมือเรื่องข้าวฟรี: เครื่องสแกนเมล็ดข้าว คำนวณความชื้น และวิธีถ่ายภาพ | rice.ag'},
         desc={'en': 'Photograph a rice sample and get head rice vs. broken %, kernel length and shape, colour consistency and suspect foreign objects in seconds. Free, private, runs in your browser.',
               'th': 'ถ่ายภาพตัวอย่างข้าว แล้วรู้ผลต้นข้าวและข้าวหัก ความยาวและรูปร่างเมล็ด ความสม่ำเสมอของสี และสิ่งแปลกปลอมที่น่าสงสัยภายในไม่กี่วินาที ฟรี ปลอดภัย ทำงานในเบราว์เซอร์'}),
    dict(key='scanner', path='/scanner/', src='shared/scanner.html', section='scanner', app=True,
         title={'en': 'Rice Grain Scanner — measure broken rice, length & colour from a photo | rice.ag',
                'th': 'เครื่องสแกนเมล็ดข้าว — วัดข้าวหัก ความยาว และสีจากภาพถ่าย | rice.ag'},
         desc={'en': 'Free online rice grain analyser. Counts whole, head and broken kernels (ISO 7301 / Codex classes), measures length in mm with a coin, checks colour and flags suspect objects. Photos never leave your device.',
               'th': 'เครื่องวิเคราะห์เมล็ดข้าวออนไลน์ฟรี นับเมล็ดเต็ม ต้นข้าว และข้าวหัก (ตาม ISO 7301 / Codex) วัดความยาวเป็นมิลลิเมตรด้วยเหรียญ ตรวจสี และชี้วัตถุที่น่าสงสัย ภาพไม่ออกจากอุปกรณ์ของคุณ'}),
    dict(key='guide', path='/guide/', src='guide', section='guide', kind='article',
         title={'en': 'How to photograph rice for grain analysis | rice.ag', 'th': 'วิธีถ่ายภาพข้าวเพื่อวิเคราะห์เมล็ด | rice.ag'},
         desc={'en': 'A 2-minute setup for accurate rice scans: sample size, black background, spacing, coin for scale, lighting, and a lightbox trick for chalkiness.',
               'th': 'เตรียมถ่ายภาพ 2 นาทีเพื่อผลสแกนที่แม่นยำ: ขนาดตัวอย่าง พื้นหลังสีดำ การเกลี่ยเมล็ด เหรียญอ้างอิงขนาด แสง และเทคนิคกล่องไฟสำหรับวัดท้องไข่'}),
    dict(key='methodology', path='/methodology/', src='methodology', section='scanner', kind='article',
         title={'en': 'How the rice.ag grain scanner works — methods, accuracy & limits', 'th': 'หลักการทำงานของเครื่องสแกนข้าว rice.ag — วิธีการ ความแม่นยำ และข้อจำกัด'},
         desc={'en': 'The image-analysis pipeline behind rice.ag, the ISO 7301 and Codex definitions it uses, test results, and what a photo cannot measure.',
               'th': 'ขั้นตอนการวิเคราะห์ภาพของ rice.ag นิยามตาม ISO 7301 และ Codex ที่ใช้ ผลการทดสอบ และสิ่งที่ภาพถ่ายวัดไม่ได้'}),
    dict(key='moisture', path='/tools/moisture-calculator/', src='shared/moisture.html', body='moisture', section='moisture',
         title={'en': 'Paddy moisture & drying shrink calculator | rice.ag', 'th': 'เครื่องคำนวณความชื้นข้าวเปลือกและน้ำหนักหายจากการอบ | rice.ag'},
         desc={'en': 'Calculate paddy weight after drying to 14% moisture, and back-calculate the true intake moisture from your drying records. Free, instant.',
               'th': 'คำนวณน้ำหนักข้าวเปลือกหลังอบแห้งถึงความชื้น 14% และย้อนคำนวณความชื้นจริงตอนรับซื้อจากบันทึกการอบ ฟรี ทันที'}),
    dict(key='learn', path='/learn/', src='learn', section='learn',
         title={'en': 'Learn: rice quality, grading & processing | rice.ag', 'th': 'ความรู้: คุณภาพข้าว การจำแนกเกรด และการแปรรูป | rice.ag'},
         desc={'en': 'Practical guides on rice grading, broken rice, moisture and drying, and noodle rice varieties, written by people who mill rice.',
               'th': 'คู่มือเชิงปฏิบัติเรื่องการจำแนกเกรดข้าว ข้าวหัก ความชื้นและการอบ และพันธุ์ข้าวสำหรับทำเส้น เขียนโดยคนที่สีข้าวจริง'}),
    dict(key='broken', path='/learn/broken-rice-grading/', src='broken', section='learn', kind='article',
         title={'en': 'Broken rice grading explained: whole, head rice, brokens & chips (ISO 7301, Codex) | rice.ag',
                'th': 'การจำแนกข้าวหัก: เมล็ดเต็ม ต้นข้าว ข้าวหัก และปลายข้าว (ISO 7301, Codex) | rice.ag'},
         desc={'en': 'What counts as whole, head rice, broken and chips; why broken % is measured by weight; and how to check a sample quickly.',
               'th': 'อะไรคือเมล็ดเต็ม ต้นข้าว ข้าวหัก และปลายข้าว ทำไมข้าวหักจึงวัดเป็นร้อยละโดยน้ำหนัก และวิธีตรวจตัวอย่างอย่างรวดเร็ว'}),
    dict(key='chainat', path='/learn/chainat-1-noodle-rice/', src='chainat', section='learn', kind='article',
         title={'en': 'Chainat 1 rice: the Thai high-amylose variety behind rice noodles | rice.ag',
                'th': 'ข้าวชัยนาท 1: ข้าวอมิโลสสูงของไทยสำหรับทำเส้นก๋วยเตี๋ยว | rice.ag'},
         desc={'en': 'Origin, grain traits and why noodle makers choose Chainat 1 (ชัยนาท 1) — and why single-variety supply matters for consistent noodles.',
               'th': 'ที่มา ลักษณะเมล็ด และเหตุผลที่ผู้ผลิตเส้นเลือกข้าวชัยนาท 1 รวมถึงความสำคัญของข้าวพันธุ์เดียวไม่ปนต่อคุณภาพเส้นที่สม่ำเสมอ'}),
    dict(key='shrink', path='/learn/moisture-and-drying-shrink/', src='shrink', section='learn', kind='article',
         title={'en': 'Paddy moisture, drying shrink and how to check your moisture meter | rice.ag',
                'th': 'ความชื้นข้าวเปลือก น้ำหนักหายจากการอบ และวิธีตรวจเครื่องวัดความชื้น | rice.ag'},
         desc={'en': 'The dry-matter formula every paddy buyer and seller should know, with worked examples and a simple way to catch a meter that reads low.',
               'th': 'สูตรน้ำหนักเนื้อแห้งที่ผู้ซื้อและผู้ขายข้าวเปลือกควรรู้ พร้อมตัวอย่างการคำนวณ และวิธีง่าย ๆ ในการจับเครื่องวัดความชื้นที่อ่านค่าต่ำเกินจริง'}),
    dict(key='about', path='/about/', src='about', section='about',
         title={'en': 'About rice.ag — free rice tools, prices and guides', 'th': 'เกี่ยวกับ rice.ag — เครื่องมือ ราคาข้าว และความรู้เรื่องข้าว ฟรี'},
         desc={'en': 'rice.ag is a free, independent site with a rice grain scanner, a paddy moisture calculator, daily rice prices and practical rice guides.',
               'th': 'rice.ag เป็นเว็บไซต์อิสระที่ให้ใช้ฟรี มีเครื่องสแกนเมล็ดข้าว เครื่องคำนวณความชื้นข้าวเปลือก ราคาข้าวรายวัน และความรู้เรื่องข้าวเชิงปฏิบัติ'}),
]

if FERT.get('formulas'):
    _u = (FERT.get('urea') or {}).get('median')
    _a = next((f['median'] for f in FERT['formulas'] if f['npk'] == '16-20-0'), None)
    _b = next((f['median'] for f in FERT['formulas'] if f['npk'] == '15-15-15'), None)
    PAGES.append(dict(key='fertilizer', path='/fertilizer/', src='shared/fertilizer.html', section='prices',
        title={'en': f"Fertilizer prices in Thailand today: urea 46-0-0 ฿{pp.num(_u)}/bag, 16-20-0, 15-15-15 | rice.ag",
               'th': f"ราคาปุ๋ยวันนี้: ยูเรีย 46-0-0 กระสอบละ {pp.num(_u)} บาท 16-20-0 {pp.num(_a)} 15-15-15 {pp.num(_b)} | rice.ag"},
        desc={'en': f"Thai fertilizer shop prices per 50 kg bag for {len(FERT['formulas'])} formulas and brands: urea, 16-20-0, 15-15-15, 0-0-60, 21-0-0. Cheapest source of N, P and K, a price calculator, and world urea, DAP and potash prices.",
              'th': f"ราคาปุ๋ยหน้าร้านต่อกระสอบ 50 กก. {len(FERT['formulas'])} สูตร หลายยี่ห้อ: ยูเรีย 46-0-0 16-20-0 15-15-15 0-0-60 21-0-0 สูตรไหนให้ธาตุอาหารถูกที่สุด เครื่องคำนวณความคุ้มค่า และราคาปุ๋ยตลาดโลก"}))

if FERT.get('formulas'):
    FPAGES = fp.formula_pages(FERT)
    for _f in FPAGES:
        _ff = {l: fp.formula_fill(_f, FERT, l) for l in ('en', 'th')}
        _nm = fp.INFO.get(_f['npk'], {})
        PAGES.append(dict(key='fformula', ff=_ff, path=f"/fertilizer/{_f['npk']}/", src='shared/fert_formula.html', section='prices',
            title={'en': f"{_f['npk']}{(' ' + re.sub(r' *[(].*', '', _nm['en'])) if _nm.get('en') else ''} fertilizer price today: ฿{_f['median']:,} a bag, {_f['count']} brands | rice.ag",
                   'th': f"ราคาปุ๋ย {_f['npk']}{(' ' + re.sub(r' *[(].*', '', _nm['th'])) if _nm.get('th') else ''} วันนี้ กระสอบละ {_f['median']:,} บาท ({_f['count']} ยี่ห้อ) | rice.ag"},
            desc={l: _ff[l]['lead'] for l in _ff}))
    BLENDT = fp.blend_table(FERT)
    _b = BLENDT.get('best')
    PAGES.append(dict(key='fblend', path='/fertilizer/blend/', src='shared/fert_blend.html', section='prices',
        title={'en': 'Blend your own fertilizer: cost vs ready-made 16-20-0, 15-15-15, 16-8-8 | rice.ag',
               'th': 'ผสมปุ๋ยใช้เอง สูตร 16-20-0 15-15-15 16-8-8 ถูกกว่าซื้อสำเร็จเท่าไร | rice.ag'},
        desc={'en': f"Make any N-P-K from urea, DAP and potash. At today's Thai shop prices{(', blending ' + _b['npk'] + ' saves about ' + format(_b['saving'], ',') + ' baht a bag') if _b else ''}. Free calculator.",
              'th': f"ผสมปุ๋ยทุกสูตรจากยูเรีย DAP และโพแทส ที่ราคาหน้าร้านวันนี้{(' สูตร ' + _b['npk'] + ' ผสมเองถูกกว่าราว ' + format(_b['saving'], ',') + ' บาทต่อกระสอบ') if _b else ''} พร้อมเครื่องคำนวณฟรี"}))
    RICE = fp.rice_defaults(FERT)
    _c = [e['cost'] for e in RICE['examples']] or [0]
    PAGES.append(dict(key='frice', path='/fertilizer/rice/', src='shared/fert_rice.html', section='prices',
        title={'en': f"Rice fertilizer cost per rai: {min(_c):,}–{max(_c):,} baht, which formula for which soil | rice.ag",
               'th': f"ปุ๋ยนาข้าว ใช้สูตรไหน ต้นทุนไร่ละ {min(_c):,}–{max(_c):,} บาท ตามคำแนะนำกรมการข้าว | rice.ag"},
        desc={'en': "Rice Department fertilizer recommendations for rice by variety and soil, priced at today's Thai shop prices, with a cost-per-rai calculator.",
              'th': 'คำแนะนำการใช้ปุ๋ยนาข้าวของกรมการข้าว ตามพันธุ์ข้าวและชนิดดิน คิดราคาตามราคาปุ๋ยหน้าร้านวันนี้ พร้อมเครื่องคำนวณค่าปุ๋ยต่อไร่'}))
else:
    FPAGES, BLENDT, RICE = [], {}, {}

# one page per origin and per rice type (see pricepages.HUBS); titles carry the latest price
for _h in pp.HUBS:
    _f = {lang: pp.hub_fill(_h, PRICES, lang) for lang in ('en', 'th')}
    PAGES.append(dict(key='hub', hub=_h, fill=_f, path=f"/prices/{_h['slug']}/", src='shared/price_hub.html', section='prices',
                      title={l: _f[l]['title'] for l in _f}, desc={l: _f[l]['desc'] for l in _f}))

# homepage title and description carry the benchmark prices
def _home_numbers():
    th5, vn5 = pp.stats(PRICES, 'th_5'), pp.stats(PRICES, 'vn_5')
    if not (th5 and vn5):
        return
    home = PAGES[0]
    home['title'] = {'en': f"Rice prices today: Thai 5% ${pp.num(th5['usd'])}/t, Vietnam 5% ${pp.num(vn5['usd'])}/t, export & paddy prices | rice.ag",
                     'th': f"ราคาข้าววันนี้: ข้าวขาว 5% ไทย {pp.num(th5['usd'])} ดอลลาร์/ตัน เวียดนาม {pp.num(vn5['usd'])} ราคาส่งออกและข้าวเปลือก | rice.ag"}
_home_numbers()

def url_for(path, lang):
    return path if lang == 'en' else '/th' + path

def jsonld(p, lang, url):
    graph = [ORG, {"@type": "WebSite", "@id": BASE_URL + "/#site", "url": BASE_URL + "/", "name": "rice.ag",
                   "publisher": {"@id": ORG["@id"]}, "inLanguage": ["en", "th"]}]
    if p['key'] == 'scanner':
        graph.append({"@type": "SoftwareApplication", "name": "rice.ag Rice Grain Scanner", "url": BASE_URL + url,
                      "applicationCategory": "BusinessApplication", "operatingSystem": "Any (web browser)",
                      "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                      "description": p['desc'][lang], "publisher": {"@id": ORG["@id"]}, "inLanguage": lang})
    elif p['key'] == 'moisture':
        graph.append({"@type": "WebApplication", "name": p['title'][lang].split(' | ')[0], "url": BASE_URL + url,
                      "applicationCategory": "BusinessApplication", "operatingSystem": "Any (web browser)",
                      "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "publisher": {"@id": ORG["@id"]}})
    elif p['key'] == 'hub':
        h = p['hub']
        graph.append(pp.dataset_ld(h, PRICES, lang, url, BASE_URL, ORG['@id']))
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": 'ราคาข้าว' if lang == 'th' else 'Rice prices', "item": BASE_URL + url_for('/', lang)},
            {"@type": "ListItem", "position": 2, "name": h['name'][lang], "item": BASE_URL + url}]})
    elif p['key'] == 'fertilizer':
        graph.append({"@type": "Dataset", "name": p['title'][lang].split(':')[0], "url": BASE_URL + url, "description": p['desc'][lang],
                      "inLanguage": lang, "isAccessibleForFree": True, "creator": {"@id": ORG["@id"]},
                      "variableMeasured": "Fertilizer retail price, THB per 50 kg bag", "spatialCoverage": "Thailand",
                      "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": BASE_URL + "/static/data/fertilizer.json"}]})
    elif p['key'] == 'prices':
        graph.append({"@type": "Dataset", "name": "rice.ag rice price tracker", "url": BASE_URL + url, "description": p['desc'][lang],
                      "inLanguage": lang, "isAccessibleForFree": True, "temporalCoverage": "1960-01/..",
                      "variableMeasured": "Rice price, USD per tonne", "creator": {"@id": ORG["@id"]},
                      "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": BASE_URL + "/static/data/prices.csv"},
                                       {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": BASE_URL + "/static/data/prices.json"}]})
    elif p.get('kind') == 'article':
        graph.append({"@type": "Article", "headline": p['title'][lang].split(' | ')[0], "description": p['desc'][lang],
                      "url": BASE_URL + url, "inLanguage": lang, "datePublished": "2026-09-26", "dateModified": TODAY,
                      "author": {"@id": ORG["@id"]}, "publisher": {"@id": ORG["@id"]},
                      "image": BASE_URL + "/static/img/og.png", "isPartOf": {"@id": BASE_URL + "/#site"}})
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)

def write_brief_feeds(brief):
    """/brief/feed.xml and /th/brief/feed.xml. Written even when the brief is missing, so the URL never 404s."""
    from xml.sax.saxutils import escape
    import email.utils
    names = {'oni': ('El Niño (ONI)', 'เอลนีโญ (ONI)'), 'fob': ('Thai 5% export price', 'ราคาส่งออกข้าวขาว 5%'),
             'paddy': ('Thai paddy price', 'ราคาข้าวเปลือก'), 'fx': ('Baht (USD/THB)', 'ค่าเงินบาท'),
             'india': ("India's export policy", 'นโยบายส่งออกข้าวของอินเดีย')}
    sig = {'up': ('pointing up', 'ชี้ขึ้น'), 'down': ('pointing down', 'ชี้ลง'), 'steady': ('steady', 'ทรงตัว'),
           'unknown': ('no data', 'ไม่มีข้อมูล')}
    for lang in ('en', 'th'):
        th = lang == 'th'; k = 1 if th else 0
        link = BASE_URL + url_for('/brief/', lang)
        items = ''
        if brief.get('week_of') and brief.get('summary'):
            s = brief['summary']
            wk = fdate(brief['week_of'], lang)
            title = (f'สรุปตลาดข้าวสัปดาห์ของวันที่ {wk}: {s["up"]} จาก {s["known"]} สัญญาณชี้ว่าราคาข้าวไทยสูงขึ้น' if th else
                     f'Rice brief, week of {wk}: {s["up"]} of {s["known"]} signals point to higher Thai rice prices')
            lines = [f'{names.get(i["id"], (i["id"], i["id"]))[k]}: {sig.get(i.get("signal"), sig["unknown"])[k]}'
                     for i in brief.get('indicators', [])]
            note = brief.get('note_th' if th else 'note_en')
            desc = '<p>' + '<br>'.join(escape(x) for x in lines) + '</p>' + (f'<p>{escape(note)}</p>' if note else '')
            desc += f'<p><a href="{link}">{"อ่านฉบับเต็ม" if th else "Read the full brief"}</a></p>'
            pub = datetime.datetime.fromisoformat(brief['week_of']).replace(tzinfo=datetime.timezone.utc)
            items = (f'<item><title>{escape(title)}</title><link>{link}</link>'
                     f'<guid isPermaLink="false">rice.ag-brief-{lang}-{brief["week_of"]}</guid>'
                     f'<pubDate>{email.utils.format_datetime(pub)}</pubDate>'
                     f'<description>{escape(desc)}</description></item>')
        ch_title = 'rice.ag – สรุปสัญญาณตลาดข้าวรายสัปดาห์' if th else 'rice.ag – weekly rice early-warning brief'
        ch_desc = ('ห้าสัญญาณที่ขับเคลื่อนราคาข้าวไทย ทุกสัปดาห์' if th else
                   'The five signals that move Thai rice prices, every week.')
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
               f'<title>{escape(ch_title)}</title><link>{link}</link><description>{escape(ch_desc)}</description>'
               f'<language>{lang}</language><atom:link href="{link}feed.xml" rel="self" type="application/rss+xml"/>'
               f'{items}</channel></rss>\n')
        out = DIST / url_for('/brief/', lang).lstrip('/') / 'feed.xml'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(xml, encoding='utf-8')

def main():
    if DIST.exists(): shutil.rmtree(DIST)
    DIST.mkdir()
    # static
    shutil.copytree(SRC / 'static', DIST / 'static')
    data = DIST / 'static/data'; data.mkdir(exist_ok=True)
    if not (data / 'prices.json').exists():
        (data / 'prices.json').write_text('{"generated":"1970-01-01T00:00:00Z","groups":[],"series":{},"sources":{}}')
    for f in (SRC / 'root').glob('*'):
        shutil.copy(f, DIST / f.name)
    ver = hashlib.md5(b''.join(p.read_bytes() for p in sorted((SRC / 'static').rglob('*')) if p.is_file())).hexdigest()[:8]
    w = DIST / 'static/js/worker.js'; w.write_text(w.read_text().replace('__VER__', ver))

    sitemap = []
    for p in PAGES:
        for lang in ('en', 'th'):
            T = I18N[lang]; prefix = '' if lang == 'en' else '/th'
            url = url_for(p['path'], lang); alt_lang = 'th' if lang == 'en' else 'en'
            ctx = dict(lang=lang, T=T, prefix=prefix, url=url, base_url=BASE_URL, year=datetime.date.today().year, ver=ver)
            if p['key'] == 'brief':
                ctx['brief'] = load_brief()
            if p['key'] == 'prices':
                seen, groups = set(), []
                for gr in PRICES.get('groups', []):
                    rows = []
                    for sid in gr['series'] + gr.get('table_extra', []):
                        st = pp.stats(PRICES, sid)
                        if st and sid not in seen:
                            seen.add(sid); rows.append(st)
                    groups.append((gr[lang], rows))
                ctx['px'] = dict(groups=[g for g in groups if g[1]], verdict=pp.market_verdict(PRICES, load_brief(), lang),
                                 generated=PRICES.get('generated'))
            if p['key'] == 'hub':
                ctx.update(hub=p['hub'], fill=p['fill'][lang], india=pp.load_india(), generated=PRICES.get('generated'))
            if p['key'] in ('fertilizer', 'fformula', 'fblend', 'frice'):
                _paddy = (FERT.get('paddy') or {}).get('baht_per_kg')
                ctx.update(F=dict(FERT), fert=dict(FERT, lead=fert_lead(FERT, lang)), fpages=FPAGES,
                           fpage_keys=[x['npk'] for x in FPAGES], paddy_kg=_paddy)
            if p['key'] == 'fformula':
                ctx.update(ff=p['ff'][lang])
            if p['key'] == 'fblend':
                ctx.update(blendt=BLENDT, shopmed=FERT['calc']['formulas'])
            if p['key'] == 'frice':
                ctx.update(rice=RICE, ricejs=dict(opts=RICE['opts'], top=RICE['top'], plan=RICE['plan'], paddy=_paddy))
            if p['key'] == 'fertilizer':
                ctx.update(fert=dict(FERT, lead=fert_lead(FERT, lang)),
                           charts=dict(world={'2y': pp.fert_chart(FERT, ['urea', 'dap', 'kcl'], lang, years=2),
                                              '10y': pp.fert_chart(FERT, ['urea', 'dap', 'kcl'], lang, years=10),
                                              'all': pp.fert_chart(FERT, ['urea', 'dap', 'kcl'], lang, years=27)},
                                       paddy_bag=pp.paddy_bag_chart(FERT, lang)))
            if p['src'].startswith('shared/'):
                body = ''
                if p.get('body'):
                    body = env.get_template(f"{lang}/{p['body']}.html").render(**ctx)
                content = env.get_template(p['src']).render(body=body, **ctx)
            else:
                content = env.get_template(f"{lang}/{p['src']}.html").render(**ctx)
            scripts = ''
            if p.get('app'):
                scripts = (f'<script>window.RICE_T={json.dumps(T, ensure_ascii=False)};'
                           f'window.RICE_WORKER="/static/js/worker.js?v={ver}";window.RICE_SAMPLE="/static/img/sample-rice.jpg";</script>\n'
                           f'<script src="/static/js/engine.js?v={ver}"></script>\n<script src="/static/js/app.js?v={ver}"></script>')
            for js in p.get('js', []):
                scripts += f'\n<script src="/static/js/{js}?v={ver}" defer></script>'
            if CF_ANALYTICS_TOKEN:
                scripts += ('\n<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                            f'data-cf-beacon=\'{{"token": "{CF_ANALYTICS_TOKEN}"}}\'></script>')
            html = env.get_template('base.html').render(
                page=dict(title=p['title'][lang], description=p['desc'][lang], kind=p.get('kind')),
                content=content, scripts=scripts, section=p['section'],
                url_en=url_for(p['path'], 'en'), url_th=url_for(p['path'], 'th'),
                alt_url=url_for(p['path'], alt_lang), alt_lang=alt_lang,
                jsonld=jsonld(p, lang, url).replace('</', '<\\/'), **ctx)
            out = DIST / url.lstrip('/') / 'index.html'
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding='utf-8')
        sitemap.append(p['path'])

    # embeddable charts at /embed/<slug>/ (noindex; framing allowed in _headers)
    for p in PAGES:
        if p['key'] != 'hub':
            continue
        for lang in ('en', 'th'):
            prefix = '' if lang == 'en' else '/th'
            html = env.get_template('embed.html').render(
                lang=lang, hub=p['hub'], fill=p['fill'][lang], generated=PRICES.get('generated'),
                base_url=BASE_URL, page_url=url_for(p['path'], lang), ver=ver)
            out = DIST / f"{prefix.lstrip('/')}/embed/{p['hub']['slug']}/index.html".lstrip('/')
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding='utf-8')

    # RSS feed for the weekly brief: one item per week (guid = week), so readers get a new post each Monday
    write_brief_feeds(load_brief())

    # 404 (bilingual, root)
    ctx = dict(lang='en', T=I18N['en'], prefix='', url='/404', base_url=BASE_URL, year=datetime.date.today().year, ver=ver)
    html = env.get_template('base.html').render(
        page=dict(title='Page not found | rice.ag', description='Page not found', kind=None),
        content=env.get_template('en/404.html').render(**ctx), scripts='', section='',
        url_en='/', url_th='/th/', alt_url='/th/', alt_lang='th', jsonld='{}', **ctx)
    (DIST / '404.html').write_text(html.replace('<link rel="canonical" href="https://rice.ag/404">', '<meta name="robots" content="noindex">'), encoding='utf-8')

    # sitemap with hreflang
    xs = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for path in sitemap:
        for lang in ('en', 'th'):
            xs.append(f'<url><loc>{BASE_URL}{url_for(path, lang)}</loc><lastmod>{TODAY}</lastmod>'
                      f'<xhtml:link rel="alternate" hreflang="en" href="{BASE_URL}{url_for(path, "en")}"/>'
                      f'<xhtml:link rel="alternate" hreflang="th" href="{BASE_URL}{url_for(path, "th")}"/>'
                      f'<xhtml:link rel="alternate" hreflang="x-default" href="{BASE_URL}{url_for(path, "en")}"/></url>')
    xs.append('</urlset>')
    (DIST / 'sitemap.xml').write_text('\n'.join(xs), encoding='utf-8')
    (DIST / 'robots.txt').write_text(f'User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n')
    print('built', len(PAGES) * 2 + 1, 'pages, ver', ver)

if __name__ == '__main__':
    main()
