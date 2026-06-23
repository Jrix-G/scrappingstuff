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

    C.renderRadar($('#radarBox'), arr, { lang: Sh.lang, onSelect: (p) => { selectedId = p.id; renderDetail(); highlightSel(); } });
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
    const ringCol = p.verdict === 'BUY' ? col : p.verdict === 'WATCH' ? 'var(--watch)' : 'var(--pass)';
    const up = p.growth >= 0;
    const opp = p.tandor >= 78 ? s.high : p.tandor >= 60 ? s.med : s.low;
    const riskLbl = p.risk === 'low' ? T.STR[Sh.lang].risk_low : p.risk === 'mod' ? T.STR[Sh.lang].risk_mod : T.STR[Sh.lang].risk_high;
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
        <div class="pd-fact" style="display:flex;justify-content:space-between;font-size:12.5px"><span style="color:var(--text-tertiary)">${s.verdict}</span><span class="verdict ${T.VERDICTS[p.verdict].v}">${T.VERDICTS[p.verdict][Sh.lang]}</span></div>
        <div class="pd-fact" style="display:flex;justify-content:space-between;font-size:12.5px"><span style="color:var(--text-tertiary)">${s.phase}</span><span class="badge phase-badge"><span class="pdot" style="background:${col}"></span>${ph[Sh.lang]}</span></div>
        <div class="pd-fact" style="display:flex;justify-content:space-between;font-size:12.5px"><span style="color:var(--text-tertiary)">${s.risk}</span><b class="risk ${p.risk}" style="white-space:nowrap"><span class="rdot"></span>${riskLbl}</b></div>
        <div class="pd-fact" style="display:flex;justify-content:space-between;font-size:12.5px"><span style="color:var(--text-tertiary)">${s.conf}</span><b class="mono">${pct(p.confidence * 100)}</b></div>
      </div>
      <div style="padding:0 18px 6px">
        <div class="pd-econ" style="grid-template-columns:1fr 1fr">
          <div class="pd-econ-tile"><span class="micro">${s.margin}</span><b class="mono">${money(p.net, 1)}</b></div>
          <div class="pd-econ-tile"><span class="micro">${s.velocity}</span><b class="mono" style="color:${up ? 'var(--buy)' : 'var(--pass)'}">${up ? '+' : ''}${Math.round(p.growth * 100)}%</b></div>
          ${(p.aliExpressSold != null && p.aliExpressSold > 0) ? `<div class="pd-econ-tile"><span class="micro">${Sh.lang === 'fr' ? 'Vendus (AliExpress)' : 'Sold (AliExpress)'}</span><b class="mono">${Sh.fmt(p.aliExpressSold)}</b></div>` : ''}
          ${(p.salesScore != null) ? `<div class="pd-econ-tile"><span class="micro">${Sh.lang === 'fr' ? 'Score demande' : 'Demand score'}</span><b class="mono">${Math.round(p.salesScore)}</b></div>` : ''}
        </div>
      </div>
      <div style="padding:14px 18px 4px">${gauges.map(([k, v, c]) => `<div class="pd-gauge"><span class="pd-g-l">${k}</span>${C.microGauge(v, c)}<span class="pd-g-v mono">${Math.round(v)}</span></div>`).join('')}</div>
      <div style="padding:8px 18px 6px"><p style="font-size:12px;color:var(--text-secondary);line-height:1.55">${p.reason[Sh.lang]}</p></div>
      <div style="padding:12px 18px 16px"><button class="btn-pri" style="width:100%" id="rdOpen">${ic('eye')}${s.open}</button></div>`;
    $('#rdOpen').addEventListener('click', () => Sh.openProduct(p));
  }

  Sh.start({ active: 'n_radar', render });
}
