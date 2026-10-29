#!/usr/bin/env python3
"""rice.ag static site builder. Usage: python3 build.py  -> dist/"""
import json, shutil, hashlib, datetime, os, re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
SRC, DIST = ROOT / 'src', ROOT / 'dist'
BASE_URL = 'https://rice.ag'
TODAY = datetime.date.today().isoformat()
I18N = json.loads((SRC / 'i18n.json').read_text(encoding='utf-8'))

env = Environment(loader=FileSystemLoader([str(SRC / 'templates'), str(SRC / 'pages')]),
                  autoescape=select_autoescape(['html']), trim_blocks=True, lstrip_blocks=True)

ORG = {"@type": "Organization", "@id": BASE_URL + "/#org", "name": "rice.ag", "url": BASE_URL + "/",
       "logo": BASE_URL + "/icon-512.png"}

PAGES = [
    dict(key='home', path='/', src='home', section='home',
         title={'en': 'rice.ag — Free Rice Grain Scanner: broken rice %, grain size & quality from a photo',
                'th': 'rice.ag — เครื่องสแกนเมล็ดข้าวฟรี วัดข้าวหัก ขนาดเมล็ด และคุณภาพจากภาพถ่าย'},
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
    dict(key='prices', path='/prices/', src='shared/prices.html', section='prices', js=['prices.js'],
         title={'en': 'Rice prices today: Thai, Viet Nam, US export FOB & Thai paddy prices in USD/t | rice.ag',
                'th': 'ราคาข้าววันนี้: ราคาส่งออกข้าวไทย เวียดนาม สหรัฐฯ และราคาข้าวเปลือก (ดอลลาร์/ตัน) | rice.ag'},
         desc={'en': 'Free daily-updated rice price charts: Thai 5%, Hom Mali, jasmine, glutinous and parboiled export prices, Viet Nam, US, Uruguay and Pakistan FOB quotes, and Thai paddy prices, all in USD per tonne. Download the data.',
               'th': 'กราฟราคาข้าวอัปเดตทุกวัน ฟรี: ราคาส่งออกข้าวขาว 5% ข้าวหอมมะลิ ข้าวหอมไทย ข้าวเหนียว ข้าวนึ่ง ราคา FOB เวียดนาม สหรัฐฯ อุรุกวัย ปากีสถาน และราคาข้าวเปลือกไทย เป็นดอลลาร์ต่อตัน ดาวน์โหลดข้อมูลได้'}),
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
