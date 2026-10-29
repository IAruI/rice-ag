"""What rice.ag/prices shows, and where each line comes from.

SERIES[id]['from'] lists (source, raw series id) in priority order. The first source
with data is used in full; each lower-priority source only adds points *earlier* than
anything already taken. So recent data comes from the most direct, most frequent
source, and long history is spliced on from slower ones.

To add a line: add it here (and to a GROUP), push, and the next daily run includes it.
"""

SOURCES = {
    'trea': {'name': 'Thai Rice Exporters Association', 'url': 'http://www.thairiceexporters.or.th/price_eng.html',
             'freq': 'weekly (Wednesday quotes) + monthly averages',
             'terms': 'Public price list; credited and linked.'},
    'fao': {'name': 'FAO GIEWS Food Price Monitoring and Analysis (FPMA)', 'url': 'https://fpma.fao.org/giews/fpmat4/#/dashboard/tool/international',
            'freq': 'weekly / monthly',
            'terms': 'FAO data, non-commercial reuse with attribution.',
            'series': [
                'eb6de409-12ab-4d90-a427-ecaec4c13edb',  # Thailand 5% broken (weekly from 2000)
                'c7208b39-2617-426c-b248-c975cb951254',  # Thailand 100% B (weekly from 1989)
                'd7130a81-3eea-4d1c-a57d-77bf02ff8dd2',  # Thailand A1 Super (weekly from 1989)
                '92abeed2-d741-4cfa-9bd3-cd630456e051',  # Thailand fragrant 100%
                '7a2d1b6f-58e7-4998-b697-100a9e281e9a',  # Thailand glutinous 10%
                '2984e2ac-ce7d-4025-aa11-42a3f8a8c81c',  # Thailand parboiled 100%
                'ec5d9f1a-40a7-43f0-b745-761aa96a08ee',  # Viet Nam 5% broken
                'd01dd4c4-6815-4af9-aabf-3bf1c6b02bb3',  # US No.2 4% long grain
                '49761070-9158-4170-bc94-6d990e1451df',  # Uruguay 5% broken
                '1351def4-604a-4b21-815f-1e24792a5942',  # Pakistan Super Kernel Basmati 2%
            ]},
    'wb': {'name': 'World Bank Commodity Price Data (Pink Sheet)', 'url': 'https://www.worldbank.org/en/research/commodity-markets',
           'freq': 'monthly', 'terms': 'CC BY 4.0.'},
    'dit': {'name': 'Department of Internal Trade, Thailand (กรมการค้าภายใน)', 'url': 'https://pricelist.dit.go.th/',
            'freq': 'daily (business days)', 'terms': 'Thai government public price list; credited and linked.',
            'series': {
                'R11057': {'group': 'R11000'},  # ข้าวเปลือกเจ้า
                'R11055': {'group': 'R11000'},  # ข้าวเปลือกหอมมะลิ
                'R11058': {'group': 'R11000'},  # ข้าวเปลือกปทุมธานี
                'R11059': {'group': 'R11000'},  # ข้าวเปลือกเหนียวเมล็ดยาว
                'R11054': {'group': 'R11000'},  # ข้าวเปลือกเจ้า 5% นาปี จ.สุพรรณบุรี
                'R11007': {'group': 'R11000'},  # ข้าวขาว 5% (wholesale, Bangkok)
                'R11029': {'group': 'R11000'},  # ข้าวหอมมะลิ 100% ชั้น 1 (wholesale, Bangkok)
                'R11018': {'group': 'R11000'},  # ข้าวสารเหนียว กข.6 (wholesale, Bangkok)
            }},
    'fx': {'name': 'European Central Bank reference rates (via Frankfurter)', 'url': 'https://frankfurter.dev/',
           'freq': 'daily', 'terms': 'Used to convert THB prices to USD.'},
}

FOB = {'en': 'Export, FOB', 'th': 'ส่งออก FOB'}
DOM = {'en': 'Thai domestic wholesale', 'th': 'ขายส่งในประเทศ'}
MILLED, PADDY = 'milled', 'paddy'

SERIES = {
    # ---- export prices by origin
    'th_5': dict(en='Thailand white rice 5%', th='ไทย ข้าวขาว 5%', origin='TH', basis=MILLED, market=FOB,
                 **{'from': [('trea', 'w:w5'), ('fao', 'w:eb6de409-12ab-4d90-a427-ecaec4c13edb'),
                             ('trea', 'm:white-rice-5'), ('wb', 'rice-thai-5')]}),
    'vn_5': dict(en='Viet Nam white rice 5%', th='เวียดนาม ข้าวขาว 5%', origin='VN', basis=MILLED, market=FOB,
                 **{'from': [('fao', 'm:ec5d9f1a-40a7-43f0-b745-761aa96a08ee'), ('wb', 'rice-viet-namese-5')]}),
    'us_lg': dict(en='US long grain No.2, 4%', th='สหรัฐฯ เมล็ดยาว No.2 4%', origin='US', basis=MILLED, market=FOB,
                  **{'from': [('fao', 'm:d01dd4c4-6815-4af9-aabf-3bf1c6b02bb3')]}),
    'uy_5': dict(en='Uruguay white rice 5%', th='อุรุกวัย ข้าวขาว 5%', origin='UY', basis=MILLED, market=FOB,
                 **{'from': [('fao', 'm:49761070-9158-4170-bc94-6d990e1451df')]}),
    'pk_basmati': dict(en='Pakistan Super Kernel basmati 2%', th='ปากีสถาน บาสมาติ 2%', origin='PK', basis=MILLED, market=FOB,
                       **{'from': [('fao', 'm:1351def4-604a-4b21-815f-1e24792a5942')]}),
    'th_hm': dict(en='Thai Hom Mali (premium)', th='ไทย ข้าวหอมมะลิ (พรีเมียม)', origin='TH', basis=MILLED, market=FOB,
                  note_en='Newest crop year. Before 2018: FAO "fragrant 100%".',
                  note_th='ใช้ปีการผลิตล่าสุด ก่อนปี 2561 ใช้ข้าวหอม 100% จาก FAO',
                  **{'from': [('trea', 'w:hm_prem_new'), ('trea', 'm:hom-mali-premium-quality-latest-crop'),
                              ('fao', 'm:92abeed2-d741-4cfa-9bd3-cd630456e051')]}),
    # ---- other Thai export grades
    'th_100b': dict(en='Thai white 100% grade B', th='ไทย ข้าวขาว 100% ชั้น 2', origin='TH', basis=MILLED, market=FOB,
                    **{'from': [('trea', 'w:w100b'), ('fao', 'w:c7208b39-2617-426c-b248-c975cb951254'),
                                ('trea', 'm:white-rice-100-grade-b')]}),
    'th_25': dict(en='Thai white 25%', th='ไทย ข้าวขาว 25%', origin='TH', basis=MILLED, market=FOB,
                  **{'from': [('trea', 'w:w25'), ('trea', 'm:white-rice-25'), ('wb', 'rice-thai-25')]}),
    'th_a1s': dict(en='Thai broken A1 Super', th='ไทย ปลายข้าว เอ1 ซุปเปอร์', origin='TH', basis=MILLED, market=FOB,
                   **{'from': [('trea', 'w:a1s'), ('fao', 'w:d7130a81-3eea-4d1c-a57d-77bf02ff8dd2'),
                               ('trea', 'm:white-broken-rice-a-1-super'), ('wb', 'rice-thai-a-1')]}),
    'th_jas': dict(en='Thai jasmine (Pathum fragrant)', th='ไทย ข้าวหอมไทย (ปทุมธานี)', origin='TH', basis=MILLED, market=FOB,
                   **{'from': [('trea', 'w:jasmine'), ('trea', 'm:thai-jasmine-rice')]}),
    'th_glu': dict(en='Thai glutinous 10%', th='ไทย ข้าวเหนียว 10%', origin='TH', basis=MILLED, market=FOB,
                   **{'from': [('trea', 'w:glu10'), ('trea', 'm:white-glutinous-rice-10-major-crop'),
                               ('fao', 'm:7a2d1b6f-58e7-4998-b697-100a9e281e9a')]}),
    'th_pb': dict(en='Thai parboiled 100%', th='ไทย ข้าวนึ่ง 100%', origin='TH', basis=MILLED, market=FOB,
                  **{'from': [('trea', 'w:pb100'), ('trea', 'm:parboiled-rice-100'),
                              ('fao', 'm:2984e2ac-ce7d-4025-aa11-42a3f8a8c81c')]}),
    'th_hmbrk': dict(en='Thai Hom Mali broken A1 Super', th='ไทย ปลายข้าวหอมมะลิ เอ1 ซุปเปอร์', origin='TH', basis=MILLED, market=FOB,
                     **{'from': [('trea', 'w:hm_brk_a1s'), ('trea', 'm:thai-hom-mali-broken-rice-a-1-super')]}),
    # ---- Thai domestic (DIT, THB converted at the day's ECB rate)
    'dit_paddy': dict(en='White paddy', th='ข้าวเปลือกเจ้า', origin='TH', basis=PADDY, market=DOM, currency='THB',
                      **{'from': [('dit', 'R11057')]}),
    'dit_paddy_supan': dict(en='White paddy 5%, wet season, Suphan Buri', th='ข้าวเปลือกเจ้า 5% นาปี สุพรรณบุรี', origin='TH',
                            basis=PADDY, market=DOM, currency='THB', **{'from': [('dit', 'R11054')]}),
    'dit_paddy_hm': dict(en='Hom Mali paddy', th='ข้าวเปลือกหอมมะลิ', origin='TH', basis=PADDY, market=DOM, currency='THB',
                         **{'from': [('dit', 'R11055')]}),
    'dit_paddy_pathum': dict(en='Pathum Thani fragrant paddy', th='ข้าวเปลือกปทุมธานี', origin='TH', basis=PADDY, market=DOM,
                             currency='THB', **{'from': [('dit', 'R11058')]}),
    'dit_paddy_glu': dict(en='Glutinous paddy, long grain', th='ข้าวเปลือกเหนียวเมล็ดยาว', origin='TH', basis=PADDY, market=DOM,
                          currency='THB', **{'from': [('dit', 'R11059')]}),
    'dit_w5': dict(en='White rice 5%, Bangkok wholesale', th='ข้าวขาว 5% ขายส่ง กทม.', origin='TH', basis=MILLED, market=DOM,
                   currency='THB', **{'from': [('dit', 'R11007')]}),
    'dit_hm': dict(en='Hom Mali 100% grade 1, Bangkok wholesale', th='ข้าวหอมมะลิ 100% ชั้น 1 ขายส่ง กทม.', origin='TH',
                   basis=MILLED, market=DOM, currency='THB', **{'from': [('dit', 'R11029')]}),
    'dit_glu': dict(en='Glutinous RD6 milled, Bangkok wholesale', th='ข้าวสารเหนียว กข.6 ขายส่ง กทม.', origin='TH',
                    basis=MILLED, market=DOM, currency='THB', **{'from': [('dit', 'R11018')]}),
}

GROUPS = [
    {'id': 'origins', 'en': 'Export prices by origin', 'th': 'ราคาส่งออกตามประเทศ',
     'desc_en': 'FOB export quotes for milled rice, USD per tonne.',
     'desc_th': 'ราคาส่งออก FOB ข้าวสาร ดอลลาร์สหรัฐต่อตัน',
     'series': ['th_5', 'vn_5', 'us_lg', 'uy_5', 'pk_basmati', 'th_hm']},
    {'id': 'thai', 'en': 'Thai export grades', 'th': 'ราคาส่งออกข้าวไทยตามชนิด',
     'desc_en': 'TREA FOB Bangkok quotes for milled rice, USD per tonne.',
     'desc_th': 'ราคาส่งออก FOB กรุงเทพฯ จากสมาคมผู้ส่งออกข้าวไทย ดอลลาร์สหรัฐต่อตัน',
     'series': ['th_5', 'th_jas', 'th_glu', 'th_100b', 'th_25', 'th_hm', 'th_pb', 'th_a1s'],
     'table_extra': ['th_hmbrk']},
    {'id': 'domestic', 'en': 'Thailand domestic: paddy and wholesale', 'th': 'ราคาในประเทศไทย: ข้าวเปลือกและขายส่ง',
     'desc_en': 'Department of Internal Trade daily prices, converted from baht at the ECB rate. Paddy is unmilled, so it is not comparable with milled prices.',
     'desc_th': 'ราคารายวันจากกรมการค้าภายใน แปลงจากบาทด้วยอัตราแลกเปลี่ยน ECB ข้าวเปลือกยังไม่สี จึงเทียบกับราคาข้าวสารโดยตรงไม่ได้',
     'series': ['dit_paddy', 'dit_paddy_supan', 'dit_paddy_hm', 'dit_paddy_pathum', 'dit_paddy_glu', 'dit_w5', 'dit_hm', 'dit_glu']},
]
