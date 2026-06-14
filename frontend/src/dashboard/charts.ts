/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — app-charts.js
   Hand-built SVG chart primitives, tuned to the light system.
   No external libraries. All charts respect prefers-reduced-motion
   (the CSS gates the entrance animations).
   ============================================================ */
(function () {
  'use strict';
  const SVGNS = 'http://www.w3.org/2000/svg';
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  function el(tag, attrs, parent) {
    const n = document.createElementNS(SVGNS, tag);
    if (attrs) for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }

  /* ---------- path from values (smooth catmull-rom → bezier) ---------- */
  function smoothPath(pts) {
    if (pts.length < 2) return '';
    let d = `M ${pts[0][0]},${pts[0][1]}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[i + 2] || p2;
      const c1x = p1[0] + (p2[0] - p0[0]) / 6;
      const c1y = p1[1] + (p2[1] - p0[1]) / 6;
      const c2x = p2[0] - (p3[0] - p1[0]) / 6;
      const c2y = p2[1] - (p3[1] - p1[1]) / 6;
      d += ` C ${c1x},${c1y} ${c2x},${c2y} ${p2[0]},${p2[1]}`;
    }
    return d;
  }

  function pointsFor(values, w, h, pad) {
    const min = Math.min(...values), max = Math.max(...values);
    const range = max - min || 1;
    const n = values.length;
    return values.map((v, i) => [
      pad + (i / (n - 1)) * (w - pad * 2),
      h - pad - ((v - min) / range) * (h - pad * 2),
    ]);
  }

  /* ---------- sparkline (returns SVG string) ---------- */
  function sparkline(values, opts) {
    const o = Object.assign({ w: 120, h: 34, stroke: 'var(--signal)', fill: true, sw: 1.8, pad: 3 }, opts || {});
    const pts = pointsFor(values, o.w, o.h, o.pad);
    const line = smoothPath(pts);
    const gid = 'sg' + Math.random().toString(36).slice(2, 8);
    const last = pts[pts.length - 1];
    const area = o.fill
      ? `<defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
           <stop offset="0%" stop-color="${o.stroke}" stop-opacity=".18"/>
           <stop offset="100%" stop-color="${o.stroke}" stop-opacity="0"/>
         </linearGradient></defs>
         <path d="${line} L ${last[0]},${o.h - o.pad} L ${pts[0][0]},${o.h - o.pad} Z" fill="url(#${gid})"/>`
      : '';
    return `<svg class="spark" viewBox="0 0 ${o.w} ${o.h}" preserveAspectRatio="none" aria-hidden="true">
        ${area}
        <path d="${line}" fill="none" stroke="${o.stroke}" stroke-width="${o.sw}" stroke-linecap="round" stroke-linejoin="round"/>
        ${o.dot ? `<circle cx="${last[0]}" cy="${last[1]}" r="${o.sw + 0.8}" fill="${o.stroke}"/>` : ''}
      </svg>`;
  }

  /* ---------- score ring (returns SVG string; number placed by caller) ---------- */
  function ring(pct, color, size, sw, confidence) {
    size = size || 44; sw = sw || 4;
    const r = (size - sw) / 2 - (confidence != null ? 3 : 0);
    const c = 2 * Math.PI * r;
    const off = c * (1 - clamp(pct, 0, 100) / 100);
    const cx = size / 2;
    let conf = '';
    if (confidence != null) {
      const r2 = r + 3.4;
      const c2 = 2 * Math.PI * r2;
      conf = `<circle cx="${cx}" cy="${cx}" r="${r2}" fill="none" stroke="var(--border-subtle)" stroke-width="1.4"/>
        <circle cx="${cx}" cy="${cx}" r="${r2}" fill="none" stroke="var(--text-tertiary)" stroke-width="1.4"
          stroke-linecap="round" stroke-dasharray="${c2}" stroke-dashoffset="${c2 * (1 - clamp(confidence, 0, 1))}"
          transform="rotate(-90 ${cx} ${cx})"/>`;
    }
    return `<svg class="ring" viewBox="0 0 ${size} ${size}" style="width:${size}px;height:${size}px" aria-hidden="true">
        <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="var(--border-subtle)" stroke-width="${sw}"/>
        <circle class="ring-val" cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${color}" stroke-width="${sw}"
          stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}"
          transform="rotate(-90 ${cx} ${cx})"/>
        ${conf}
      </svg>`;
  }

  /* ---------- micro horizontal gauge (5-segment) ---------- */
  function microGauge(pct, color) {
    const filled = Math.round(clamp(pct, 0, 100) / 20);
    let s = '<span class="mg" aria-hidden="true">';
    for (let i = 0; i < 5; i++) s += `<i class="${i < filled ? 'on' : ''}" style="${i < filled ? '--mgc:' + color : ''}"></i>`;
    return s + '</span>';
  }

  /* ============================================================
     RADAR EXPRESS — bubble matrix (momentum × maturity)
     ============================================================ */
  function renderRadar(container, products, ctx) {
    const T = window.TANDOR, S = T.STR[ctx.lang];
    container.innerHTML = '';
    const W = container.clientWidth || 360, H = container.clientHeight || 300;
    const m = { t: 14, r: 14, b: 26, l: 30 };
    const pw = W - m.l - m.r, ph = H - m.t - m.b;
    const x = (v) => m.l + (v / 100) * pw;
    const y = (v) => m.t + (1 - v / 100) * ph;

    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'radar-svg', width: W, height: H });
    container.appendChild(svg);

    // target quadrant tint (top-left = low maturity, high momentum)
    el('rect', { x: m.l, y: m.t, width: pw / 2, height: ph / 2, fill: 'var(--signal)', 'fill-opacity': '.06', rx: 6 }, svg);

    // grid
    [25, 50, 75].forEach((g) => {
      el('line', { x1: x(g), y1: m.t, x2: x(g), y2: m.t + ph, stroke: 'var(--border-subtle)', 'stroke-width': 1 }, svg);
      el('line', { x1: m.l, y1: y(g), x2: m.l + pw, y2: y(g), stroke: 'var(--border-subtle)', 'stroke-width': 1 }, svg);
    });
    // mid cross stronger
    el('line', { x1: x(50), y1: m.t, x2: x(50), y2: m.t + ph, stroke: 'var(--border-strong)', 'stroke-width': 1, 'stroke-dasharray': '3 3' }, svg);
    el('line', { x1: m.l, y1: y(50), x2: m.l + pw, y2: y(50), stroke: 'var(--border-strong)', 'stroke-width': 1, 'stroke-dasharray': '3 3' }, svg);

    // quadrant labels
    const qlab = (tx, ty, text, strong) => {
      const t = el('text', { x: tx, y: ty, class: 'radar-q' + (strong ? ' strong' : ''), 'text-anchor': 'middle' }, svg);
      t.textContent = text;
    };
    qlab(m.l + pw * 0.25, m.t + 12, S.q_emerg, true);
    qlab(m.l + pw * 0.75, m.t + 12, S.q_growth);
    qlab(m.l + pw * 0.75, m.t + ph - 6, S.q_sat);
    qlab(m.l + pw * 0.25, m.t + ph - 6, S.q_avoid);

    // axis labels
    const ax = el('text', { x: m.l + pw / 2, y: H - 6, class: 'radar-axis', 'text-anchor': 'middle' }, svg); ax.textContent = S.maturity + ' →';
    const ay = el('text', { x: 9, y: m.t + ph / 2, class: 'radar-axis', 'text-anchor': 'middle', transform: `rotate(-90 9 ${m.t + ph / 2})` }, svg); ay.textContent = S.momentum + ' →';

    const last20 = products.slice().sort((a, b) => b.tandor - a.tandor).slice(0, 20);
    const maxMargin = Math.max(...last20.map((p) => p.gross));

    last20.forEach((p, i) => {
      const cx = x(p.maturity), cy = y(p.momentum);
      const r = 6 + (p.gross / maxMargin) * 12;
      const col = `var(--${T.PHASES[p.phase].v})`;
      const g = el('g', { class: 'radar-bub', 'data-id': p.id, style: `--d:${i * 35}ms` }, svg);
      // halo = confidence
      el('circle', { cx, cy, r: r + 4 * p.confidence, fill: col, 'fill-opacity': (0.10 + 0.10 * p.confidence).toFixed(2) }, g);
      const dot = el('circle', { cx, cy, r, fill: col, 'fill-opacity': '.7', stroke: col, 'stroke-width': 1.5 }, g);
      g.style.cursor = 'pointer';
      g.addEventListener('mouseenter', (e) => {
        dot.setAttribute('fill-opacity', '.95');
        window.Tip && window.Tip.show(radarTip(p, ctx), e);
      });
      g.addEventListener('mousemove', (e) => window.Tip && window.Tip.move(e));
      g.addEventListener('mouseleave', () => { dot.setAttribute('fill-opacity', '.7'); window.Tip && window.Tip.hide(); });
      g.addEventListener('click', () => ctx.onSelect && ctx.onSelect(p));
    });
  }

  function radarTip(p, ctx) {
    const T = window.TANDOR, S = T.STR[ctx.lang];
    return `<div class="tip-h"><b>${p.name}</b><span class="tip-score">${p.tandor}</span></div>
      <div class="tip-rows">
        <div><span>${S.momentum}</span><b>${p.momentum}</b></div>
        <div><span>${S.maturity}</span><b>${p.maturity}</b></div>
        <div><span>${S.kpi_margin.split(' ')[0] === 'Median' ? 'Margin' : 'Marge'}</span><b>+${p.gross.toFixed(0)}€</b></div>
        <div><span>${S.conf}</span><b>${Math.round(p.confidence * 100)}%</b></div>
      </div>`;
  }

  /* ============================================================
     TREEMAP — squarified, category weight = #BUY, colour = avg score
     ============================================================ */
  function squarify(data, x, y, w, h) {
    // data: [{value,...}] sorted desc; returns rects [{...,x,y,w,h}]
    const out = [];
    const items = data.slice();
    const total = items.reduce((s, d) => s + d.value, 0);
    let area = { x, y, w, h };
    let scale = (w * h) / total;
    let remaining = items.map((d) => Object.assign({}, d, { a: d.value * scale }));

    function worst(row, len) {
      const sum = row.reduce((s, r) => s + r.a, 0);
      const max = Math.max(...row.map((r) => r.a));
      const min = Math.min(...row.map((r) => r.a));
      return Math.max((len * len * max) / (sum * sum), (sum * sum) / (len * len * min));
    }
    function layoutRow(row, len, horizontal) {
      const sum = row.reduce((s, r) => s + r.a, 0);
      const thick = sum / len;
      let off = horizontal ? area.y : area.x;
      row.forEach((r) => {
        const cell = r.a / thick;
        if (horizontal) { out.push(Object.assign(r, { x: area.x, y: off, w: thick, h: cell })); off += cell; }
        else { out.push(Object.assign(r, { x: off, y: area.y, w: cell, h: thick })); off += cell; }
      });
      if (horizontal) { area.x += thick; area.w -= thick; } else { area.y += thick; area.h -= thick; }
    }
    let row = [];
    while (remaining.length) {
      const horizontal = area.w >= area.h;
      const len = horizontal ? area.h : area.w;
      const next = remaining[0];
      if (row.length === 0 || worst(row, len) >= worst(row.concat(next), len)) {
        row.push(next); remaining.shift();
      } else {
        layoutRow(row, len, horizontal); row = [];
      }
    }
    if (row.length) layoutRow(row, area.w >= area.h ? area.h : area.w, area.w >= area.h);
    return out;
  }

  function renderTreemap(container, products, ctx) {
    const T = window.TANDOR;
    container.innerHTML = '';
    const W = container.clientWidth || 400, H = container.clientHeight || 220;
    const byCat = {};
    products.forEach((p) => {
      const k = p.cat;
      byCat[k] = byCat[k] || { cat: k, value: 0, scoreSum: 0, n: 0 };
      if (p.verdict === 'BUY' || p.verdict === 'WATCH') byCat[k].value += p.verdict === 'BUY' ? 2 : 1;
      byCat[k].scoreSum += p.tandor; byCat[k].n++;
    });
    let data = Object.values(byCat).filter((d) => d.value > 0).map((d) => ({ cat: d.cat, value: d.value, avg: Math.round(d.scoreSum / d.n) }));
    data.sort((a, b) => b.value - a.value);
    const rects = squarify(data, 0, 0, W, H);

    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H, class: 'tm-svg' });
    container.appendChild(svg);
    const maxAvg = Math.max(...data.map((d) => d.avg)), minAvg = Math.min(...data.map((d) => d.avg));
    rects.forEach((r, i) => {
      const t = (r.avg - minAvg) / (maxAvg - minAvg || 1);
      // colour: low avg → neutral tint, high → signal
      const fill = `color-mix(in oklab, var(--signal) ${Math.round(18 + t * 62)}%, var(--surface-1))`;
      const g = el('g', { class: 'tm-cell', style: `--d:${i * 45}ms`, 'data-cat': r.cat }, svg);
      el('rect', { x: r.x + 1.5, y: r.y + 1.5, width: Math.max(0, r.w - 3), height: Math.max(0, r.h - 3), rx: 7, fill, stroke: 'var(--border-subtle)', 'stroke-width': 1 }, g);
      if (r.w > 42 && r.h > 24) {
        const nm = el('text', { x: r.x + 11, y: r.y + 21, class: 'tm-label' }, g);
        nm.textContent = T.CATS[r.cat][ctx.lang];
        const sc = el('text', { x: r.x + 11, y: r.y + 37, class: 'tm-sub' }, g);
        sc.textContent = r.avg;
      }
      g.style.cursor = 'pointer';
      g.addEventListener('mouseenter', (e) => window.Tip && window.Tip.show(
        `<div class="tip-h"><b>${T.CATS[r.cat][ctx.lang]}</b></div>
         <div class="tip-rows"><div><span>${ctx.lang === 'fr' ? 'Score moyen' : 'Avg score'}</span><b>${r.avg}</b></div></div>`, e));
      g.addEventListener('mousemove', (e) => window.Tip && window.Tip.move(e));
      g.addEventListener('mouseleave', () => window.Tip && window.Tip.hide());
      g.addEventListener('click', () => ctx.onCat && ctx.onCat(r.cat));
    });
  }

  /* ============================================================
     HEATMAP — month × category seasonality multiplier
     ============================================================ */
  function renderHeatmap(container, ctx) {
    const T = window.TANDOR, M = T.MONTHS[ctx.lang];
    container.innerHTML = '';
    const matrix = T.seasonMatrix();
    const rows = matrix.length, cols = 12;
    const W = container.clientWidth || 460, H = container.clientHeight || 220;
    const labW = 56, headH = 16;
    const cw = (W - labW) / cols, chh = (H - headH) / rows, gap = 2.5;
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H, class: 'hm-svg' });
    container.appendChild(svg);

    // month headers
    for (let c = 0; c < cols; c++) {
      const t = el('text', { x: labW + c * cw + cw / 2, y: 11, class: 'hm-head' + (c === T.CUR_MONTH ? ' cur' : ''), 'text-anchor': 'middle' }, svg);
      t.textContent = M[c][0];
    }
    matrix.forEach((row, ri) => {
      const ty = headH + ri * chh;
      const lab = el('text', { x: 0, y: ty + chh / 2 + 3, class: 'hm-rowlab' }, svg);
      lab.textContent = T.CATS[row.cat][ctx.lang];
      row.vals.forEach((v, ci) => {
        // value 0.7..1.4 → colour: <1 neutral/slate, >1 signal, >1.2 amber
        const t = (v - 0.7) / 0.7;
        let fill;
        if (v < 0.98) fill = `color-mix(in oklab, var(--text-tertiary) ${Math.round(8 + (1 - t) * 14)}%, var(--surface-1))`;
        else if (v < 1.18) fill = `color-mix(in oklab, var(--signal) ${Math.round(18 + (t) * 48)}%, var(--surface-1))`;
        else fill = `color-mix(in oklab, var(--amber) ${Math.round(40 + (t) * 45)}%, var(--surface-1))`;
        const cell = el('rect', {
          x: labW + ci * cw + gap / 2, y: ty + gap / 2,
          width: cw - gap, height: chh - gap, rx: 4, fill,
          class: 'hm-cell' + (ci === T.CUR_MONTH ? ' cur' : ''), style: `--d:${(ri + ci) * 22}ms`,
        }, svg);
        cell.addEventListener('mouseenter', (e) => window.Tip && window.Tip.show(
          `<div class="tip-h"><b>${T.CATS[row.cat][ctx.lang]} · ${M[ci]}</b></div>
           <div class="tip-rows"><div><span>${ctx.lang === 'fr' ? 'Demande' : 'Demand'}</span><b>×${v.toFixed(2)}</b></div></div>`, e));
        cell.addEventListener('mousemove', (e) => window.Tip && window.Tip.move(e));
        cell.addEventListener('mouseleave', () => window.Tip && window.Tip.hide());
      });
    });
  }

  window.Charts = { sparkline, ring, microGauge, renderRadar, renderTreemap, renderHeatmap };
})();

export {};
