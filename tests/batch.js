const sharp = require('/home/claude/.npm-global/lib/node_modules/sharp');
const fs = require('fs'); const eng = require('../src/static/js/engine.js');
(async () => {
  let tot = 0, correct = 0, lenErr = [], brokenErr = [], contam = { found: 0, n: 0 }, rcStone = { found: 0, n: 0 }, clumps = { f: 0, n: 0 }, chalkErr = [];
  for (let s = 0; s < 10; s++) {
    const f = `batch/b${s}.jpg`, truth = JSON.parse(fs.readFileSync(f + '.json'));
    const { data, info } = await sharp(f).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const r = eng.analyze({ width: info.width, height: info.height, data: new Uint8ClampedArray(data) }, { coinMM: 26 });
    const near = t => { let b = null, d = 1e9; for (const o of r.objects) { const q = Math.hypot(o.cx - t.x, o.cy - t.y); if (q < d) { d = q; b = o; } } return d < 25 ? b : null; };
    let tb = 0, tbw = 0, tw = 0, twA = 0; // truth broken by area approx (L*W)
    for (const t of truth.truth) {
      if (t.kind === 'whole' || t.kind === 'broken') {
        const exp = t.kind === 'whole' ? 'whole' : t.keep >= 0.9 ? 'whole' : t.keep >= 0.75 ? 'head' : t.keep >= 0.5 ? 'largeBroken' : t.keep >= 0.25 ? 'mediumBroken' : 'smallBroken';
        const o = near(t); tot++; if (o && (o.cls === exp || (exp === 'smallBroken' && o.cls === 'chip'))) correct++;
        const a = t.L * t.W; tw += a; if (t.kind === 'broken' && t.keep < 0.75) tbw += a;
      }
      if (t.kind === 'chip') tw += t.L * t.W, tbw += t.L * t.W;
      if (['stone_dark', 'yellow', 'paddy', 'husk'].includes(t.kind)) { contam.n++; const o = near(t); if (o && o.flags.length) contam.found++; }
      if (t.kind === 'stone_ricecolor') { rcStone.n++; const o = near(t); if (o && o.flags.length) rcStone.found++; }
      if (t.kind === 'clump') { clumps.n++; const o = near(t); if (o && o.cls === 'clump') clumps.f++; }
      if (t.kind === 'whole' && truth.mode === 'backlit') { const o = near(t); if (o && o.chalk != null) chalkErr.push(Math.abs(o.chalk - t.chalk)); }
    }
    lenErr.push(Math.abs(r.size.lengthMM - truth.length_mm));
    brokenErr.push(Math.abs(r.broken.weight - 100 * tbw / tw));
    console.log(f, truth.mode, 'broken est', r.broken.weight.toFixed(1), 'truth', (100 * tbw / tw).toFixed(1), 'len', r.size.lengthMM.toFixed(2), 'vs', truth.length_mm.toFixed(2), 'warn', r.warnings.join(','));
  }
  const m = a => a.reduce((s, v) => s + v, 0) / a.length;
  console.log({ kernelAccuracy: (100 * correct / tot).toFixed(2) + '% of ' + tot, meanLenErrMM: m(lenErr).toFixed(3), maxLenErrMM: Math.max(...lenErr).toFixed(3),
    meanBrokenErrPts: m(brokenErr).toFixed(2), maxBrokenErrPts: Math.max(...brokenErr).toFixed(2),
    contaminantsFlagged: contam.found + '/' + contam.n, riceColouredStonesFlagged: rcStone.found + '/' + rcStone.n, clumpsDetected: clumps.f + '/' + clumps.n,
    chalkMAE: chalkErr.length ? m(chalkErr).toFixed(3) : null });
})();
