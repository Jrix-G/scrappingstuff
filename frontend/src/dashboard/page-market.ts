/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-market.js   (Market Signals)
   HONNÊTETÉ : cette vue n'affiche que des agrégats RÉELS calculés
   à partir de T.PRODUCTS (catégories, phases, marges) et le signal
   de demande réel mesuré (Amazon « bought/mo » ou AliExpress unités
   vendues). Aucune anomalie sur `growth` (non mesuré → null partout),
   aucune corrélation de sources (trendsScore = placeholder, reddit
   non mesuré) ni flux « Trends × Reddit » fabriqué.
   ============================================================ */
export function mountMarket() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts, X = window.ChartsX, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic;

  const STR = {
    en: { title: 'Market Signals', sub: 'real catalogue aggregates · measured demand only',
      k_total: 'Products tracked', k_cats: 'Categories covered', k_margin: 'Median gross margin', k_demand: 'With real demand signal',
      cat: 'Category distribution', cat_s: 'real product counts per category',
      phase: 'Lifecycle phase', phase_s: 'real phase mix across the catalogue',
      margin: 'Gross margin by category', margin_s: 'average (retail − cost) / retail · real',
      demand: 'Real demand leaders', demand_s: 'measured units — Amazon bought/mo or AliExpress sold',
      empty_demand: 'No measured demand signal in the catalogue yet — we never fabricate units.',
      amz: 'bought/mo', ali: 'sold', none: '—', avg: 'avg', count: '' },
    fr: { title: 'Signaux marché', sub: 'agrégats réels du catalogue · demande mesurée uniquement',
      k_total: 'Produits suivis', k_cats: 'Catégories couvertes', k_margin: 'Marge brute médiane', k_demand: 'Avec signal de demande réel',
      cat: 'Répartition par catégorie', cat_s: 'effectifs réels par catégorie',
      phase: 'Phase de cycle de vie', phase_s: 'répartition réelle des phases du catalogue',
      margin: 'Marge brute par catégorie', margin_s: 'moyenne (prix − coût) / prix · réel',
      demand: 'Leaders de demande réelle', demand_s: 'unités mesurées — Amazon achetés/mois ou AliExpress vendus',
      empty_demand: 'Aucun signal de demande mesuré dans le catalogue — nous ne fabriquons jamais d’unités.',
      amz: 'achetés/mois', ali: 'vendus', none: '—', avg: 'moy.', count: '' },
  };
  const L = () => STR[Sh.lang];

  function median(arr) {
    if (!arr.length) return null;
    const a = arr.slice().sort((x, y) => x - y), m = Math.floor(a.length / 2);
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
  }
  // Signal de demande RÉEL : Amazon « bought/mo » prioritaire, sinon AliExpress vendus.
  function demandOf(p) {
    if (p.amazonBought != null && p.amazonBought > 0) return { units: p.amazonBought, label: L().amz };
    if (p.aliExpressSold != null && p.aliExpressSold > 0) return { units: p.aliExpressSold, label: L().ali };
    return null;
  }
  const catColor = (cat) => `hsl(${T.CAT_HUE[cat] || 210} 58% 56%)`;

  function render() {
    const s = L();
    // --- agrégats réels ---
    const byCat = {}; P.forEach((p) => { (byCat[p.cat] = byCat[p.cat] || []).push(p); });
    const cats = Object.keys(byCat).sort((a, b) => byCat[b].length - byCat[a].length);
    const byPhase = {}; P.forEach((p) => { byPhase[p.phase] = (byPhase[p.phase] || 0) + 1; });
    const phases = Object.keys(byPhase).sort((a, b) => byPhase[b] - byPhase[a]);
    const medMargin = median(P.map((p) => p.margin_pct).filter((v) => v != null));
    const withDemand = P.filter((p) => demandOf(p));
    const demandLeaders = withDemand.slice().sort((a, b) => demandOf(b).units - demandOf(a).units).slice(0, 8);

    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
      </div>
      <div class="kpi-mono-row rv">
        ${statTile('layers', s.k_total, Sh.fmt(P.length), 'var(--signal)')}
        ${statTile('grid', s.k_cats, String(cats.length), 'var(--azure)')}
        ${statTile('coins', s.k_margin, medMargin == null ? s.none : Math.round(medMargin * 100) + '%', 'var(--buy)')}
        ${statTile('activity', s.k_demand, `${withDemand.length} / ${P.length}`, 'var(--amber)')}
      </div>
      <div class="section-row grid-21">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.cat}</div><div class="sub">${s.cat_s}</div></div></div>
          <div style="display:flex;align-items:center;gap:22px;padding:16px 18px;flex-wrap:wrap">
            <div id="catDonut" style="flex:none"></div>
            <div class="legend" style="flex-direction:column;align-items:stretch;gap:9px;flex:1;min-width:160px" id="catLegend"></div>
          </div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.phase}</div><div class="sub">${s.phase_s}</div></div></div>
          <div id="phaseList"></div>
        </section>
      </div>
      <div class="section-row grid-2">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.margin}</div><div class="sub">${s.margin_s}</div></div></div>
          <div id="marginList"></div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.demand}</div><div class="sub">${s.demand_s}</div></div></div>
          <div id="demandList"></div>
        </section>
      </div>`;

    // --- répartition catégorie : donut + légende (effectifs réels) ---
    X.donut($('#catDonut'), cats.map((c) => ({ value: byCat[c].length, color: catColor(c), label: c })),
      { size: 148, thickness: 22, center: P.length, centerSub: Sh.lang === 'fr' ? 'produits' : 'products' });
    $('#catLegend').innerHTML = cats.map((c) => `
      <div class="legend-item" style="justify-content:space-between;cursor:default">
        <span style="display:inline-flex;align-items:center;gap:7px"><span class="ldot" style="background:${catColor(c)}"></span>${T.CATS[c][Sh.lang]}</span>
        <b class="mono">${byCat[c].length}</b></div>`).join('');

    // --- répartition phase : barres réelles ---
    const maxPh = Math.max(...phases.map((p) => byPhase[p]), 1);
    $('#phaseList').innerHTML = phases.map((ph) => `
      <div class="sub-row">
        <div><div class="sub-name"><span class="pdot" style="width:10px;height:10px;border-radius:3px;background:var(--${T.PHASES[ph].v})"></span>${T.PHASES[ph][Sh.lang]}</div>
          <div class="sub-bar"><i style="width:${Math.round(byPhase[ph] / maxPh * 100)}%;background:var(--${T.PHASES[ph].v})"></i></div></div>
        <div class="sub-val">${byPhase[ph]}</div></div>`).join('');

    // --- marge brute moyenne par catégorie (réel) ---
    const catMargin = cats.map((c) => {
      const ms = byCat[c].map((p) => p.margin_pct).filter((v) => v != null);
      return { c, m: ms.length ? ms.reduce((a, b) => a + b, 0) / ms.length : 0 };
    }).sort((a, b) => b.m - a.m);
    const maxM = Math.max(...catMargin.map((x) => x.m), 0.01);
    $('#marginList').innerHTML = catMargin.map((x) => `
      <div class="sub-row">
        <div><div class="sub-name"><span class="ldot" style="background:${catColor(x.c)}"></span>${T.CATS[x.c][Sh.lang]}</div>
          <div class="sub-bar"><i style="width:${Math.round(x.m / maxM * 100)}%;background:${catColor(x.c)}"></i></div></div>
        <div class="sub-val">${Math.round(x.m * 100)}%</div></div>`).join('');

    // --- leaders de demande réelle (unités mesurées) — empty-state si aucun ---
    if (!demandLeaders.length) {
      $('#demandList').innerHTML = `<div class="empty"><div class="e-art">${ic('activity')}</div><div class="e-s">${s.empty_demand}</div></div>`;
    } else {
      $('#demandList').innerHTML = demandLeaders.map((p) => {
        const d = demandOf(p);
        return `<div class="anom-row" data-id="${p.id}" style="grid-template-columns:1fr auto">
          <div class="cell-prod">${Sh.thumb(p, 30)}<div><div class="cp-name">${p.name}</div><div class="cp-sub">${T.CATS[p.cat][Sh.lang]}</div></div></div>
          <span class="sub-val">${Sh.fmt(d.units)} <span class="cp-sub" style="font-size:10.5px">${d.label}</span></span></div>`;
      }).join('');
      $$('#demandList .anom-row').forEach((r) => r.addEventListener('click', () => Sh.openProduct(P.find((p) => p.id === r.dataset.id))));
    }
  }

  function statTile(icn, label, val, col) {
    return `<div class="stat-tile">
      <div class="st-l"><span class="st-ico" style="background:color-mix(in oklab, ${col} 14%, var(--surface-1));color:${col}">${ic(icn)}</span><span class="micro">${label}</span></div>
      <div class="st-v">${val}</div></div>`;
  }

  Sh.start({ active: 'n_market', render });
}
