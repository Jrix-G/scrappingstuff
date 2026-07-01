/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — charts-x (ChartsX)
   Primitives SVG ÉTENDUES, faites main, sans dépendance externe.
   Portage du prototype vanilla : les pages Trends / Reddit / Market /
   Engine attendent `window.ChartsX` (lineChart, scatter, histogram,
   donut, divergingArea). charts.ts ne posait que window.Charts ; ce
   module comble le trou. Couleurs via variables CSS du thème, tooltips
   via le helper global window.Tip (posé par shell.ts).
   ============================================================ */
(function () {
  'use strict';
  const SVGNS = 'http://www.w3.org/2000/svg';
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  let _uid = 0;

  function el(tag, attrs, parent) {
    const n = document.createElementNS(SVGNS, tag);
    if (attrs) for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function txt(parent, x, y, s, attrs) {
    const t = el('text', Object.assign({ x, y, fill: 'var(--muted)', 'font-size': 10, 'font-family': 'inherit' }, attrs || {}), parent);
    t.textContent = s;
    return t;
  }
  function width(container, fallback) {
    return container.clientWidth || (container.getBoundingClientRect && container.getBoundingClientRect().width) || fallback;
  }
  // catmull-rom -> bezier (identique à charts.ts)
  function smoothPath(pts) {
    if (pts.length < 2) return pts.length ? `M ${pts[0][0]},${pts[0][1]}` : '';
    let d = `M ${pts[0][0]},${pts[0][1]}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      const c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6;
      const c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6;
      d += ` C ${c1x},${c1y} ${c2x},${c2y} ${p2[0]},${p2[1]}`;
    }
    return d;
  }
  function svgIn(container, W, H, cls) {
    container.innerHTML = '';
    return el('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', height: H, class: cls, preserveAspectRatio: 'none' }, container);
  }

  /* ---------- lineChart : courbes multiples ----------
     series = [{ name, color, values:number[] }]
     opts   = { xlabels, yMin, yMax, area, height } */
  function lineChart(container, series, opts) {
    const o = Object.assign({ yMin: 0, yMax: 100, height: 300, area: false, xlabels: [] }, opts || {});
    const W = width(container, 600), H = o.height;
    const padL = 30, padR = 12, padT = 12, padB = 24;
    const svg = svgIn(container, W, H, 'cx-line');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    const plotW = W - padL - padR, plotH = H - padT - padB;
    const span = (o.yMax - o.yMin) || 1;
    const xFor = (i, n) => padL + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
    const yFor = (v) => padT + plotH - ((clamp(v, o.yMin, o.yMax) - o.yMin) / span) * plotH;
    // grille horizontale + graduations Y
    for (let t = 0; t <= 4; t++) {
      const val = o.yMin + span * t / 4, y = yFor(val);
      el('line', { x1: padL, y1: y, x2: W - padR, y2: y, stroke: 'var(--line)', 'stroke-opacity': 0.45, 'stroke-width': 1 }, svg);
      txt(svg, padL - 6, y + 3, String(Math.round(val)), { 'text-anchor': 'end' });
    }
    // labels X (max ~6, évite la surcharge)
    const xl = o.xlabels || [], nL = xl.length;
    if (nL) {
      const step = Math.max(1, Math.ceil(nL / 6));
      for (let i = 0; i < nL; i += step) txt(svg, xFor(i, nL), H - 7, String(xl[i]), { 'text-anchor': 'middle' });
    }
    (series || []).forEach((sd) => {
      const vals = sd.values || [], n = vals.length;
      if (!n) return;
      const pts = vals.map((v, i) => [xFor(i, n), yFor(v)]);
      const d = smoothPath(pts);
      if (o.area && pts.length) {
        const areaD = d + ` L ${pts[pts.length - 1][0]},${padT + plotH} L ${pts[0][0]},${padT + plotH} Z`;
        el('path', { d: areaD, fill: sd.color || 'var(--signal)', 'fill-opacity': 0.12, stroke: 'none' }, svg);
      }
      el('path', { d, fill: 'none', stroke: sd.color || 'var(--signal)', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
    });
  }

  /* ---------- scatter : nuage de points ----------
     pts  = [{ x, y, r, color, p, tip }]
     opts = { xMax, yMax, xLabel, yLabel, height, onPoint } */
  function scatter(container, pts, opts) {
    const o = Object.assign({ xMax: 100, yMax: 100, height: 300 }, opts || {});
    const W = width(container, 600), H = o.height;
    const padL = 40, padR = 14, padT = 12, padB = 30;
    const svg = svgIn(container, W, H, 'cx-scatter');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    const plotW = W - padL - padR, plotH = H - padT - padB;
    const xFor = (x) => padL + (clamp(x, 0, o.xMax) / (o.xMax || 1)) * plotW;
    const yFor = (y) => padT + plotH - (clamp(y, 0, o.yMax) / (o.yMax || 1)) * plotH;
    // grille
    for (let t = 1; t <= 4; t++) {
      const gx = padL + plotW * t / 4, gy = padT + plotH - plotH * t / 4;
      el('line', { x1: gx, y1: padT, x2: gx, y2: padT + plotH, stroke: 'var(--line)', 'stroke-opacity': 0.3, 'stroke-width': 1 }, svg);
      el('line', { x1: padL, y1: gy, x2: W - padR, y2: gy, stroke: 'var(--line)', 'stroke-opacity': 0.3, 'stroke-width': 1 }, svg);
    }
    // axes
    el('line', { x1: padL, y1: padT, x2: padL, y2: padT + plotH, stroke: 'var(--line)', 'stroke-width': 1 }, svg);
    el('line', { x1: padL, y1: padT + plotH, x2: W - padR, y2: padT + plotH, stroke: 'var(--line)', 'stroke-width': 1 }, svg);
    if (o.xLabel) txt(svg, padL + plotW / 2, H - 6, o.xLabel, { 'text-anchor': 'middle' });
    if (o.yLabel) txt(svg, 12, padT + plotH / 2, o.yLabel, { 'text-anchor': 'middle', transform: `rotate(-90 12 ${padT + plotH / 2})` });
    (pts || []).forEach((pt) => {
      const c = el('circle', {
        cx: xFor(pt.x || 0), cy: yFor(pt.y || 0), r: pt.r || 5,
        fill: pt.color || 'var(--signal)', 'fill-opacity': 0.65,
        stroke: pt.color || 'var(--signal)', 'stroke-width': 1,
      }, svg);
      c.style.cursor = 'pointer';
      if (pt.tip) {
        c.addEventListener('mouseenter', (e) => { c.setAttribute('fill-opacity', '1'); window.Tip && window.Tip.show(pt.tip, e); });
        c.addEventListener('mousemove', (e) => window.Tip && window.Tip.move(e));
        c.addEventListener('mouseleave', () => { c.setAttribute('fill-opacity', '0.65'); window.Tip && window.Tip.hide(); });
      }
      if (o.onPoint) c.addEventListener('click', () => o.onPoint(pt));
    });
  }

  /* ---------- histogram : barres ----------
     bins = number[] (effectifs)   opts = { height } */
  function histogram(container, bins, opts) {
    const o = Object.assign({ height: 200 }, opts || {});
    const W = width(container, 600), H = o.height;
    const padL = 28, padR = 10, padT = 10, padB = 22;
    const svg = svgIn(container, W, H, 'cx-hist');
    const plotW = W - padL - padR, plotH = H - padT - padB;
    const max = Math.max(1, ...bins);
    const n = bins.length || 1, slot = plotW / n, gap = Math.min(6, slot * 0.2), bw = Math.max(1, slot - gap);
    bins.forEach((v, i) => {
      const bh = (v / max) * plotH, x = padL + i * slot + gap / 2, y = padT + plotH - bh;
      el('rect', { x, y, width: bw, height: Math.max(0, bh), rx: 2, fill: 'var(--signal)', 'fill-opacity': 0.8 }, svg);
      if (i % 2 === 0) txt(svg, x + bw / 2, H - 6, String(i * 10), { 'text-anchor': 'middle' });
    });
    el('line', { x1: padL, y1: padT + plotH, x2: W - padR, y2: padT + plotH, stroke: 'var(--line)', 'stroke-width': 1 }, svg);
  }

  /* ---------- donut ----------
     counts = [{ value, color, label }]
     opts   = { size, thickness, center, centerSub } */
  function donut(container, counts, opts) {
    const o = Object.assign({ size: 160, thickness: 20 }, opts || {});
    const size = o.size, r = (size - o.thickness) / 2, cx = size / 2, cy = size / 2;
    const total = (counts || []).reduce((s, c) => s + (c.value || 0), 0) || 1;
    container.innerHTML = '';
    const svg = el('svg', { viewBox: `0 0 ${size} ${size}`, width: size, height: size, class: 'cx-donut' }, container);
    const live = (counts || []).filter((c) => c.value > 0);
    if (live.length === 1) {
      // segment unique : un anneau complet (l'arc A ne se trace pas sur 360°)
      el('circle', { cx, cy, r, fill: 'none', stroke: live[0].color, 'stroke-width': o.thickness }, svg);
    } else {
      let a0 = -Math.PI / 2;
      live.forEach((c) => {
        const frac = c.value / total, a1 = a0 + frac * Math.PI * 2, large = frac > 0.5 ? 1 : 0;
        const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
        const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
        el('path', { d: `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`, fill: 'none', stroke: c.color, 'stroke-width': o.thickness, 'stroke-linecap': 'butt' }, svg);
        a0 = a1;
      });
    }
    if (o.center) txt(svg, cx, cy + 2, String(o.center), { 'text-anchor': 'middle', 'dominant-baseline': 'middle', fill: 'var(--ink)', 'font-size': 26, 'font-weight': 800 });
    if (o.centerSub) txt(svg, cx, cy + 20, String(o.centerSub), { 'text-anchor': 'middle', 'dominant-baseline': 'middle', 'font-size': 10 });
  }

  /* ---------- divergingArea : aire +/- autour de zéro ----------
     acc  = number[] (peut être négatif)
     opts = { xlabels, height, posLabel, negLabel, label } */
  function divergingArea(container, acc, opts) {
    const o = Object.assign({ height: 180, xlabels: [] }, opts || {});
    const W = width(container, 600), H = o.height;
    const padL = 30, padR = 12, padT = 16, padB = 22;
    const svg = svgIn(container, W, H, 'cx-diverge');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    const plotW = W - padL - padR, plotH = H - padT - padB;
    const data = (acc || []).map((v) => +v || 0);
    const maxAbs = Math.max(1e-6, ...data.map((v) => Math.abs(v)));
    const n = data.length;
    const zeroY = padT + plotH / 2;
    const xFor = (i) => padL + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
    const yFor = (v) => zeroY - (v / maxAbs) * (plotH / 2);
    // dégradé vertical vert(haut) -> rouge(bas) pour la zone d'aire
    const gid = 'cx-div-' + (++_uid);
    const defs = el('defs', null, svg);
    const grad = el('linearGradient', { id: gid, x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
    el('stop', { offset: '0%', 'stop-color': 'var(--buy, #34d399)', 'stop-opacity': 0.5 }, grad);
    el('stop', { offset: '50%', 'stop-color': 'var(--line)', 'stop-opacity': 0.05 }, grad);
    el('stop', { offset: '100%', 'stop-color': 'var(--pass, #f87171)', 'stop-opacity': 0.5 }, grad);
    if (n) {
      const pts = data.map((v, i) => [xFor(i), yFor(v)]);
      const d = smoothPath(pts);
      const areaD = d + ` L ${pts[pts.length - 1][0]},${zeroY} L ${pts[0][0]},${zeroY} Z`;
      el('path', { d: areaD, fill: `url(#${gid})`, stroke: 'none' }, svg);
      el('path', { d, fill: 'none', stroke: 'var(--ink)', 'stroke-opacity': 0.5, 'stroke-width': 1.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
    }
    // ligne zéro
    el('line', { x1: padL, y1: zeroY, x2: W - padR, y2: zeroY, stroke: 'var(--line)', 'stroke-width': 1 }, svg);
    if (o.posLabel) txt(svg, W - padR, padT + 4, o.posLabel, { 'text-anchor': 'end', fill: 'var(--buy, #34d399)' });
    if (o.negLabel) txt(svg, W - padR, H - 6, o.negLabel, { 'text-anchor': 'end', fill: 'var(--pass, #f87171)' });
    const xl = o.xlabels || [];
    if (xl.length) {
      const step = Math.max(1, Math.ceil(xl.length / 6));
      for (let i = 0; i < xl.length; i += step) txt(svg, xFor(i), H - 6, String(xl[i]), { 'text-anchor': 'middle' });
    }
  }

  window.ChartsX = { lineChart, scatter, histogram, donut, divergingArea };
})();
export {};
