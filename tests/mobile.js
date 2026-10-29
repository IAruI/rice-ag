const { chromium, devices } = require('/home/claude/.npm-global/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ ...devices['iPhone 13'], acceptDownloads: true });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error' && !/fonts|TUNNEL/.test(m.text())) errs.push(m.text()); });
  await p.goto('http://localhost:8765/scanner/');
  await p.setInputFiles('#fFile', 'tests/batch/b1.jpg');
  await p.waitForSelector('#results .stats', { timeout: 30000 });
  await p.waitForTimeout(800);
  const info = await p.evaluate(() => {
    const cv = document.getElementById('cv'); const g = cv.getContext('2d');
    const d = g.getImageData(0, 0, cv.width, cv.height).data; let nz = 0; for (let i = 0; i < d.length; i += 400) if (d[i] > 20) nz++;
    const thumbs = [...document.querySelectorAll('.flag canvas')].map(c => { const x = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let s = 0; for (let i = 0; i < x.length; i += 4) s += x[i]; return Math.round(s / (x.length / 4)); });
    return { w: cv.width, h: cv.height, brightSamples: nz, thumbsMeanRed: thumbs, displayed: cv.getBoundingClientRect().width, stats: [...document.querySelectorAll('.stat .v')].map(e => e.textContent) };
  });
  const [dl] = await Promise.all([p.waitForEvent('download', { timeout: 10000 }).catch(() => null), p.click('#bPng')]);
  info.download = dl ? dl.suggestedFilename() : 'NONE';
  info.errs = errs;
  await p.screenshot({ path: 'tests/shot-iphone.png', fullPage: false });
  console.log(JSON.stringify(info));
  await b.close();
})();
