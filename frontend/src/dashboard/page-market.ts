/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-market.js   (Market Signals)
   The "trading floor" multi-source view: velocity × level
   scatter, cross-source correlation matrix, anomaly detector
   and corroboration feed.
   ============================================================ */
export function mountMarket() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts, X = window.ChartsX, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic, clamp = Sh.clamp;

  const STR = {
    en: { title: 'Market Signals', sub: 'multi-source corroboration · anomalies',
      k_emerging: 'Emerging products', k_corro: 'Corroborated signals', k_anom: 'Anomalies flagged', k_sources: 'Score sources',
      scatter: 'Velocity × maturity', scatter_s: 'low maturity + high velocity = the Graal',
      matrix: 'Source correlation', matrix_s: 'z-score correlation across the catalogue',
      anom: 'Anomaly detector', anom_s: 'velocity spikes · |z| > 1.3', corroborated: 'corroborated', isolated: 'isolated',
      corro: 'Corroboration feed', corro_s: 'Trends and Reddit rising together', by: '×',
      maturity: 'Maturity', velocity: 'Velocity', empty: 'No anomalies in the current window.' },
    fr: { title: 'Signaux marché', sub: 'corroboration multi-sources · anomalies',
      k_emerging: 'Produits émergents', k_corro: 'Signaux corroborés', k_anom: 'Anomalies détectées', k_sources: 'Sources de score',
      scatter: 'Vélocité × maturité', scatter_s: 'maturité faible + vélocité forte = le Graal',
      matrix: 'Corrélation des sources', matrix_s: 'corrélation des z-scores sur le catalogue',
      anom: 'Détecteur d’anomalies', anom_s: 'pics de vélocité · |z| > 1,3', corroborated: 'corroboré', isolated: 'isolé',
      corro: 'Flux de corroboration', corro_s: 'Trends et Reddit montent ensemble', by: '×',
      maturity: 'Maturité', velocity: 'Vélocité', empty: 'Aucune anomalie sur la fenêtre actuelle.' },
  };
  const L = () => STR[Sh.lang];

  const SOURCES = [
    { k: 'trendsScore', l: 'Trends' }, { k: 'redditScore', l: 'Reddit' },
    { k: 'growthScore', l: Sh.lang === 'fr' ? 'CJ vél.' : 'CJ vel.' }, { k: 'organic', l: Sh.lang === 'fr' ? 'Potentiel' : 'Potential' },
    { k: 'mpct', l: Sh.lang === 'fr' ? 'Marge' : 'Margin' },
  ];
  function val(p, k) { return k === 'mpct' ? p.margin_pct * 100 : p[k]; }
  function pearson(a, b) {
    const n = a.length, ma = a.reduce((s, v) => s + v, 0) / n, mb = b.reduce((s, v) => s + v, 0) / n;
    let num = 0, da = 0, db = 0;
    for (let i = 0; i < n; i++) { const x = a[i] - ma, y = b[i] - mb; num += x * y; da += x * x; db += y * y; }
    return num / (Math.sqrt(da * db) || 1);
  }

  function render() {
    const s = L();
    const growths = P.map((p) => p.growth), mg = growths.reduce((a, b) => a + b, 0) / growths.length;
    const sd = Math.sqrt(growths.reduce((a, b) => a + (b - mg) ** 2, 0) / growths.length) || 1;
    const anomalies = P.map((p) => ({ p, z: (p.growth - mg) / sd })).filter((x) => Math.abs(x.z) > 1.3).sort((a, b) => Math.abs(b.z) - Math.abs(a.z));
    const corro = P.filter((p) => p.redditScore > 60 && p.trendsScore > 60).sort((a, b) => b.tandor - a.tandor);
    const emerging = P.filter((p) => p.phase === 'EMERGENT').length;

    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
      </div>
      <div class="kpi-mono-row rv">
        ${statTile('sparkles', s.k_emerging, emerging, 'var(--signal)')}
        ${statTile('check', s.k_corro, corro.length, 'var(--buy)')}
        ${statTile('zap', s.k_anom, anomalies.length, 'var(--amber)')}
        ${statTile('layers', s.k_sources, String(SOURCES.length), 'var(--azure)')}
      </div>
      <div class="section-row grid-21">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.scatter}</div><div class="sub">${s.scatter_s}</div></div></div>
          <div class="chart-box"><div id="scBox" style="width:100%;height:380px"></div></div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.matrix}</div><div class="sub">${s.matrix_s}</div></div></div>
          <div style="padding:14px 18px 18px" id="matrixBox"></div>
        </section>
      </div>
      <div class="section-row grid-2">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.anom}</div><div class="sub">${s.anom_s}</div></div></div>
          <div id="anomList"></div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.corro}</div><div class="sub">${s.corro_s}</div></div></div>
          <div id="corroList"></div>
        </section>
      </div>`;

    // scatter
    const pts = P.map((p) => ({
      x: p.maturity, y: p.momentum, r: 6 + p.gross / 2.6, color: `var(--${T.PHASES[p.phase].v})`, p,
      tip: `<div class="tip-h"><b>${p.name}</b><span class="tip-score">${p.tandor}</span></div><div class="tip-rows"><div><span>${s.velocity}</span><b>${p.momentum}</b></div><div><span>${s.maturity}</span><b>${p.maturity}</b></div></div>`,
    }));
    X.scatter($('#scBox'), pts, { xMax: 100, yMax: 100, xLabel: s.maturity, yLabel: s.velocity, height: 380, onPoint: (pt) => Sh.openProduct(pt.p) });

    renderMatrix();

    // anomalies
    $('#anomList').innerHTML = anomalies.length ? anomalies.slice(0, 7).map((a) => {
      const corr = a.p.redditScore > 60 && a.p.trendsScore > 60;
      const up = a.z >= 0;
      return `<div class="anom-row" data-id="${a.p.id}">
        <span class="anom-z" style="color:${up ? 'var(--buy)' : 'var(--pass)'}">${up ? '+' : ''}${a.z.toFixed(1)}σ</span>
        <div class="cell-prod">${Sh.thumb(a.p, 30)}<div><div class="cp-name">${a.p.name}</div><div class="cp-sub">${T.CATS[a.p.cat][Sh.lang]}</div></div></div>
        <span class="badge phase-badge"><span class="pdot" style="background:var(--${T.PHASES[a.p.phase].v})"></span>${T.PHASES[a.p.phase][Sh.lang]}</span>
        <span class="corro-badge ${corr ? 'ok' : 'iso'}">${corr ? s.corroborated : s.isolated}</span></div>`;
    }).join('') : `<div class="empty"><div class="e-art">${ic('signal')}</div><div class="e-s">${s.empty}</div></div>`;
    $$('#anomList .anom-row').forEach((r) => r.addEventListener('click', () => Sh.openProduct(P.find((p) => p.id === r.dataset.id))));

    // corroboration
    $('#corroList').innerHTML = corro.slice(0, 7).map((p) => {
      const n = [p.trendsScore > 60, p.redditScore > 60, p.growthScore > 60].filter(Boolean).length;
      const up = p.growth >= 0;
      // REAL demand signal when present: AliExpress units sold.
      const soldVal = (p.aliExpressSold != null && p.aliExpressSold > 0)
        ? `<span class="cp-sub mono" style="font-size:10.5px">${Sh.fmt(p.aliExpressSold)} ${Sh.lang === 'fr' ? 'vendus' : 'sold'}</span>` : '';
      return `<div class="anom-row" data-id="${p.id}" style="grid-template-columns:auto 1fr auto auto">
        <span class="feed-score" style="width:34px;height:34px">${C.ring(p.tandor, `var(--${T.PHASES[p.phase].v})`, 34, 3)}<b style="position:absolute;inset:0;display:grid;place-items:center;font-family:var(--font-mono);font-weight:600;font-size:11px">${p.tandor}</b></span>
        <div class="cell-prod">${Sh.thumb(p, 30)}<div><div class="cp-name">${p.name}</div><div class="cp-sub">${T.CATS[p.cat][Sh.lang]}</div>${soldVal}</div></div>
        <span class="feed-growth ${up ? 'up' : 'down'} mono">${up ? '+' : ''}${Math.round(p.growth * 100)}%</span>
        <span class="corro-badge ok">${s.corroborated} ${s.by}${n}</span></div>`;
    }).join('');
    $$('#corroList .anom-row').forEach((r) => r.addEventListener('click', () => Sh.openProduct(P.find((p) => p.id === r.dataset.id))));
  }

  function statTile(icn, label, val, col) {
    return `<div class="stat-tile">
      <div class="st-l"><span class="st-ico" style="background:color-mix(in oklab, ${col} 14%, var(--surface-1));color:${col}">${ic(icn)}</span><span class="micro">${label}</span></div>
      <div class="st-v">${val}</div></div>`;
  }

  function renderMatrix() {
    const cols = SOURCES.map((s) => P.map((p) => val(p, s.k)));
    const n = SOURCES.length;
    let html = `<div class="corr-matrix" style="grid-template-columns:64px repeat(${n}, 1fr)">`;
    html += `<div></div>` + SOURCES.map((s) => `<div class="micro" style="text-align:center;align-self:center">${s.l}</div>`).join('');
    SOURCES.forEach((rs, ri) => {
      html += `<div class="micro" style="align-self:center">${rs.l}</div>`;
      SOURCES.forEach((cs, ci) => {
        const r = ri === ci ? 1 : pearson(cols[ri], cols[ci]);
        const t = clamp(r, -1, 1);
        let fill;
        if (t >= 0) fill = `color-mix(in oklab, var(--signal) ${Math.round(12 + t * 70)}%, var(--surface-1))`;
        else fill = `color-mix(in oklab, var(--amber) ${Math.round(12 + (-t) * 60)}%, var(--surface-1))`;
        const txtCol = Math.abs(t) > 0.62 ? '#fff' : 'var(--text-secondary)';
        html += `<div class="corr-cell" style="background:${fill};color:${txtCol}" title="${rs.l} × ${cs.l}: ${r.toFixed(2)}">${ri === ci ? '·' : r.toFixed(2)}</div>`;
      });
    });
    html += `</div>`;
    $('#matrixBox').innerHTML = html;
  }

  Sh.start({ active: 'n_market', render });
}
