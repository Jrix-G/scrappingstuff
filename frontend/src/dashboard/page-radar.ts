/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-radar.js   (Opportunity Radar)
   Full-bleed opportunity matrix (momentum × maturity, size =
   margin, colour = phase, halo = confidence). Select a bubble →
   inline decision panel; open the full dossier from there.
   ============================================================ */
export function mountRadar() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic, clamp = Sh.clamp;
  const money = Sh.money, pct = Sh.pct;

  const STR = {
    en: { title: 'Opportunity Radar', sub: 'momentum × maturity · the hedge-fund view',
      all: 'All markets', filter_cat: 'Category', allcat: 'All categories',
      q_emerg: 'Emergent · high potential', q_growth: 'Growing', q_sat: 'Saturated', q_avoid: 'Avoid',
      select: 'Select a product', select_s: 'Click any bubble on the matrix to open its decision panel — verdict, economics and the signals behind the score.',
      opportunity: 'Opportunity', risk: 'Risk', conf: 'Confidence', open: 'Open full dossier',
      momentum: 'Momentum', maturity: 'Maturity', margin: 'Net margin', velocity: 'Velocity',
      legend_size: 'Bubble size = gross margin', legend_halo: 'Halo = prediction confidence',
      high: 'High', med: 'Medium', low: 'Low', phase: 'Phase', verdict: 'Verdict' },
    fr: { title: 'Opportunity Radar', sub: 'momentum × maturité · la vue hedge fund',
      all: 'Tous les marchés', filter_cat: 'Catégorie', allcat: 'Toutes catégories',
      q_emerg: 'Émergent · fort potentiel', q_growth: 'En croissance', q_sat: 'Saturé', q_avoid: 'À éviter',
      select: 'Sélectionnez un produit', select_s: 'Cliquez sur une bulle de la matrice pour ouvrir son panneau de décision — verdict, économie et les signaux derrière le score.',
      opportunity: 'Opportunité', risk: 'Risque', conf: 'Confiance', open: 'Ouvrir le dossier complet',
      momentum: 'Momentum', maturity: 'Maturité', margin: 'Marge nette', velocity: 'Vélocité',
      legend_size: 'Taille de bulle = marge brute', legend_halo: 'Halo = confiance de prédiction',
      high: 'Élevée', med: 'Moyenne', low: 'Faible', phase: 'Phase', verdict: 'Verdict' },
  };
  const L = () => STR[Sh.lang];

  let selectedId = null, catFilter = 'all';

  function pool() { return catFilter === 'all' ? P : P.filter((p) => p.cat === catFilter); }

  function render() {
    const s = L(), cats = Object.keys(T.CATS).filter((c) => P.some((p) => p.cat === c));
    if (!selectedId) selectedId = P.slice().sort((a, b) => b.tandor - a.tandor)[0].id;
    const arr = pool();
    // quadrant counts (top-left target = maturity<50 & momentum>50)
    const q = { emerg: 0, growth: 0, sat: 0, avoid: 0 };
    arr.forEach((p) => { const lowMat = p.maturity < 50, hiMom = p.momentum >= 50; if (lowMat && hiMom) q.emerg++; else if (!lowMat && hiMom) q.growth++; else if (!lowMat && !hiMom) q.sat++; else q.avoid++; });

    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
        <div class="sel-wrap"><select class="sel" id="catSel">
          <option value="all">${s.allcat}</option>
          ${cats.map((c) => `<option value="${c}" ${c === catFilter ? 'selected' : ''}>${T.CATS[c][Sh.lang]}</option>`).join('')}
        </select></div>
      </div>
      <div class="section-row grid-21">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.momentum} × ${s.maturity}</div><div class="sub">${arr.length} ${Sh.lang === 'fr' ? 'produits suivis' : 'tracked products'}</div></div></div>
          <div style="padding:0 18px;display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--text-tertiary)"><span>${s.legend_size}</span><span style="opacity:.5">·</span><span>${s.legend_halo}</span></div>
          <div class="chart-box"><div class="radar-page-box" id="radarBox"></div></div>
          <div class="rd-quad-legend" style="margin:0 16px 16px">
            <div class="rd-quad target"><div class="q-n mono">${q.emerg}</div><div class="q-l">${s.q_emerg}</div></div>
            <div class="rd-quad"><div class="q-n mono">${q.growth}</div><div class="q-l">${s.q_growth}</div></div>
            <div class="rd-quad"><div class="q-n mono">${q.avoid}</div><div class="q-l">${s.q_avoid}</div></div>
            <div class="rd-quad"><div class="q-n mono">${q.sat}</div><div class="q-l">${s.q_sat}</div></div>
          </div>
        </section>
        <aside class="radar-detail rv"><section class="panel" id="rdPanel"></section></aside>
      </div>`;

    $('#catSel').addEventListener('change', (e) => { catFilter = e.target.value; selectedId = pool()[0] ? pool().slice().sort((a, b) => b.tandor - a.tandor)[0].id : null; render(); });

    renderRadarBox($('#radarBox'), arr, (p) => { selectedId = p.id; renderDetail(); highlightSel(); });
    renderDetail();
    requestAnimationFrame(highlightSel);
  }

  function highlightSel() {
    $$('#radarBox .radar-bub').forEach((g) => {
      const on = g.dataset.id === selectedId;
      g.style.outline = '';
      const dot = g.querySelector('circle:last-of-type');
      if (dot) dot.setAttribute('stroke-width', on ? 2.6 : 1.5);
      if (on) { const c = g.querySelector('circle:last-of-type'); if (c) c.setAttribute('fill-opacity', '.95'); }
    });
  }

  function renderDetail() {
    const s = L();
    const p = pool().find((x) => x.id === selectedId) || pool()[0];
    if (!p) { $('#rdPanel').innerHTML = `<div class="rd-empty"><div class="e-art" style="margin:0 auto 16px">${ic('radar')}</div><div class="e-t">${s.select}</div><div class="e-s">${s.select_s}</div></div>`; return; }
    selectedId = p.id;
    const ph = T.PHASES[p.phase], col = `var(--${ph.v})`;
    const ringCol = p.trapVerdict === 'VIABLE' ? col : p.trapVerdict === 'RISKY' ? 'var(--watch)' : 'var(--pass)';
    const tm = T.trapMeta(p, Sh.lang);
    const up = (p.growth || 0) >= 0;
    const gTxt = p.hasGrowth ? `${up ? '+' : ''}${Math.round(p.growth * 100)}%` : (Sh.lang === 'fr' ? 'n.d.' : 'n/a');
    const opp = p.tandor >= 78 ? s.high : p.tandor >= 60 ? s.med : s.low;
    const riskLbl = p.risk === 'low' ? T.STR[Sh.lang].risk_low : p.risk === 'mod' ? T.STR[Sh.lang].risk_mod : T.STR[Sh.lang].risk_high;
    // Jauges : la valeur peut être null (non mesuré) -> rendu « non mesuré », pas un faux 0.
    const gauges = [[s.velocity, p.growthScore, 'var(--signal)'], [s.margin, Math.round(p.margin_pct * 100), 'var(--buy)'], ['Reddit', p.redditScore, 'var(--reddit)'], ['Trends', p.trendsScore, 'var(--azure)']];
    $('#rdPanel').innerHTML = `
      <div class="rd-hero">
        ${Sh.thumb(p, 48)}
        <div style="flex:1;min-width:0">
          <div style="font-size:14.5px;font-weight:700;letter-spacing:-.01em">${p.name}</div>
          <div class="mono" style="font-size:11px;color:var(--text-tertiary);margin-top:2px">${T.CATS[p.cat][Sh.lang]} · ${p.id}</div>
        </div>
        <div class="pd-ring">${C.ring(p.tandor, ringCol, 76, 6, p.confidence)}<b>${p.tandor}</b></div>
      </div>
      <div style="padding:14px 18px;display:flex;flex-direction:column;gap:9px">
        <div class="pd-fact" style="display:flex;justify-content:space-between;font-size:12.5px"><span style="color:var(--text-tertiary)">${s.opportunity}</span><b style="color:${ringCol}">${opp} ${up ? '▲' : '▼'}</b></div>
        <div class="pd-fact" style="display:flex;justify-content:space-between;font-size:12.5px"><span style="color:var(--text-tertiary)">${s.verdict}</span><span><span class="verdict ${tm.v}">${tm.label}</span>${tm.coverage ? `<span class="mono" style="margin-left:6px;font-size:10px;color:var(--text-tertiary)">· ${tm.coverage}</span>` : ''}</span></div>
        <div class="pd-fact" style="display:flex;justify-content:space-between;font-size:12.5px"><span style="color:var(--text-tertiary)">${s.phase}</span><span class="badge phase-badge"><span class="pdot" style="background:${col}"></span>${ph[Sh.lang]}</span></div>
        <div class="pd-fact" style="display:flex;justify-content:space-between;font-size:12.5px"><span style="color:var(--text-tertiary)">${s.risk}</span><b class="risk ${p.risk}" style="white-space:nowrap"><span class="rdot"></span>${riskLbl}</b></div>
        <div class="pd-fact" style="display:flex;justify-content:space-between;font-size:12.5px"><span style="color:var(--text-tertiary)">${s.conf}</span><b class="mono">${pct(p.confidence * 100)}</b></div>
      </div>
      <div style="padding:0 18px 6px">
        <div class="pd-econ" style="grid-template-columns:1fr 1fr">
          <div class="pd-econ-tile"><span class="micro">${s.margin}</span><b class="mono">${money(p.net, 1)}</b></div>
          <div class="pd-econ-tile"><span class="micro">${s.velocity}</span><b class="mono" style="color:${up ? 'var(--buy)' : 'var(--pass)'}">${gTxt}</b></div>
          ${(p.aliExpressSold != null && p.aliExpressSold > 0) ? `<div class="pd-econ-tile"><span class="micro">${Sh.lang === 'fr' ? 'Vendus (AliExpress)' : 'Sold (AliExpress)'}</span><b class="mono">${Sh.fmt(p.aliExpressSold)}</b></div>` : ''}
          ${(p.salesScore != null) ? `<div class="pd-econ-tile"><span class="micro">${Sh.lang === 'fr' ? 'Score demande' : 'Demand score'}</span><b class="mono">${Math.round(p.salesScore)}</b></div>` : ''}
        </div>
      </div>
      <div style="padding:14px 18px 4px">${gauges.map(([k, v, c]) => (v == null || Number.isNaN(v))
        ? `<div class="pd-gauge"><span class="pd-g-l">${k}</span><span class="pd-g-v mono" style="color:var(--text-tertiary);margin-left:auto">${Sh.lang === 'fr' ? 'non mesuré' : 'n/a'}</span></div>`
        : `<div class="pd-gauge"><span class="pd-g-l">${k}</span>${C.microGauge(v, c)}<span class="pd-g-v mono">${Math.round(v)}</span></div>`).join('')}</div>
      <div style="padding:8px 18px 6px"><p style="font-size:12px;color:var(--text-secondary);line-height:1.55">${p.reason[Sh.lang]}</p></div>
      <div style="padding:12px 18px 16px"><button class="btn-pri" style="width:100%" id="rdOpen">${ic('eye')}${s.open}</button></div>`;
    $('#rdOpen').addEventListener('click', () => Sh.openProduct(p));
  }

  /* ============================================================
     Radar matrix — rendu LOCAL (page-radar). Bulles positionnées
     par maturity (x) × momentum (y), TAILLE = marge brute (p.gross),
     halo = confiance réelle (p.confidence). Données = T.PRODUCTS.
     ------------------------------------------------------------
     Correctif lisibilité : l'ancienne échelle (rayon 6→18px, halo
     +4px) produisait des bulles géantes qui se chevauchaient. Ici
     rayon 4→14px avec mise à l'échelle √(marge) pour limiter les
     écarts, halo discret (+3px max) atténué quand la confiance est
     faible — on n'invente aucun signal.
     ============================================================ */
  const SVGNS = 'http://www.w3.org/2000/svg';
  function svgEl(tag, attrs, parent) {
    const e = document.createElementNS(SVGNS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  const R_MIN = 4, R_MAX = 14; // rayon lisible, non chevauchant

  function radarTip(p) {
    const s = L();
    const marginLbl = Sh.lang === 'fr' ? 'Marge brute' : 'Gross margin';
    return `<div class="tip-h"><b>${p.name}</b><span class="tip-score">${p.tandor}</span></div>
      <div class="tip-rows">
        <div><span>${s.momentum}</span><b>${Math.round(p.momentum)}</b></div>
        <div><span>${s.maturity}</span><b>${Math.round(p.maturity)}</b></div>
        <div><span>${marginLbl}</span><b>+${(p.gross || 0).toFixed(0)}€</b></div>
        <div><span>${s.conf}</span><b>${Math.round((p.confidence || 0) * 100)}%</b></div>
      </div>`;
  }

  function renderRadarBox(box, arr, onSelect) {
    const s = L();
    box.innerHTML = '';
    // Empty-state honnête : aucun produit pour ce filtre.
    if (!arr || !arr.length) {
      box.innerHTML = `<div class="rd-empty" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;text-align:center;padding:24px">
        <div class="e-art" style="margin:0 auto 14px">${ic('radar')}</div>
        <div class="e-t">${Sh.lang === 'fr' ? 'Aucun produit à afficher' : 'No product to display'}</div>
        <div class="e-s">${Sh.lang === 'fr' ? 'Aucun signal pour ce filtre.' : 'No signal for this filter.'}</div></div>`;
      return;
    }
    const W = box.clientWidth || 360, H = box.clientHeight || 420;
    const m = { t: 14, r: 14, b: 26, l: 30 };
    const pw = W - m.l - m.r, ph = H - m.t - m.b;
    const x = (v) => m.l + (clamp(v, 0, 100) / 100) * pw;
    const y = (v) => m.t + (1 - clamp(v, 0, 100) / 100) * ph;

    const root = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, class: 'radar-svg', width: W, height: H }, box);

    // target quadrant tint (haut-gauche = faible maturité, fort momentum)
    svgEl('rect', { x: m.l, y: m.t, width: pw / 2, height: ph / 2, fill: 'var(--signal)', 'fill-opacity': '.06', rx: 6 }, root);
    // grille
    [25, 50, 75].forEach((g) => {
      svgEl('line', { x1: x(g), y1: m.t, x2: x(g), y2: m.t + ph, stroke: 'var(--border-subtle)', 'stroke-width': 1 }, root);
      svgEl('line', { x1: m.l, y1: y(g), x2: m.l + pw, y2: y(g), stroke: 'var(--border-subtle)', 'stroke-width': 1 }, root);
    });
    // croix médiane
    svgEl('line', { x1: x(50), y1: m.t, x2: x(50), y2: m.t + ph, stroke: 'var(--border-strong)', 'stroke-width': 1, 'stroke-dasharray': '3 3' }, root);
    svgEl('line', { x1: m.l, y1: y(50), x2: m.l + pw, y2: y(50), stroke: 'var(--border-strong)', 'stroke-width': 1, 'stroke-dasharray': '3 3' }, root);
    // labels de quadrant
    const qlab = (tx, ty, text, strong) => { const t = svgEl('text', { x: tx, y: ty, class: 'radar-q' + (strong ? ' strong' : ''), 'text-anchor': 'middle' }, root); t.textContent = text; };
    qlab(m.l + pw * 0.25, m.t + 12, s.q_emerg, true);
    qlab(m.l + pw * 0.75, m.t + 12, s.q_growth);
    qlab(m.l + pw * 0.75, m.t + ph - 6, s.q_sat);
    qlab(m.l + pw * 0.25, m.t + ph - 6, s.q_avoid);
    // axes
    const ax = svgEl('text', { x: m.l + pw / 2, y: H - 6, class: 'radar-axis', 'text-anchor': 'middle' }, root); ax.textContent = s.maturity + ' →';
    const ay = svgEl('text', { x: 9, y: m.t + ph / 2, class: 'radar-axis', 'text-anchor': 'middle', transform: `rotate(-90 9 ${m.t + ph / 2})` }, root); ay.textContent = s.momentum + ' →';

    // bulles — 20 meilleurs par score, taille = marge brute, halo = confiance
    const top = arr.slice().sort((a, b) => b.tandor - a.tandor).slice(0, 20);
    const maxMargin = Math.max(1, ...top.map((p) => p.gross || 0));
    top.forEach((p, i) => {
      const cx = x(p.maturity), cy = y(p.momentum);
      // √-échelle : conserve « taille = marge » mais resserre l'écart min/max.
      const frac = Math.sqrt(Math.max(0, p.gross || 0) / maxMargin);
      const r = R_MIN + frac * (R_MAX - R_MIN);
      const conf = clamp(p.confidence || 0, 0, 1);
      const col = `var(--${T.PHASES[p.phase].v})`;
      const g = svgEl('g', { class: 'radar-bub', 'data-id': p.id, style: `--d:${i * 35}ms` }, root);
      g.style.cursor = 'pointer';
      // halo = confiance (discret quand la confiance est faible)
      svgEl('circle', { cx, cy, r: r + 3 * conf, fill: col, 'fill-opacity': (0.07 + 0.10 * conf).toFixed(2) }, g);
      const dot = svgEl('circle', { cx, cy, r, fill: col, 'fill-opacity': '.7', stroke: col, 'stroke-width': 1.5 }, g);
      g.addEventListener('mouseenter', (e) => { dot.setAttribute('fill-opacity', '.95'); window.Tip && window.Tip.show(radarTip(p), e); });
      g.addEventListener('mousemove', (e) => window.Tip && window.Tip.move(e));
      g.addEventListener('mouseleave', () => { dot.setAttribute('fill-opacity', '.7'); window.Tip && window.Tip.hide(); });
      g.addEventListener('click', () => onSelect && onSelect(p));
    });
  }

  Sh.start({ active: 'n_radar', render });
}
