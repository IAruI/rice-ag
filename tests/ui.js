const { chromium } = require('/home/claude/.npm-global/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch();
  const out = {};
  for (const [name, vp] of [['desktop', { width: 1366, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
    const p = await b.newPage({ viewport: vp, deviceScaleFactor: 1 });
    const errs = [];
    p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    p.on('pageerror', e => errs.push('PAGEERR ' + e.message));
    await p.goto('http://localhost:8765/scanner/?sample=1');
    await p.waitForSelector('#results .stats', { timeout: 30000 });
    await p.waitForTimeout(500);
    out[name] = { errs: errs.filter(e => !/fonts\.g/.test(e)), stats: await p.$$eval('.stat .v', els => els.map(e => e.textContent)), meta: await p.textContent('#meta') };
    await p.screenshot({ path: `tests/shot-scanner-${name}.png`, fullPage: true });
    // horizontal overflow check
    out[name].overflow = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    if (name === 'desktop') {
      const data = await p.evaluate(() => document.getElementById('cv').toDataURL('image/jpeg', 0.9));
      require('fs').writeFileSync('tests/hero-full.jpg', Buffer.from(data.split(',')[1], 'base64'));
    }
    await p.close();
  }
  for (const path of ['/', '/th/', '/guide/', '/th/scanner/', '/tools/moisture-calculator/', '/th/learn/chainat-1-noodle-rice/', '/methodology/', '/about/', '/404.html']) {
    const p = await b.newPage({ viewport: { width: 390, height: 844 } });
    const errs = []; p.on('pageerror', e => errs.push(e.message));
    const r = await p.goto('http://localhost:8765' + path);
    const ov = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    out[path] = { status: r.status(), errs, overflow: ov };
    if (path === '/' || path === '/tools/moisture-calculator/' || path === '/th/') await p.screenshot({ path: `tests/shot${path.replace(/\//g, '_')}.png`, fullPage: true });
    if (path === '/tools/moisture-calculator/') out.calc = await p.textContent('#bOut');
    await p.close();
  }
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
