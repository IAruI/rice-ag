/* rice.ag scanner UI */
(function () {
  'use strict';
  const T = window.RICE_T || {};
  const LANG = document.documentElement.lang || 'en';
  const $ = id => document.getElementById(id);
  const fmt = (s, o) => s.replace(/\{(\w+)\}/g, (_, k) => o[k]);
  const nf = (v, d = 1) => (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString(LANG === 'th' ? 'th-TH' : 'en-US', { minimumFractionDigits: d, maximumFractionDigits: d });

  const COLORS = {
    whole: '#2FBF71', head: '#9BE07A', largeBroken: '#F6C343', mediumBroken: '#F39237',
    smallBroken: '#E8553E', chip: '#C166E8', clump: '#9AA3AD', object: '#FF2D6F', coin: '#3D8BFD', edge: '#5b6168'
  };
  const CLASSES = ['whole', 'head', 'largeBroken', 'mediumBroken', 'smallBroken', 'chip'];
  // iOS Safari has a small total budget for canvas memory; keep images modest on phones
  const IS_TOUCH = matchMedia('(pointer: coarse)').matches || /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  const MAX_SIDE = IS_TOUCH ? 2000 : 2400;

  let srcData = null;        // original (downscaled) pixels, kept as ImageData (JS memory, not canvas memory)
  let pngBlob = null;        // pre-rendered export so phone share sheets open instantly
  let result = null;
  let overlayOn = true;
  let highlight = null;
  let sourceName = 'scan';

  const cv = $('cv'), ctx = cv.getContext('2d');
  let worker = null;
  function getWorker() {
    if (!worker) worker = new Worker(window.RICE_WORKER);
    return worker;
  }

  // ---------- image input ----------
  function loadFile(file) {
    if (!file) return;
    sourceName = (file.name || 'scan').replace(/\.[^.]+$/, '');
    const url = URL.createObjectURL(file);
    loadUrl(url, sourceName, true);
  }
  function loadUrl(url, name, revoke) {
    sourceName = name || 'sample';
    const img = new Image();
    img.decoding = 'async';
    img.onload = () => {
      try { setSource(img); } catch (e) { showError(T.e_load); return; }
      if (revoke) URL.revokeObjectURL(url);
      img.src = '';
      run();
    };
    img.onerror = () => { if (revoke) URL.revokeObjectURL(url); showError(T.e_load); };
    img.src = url;
  }
  function setSource(img) {
    const w0 = img.naturalWidth || img.width, h0 = img.naturalHeight || img.height;
    const k = Math.min(1, MAX_SIDE / Math.max(w0, h0));
    const w = Math.round(w0 * k), h = Math.round(h0 * k);
    // draw straight into the visible canvas (one canvas instead of two), then keep a pixel copy
    cv.width = w; cv.height = h;
    ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, 0, 0, w, h);
    srcData = ctx.getImageData(0, 0, w, h);
    $('empty').classList.add('hidden');
    cv.classList.remove('hidden');
    $('bRun').disabled = false;
    result = null; pngBlob = null;
    $('results').classList.add('hidden'); $('tools').classList.add('hidden');
  }

  function options() {
    let coin = $('oCoin').value;
    let coinMM = null;
    if (coin === 'custom') coinMM = parseFloat($('oCoinMM').value) || null;
    else if (coin) coinMM = parseFloat(coin);
    const known = parseFloat($('oKnown').value);
    return {
      lighting: $('oLight').value,
      coinMM,
      knownLengthMM: known > 0 ? known : null,
      chalkRatio: parseFloat($('oChalk').value) || 0.45
    };
  }

  function run() {
    if (!srcData) return;
    $('busy').classList.remove('hidden');
    $('bRun').disabled = true;
    const w = srcData.width, h = srcData.height;
    const copy = new Uint8ClampedArray(srcData.data);
    const opts = options();
    const done = (res) => {
      $('busy').classList.add('hidden');
      $('bRun').disabled = false;
      if (!res.ok) { result = null; draw(); showError(T['e_' + res.error] || res.error, res.warnings); return; }
      result = res; highlight = null; draw(); renderResults();
      setTimeout(prepareExport, 50);
      if (window.innerWidth < 960) $('stage').scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
    try {
      const wk = getWorker();
      wk.onmessage = (e) => { if (e.data.ok) done(e.data.res); else { $('busy').classList.add('hidden'); $('bRun').disabled = false; showError(e.data.error); } };
      wk.onerror = () => { worker = null; fallback(); };
      wk.postMessage({ width: w, height: h, buffer: copy.buffer, options: opts }, [copy.buffer]);
    } catch (e) { fallback(); }
    function fallback() {
      setTimeout(() => done(window.RiceScanner.analyze({ width: w, height: h, data: new Uint8ClampedArray(srcData.data) }, opts)), 30);
    }
  }

  // ---------- drawing ----------
  function draw() {
    if (!srcData) return;
    ctx.putImageData(srcData, 0, 0);
    if (!result || !overlayOn) return;
    const lw = Math.max(1.5, Math.min(cv.width, cv.height) / 500);
    ctx.lineWidth = lw;
    for (const o of result.objects) {
      const col = COLORS[o.cls] || '#fff';
      ctx.save();
      ctx.strokeStyle = col;
      if (o.cls === 'clump' || o.cls === 'edge') ctx.setLineDash([lw * 3, lw * 2]);
      ctx.beginPath();
      ctx.ellipse(o.cx, o.cy, Math.max(2, o.L / 2 + lw), Math.max(2, o.W / 2 + lw), o.theta, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
    // flags
    let n = 0;
    const fs = Math.max(12, Math.round(Math.min(cv.width, cv.height) / 55));
    ctx.font = `600 ${fs}px system-ui, sans-serif`;
    for (const o of flaggedList()) {
      n++;
      const [x0, y0, x1, y1] = o.bbox, pad = lw * 4;
      ctx.strokeStyle = COLORS.object; ctx.lineWidth = lw * 1.6;
      ctx.strokeRect(x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad);
      const label = String(n), tw = ctx.measureText(label).width + fs * 0.6;
      ctx.fillStyle = COLORS.object; ctx.fillRect(x0 - pad, y0 - pad - fs * 1.3, tw, fs * 1.3);
      ctx.fillStyle = '#fff'; ctx.fillText(label, x0 - pad + fs * 0.3, y0 - pad - fs * 0.3);
      ctx.lineWidth = lw;
    }
    if (result.coin) {
      ctx.strokeStyle = COLORS.coin; ctx.lineWidth = lw * 2;
      ctx.beginPath(); ctx.arc(result.coin.cx, result.coin.cy, result.coin.r + lw * 2, 0, Math.PI * 2); ctx.stroke();
    }
    if (highlight) {
      const [x0, y0, x1, y1] = highlight.bbox;
      const r = Math.max(x1 - x0, y1 - y0) / 2 + 30;
      ctx.strokeStyle = '#fff'; ctx.lineWidth = lw * 3;
      ctx.beginPath(); ctx.arc((x0 + x1) / 2, (y0 + y1) / 2, r, 0, Math.PI * 2); ctx.stroke();
    }
  }
  function flaggedList() {
    if (!result) return [];
    return result.objects.filter(o => o.flags && o.flags.length && o.cls !== 'edge')
      .sort((a, b) => (b.cls === 'object') - (a.cls === 'object') || a.cy - b.cy);
  }

  // ---------- results ----------
  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
  function renderResults() {
    const r = result, el = $('results');
    const mm = !!r.scale;
    let h = `<h2 style="margin-top:0">${esc(T.sc_results)}</h2>`;
    if (r.warnings.length) {
      h += `<div class="warns"><strong>${esc(T.sc_warn_title)}</strong>` + r.warnings.map(w => `<div class="warn">${esc(T['w_' + w] || w)}</div>`).join('') + `</div>`;
    }
    h += `<div class="stats">
      <div class="stat"><div class="k">${esc(T.sc_kernels)}</div><div class="v">${r.counts.kernels}</div><div class="s">${r.counts.clumps ? '+' + r.counts.clumps + ' ' + esc(T.cls_clump) : '&nbsp;'}</div></div>
      <div class="stat"><div class="k">${esc(T.sc_head)}</div><div class="v">${nf(r.headRice.weight)}%</div><div class="s">${esc(T.sc_by_weight)} · ${nf(r.headRice.count)}% ${esc(T.sc_by_count)}</div></div>
      <div class="stat"><div class="k">${esc(T.sc_broken)}</div><div class="v">${nf(r.broken.weight)}%</div><div class="s">${esc(T.sc_by_weight)} · ${nf(r.broken.count)}% ${esc(T.sc_by_count)}</div></div>
      <div class="stat"><div class="k">${esc(mm ? T.sc_length : T.sc_ratio)}</div><div class="v">${mm ? nf(r.size.lengthMM, 2) + ' mm' : nf(r.size.ratio, 2)}</div><div class="s">${mm ? 'L/W ' + nf(r.size.ratio, 2) : esc(T.sc_rel_only)}</div></div>
    </div>`;

    // breakdown
    h += `<div class="res-sec"><h3>${esc(T.sc_breakdown)}</h3><div class="bars">`;
    for (const k of CLASSES) {
      if (k === 'chip' && !mm && !r.byCount.chip) continue;
      h += `<div class="bar"><span>${esc(T['cls_' + k])}</span><div class="track"><div class="fill" style="width:${Math.min(100, r.byWeight[k]).toFixed(1)}%;background:${COLORS[k]}"></div></div><span class="num">${nf(r.byWeight[k])}% · n=${r.objects.filter(o => o.cls === k).length}</span></div>`;
    }
    h += `</div><p class="fine">${esc(T.sc_breakdown_note)}</p></div>`;

    // size
    h += `<div class="res-sec"><h3>${esc(T.sc_size)}</h3><div class="kv">`;
    if (mm) {
      h += `<div>${esc(T.sc_len)}<b>${nf(r.size.lengthMM, 2)} mm</b></div>`;
      h += `<div>${esc(T.sc_wid)}<b>${nf(r.size.widthMM, 2)} mm</b></div>`;
      h += `<div>${esc(T.sc_len_sd)}<b>± ${nf(r.size.lengthSD_MM, 2)} mm</b></div>`;
      h += `<div>${esc(T.sc_len_class)}<b>${esc(T['sz_' + r.size.lengthClass])}</b></div>`;
    }
    h += `<div>${esc(T.sc_lw)}<b>${nf(r.size.ratio, 2)}</b></div>`;
    h += `<div>${esc(T.sc_shape_class)}<b>${esc(T['sh_' + r.size.shapeClass])}</b></div>`;
    h += `</div><h3 style="margin-top:16px">${esc(T.sc_hist)}</h3><canvas class="hist" id="hist" width="800" height="200"></canvas></div>`;

    // colour
    const rgb = r.colour.meanRGB ? `rgb(${r.colour.meanRGB.map(v => Math.round(v)).join(',')})` : '#ccc';
    h += `<div class="res-sec"><h3>${esc(T.sc_colour)}</h3><div class="kv">
      <div>${esc(T.sc_consistency)}<b>${nf(r.colour.consistency, 0)}%</b><span class="fine">${esc(T.sc_consistency_hint)}</span></div>
      <div>${esc(T.sc_lightness)}<b>${nf(r.colour.L, 1)}</b></div>
      <div>${esc(T.sc_yellowness)}<b>${nf(r.colour.b, 1)}</b></div>
      <div><span style="display:inline-block;width:100%;height:34px;border-radius:8px;background:${rgb};border:1px solid var(--line)"></span></div>
    </div><p class="fine">${esc(T.sc_colour_note)}</p></div>`;

    // chalk
    h += `<div class="res-sec"><h3>${esc(T.sc_chalk)} <span class="pill beta">beta</span></h3>`;
    if (r.chalk) {
      h += `<div class="kv">
        <div>${esc(T.sc_chalk_mean)}<b>${nf(r.chalk.meanArea)}%</b></div>
        <div>${esc(T.sc_chalk_kernels)}<b>${nf(r.chalk.chalkyKernels)}%</b></div>
        <div>${esc(T.sc_chalk_partial)}<b>${nf(r.chalk.partial)}%</b></div></div>`;
    } else h += `<p class="fine">${esc(T.sc_chalk_need)}</p>`;
    h += `</div>`;

    // flags
    const fl = flaggedList();
    h += `<div class="res-sec"><h3>${esc(T.sc_flags)} <span class="pill beta">beta</span></h3>`;
    if (!fl.length) h += `<p>${esc(T.sc_flags_none)}</p>`;
    else {
      h += `<div class="flags">` + fl.map((o, i) => `<button type="button" class="flag" data-i="${i}"><canvas width="120" height="90"></canvas><b>#${i + 1}</b> ${o.flags.map(f => esc(T['fl_' + f] || f)).join(', ')}</button>`).join('') + `</div>`;
    }
    h += `<p class="fine" style="margin-top:10px">${esc(T.sc_flags_note)}</p></div>`;


    el.innerHTML = h;
    el.classList.remove('hidden');
    $('tools').classList.remove('hidden');
    renderLegend();
    const meta = [fmt(T.sc_time, { n: r.objects.length, ms: r.ms, w: r.width, h: r.height }), r.scale ? fmt(T.sc_scale, { mm: nf(r.scale.mmPerPx, 4), d: r.scale.coinMM }) : T.sc_noscale].join(' ');
    $('meta').textContent = meta; $('meta').classList.remove('hidden');
    drawHist();
    // thumbnails
    el.querySelectorAll('.flag').forEach(btn => {
      const o = fl[+btn.dataset.i];
      const c = btn.querySelector('canvas'), g = c.getContext('2d');
      const [x0, y0, x1, y1] = o.bbox;
      const size = Math.max(x1 - x0, y1 - y0) * 1.6 + 20;
      const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
      const sw = size * 4 / 3, sh = size;
      g.fillStyle = '#000'; g.fillRect(0, 0, 120, 90);
      drawCrop(g, cx - sw / 2, cy - sh / 2, sw, sh, 120, 90);
      btn.addEventListener('click', () => {
        highlight = o; draw();
        $('stage').scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    });
  }

  // copy a region of the source pixels (clamped to the image) into a small thumbnail context
  function drawCrop(g, sx, sy, sw, sh, dw, dh) {
    const W = srcData.width, H = srcData.height;
    const x0 = Math.max(0, Math.floor(sx)), y0 = Math.max(0, Math.floor(sy));
    const x1 = Math.min(W, Math.ceil(sx + sw)), y1 = Math.min(H, Math.ceil(sy + sh));
    if (x1 <= x0 || y1 <= y0) return;
    const tmp = document.createElement('canvas');
    tmp.width = x1 - x0; tmp.height = y1 - y0;
    tmp.getContext('2d').putImageData(srcData, -x0, -y0, x0, y0, x1 - x0, y1 - y0);
    const k = dw / sw;
    g.drawImage(tmp, (x0 - sx) * k, (y0 - sy) * k, (x1 - x0) * k, (y1 - y0) * k);
    tmp.width = tmp.height = 0; // release canvas memory right away (iOS)
  }

  function renderLegend() {
    const keys = ['whole', 'head', 'largeBroken', 'mediumBroken', 'smallBroken', 'chip', 'clump', 'object', 'coin'];
    $('legend').innerHTML = keys.map(k => `<span><i style="background:${COLORS[k]}"></i>${esc(T['cls_' + k])}</span>`).join('');
    $('legend').classList.remove('hidden');
  }

  function drawHist() {
    const c = $('hist'); if (!c) return;
    const g = c.getContext('2d');
    const W = c.width, H = c.height;
    const style = getComputedStyle(document.documentElement);
    const ink = style.getPropertyValue('--muted').trim() || '#666';
    const line = style.getPropertyValue('--line').trim() || '#ddd';
    g.clearRect(0, 0, W, H);
    const objs = result.objects.filter(o => CLASSES.includes(o.cls));
    const bins = 24, maxR = 1.25;
    const counts = Array.from({ length: bins }, () => ({}));
    for (const o of objs) {
      const b = Math.min(bins - 1, Math.floor((o.L / result.Lref) / maxR * bins));
      counts[b][o.cls] = (counts[b][o.cls] || 0) + 1;
    }
    const tot = counts.map(c => Object.values(c).reduce((s, v) => s + v, 0));
    const mx = Math.max(1, ...tot);
    const pl = 30, pb = 26, bw = (W - pl - 6) / bins;
    g.strokeStyle = line; g.beginPath(); g.moveTo(pl, H - pb); g.lineTo(W, H - pb); g.stroke();
    counts.forEach((cs, i) => {
      let y = H - pb;
      for (const k of CLASSES) {
        const v = cs[k] || 0; if (!v) continue;
        const bh = v / mx * (H - pb - 10);
        g.fillStyle = COLORS[k]; g.fillRect(pl + i * bw + 1, y - bh, bw - 2, bh); y -= bh;
      }
    });
    g.fillStyle = ink; g.font = '20px system-ui, sans-serif'; g.textAlign = 'center';
    const mm = result.scale ? result.scale.mmPerPx * result.Lref : null;
    for (const f of [0.25, 0.5, 0.75, 1.0, 1.25]) {
      const x = pl + f / maxR * (W - pl - 6);
      g.fillText(mm ? (f * mm).toFixed(1) + (f === 1.25 ? ' mm' : '') : (f * 100) + '%', Math.min(W - 30, x), H - 4);
      g.strokeStyle = line; g.setLineDash([4, 4]); g.beginPath(); g.moveTo(x, 6); g.lineTo(x, H - pb); g.stroke(); g.setLineDash([]);
    }
    g.textAlign = 'left'; g.fillText(String(mx), 2, 18);
  }

  function showError(msg, warnings) {
    const el = $('results');
    let h = `<div class="warn"><strong>${esc(msg)}</strong></div>`;
    if (warnings && warnings.length) h += warnings.map(w => `<div class="warn">${esc(T['w_' + w] || w)}</div>`).join('');
    h += `<p style="margin-top:10px"><a href="${LANG === 'th' ? '/th' : ''}/guide/">${esc(T.nav_guide)} →</a></p>`;
    el.innerHTML = h; el.classList.remove('hidden');
  }

  // ---------- exports ----------
  function download(blob, name) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
  }
  // phones: open the share sheet (Save Image / LINE / etc.); desktop: normal download
  function save(blob, name) {
    try {
      const file = new File([blob], name, { type: blob.type });
      if (IS_TOUCH && navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], title: 'rice.ag scan' }).catch(e => { if (e && e.name !== 'AbortError') download(blob, name); });
        return;
      }
    } catch (e) { /* fall through */ }
    download(blob, name);
  }
  function stamp() {
    const d = new Date().toISOString().slice(0, 10);
    return `${sourceName}-riceag-${d}`;
  }
  function prepareExport(cb) {
    const r = result; if (!r) return;
    const wasOn = overlayOn; if (!wasOn) { overlayOn = true; draw(); }
    const pad = Math.round(cv.width / 40), fs = Math.round(cv.width / 45);
    const out = document.createElement('canvas');
    out.width = cv.width; out.height = cv.height + Math.round(fs * 3.4) + pad;
    const g = out.getContext('2d');
    g.fillStyle = '#111611'; g.fillRect(0, 0, out.width, out.height);
    g.drawImage(cv, 0, 0);
    if (!wasOn) { overlayOn = false; draw(); }
    g.fillStyle = '#ECEAE2'; g.font = `600 ${fs}px system-ui, sans-serif`;
    const line1 = `${T.sc_head} ${nf(r.headRice.weight)}% · ${T.sc_broken} ${nf(r.broken.weight)}% (${T.sc_by_weight}) · n=${r.counts.kernels}` + (r.scale ? ` · L ${nf(r.size.lengthMM, 2)} mm` : '') + ` · L/W ${nf(r.size.ratio, 2)}`;
    g.fillText(line1, pad, cv.height + fs * 1.5);
    g.fillStyle = '#A4AEA1'; g.font = `${Math.round(fs * 0.75)}px system-ui, sans-serif`;
    g.fillText(`rice.ag grain scanner v${r.version} · ${new Date().toLocaleString(LANG === 'th' ? 'th-TH' : 'en-GB')} · ${T.by_wildfield}`, pad, cv.height + fs * 2.8);
    // JPEG keeps phone files small; release the big canvas as soon as it's encoded
    out.toBlob(b => { pngBlob = b; out.width = out.height = 0; if (cb) cb(b); }, 'image/jpeg', 0.9);
  }
  function exportPng() {
    if (!result) return;
    if (pngBlob) save(pngBlob, stamp() + '.jpg');
    else prepareExport(b => save(b, stamp() + '.jpg'));
  }
  function exportCsv() {
    const r = result; if (!r) return;
    const k = r.scale ? r.scale.mmPerPx : null;
    const rows = [T.csv_head];
    r.objects.forEach((o, i) => rows.push([i + 1, o.cls, (o.flags || []).join('|'), o.L.toFixed(1), o.W.toFixed(1),
      k ? (o.L * k).toFixed(3) : '', k ? (o.W * k).toFixed(3) : '', (o.L / r.Lref).toFixed(3), o.area,
      o.lab[0].toFixed(1), o.lab[1].toFixed(1), o.lab[2].toFixed(1), o.chalk == null ? '' : o.chalk.toFixed(3),
      o.cx.toFixed(0), o.cy.toFixed(0)].join(',')));
    download(new Blob(['﻿' + rows.join('\n')], { type: 'text/csv' }), stamp() + '.csv');
  }

  // ---------- wiring ----------
  $('fCam').addEventListener('change', e => loadFile(e.target.files[0]));
  $('fFile').addEventListener('change', e => loadFile(e.target.files[0]));
  $('bSample').addEventListener('click', () => {
    $('oCoin').value = '26';
    $('oCoinMM').classList.add('hidden');
    loadUrl(window.RICE_SAMPLE, 'sample');
  });
  $('bRun').addEventListener('click', run);
  $('bOverlay').addEventListener('click', () => { overlayOn = !overlayOn; draw(); });
  $('bPng').addEventListener('click', exportPng);
  $('bCsv').addEventListener('click', exportCsv);
  $('bPrint').addEventListener('click', () => window.print());
  $('oCoin').addEventListener('change', e => { $('oCoinMM').classList.toggle('hidden', e.target.value !== 'custom'); if (srcData && result) run(); });
  $('oLight').addEventListener('change', () => { if (srcData && result) run(); });
  $('oChalk').addEventListener('input', e => { $('oChalkV').textContent = (+e.target.value).toFixed(2); });
  $('oChalk').addEventListener('change', () => { if (srcData && result) run(); });
  $('stage').addEventListener('click', e => {
    if (e.target !== cv) return;
    const st = $('stage');
    st.classList.toggle('zoom');
  });
  const drop = $('drop');
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', e => { const f = e.dataTransfer.files[0]; if (f) loadFile(f); });
  window.addEventListener('paste', e => {
    const it = [...(e.clipboardData || {}).items || []].find(i => i.type.startsWith('image/'));
    if (it) loadFile(it.getAsFile());
  });
  if (/[?&]sample=1/.test(location.search)) $('bSample').click();
})();
