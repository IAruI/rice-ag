// Usage: node run.js image.png [coinMM] [lighting]
const sharp = require('/home/claude/.npm-global/lib/node_modules/sharp');
const fs = require('fs');
const eng = require('../src/static/js/engine.js');

(async () => {
  const file = process.argv[2];
  const coinMM = process.argv[3] && process.argv[3] !== 'none' ? parseFloat(process.argv[3]) : null;
  const lighting = process.argv[4] || 'auto';
  const { data, info } = await sharp(file).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const res = eng.analyze({ width: info.width, height: info.height, data: new Uint8ClampedArray(data) }, { coinMM, lighting });
  const out = { file, ok: res.ok, mode: res.mode, ms: res.ms, warnings: res.warnings };
  if (!res.ok) { console.log(JSON.stringify(out, null, 1), res.error); return; }
  Object.assign(out, {
    counts: res.counts, headRice: res.headRice, broken: res.broken,
    byCount: res.byCount, size: res.size, colour: res.colour, chalk: res.chalk, flags: res.flags,
    scale: res.scale, Lref: res.Lref,
  });
  let truth = null;
  if (fs.existsSync(file + '.json')) truth = JSON.parse(fs.readFileSync(file + '.json'));
  if (truth) {
    const objs = res.objects;
    const nearest = (t) => {
      let best = null, bd = 1e9;
      for (const o of objs) { const d = Math.hypot(o.cx - t.x, o.cy - t.y); if (d < bd) { bd = d; best = o; } }
      return bd < 25 ? best : null;
    };
    const conf = {};
    let chalkErr = [];
    for (const t of truth.truth) {
      if (t.kind === 'coin') continue;
      const o = nearest(t);
      const exp = t.kind === 'broken' ? (t.keep >= 0.9 ? 'whole' : t.keep >= 0.75 ? 'head' : t.keep >= 0.5 ? 'largeBroken' : t.keep >= 0.25 ? 'mediumBroken' : 'smallBroken') : t.kind;
      const got = o ? o.cls + (o.flags.length ? '[' + o.flags.join(',') + ']' : '') : 'MISSING';
      const key = exp + ' -> ' + got;
      conf[key] = (conf[key] || 0) + 1;
      if (o && t.chalk !== undefined && o.chalk != null && res.mode === 'backlit' && t.kind === 'whole') chalkErr.push(o.chalk - t.chalk);
    }
    out.confusion = Object.fromEntries(Object.entries(conf).sort());
    if (chalkErr.length) out.chalkMeanAbsErr = chalkErr.reduce((s, v) => s + Math.abs(v), 0) / chalkErr.length;
    const tb = truth.truth.filter(t => ['whole', 'broken'].includes(t.kind));
    const tBroken = tb.filter(t => t.kind === 'broken' && t.keep < 0.75).length;
    out.truthBrokenPctCount = 100 * tBroken / (tb.length + truth.truth.filter(t => t.kind === 'chip').length);
    out.truthLengthMM = truth.length_mm;
  }
  console.log(JSON.stringify(out, (k, v) => typeof v === 'number' ? Math.round(v * 100) / 100 : v, 1));
})();
