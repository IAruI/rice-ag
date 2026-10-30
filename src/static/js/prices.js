/* rice.ag/prices: charts + tables from /static/data/prices.json (built daily by pipeline/fetch_prices.py). */
(function () {
  'use strict';
  var TH = document.documentElement.lang === 'th';
  var LOC = TH ? 'th-TH' : 'en-US';
  var T = TH ? {
    range: 'ช่วงเวลา', all: 'ทั้งหมด', y: 'ปี', latest: 'ราคาล่าสุด', series: 'รายการ', market: 'ตลาด', basis: 'ชนิด',
    usd: 'USD/ตัน', thb: 'บาท/ตัน', date: 'วันที่', m1: '1 เดือน', y1: '1 ปี', src: 'แหล่งข้อมูล', milled: 'ข้าวสาร', paddy: 'ข้าวเปลือก',
    loadfail: 'โหลดข้อมูลราคาไม่สำเร็จ ลองรีเฟรชหน้าอีกครั้ง', nodata: 'ยังไม่มีข้อมูล ระบบจะดึงข้อมูลชุดแรกในรอบถัดไป',
    updated: 'อัปเดตข้อมูล', ok: 'ดึงข้อมูลสำเร็จล่าสุด', failed: 'ดึงข้อมูลครั้งล่าสุดไม่สำเร็จ', never: 'ยังไม่เคยดึงสำเร็จ',
    show: 'แสดง/ซ่อน', chartLabel: 'กราฟราคา', noVisible: 'เลือกอย่างน้อยหนึ่งรายการจากด้านบน', stale: 'ข้อมูลอาจไม่เป็นปัจจุบัน',
    perWeek: 'รายสัปดาห์', perMonth: 'รายเดือน', perDay: 'รายวัน',
    upd: 'การอัปเดตข้อมูล', latestv: 'ล่าสุด', histonly: 'ใช้เป็นข้อมูลย้อนหลังถึง', checks: 'rice.ag ตรวจทุกแหล่งข้อมูลทุกวันเวลา 17:37 น. (เวลาไทย)', lastcheck: 'ตรวจล่าสุด', fxnote: 'แปลงสกุลเงินด้วยอัตรา ECB ของแต่ละวัน'
  } : {
    range: 'Range', all: 'All', y: 'Y', latest: 'Latest prices', series: 'Series', market: 'Market', basis: 'Basis',
    usd: 'USD/t', thb: 'THB/t', date: 'Date', m1: '1 mo', y1: '1 yr', src: 'Source', milled: 'milled', paddy: 'paddy',
    loadfail: 'Could not load price data. Try refreshing the page.', nodata: 'No data yet. The first daily pull will fill this in.',
    updated: 'Data updated', ok: 'Last successful pull', failed: 'Last pull failed', never: 'never pulled successfully',
    show: 'Show or hide', chartLabel: 'Price chart', noVisible: 'Pick at least one series above.', stale: 'may be out of date',
    perWeek: 'weekly', perMonth: 'monthly', perDay: 'daily',
    upd: 'Updates', latestv: 'latest', histonly: 'used for older history, up to', checks: 'rice.ag checks every source daily at 17:37 Bangkok time', lastcheck: 'last checked', fxnote: 'baht converted at each day\'s ECB rate'
  };
  var DAY = 864e5;
  var SRCNAME = { trea: 'TREA', fao: 'FAO', wb: 'World Bank', usda: 'USDA', dit: TH ? 'กรมการค้าภายใน' : 'DIT', fx: 'ECB' };
  var DEFAULT_ON = { origins: ['th_5', 'vn_5', 'in_5', 'us_lg', 'pk_5', 'uy_5'], more: ['in_25', 'vn_25', 'pk_25', 'th_15'], thai: ['th_5', 'th_jas', 'th_glu', 'th_hm'], domestic: ['dit_paddy', 'dit_paddy_hm', 'dit_paddy_glu', 'dit_w5'] };
  var root = document.getElementById('prices-app');
  if (!root) return;
  var state = { years: 3, data: null, on: {} };
  try { var saved = JSON.parse(localStorage.getItem('riceag-prices') || 'null'); if (saved) { state.years = saved.years; state.on = saved.on || {}; } } catch (e) { /* storage unavailable */ }
  function persist() { try { localStorage.setItem('riceag-prices', JSON.stringify({ years: state.years, on: state.on })); } catch (e) { /* ignore */ } }

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function svg(tag, attrs) { var e = document.createElementNS('http://www.w3.org/2000/svg', tag); for (var k in attrs) e.setAttribute(k, attrs[k]); return e; }
  var nf0 = new Intl.NumberFormat(LOC, { maximumFractionDigits: 0 });
  var pf = new Intl.NumberFormat(LOC, { maximumFractionDigits: 1, minimumFractionDigits: 1, signDisplay: 'exceptZero' });
  function fdate(ms, opt) { return new Date(ms).toLocaleDateString(LOC, opt || { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }); }
  function name(s) { return TH ? s.th : s.en; }
  // moments (pull times) in the viewer's local time; fdate above is for date-only data points
  function fwhen(ms) { return new Date(ms).toLocaleString(LOC, { dateStyle: 'medium', timeStyle: 'short' }); }

  // value of series at or before t, if within `tol` days
  function at(s, t, tol, arr) {
    arr = arr || s.v;
    var d = s.d, lo = 0, hi = d.length - 1, day = t / DAY;
    if (!d.length || d[0] > day) return null;
    while (lo < hi) { var mid = (lo + hi + 1) >> 1; if (d[mid] <= day) lo = mid; else hi = mid - 1; }
    return day - d[lo] <= tol && arr[lo] != null ? { i: lo, v: arr[lo], t: d[lo] * DAY } : null;
  }
  function freqOf(s) {
    var n = s.d.length; if (n < 3) return T.perMonth;
    var gap = (s.d[n - 1] - s.d[Math.max(0, n - 10)]) / Math.min(9, n - 1);
    return gap < 4 ? T.perDay : gap < 12 ? T.perWeek : T.perMonth;
  }
  function tolOf(s) { var f = freqOf(s); return f === T.perDay ? 7 : f === T.perWeek ? 14 : 45; }

  function niceTicks(min, max, n) {
    var span = max - min || 1, step = Math.pow(10, Math.floor(Math.log10(span / n))), err = span / n / step;
    step *= err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1;
    var out = []; for (var v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(v);
    return out;
  }

  function chart(group, host) {
    var S = state.data.series, ids = group.series.filter(function (id) { return S[id]; });
    var baht = group.unit === 'THB';
    function vals(s) { return baht ? (s.thb || []) : s.v; }
    var on = state.on[group.id] || (DEFAULT_ON[group.id] || ids).filter(function (id) { return S[id]; });
    state.on[group.id] = on;
    host.textContent = '';
    var legend = el('div', 'px-legend'); legend.setAttribute('role', 'group'); legend.setAttribute('aria-label', T.show);
    ids.forEach(function (id) {
      var b = el('button', 'px-chip'); b.type = 'button';
      b.style.setProperty('--c', 'var(--s' + (group.series.indexOf(id) + 1) + ')');
      b.setAttribute('aria-pressed', on.indexOf(id) >= 0 ? 'true' : 'false');
      b.appendChild(el('i')); b.appendChild(document.createTextNode(name(S[id])));
      b.addEventListener('click', function () {
        var k = on.indexOf(id); if (k >= 0) on.splice(k, 1); else on.push(id);
        persist(); chart(group, host);
      });
      legend.appendChild(b);
    });
    host.appendChild(legend);
    var box = el('div', 'px-plot'); host.appendChild(box);
    var vis = ids.filter(function (id) { return on.indexOf(id) >= 0; });
    if (!vis.length) { box.appendChild(el('p', 'fine px-empty', T.noVisible)); return; }

    var W = Math.max(300, box.clientWidth || host.clientWidth || 600), narrow = W < 560;
    var labelEnds = vis.length <= 4 && !narrow;
    var H = narrow ? 260 : 330, M = { l: 52, r: labelEnds ? 200 : 14, t: 28, b: 28 };
    var tMax = 0; vis.forEach(function (id) { var d = S[id].d; tMax = Math.max(tMax, d[d.length - 1] * DAY); });
    var tMin = state.years ? tMax - state.years * 365.25 * DAY : Infinity;
    if (!state.years) vis.forEach(function (id) { tMin = Math.min(tMin, S[id].d[0] * DAY); });
    var lines = vis.map(function (id) {
      var s = S[id], pts = [];
      var arr = vals(s);
      for (var i = 0; i < s.d.length; i++) { var t = s.d[i] * DAY; if (t >= tMin && arr[i] != null) pts.push([t, arr[i]]); }
      var cap = Math.round((W - M.l - M.r) * 1.2);  // thin long histories to about one point per pixel
      if (pts.length > cap) { var k = Math.ceil(pts.length / cap), th = []; for (var j = 0; j < pts.length; j += k) { var sl = pts.slice(j, j + k), m = 0; sl.forEach(function (p) { m += p[1]; }); th.push([sl[sl.length >> 1][0], m / sl.length]); } th.push(pts[pts.length - 1]); pts = th; }
      return { id: id, s: s, pts: pts, c: 'var(--s' + (group.series.indexOf(id) + 1) + ')' };
    }).filter(function (l) { return l.pts.length; });
    var vMin = Infinity, vMax = -Infinity;
    lines.forEach(function (l) { l.pts.forEach(function (p) { if (p[1] < vMin) vMin = p[1]; if (p[1] > vMax) vMax = p[1]; }); });
    var pad = (vMax - vMin) * 0.08 || 10; vMin = Math.max(0, vMin - pad); vMax += pad;
    var yt = niceTicks(vMin, vMax, narrow ? 4 : 5); vMin = Math.min(vMin, yt[0]); vMax = Math.max(vMax, yt[yt.length - 1]);
    var X = function (t) { return M.l + (t - tMin) / (tMax - tMin || 1) * (W - M.l - M.r); };
    var Y = function (v) { return M.t + (1 - (v - vMin) / (vMax - vMin || 1)) * (H - M.t - M.b); };

    var g = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, class: 'px-svg', role: 'img', tabindex: '0' });
    g.setAttribute('aria-label', T.chartLabel + ': ' + (TH ? group.th : group.en));
    yt.forEach(function (v) {
      g.appendChild(svg('line', { x1: M.l, x2: W - M.r, y1: Y(v), y2: Y(v), class: 'px-grid' }));
      var tx = svg('text', { x: M.l - 8, y: Y(v) + 4, class: 'px-tick', 'text-anchor': 'end' }); tx.textContent = nf0.format(v); g.appendChild(tx);
    });
    var spanY = (tMax - tMin) / (365.25 * DAY), yearStep = spanY > 24 ? 5 : spanY > 10 ? 2 : 1;
    var d0 = new Date(tMin), xt = [];
    if (spanY <= 2.5) { for (var m = new Date(Date.UTC(d0.getUTCFullYear(), d0.getUTCMonth() + 1, 1)); m <= tMax; m = new Date(Date.UTC(m.getUTCFullYear(), m.getUTCMonth() + (narrow ? 4 : spanY > 1.5 ? 3 : 2), 1))) xt.push([+m, fdate(+m, { month: 'short', year: '2-digit', timeZone: 'UTC' })]); }
    else { for (var yr = Math.ceil((d0.getUTCFullYear() + 1) / yearStep) * yearStep; Date.UTC(yr, 0, 1) <= tMax; yr += yearStep * (narrow && spanY > 4 ? 2 : 1)) xt.push([Date.UTC(yr, 0, 1), String(TH ? yr + 543 : yr)]); }
    xt.forEach(function (x) { var tx = svg('text', { x: X(x[0]), y: H - 8, class: 'px-tick', 'text-anchor': 'middle' }); tx.textContent = x[1]; g.appendChild(tx); });
    g.appendChild(svg('line', { x1: M.l, x2: W - M.r, y1: H - M.b, y2: H - M.b, class: 'px-axis' }));
    var ylab = svg('text', { x: 4, y: 12, class: 'px-tick' }); ylab.textContent = baht ? T.thb : T.usd; g.appendChild(ylab);
    lines.forEach(function (l) {
      var dstr = l.pts.map(function (p, i) { return (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1); }).join('');
      g.appendChild(svg('path', { d: dstr, class: 'px-line', style: 'stroke:' + l.c }));
    });
    if (labelEnds) {  // direct labels at line ends, nudged apart so they never overlap
      var ends = lines.map(function (l) { var p = l.pts[l.pts.length - 1]; return { l: l, y: Y(p[1]), v: p[1], x: X(p[0]) }; }).sort(function (a, b) { return a.y - b.y; });
      for (var i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 15) ends[i].y = ends[i - 1].y + 15;
      ends.forEach(function (e) {
        g.appendChild(svg('circle', { cx: e.x, cy: Y(e.v), r: 4, class: 'px-dot', style: 'fill:' + e.l.c }));
        var tx = svg('text', { x: W - M.r + 10, y: e.y + 4, class: 'px-end' });
        var nm = name(e.l.s); tx.textContent = nf0.format(e.v) + '  ' + (nm.length > 24 ? nm.slice(0, 23) + '…' : nm);
        g.appendChild(tx);
      });
    }
    var cross = svg('line', { y1: M.t, y2: H - M.b, class: 'px-cross', visibility: 'hidden' }); g.appendChild(cross);
    var dots = lines.map(function (l) { var c = svg('circle', { r: 4, class: 'px-dot', visibility: 'hidden', style: 'fill:' + l.c }); g.appendChild(c); return c; });
    box.appendChild(g);
    var tip = el('div', 'px-tip'); tip.hidden = true; box.appendChild(tip);

    // one crosshair, every visible series; keyboard arrows step through dates
    var allT = []; lines.forEach(function (l) { l.pts.forEach(function (p) { allT.push(p[0]); }); });
    allT = allT.sort(function (a, b) { return a - b; }).filter(function (t, i, a) { return !i || t !== a[i - 1]; });
    var cur = -1;
    function show(idx) {
      if (idx < 0 || idx >= allT.length) return;
      cur = idx; var t = allT[idx], x = X(t);
      cross.setAttribute('x1', x); cross.setAttribute('x2', x); cross.setAttribute('visibility', 'visible');
      tip.textContent = '';
      tip.appendChild(el('div', 'px-tip-d', fdate(t)));
      var rows = [];
      lines.forEach(function (l, i) {
        var hit = at(l.s, t, tolOf(l.s), vals(l.s));
        if (hit && hit.t >= tMin) { dots[i].setAttribute('cx', X(hit.t)); dots[i].setAttribute('cy', Y(hit.v)); dots[i].setAttribute('visibility', 'visible'); rows.push({ l: l, v: hit.v, i: hit.i }); }
        else dots[i].setAttribute('visibility', 'hidden');
      });
      rows.sort(function (a, b) { return b.v - a.v; }).forEach(function (r) {
        var row = el('div', 'px-tip-r'); var k = el('i'); k.style.background = r.l.c; row.appendChild(k);
        // baht charts: ฿ value, then the dollar price highlighted; dollar charts: the dollar price highlighted
        if (baht) row.appendChild(el('b', 'px-tip-v', '฿' + nf0.format(r.v)));
        row.appendChild(el('b', 'px-tip-usd', '$' + nf0.format(baht ? r.l.s.v[r.i] : r.v)));
        if (!baht) row.appendChild(el('b', 'px-tip-v', ''));
        row.appendChild(el('span', 'px-tip-n', name(r.l.s))); tip.appendChild(row);
      });
      tip.hidden = false;
      var bw = box.clientWidth, tw = tip.offsetWidth;
      var left = x * (box.clientWidth / W) + 14; if (left + tw > bw) left = x * (box.clientWidth / W) - tw - 14;
      tip.style.left = Math.max(0, Math.min(left, bw - tw)) + 'px';
    }
    function hide() { cross.setAttribute('visibility', 'hidden'); dots.forEach(function (d) { d.setAttribute('visibility', 'hidden'); }); tip.hidden = true; }
    function nearest(clientX) {
      var r = g.getBoundingClientRect(), x = (clientX - r.left) * (W / r.width);
      var t = tMin + (x - M.l) / (W - M.l - M.r) * (tMax - tMin), lo = 0, hi = allT.length - 1;
      while (lo < hi) { var mid = (lo + hi) >> 1; if (allT[mid] < t) lo = mid + 1; else hi = mid; }
      if (lo > 0 && Math.abs(allT[lo - 1] - t) < Math.abs(allT[lo] - t)) lo--;
      return lo;
    }
    g.addEventListener('pointermove', function (e) { show(nearest(e.clientX)); });
    g.addEventListener('pointerdown', function (e) { show(nearest(e.clientX)); });  // tap on phones
    g.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse') hide(); });
    g.addEventListener('focus', function () { show(cur >= 0 ? cur : allT.length - 1); });
    g.addEventListener('blur', hide);
    g.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); show(Math.min(allT.length - 1, Math.max(0, cur + (e.key === 'ArrowLeft' ? -1 : 1) * (e.shiftKey ? 10 : 1)))); }
      if (e.key === 'Escape') hide();
    });
  }

  function note(gr, host) {
    var S = state.data.series, src = state.data.sources, last = {};
    gr.series.concat(gr.table_extra || []).forEach(function (id) {
      var s = S[id]; if (!s || !s.srclast) return;
      Object.keys(s.srclast).forEach(function (k) { last[k] = Math.max(last[k] || 0, s.srclast[k]); });
    });
    var keys = ['trea', 'dit', 'fao', 'usda', 'wb'].filter(function (k) { return last[k]; });
    if (!keys.length) return;
    var newest = 0; keys.forEach(function (k) { newest = Math.max(newest, last[k]); });
    var box = el('div', 'px-upd'); box.appendChild(el('b', null, T.upd));
    var ul = el('ul'), checked = 0;
    keys.forEach(function (k) {
      var info = src[k] || {}, monthly = k === 'fao' || k === 'wb' || k === 'usda';
      var latest = fdate(last[k] * DAY, monthly ? { month: 'long', year: 'numeric', timeZone: 'UTC' } : undefined);
      var sched = (TH ? info.sched_th : info.sched_en) || info.freq || '';
      // a source that only fills in early years isn't "stale": say what it's used for
      var text = newest - last[k] > 400 ? T.histonly + ' ' + latest : sched + ' · ' + T.latestv + ' ' + latest;
      ul.appendChild(el('li', null, (SRCNAME[k] || k) + ': ' + text));
      if (info.last_ok) checked = Math.max(checked, Date.parse(info.last_ok));
    });
    if (gr.unit === 'THB' || gr.id === 'domestic') ul.appendChild(el('li', null, 'ECB: ' + T.fxnote));
    ul.appendChild(el('li', null, T.checks + (checked ? ' · ' + T.lastcheck + ' ' + fwhen(checked) : '')));
    box.appendChild(ul); host.appendChild(box);
  }

  function change(s, days) {
    var n = s.d.length - 1, t = (s.d[n] - days) * DAY, prev = at(s, t, Math.max(tolOf(s), days * 0.25));
    return prev && prev.v ? (s.v[n] / prev.v - 1) * 100 : null;
  }

  function table(host) {
    var S = state.data.series, wrap = el('div', 'table-scroll'), tb = el('table', 'px-table');
    var head = el('tr');
    [T.series, T.basis, T.usd, T.thb, T.date, T.m1, T.y1, T.src].forEach(function (h, i) { var th = el('th', i >= 2 && i !== 4 && i !== 7 ? 'num' : null, h); th.scope = 'col'; head.appendChild(th); });
    var thead = el('thead'); thead.appendChild(head); tb.appendChild(thead);
    var seen = {};
    state.data.groups.forEach(function (gr) {
      var body = el('tbody'), hr = el('tr', 'px-grp'), hc = el('th', null, TH ? gr.th : gr.en); hc.colSpan = 8; hc.scope = 'colgroup'; hr.appendChild(hc); body.appendChild(hr);
      gr.series.concat(gr.table_extra || []).forEach(function (id) {
        var s = S[id]; if (!s || seen[id]) return; seen[id] = 1;
        var n = s.d.length - 1, tr = el('tr');
        var nm = el('th', null, name(s)); nm.scope = 'row'; tr.appendChild(nm);
        tr.appendChild(el('td', null, (s.basis === 'paddy' ? T.paddy : T.milled) + ' · ' + (TH ? s.market.th : s.market.en)));
        tr.appendChild(el('td', 'num', nf0.format(s.v[n])));
        tr.appendChild(el('td', 'num', s.thb && s.thb[n] ? nf0.format(s.thb[n]) : ''));
        tr.appendChild(el('td', null, fdate(s.d[n] * DAY) + ' · ' + freqOf(s)));
        [30, 365].forEach(function (d) { var c = change(s, d); tr.appendChild(el('td', 'num', c == null ? '–' : pf.format(c) + '%')); });
        tr.appendChild(el('td', null, s.src.map(function (k) { return SRCNAME[k] || k; }).join(', ')));
        body.appendChild(tr);
      });
      tb.appendChild(body);
    });
    wrap.appendChild(tb); host.textContent = ''; host.appendChild(wrap);
  }

  function sources(host) {
    host.textContent = '';
    var ul = el('ul', 'px-sources'), now = Date.now();
    Object.keys(state.data.sources).forEach(function (k) {
      var s = state.data.sources[k], li = el('li'), a = el('a', null, s.name); a.href = s.url; a.rel = 'noopener';
      li.appendChild(a); li.appendChild(document.createTextNode(' — ' + s.freq + '. ' + s.terms + ' '));
      var st = el('span', 'fine');
      if (!s.last_ok) st.textContent = T.never + '.';
      else {
        var okd = Date.parse(s.last_ok), stale = now - okd > 3 * DAY;
        st.textContent = T.ok + ': ' + fwhen(okd) + (stale ? ' (' + T.stale + ')' : '') + '.';
        if (stale) st.className = 'fine px-stale';
      }
      if (s.last_error && (!s.last_ok || Date.parse(s.last_attempt) > Date.parse(s.last_ok))) st.textContent += ' ' + T.failed + '.';
      li.appendChild(st); ul.appendChild(li);
    });
    host.appendChild(ul);
  }

  function converter() {
    var inp = document.getElementById('px-cwt'); if (!inp || inp.dataset.wired) return; inp.dataset.wired = '1';
    var fx = state.data.fx, out = document.getElementById('px-cwt-out');
    function upd() {
      var v = parseFloat(inp.value);
      if (!(v > 0)) { out.textContent = '–'; return; }
      var usd = v * 22.0462;
      out.textContent = '$' + nf0.format(usd) + (TH ? ' ต่อตันข้าวเปลือก' : ' per tonne of paddy') +
        (fx && fx.usd_thb ? ' ≈ ฿' + nf0.format(usd * fx.usd_thb) + (TH ? ' (อัตรา ' : ' (at ') + fx.usd_thb.toFixed(2) + ' THB/USD, ' + fdate(Date.parse(fx.date)) + ')' : '');
    }
    inp.addEventListener('input', upd); upd();
  }

  function rangeBar() {
    var bar = document.getElementById('px-range'); if (!bar) return;
    bar.textContent = '';
    bar.appendChild(el('span', 'px-range-l', T.range));
    [1, 3, 5, 10, 0].forEach(function (y) {
      var b = el('button', 'btn btn-ghost btn-sm', y ? y + T.y : T.all); b.type = 'button';
      b.setAttribute('aria-pressed', state.years === y ? 'true' : 'false');
      b.addEventListener('click', function () { state.years = y; persist(); render(); });
      bar.appendChild(b);
    });
  }

  function render() {
    rangeBar();
    state.data.groups.forEach(function (gr) { var h = document.getElementById('px-chart-' + gr.id); if (h) { chart(gr, h); note(gr, h); } });
    converter();
    table(document.getElementById('px-table'));
    sources(document.getElementById('px-sources'));
    var up = document.getElementById('px-updated');
    if (up) up.textContent = T.updated + ': ' + new Date(state.data.generated).toLocaleString(LOC, { dateStyle: 'medium', timeStyle: 'short' });
  }

  fetch('/static/data/prices.json', { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (d) {
      state.data = d;
      if (!Object.keys(d.series).length) { root.querySelector('.px-status').textContent = T.nodata; }
      else root.querySelector('.px-status').remove();
      render();
      var rt; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(render, 150); });
    })
    .catch(function () { root.querySelector('.px-status').textContent = T.loadfail; });
})();
