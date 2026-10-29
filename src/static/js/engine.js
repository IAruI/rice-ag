/*!
 * rice.ag Grain Scanner engine v1.0
 * Runs entirely in the browser. No image data ever leaves the device.
 * Classical computer vision: background correction, Otsu threshold,
 * connected components, principal-axis (Feret) measurement, CIELAB colour.
 * (c) Wild Field Foods Co., Ltd. — https://wildfield.org
 */
(function (root) {
  'use strict';

  // ---------- helpers ----------
  function median(arr) {
    if (!arr.length) return NaN;
    const a = Float64Array.from(arr).sort();
    const m = a.length >> 1;
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
  }
  function percentile(arr, p) {
    if (!arr.length) return NaN;
    const a = Float64Array.from(arr).sort();
    const i = Math.min(a.length - 1, Math.max(0, Math.round((a.length - 1) * p)));
    return a[i];
  }
  function mad(arr, med) {
    return median(arr.map(v => Math.abs(v - med)));
  }
  function mean(arr) { let s = 0; for (const v of arr) s += v; return arr.length ? s / arr.length : NaN; }

  // sRGB (0-255) -> CIELAB (D65)
  function srgbToLab(r, g, b) {
    const lin = c => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    const R = lin(r), G = lin(g), B = lin(b);
    let X = (R * 0.4124564 + G * 0.3575761 + B * 0.1804375) / 0.95047;
    let Y = (R * 0.2126729 + G * 0.7151522 + B * 0.0721750);
    let Z = (R * 0.0193339 + G * 0.1191920 + B * 0.9503041) / 1.08883;
    const f = t => t > 216 / 24389 ? Math.cbrt(t) : (24389 / 27 * t + 16) / 116;
    const fx = f(X), fy = f(Y), fz = f(Z);
    return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
  }
  function deltaE(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }

  function otsu(values, bins) {
    // values: Float32Array already clipped to [0, bins-1]
    const hist = new Float64Array(bins);
    for (let i = 0; i < values.length; i++) hist[values[i] | 0]++;
    const total = values.length;
    let sum = 0; for (let i = 0; i < bins; i++) sum += i * hist[i];
    let sumB = 0, wB = 0, best = 0, thr = 0;
    for (let t = 0; t < bins; t++) {
      wB += hist[t]; if (!wB) continue;
      const wF = total - wB; if (!wF) break;
      sumB += t * hist[t];
      const mB = sumB / wB, mF = (sum - sumB) / wF;
      const between = wB * wF * (mB - mF) * (mB - mF);
      if (between > best) { best = between; thr = t; }
    }
    // separation quality: between-class variance / total variance
    const mu = sum / total; let tv = 0;
    for (let i = 0; i < bins; i++) tv += hist[i] * (i - mu) * (i - mu);
    return { thr: thr + 0.5, quality: tv ? best / total / tv : 0 };
  }

  // 3-class Otsu: returns [t1, t2]
  function otsu3(values, bins) {
    const hist = new Float64Array(bins);
    for (let i = 0; i < values.length; i++) hist[values[i] | 0]++;
    const P = new Float64Array(bins + 1), Sm = new Float64Array(bins + 1);
    for (let i = 0; i < bins; i++) { P[i + 1] = P[i] + hist[i]; Sm[i + 1] = Sm[i] + i * hist[i]; }
    const tot = P[bins], mu = Sm[bins] / tot;
    let best = -1, t1b = 0, t2b = 0;
    const term = (a, b) => { const w = P[b] - P[a]; if (!w) return 0; const m = (Sm[b] - Sm[a]) / w; return w * (m - mu) * (m - mu); };
    for (let t1 = 1; t1 < bins - 1; t1++) for (let t2 = t1 + 1; t2 < bins; t2++) {
      const v = term(0, t1) + term(t1, t2) + term(t2, bins);
      if (v > best) { best = v; t1b = t1; t2b = t2; }
    }
    return [t1b - 0.5, t2b - 0.5];
  }

  // Convex hull (monotone chain) area & perimeter
  function hullArea(points) {
    if (points.length < 3) return 0;
    points.sort((p, q) => p[0] - q[0] || p[1] - q[1]);
    const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
    const lower = [], upper = [];
    for (const p of points) { while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop(); lower.push(p); }
    for (let i = points.length - 1; i >= 0; i--) { const p = points[i]; while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop(); upper.push(p); }
    const h = lower.slice(0, -1).concat(upper.slice(0, -1));
    let a = 0; for (let i = 0; i < h.length; i++) { const p = h[i], q = h[(i + 1) % h.length]; a += p[0] * q[1] - q[0] * p[1]; }
    return Math.abs(a) / 2;
  }

  // ---------- background estimation ----------
  // mask (optional): Uint8Array, 1 = foreground; background is then estimated only from mask==0 pixels
  function estimateBackground(Y, w, h, dark, mask) {
    const bs = Math.max(24, Math.round(Math.min(w, h) / (mask ? 14 : 10)));
    const gw = Math.ceil(w / bs), gh = Math.ceil(h / bs);
    let grid = new Float32Array(gw * gh).fill(NaN);
    const p = mask ? 0.5 : (dark ? 0.10 : 0.90);
    const buf = [];
    for (let gy = 0; gy < gh; gy++) for (let gx = 0; gx < gw; gx++) {
      buf.length = 0; let tot = 0;
      const x0 = gx * bs, y0 = gy * bs, x1 = Math.min(w, x0 + bs), y1 = Math.min(h, y0 + bs);
      const step = Math.max(1, Math.floor(bs / 32));
      for (let y = y0; y < y1; y += step) for (let x = x0; x < x1; x += step) {
        tot++; const i = y * w + x;
        if (!mask || !mask[i]) buf.push(Y[i]);
      }
      if (buf.length >= Math.max(8, tot * 0.12)) grid[gy * gw + gx] = percentile(buf, p);
    }
    if (!mask) {
      // min (dark) / max (light) over 3x3 blocks: blocks swamped by a large bright object (e.g. a coin) take their neighbours' value
      const g2 = new Float32Array(gw * gh);
      for (let gy = 0; gy < gh; gy++) for (let gx = 0; gx < gw; gx++) {
        let v = dark ? Infinity : -Infinity;
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
          const X = gx + dx, Yy = gy + dy;
          if (X >= 0 && Yy >= 0 && X < gw && Yy < gh) { const q = grid[Yy * gw + X]; v = dark ? Math.min(v, q) : Math.max(v, q); }
        }
        g2[gy * gw + gx] = v;
      }
      grid = g2;
    } else {
      // fill blocks with too few background pixels from valid neighbours
      for (let pass = 0; pass < gw + gh; pass++) {
        let missing = 0; const g2 = Float32Array.from(grid);
        for (let gy = 0; gy < gh; gy++) for (let gx = 0; gx < gw; gx++) {
          if (!isNaN(grid[gy * gw + gx])) continue;
          let s = 0, n = 0;
          for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
            const X = gx + dx, Yy = gy + dy;
            if (X >= 0 && Yy >= 0 && X < gw && Yy < gh && !isNaN(grid[Yy * gw + X])) { s += grid[Yy * gw + X]; n++; }
          }
          if (n) g2[gy * gw + gx] = s / n; else missing++;
        }
        grid = g2; if (!missing) break;
      }
    }
    // 3x3 mean smoothing
    const sm = new Float32Array(gw * gh);
    for (let gy = 0; gy < gh; gy++) for (let gx = 0; gx < gw; gx++) {
      let s = 0, n = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const X = gx + dx, Yy = gy + dy;
        if (X >= 0 && Yy >= 0 && X < gw && Yy < gh && !isNaN(grid[Yy * gw + X])) { s += grid[Yy * gw + X]; n++; }
      }
      sm[gy * gw + gx] = n ? s / n : (dark ? 0 : 255);
    }
    // bilinear upsample (block centres)
    const bg = new Float32Array(w * h);
    for (let y = 0; y < h; y++) {
      let fy = (y + 0.5) / bs - 0.5; fy = Math.max(0, Math.min(gh - 1, fy));
      const y0 = Math.floor(fy), y1 = Math.min(gh - 1, y0 + 1), ty = fy - y0;
      for (let x = 0; x < w; x++) {
        let fx = (x + 0.5) / bs - 0.5; fx = Math.max(0, Math.min(gw - 1, fx));
        const x0 = Math.floor(fx), x1 = Math.min(gw - 1, x0 + 1), tx = fx - x0;
        const a = sm[y0 * gw + x0], b = sm[y0 * gw + x1], c = sm[y1 * gw + x0], d = sm[y1 * gw + x1];
        bg[y * w + x] = (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
      }
    }
    return bg;
  }

  // threshold + opening + hole filling -> foreground mask
  function segment(Y, bg, w, h, dark) {
    const N = w * h;
    const S = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const s = dark ? Y[i] - bg[i] : bg[i] - Y[i];
      S[i] = s < 0 ? 0 : s > 255 ? 255 : s;
    }
    const ot = otsu(S, 256);
    let thr = Math.max(ot.thr, 14);
    if (!dark) {
      // backlit: translucent kernels transmit much of the light; chalky/opaque parts transmit little.
      // A 2-class split can land between translucent and opaque, so use the lower 3-class threshold.
      const t3 = otsu3(S, 256);
      if (t3[0] >= 14 && t3[0] < thr) thr = t3[0];
    }
    const M0 = new Uint8Array(N);
    for (let i = 0; i < N; i++) M0[i] = S[i] > thr ? 1 : 0;
    const E = new Uint8Array(N);
    for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      E[i] = (M0[i] & M0[i - 1] & M0[i + 1] & M0[i - w] & M0[i + w] & M0[i - w - 1] & M0[i - w + 1] & M0[i + w - 1] & M0[i + w + 1]);
    }
    const M = new Uint8Array(N);
    for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      M[i] = (E[i] | E[i - 1] | E[i + 1] | E[i - w] | E[i + w] | E[i - w - 1] | E[i - w + 1] | E[i + w - 1] | E[i + w + 1]) & M0[i];
    }
    // fill holes: flood background from border
    const reach = new Uint8Array(N); const st = new Int32Array(N); let sp = 0;
    const push = i => { if (!M[i] && !reach[i]) { reach[i] = 1; st[sp++] = i; } };
    for (let x = 0; x < w; x++) { push(x); push((h - 1) * w + x); }
    for (let y = 0; y < h; y++) { push(y * w); push(y * w + w - 1); }
    while (sp) {
      const i = st[--sp], x = i % w, y = (i / w) | 0;
      if (x > 0) push(i - 1); if (x < w - 1) push(i + 1); if (y > 0) push(i - w); if (y < h - 1) push(i + w);
    }
    for (let i = 0; i < N; i++) if (!M[i] && !reach[i]) M[i] = 1;
    return { S, M, thr, quality: ot.quality };
  }

  function dilate(M, w, h, r) {
    let A = M;
    for (let k = 0; k < r; k++) {
      const B = new Uint8Array(w * h);
      for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
        const i = y * w + x;
        B[i] = A[i] | A[i - 1] | A[i + 1] | A[i - w] | A[i + w];
      }
      A = B;
    }
    return A;
  }

  // ---------- main ----------
  /**
   * analyze(imageData, options)
   * imageData: {width, height, data: Uint8ClampedArray RGBA}
   * options: {
   *   lighting: 'auto'|'dark'|'backlit',
   *   coinMM: number|null      diameter of reference coin in mm (null = no scale)
   *   knownLengthMM: number|null  average whole-kernel length if known
   *   chalkRatio: number        backlit: pixel is chalky if Y < chalkRatio * local background (default 0.45)
   * }
   */
  function analyze(img, options) {
    const t0 = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    const opt = Object.assign({ lighting: 'auto', coinMM: null, knownLengthMM: null, chalkRatio: 0.45 }, options || {});
    const w = img.width, h = img.height, D = img.data, N = w * h;
    const warnings = [];

    // luminance
    const Y = new Float32Array(N);
    for (let i = 0, j = 0; i < N; i++, j += 4) Y[i] = 0.299 * D[j] + 0.587 * D[j + 1] + 0.114 * D[j + 2];

    // border luminance -> polarity
    const border = [];
    const bw = Math.max(2, Math.round(Math.min(w, h) * 0.03));
    const stepB = Math.max(1, Math.round(Math.min(w, h) / 200));
    for (let y = 0; y < h; y += stepB) for (let x = 0; x < w; x += stepB) {
      if (x < bw || y < bw || x >= w - bw || y >= h - bw) border.push(Y[y * w + x]);
    }
    const borderMed = median(border);
    let lightBg = borderMed > 120;
    let mode = opt.lighting;
    if (mode === 'auto') mode = lightBg ? 'backlit' : 'dark';
    if (mode === 'dark' && lightBg) warnings.push('lightBackgroundInDarkMode');
    if (mode === 'backlit' && !lightBg) warnings.push('darkBackgroundInBacklitMode');
    const dark = mode === 'dark';

    // two-pass background: rough estimate -> mask -> re-estimate from true background pixels only
    const bg1 = estimateBackground(Y, w, h, dark, null);
    const seg1 = segment(Y, bg1, w, h, dark);
    const bg = estimateBackground(Y, w, h, dark, dilate(seg1.M, w, h, 3));
    const seg = segment(Y, bg, w, h, dark);
    const S = seg.S, thr = seg.thr;
    let M = seg.M;
    if (seg.quality < 0.55) warnings.push('lowContrast');

    // low-contrast mask (objects much darker than rice, e.g. stones/soil on a dark cloth)
    const lowThr = Math.max(12, thr * 0.4);
    const LM = new Uint8Array(N);
    for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      // 3x3 erosion on the low mask to suppress noise/halo
      LM[i] = (S[i] > lowThr && S[i - 1] > lowThr && S[i + 1] > lowThr && S[i - w] > lowThr && S[i + w] > lowThr) ? 1 : 0;
    }

    // connected components (8-connectivity), BFS; order[] holds pixels grouped by label
    const label = new Int32Array(N);
    const order = new Int32Array(N);
    const comps = [];
    let head = 0, tail = 0, lab = 0;
    for (let s = 0; s < N; s++) {
      if (!M[s] || label[s]) continue;
      lab++; const start = tail; label[s] = lab; order[tail++] = s; head = start;
      while (head < tail) {
        const i = order[head++], x = i % w, y = (i / w) | 0;
        for (let dy = -1; dy <= 1; dy++) {
          const yy = y + dy; if (yy < 0 || yy >= h) continue;
          for (let dx = -1; dx <= 1; dx++) {
            const xx = x + dx; if (xx < 0 || xx >= w) continue;
            const j = yy * w + xx;
            if (M[j] && !label[j]) { label[j] = lab; order[tail++] = j; }
          }
        }
      }
      comps.push({ id: lab, start, end: tail });
    }

    // per-component measurements
    const objs = [];
    for (const c of comps) {
      const area = c.end - c.start;
      if (area < 12) continue;
      let sx = 0, sy = 0, minx = w, miny = h, maxx = 0, maxy = 0, touchesEdge = false;
      for (let k = c.start; k < c.end; k++) {
        const i = order[k], x = i % w, y = (i / w) | 0;
        sx += x; sy += y;
        if (x < minx) minx = x; if (x > maxx) maxx = x; if (y < miny) miny = y; if (y > maxy) maxy = y;
      }
      if (minx === 0 || miny === 0 || maxx === w - 1 || maxy === h - 1) touchesEdge = true;
      const cx = sx / area, cy = sy / area;
      let cxx = 0, cyy = 0, cxy = 0;
      for (let k = c.start; k < c.end; k++) {
        const i = order[k], dx = (i % w) - cx, dy = ((i / w) | 0) - cy;
        cxx += dx * dx; cyy += dy * dy; cxy += dx * dy;
      }
      const theta = 0.5 * Math.atan2(2 * cxy, cxx - cyy);
      const ct = Math.cos(theta), stt = Math.sin(theta);
      let umin = Infinity, umax = -Infinity, vmin = Infinity, vmax = -Infinity;
      let sr = 0, sg = 0, sb = 0, ni = 0, ar = 0, ag = 0, abb = 0;
      let chalkPix = 0, chalkN = 0, ySum = 0, bgSum = 0;
      const hullPts = [];
      for (let k = c.start; k < c.end; k++) {
        const i = order[k], x = i % w, y = (i / w) | 0;
        const dx = x - cx, dy = y - cy;
        const u = dx * ct + dy * stt, v = -dx * stt + dy * ct;
        if (u < umin) umin = u; if (u > umax) umax = u; if (v < vmin) vmin = v; if (v > vmax) vmax = v;
        const j = i * 4;
        ar += D[j]; ag += D[j + 1]; abb += D[j + 2];
        ySum += Y[i]; bgSum += bg[i];
        const isBoundary = x === 0 || y === 0 || x === w - 1 || y === h - 1 ||
          label[i - 1] !== c.id || label[i + 1] !== c.id || label[i - w] !== c.id || label[i + w] !== c.id;
        if (isBoundary) {
          hullPts.push([x, y], [x + 1, y], [x, y + 1], [x + 1, y + 1]);
        } else {
          // interior (2px from edge) for colour & chalk
          const deep = x > 1 && y > 1 && x < w - 2 && y < h - 2 &&
            label[i - 2] === c.id && label[i + 2] === c.id && label[i - 2 * w] === c.id && label[i + 2 * w] === c.id;
          if (deep) {
            sr += D[j]; sg += D[j + 1]; sb += D[j + 2]; ni++;
            if (!dark) { chalkN++; if (Y[i] < opt.chalkRatio * bg[i]) chalkPix++; }
          }
        }
      }
      const L = umax - umin + 1, W = vmax - vmin + 1;
      const rgb = ni >= 6 ? [sr / ni, sg / ni, sb / ni] : [ar / area, ag / area, abb / area];
      const hullA = hullArea(hullPts);
      objs.push({
        id: c.id, area, cx, cy, theta, L, W, ar: L / W,
        fill: area / (Math.PI * L * W / 4),
        solidity: hullA ? Math.min(1, area / hullA) : 1,
        bbox: [minx, miny, maxx, maxy], touchesEdge,
        rgb, lab: srgbToLab(rgb[0], rgb[1], rgb[2]),
        chalk: chalkN >= 8 ? chalkPix / chalkN : null,
        transmit: bgSum ? ySum / bgSum : 1,
        cls: null, flags: []
      });
    }

    // secondary components from the low mask that contain (almost) no main-mask pixels
    {
      const seen = new Uint8Array(N); const q = new Int32Array(N);
      for (let s0 = 0; s0 < N; s0++) {
        if (!LM[s0] || seen[s0] || M[s0]) continue;
        let qh = 0, qt = 0; q[qt++] = s0; seen[s0] = 1; let inMain = 0;
        while (qh < qt) {
          const i = q[qh++], x = i % w, y = (i / w) | 0;
          for (let dy = -1; dy <= 1; dy++) { const yy = y + dy; if (yy < 0 || yy >= h) continue;
            for (let dx = -1; dx <= 1; dx++) { const xx = x + dx; if (xx < 0 || xx >= w) continue;
              const j = yy * w + xx;
              if (M[j]) { inMain++; continue; }
              if (LM[j] && !seen[j]) { seen[j] = 1; q[qt++] = j; } } }
        }
        const area = qt;
        if (area < 40 || inMain > 0.25 * area) continue;
        let sx = 0, sy = 0, minx = w, miny = h, maxx = 0, maxy = 0, r = 0, g = 0, b = 0, ys = 0, bs = 0;
        for (let k = 0; k < qt; k++) { const i = q[k], x = i % w, y = (i / w) | 0; sx += x; sy += y;
          if (x < minx) minx = x; if (x > maxx) maxx = x; if (y < miny) miny = y; if (y > maxy) maxy = y;
          r += D[i * 4]; g += D[i * 4 + 1]; b += D[i * 4 + 2]; ys += Y[i]; bs += bg[i]; }
        const cx = sx / area, cy = sy / area;
        let cxx = 0, cyy = 0, cxy = 0;
        for (let k = 0; k < qt; k++) { const i = q[k], dx = (i % w) - cx, dy = ((i / w) | 0) - cy; cxx += dx * dx; cyy += dy * dy; cxy += dx * dy; }
        const theta = 0.5 * Math.atan2(2 * cxy, cxx - cyy), ct = Math.cos(theta), st = Math.sin(theta);
        let umin = 1e9, umax = -1e9, vmin = 1e9, vmax = -1e9;
        for (let k = 0; k < qt; k++) { const i = q[k], dx = (i % w) - cx, dy = ((i / w) | 0) - cy;
          const u = dx * ct + dy * st, v = -dx * st + dy * ct;
          if (u < umin) umin = u; if (u > umax) umax = u; if (v < vmin) vmin = v; if (v > vmax) vmax = v; }
        const L = umax - umin + 1, W = vmax - vmin + 1, rgb = [r / area, g / area, b / area];
        objs.push({ id: -s0, area, cx, cy, theta, L, W, ar: L / W, fill: area / (Math.PI * L * W / 4), solidity: 1,
          bbox: [minx, miny, maxx, maxy], touchesEdge: minx === 0 || miny === 0 || maxx === w - 1 || maxy === h - 1,
          rgb, lab: srgbToLab(rgb[0], rgb[1], rgb[2]), chalk: null, transmit: bs ? ys / bs : 1,
          lowContrast: true, cls: null, flags: [] });
      }
    }

    if (!objs.length) {
      return { ok: false, error: 'noObjects', warnings, mode, width: w, height: h };
    }

    // noise filter relative to typical object
    const areas = objs.map(o => o.area);
    const medArea0 = percentile(areas, 0.6);
    const minArea = Math.max(12, medArea0 * 0.03);
    let items = objs.filter(o => o.area >= minArea);

    // reference coin
    let scale = null, coin = null;
    {
      const medA = median(items.map(o => o.area));
      const cands = items.filter(o => o.area > 6 * medA && o.ar < 1.2 && o.fill > 0.82 && o.solidity > 0.92 && !o.touchesEdge);
      if (cands.length) {
        coin = cands.reduce((a, b) => (a.area > b.area ? a : b));
        coin.cls = 'coin';
        if (opt.coinMM) {
          const dpx = 2 * Math.sqrt(coin.area / Math.PI);
          scale = { mmPerPx: opt.coinMM / dpx, coinPx: dpx, coinMM: opt.coinMM };
        }
      } else if (opt.coinMM) warnings.push('coinNotFound');
    }
    items = items.filter(o => o !== coin);

    // objects cut by the photo edge are excluded from counts
    const edgeObjs = items.filter(o => o.touchesEdge);
    edgeObjs.forEach(o => { o.cls = 'edge'; });
    items = items.filter(o => !o.touchesEdge);
    if (edgeObjs.length > 3) warnings.push('edgeCut');

    if (items.length < 3) {
      return { ok: false, error: 'tooFew', warnings, mode, width: w, height: h, objects: objs };
    }

    // median width among substantial pieces
    const medAreaI = median(items.map(o => o.area));
    const substantial = items.filter(o => o.area >= 0.35 * medAreaI);
    const Wmed = median(substantial.map(o => o.W));

    // clumps: side-by-side (too wide) or crossing (low solidity)
    for (const o of items) {
      if (o.lowContrast) { o.cls = 'object'; continue; }
      const roundSolid = o.ar < 1.35 && o.solidity > 0.9 && o.fill > 0.78;
      if (roundSolid && o.W > 1.3 * Wmed) { o.cls = 'object'; o.flags.push('round'); continue; }
      if (o.W > 1.55 * Wmed || (o.solidity < 0.78 && o.area > 0.6 * medAreaI)) o.cls = 'clump';
    }
    let singles = items.filter(o => !o.cls);

    // reference (average whole-kernel) length
    let Lref;
    let LrefSource = 'auto';
    if (opt.knownLengthMM && scale) { Lref = opt.knownLengthMM / scale.mmPerPx; LrefSource = 'user'; }
    else {
      const ls = singles.map(o => o.L);
      Lref = percentile(ls, 0.85);
      for (let it = 0; it < 6; it++) {
        const set = ls.filter(l => l >= 0.88 * Lref && l <= 1.3 * Lref);
        if (!set.length) break;
        Lref = mean(set);
      }
    }
    // end-to-end touching grains
    for (const o of singles) if (o.L > 1.45 * Lref) o.cls = 'clump';
    singles = items.filter(o => !o.cls);
    if (Lref < 28) warnings.push('lowResolution');

    // classify (ISO 7301 / Codex STAN 198 style, by length relative to average whole kernel)
    for (const o of singles) {
      const r = o.L / Lref; o.r = r;
      const thin = o.W < 0.55 * Wmed && r > 0.6;
      if (thin) { o.cls = 'object'; o.flags.push('thin'); continue; }
      if (scale && o.W * scale.mmPerPx < 1.4 && r < 0.5) o.cls = 'chip';
      else if (!scale && r < 0.2 && o.W < 0.7 * Wmed) o.cls = 'chip';
      else if (r >= 0.9) o.cls = 'whole';
      else if (r >= 0.75) o.cls = 'head';          // head rice piece (>= 3/4)
      else if (r >= 0.5) o.cls = 'largeBroken';
      else if (r >= 0.25) o.cls = 'mediumBroken';
      else o.cls = 'smallBroken';
    }

    singles = singles.filter(o => o.cls !== 'object');
    // colour statistics over rice-like singles
    const riceLike = singles.filter(o => o.cls !== 'chip');
    const Ls = riceLike.map(o => o.lab[0]), As = riceLike.map(o => o.lab[1]), Bs = riceLike.map(o => o.lab[2]);
    const mL = median(Ls), mA = median(As), mB = median(Bs);
    const dL = Math.max(3, 1.4826 * mad(Ls, mL)), dA = Math.max(1.5, 1.4826 * mad(As, mA)), dB = Math.max(2, 1.4826 * mad(Bs, mB));
    const refLab = [mL, mA, mB];

    // shape reference from whole kernels
    const wholes = singles.filter(o => o.cls === 'whole' || o.cls === 'head');
    const arWhole = wholes.length ? median(wholes.map(o => o.ar)) : median(singles.map(o => o.ar));
    const areaWhole = wholes.length ? median(wholes.map(o => o.area)) : medAreaI;

    // anomaly flags (for human review)
    for (const o of items) {
      if (o.cls === 'edge') continue;
      const [l, a, b] = o.lab;
      const small = o.area < 0.15 * areaWhole;
      const add = f => { if (!o.flags.includes(f)) o.flags.push(f); };
      if (!small || o.area > 40) {
        const isDark = dark ? (l < mL - Math.max(18, 4 * dL)) : (o.transmit < 0.2);
        if (isDark || o.lowContrast) add('dark');
        else if (b > mB + Math.max(9, 4 * dB) && a < mA + Math.max(6, 4 * dA)) add('yellow');
        if (a > mA + Math.max(6, 4 * dA)) add('redBrown');
      }
      if (o.cls !== 'clump' && o.cls !== 'object') {
        if (o.area >= 0.45 * areaWhole && o.ar < 1.45 && arWhole > 2.2) add('round');
        else if (o.solidity < 0.82 && o.area >= 0.3 * areaWhole) add('irregular');
        if (o.L > 1.2 * Lref && o.L <= 1.45 * Lref && o.W > 1.12 * Wmed) add('oversize');
      }
      o.dE = deltaE(o.lab, refLab);
    }

    // ---------- summary ----------
    const counted = singles;
    const clumps = items.filter(o => o.cls === 'clump');
    const foreign = items.filter(o => o.cls === 'object');
    const clumpArea = clumps.reduce((s, o) => s + o.area, 0);
    const singleArea = counted.reduce((s, o) => s + o.area, 0);
    const estInClumps = clumps.reduce((s, o) => s + Math.max(2, Math.round(o.area / areaWhole)), 0);
    if (clumpArea > 0.15 * (clumpArea + singleArea)) warnings.push('manyClumps');
    if (counted.length < 100) warnings.push('smallSample');

    const classes = ['whole', 'head', 'largeBroken', 'mediumBroken', 'smallBroken', 'chip'];
    const byCount = {}, byWeight = {};
    for (const k of classes) {
      const set = counted.filter(o => o.cls === k);
      byCount[k] = counted.length ? 100 * set.length / counted.length : 0;
      byWeight[k] = singleArea ? 100 * set.reduce((s, o) => s + o.area, 0) / singleArea : 0;
    }
    const headRice = { count: byCount.whole + byCount.head, weight: byWeight.whole + byWeight.head };
    const broken = { count: 100 - headRice.count, weight: 100 - headRice.weight };

    // sizes (whole kernels only)
    const wk = counted.filter(o => o.cls === 'whole');
    const px2mm = scale ? scale.mmPerPx : null;
    const size = {
      lengthPx: wk.length ? mean(wk.map(o => o.L)) : Lref,
      widthPx: wk.length ? mean(wk.map(o => o.W)) : Wmed,
    };
    size.ratio = size.lengthPx / size.widthPx;
    size.lengthMM = px2mm ? size.lengthPx * px2mm : null;
    size.widthMM = px2mm ? size.widthPx * px2mm : null;
    size.lengthSD_MM = px2mm && wk.length > 2 ? Math.sqrt(mean(wk.map(o => (o.L * px2mm - size.lengthMM) ** 2))) : null;
    // IRRI classes
    const lm = size.lengthMM;
    size.lengthClass = lm == null ? null : lm > 7.5 ? 'extraLong' : lm > 6.6 ? 'long' : lm > 5.5 ? 'medium' : 'short';
    const rr = size.ratio;
    size.shapeClass = rr > 3.0 ? 'slender' : rr >= 2.1 ? 'medium' : rr >= 1.1 ? 'bold' : 'round';

    // colour
    const within6 = riceLike.filter(o => o.dE <= 6).length;
    const colour = {
      L: mL, a: mA, b: mB,
      sdL: Math.sqrt(mean(Ls.map(v => (v - mean(Ls)) ** 2))),
      consistency: riceLike.length ? 100 * within6 / riceLike.length : 0,
      meanRGB: riceLike.length ? [0, 1, 2].map(k => mean(riceLike.map(o => o.rgb[k]))) : null,
    };

    // chalkiness (backlit only)
    let chalk = null;
    if (!dark) {
      const withChalk = riceLike.filter(o => o.chalk != null);
      if (withChalk.length) {
        chalk = {
          meanArea: 100 * mean(withChalk.map(o => o.chalk)),
          chalkyKernels: 100 * withChalk.filter(o => o.chalk >= 0.75).length / withChalk.length, // Codex: >= 3/4 opaque
          partial: 100 * withChalk.filter(o => o.chalk >= 0.2 && o.chalk < 0.75).length / withChalk.length,
          ratio: opt.chalkRatio,
        };
      }
    }

    const flagged = items.filter(o => o.flags.length && o.cls !== 'edge');
    const flagCounts = {};
    for (const o of flagged) for (const f of o.flags) flagCounts[f] = (flagCounts[f] || 0) + 1;
    const flaggedArea = flagged.reduce((s, o) => s + o.area, 0);

    const t1 = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    return {
      ok: true,
      version: '1.0',
      mode, width: w, height: h, ms: Math.round(t1 - t0),
      threshold: thr, contrast: seg.quality, debug: { thr1: seg1.thr, q1: seg1.quality, fg1: seg1.M.reduce((a, v) => a + v, 0) / N, fg2: M.reduce((a, v) => a + v, 0) / N },
      scale, coin: coin ? { cx: coin.cx, cy: coin.cy, r: Math.sqrt(coin.area / Math.PI) } : null,
      Lref, LrefSource, Wmed,
      counts: { kernels: counted.length, clumps: clumps.length, estInClumps, edge: edgeObjs.length, flagged: flagged.length, objects: foreign.length },
      byCount, byWeight, headRice, broken,
      size, colour, chalk,
      flags: { counts: flagCounts, areaPct: 100 * flaggedArea / Math.max(1, singleArea + clumpArea + foreign.reduce((s, o) => s + o.area, 0)) },
      objects: items.concat(edgeObjs),
      warnings,
    };
  }

  const api = { analyze, srgbToLab, version: '1.0' };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.RiceScanner = api;
})(typeof self !== 'undefined' ? self : this);
