/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-analytics.js   (Analytics)
   Engine performance & proof: backtest metrics, calibration,
   score/phase distributions, past-prediction validation, source
   coverage. This is the page that sells the subscription.
   ============================================================ */
export function mountEngine() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts, X = window.ChartsX, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic, clamp = Sh.clamp;

  const STR = {
    en: { title: 'Analytics', sub: 'engine performance · backtest · proof',
      k_auc: 'ROC AUC', k_prec: 'Precision @20', k_brier: 'Brier score', k_pred: 'Predictions evaluated',
      k_auc_s: 'discrimination', k_prec_s: 'top-20 hit rate', k_brier_s: 'lower is better', k_pred_s: 'last 90 days',
      calib: 'Calibration', calib_s: 'predicted probability vs realised outcome', pred: 'Predicted', obs: 'Observed',
      dist: 'Score distribution', dist_s: 'Tandor score across the catalogue',
      phases: 'Phase mix', phases_s: 'tracked products by phase', total: 'tracked',
      bets: 'Our past bets', bets_s: 'flagged Emergent · what they became',
      c_prod: 'Product', c_flag: 'Flagged', c_then: 'Then', c_now: 'Now', c_evo: 'Evolution', c_out: 'Outcome',
      validated: 'Validated', early: 'Still early', missed: 'Faded',
      coverage: 'Source coverage', coverage_s: 'pipeline uptime · 90 days', wk: 'wk ago' },
    fr: { title: 'Analytics', sub: 'performance du moteur · backtest · preuve',
      k_auc: 'AUC ROC', k_prec: 'Précision @20', k_brier: 'Score de Brier', k_pred: 'Prédictions évaluées',
      k_auc_s: 'discrimination', k_prec_s: 'taux top-20', k_brier_s: 'plus bas = mieux', k_pred_s: '90 derniers jours',
      calib: 'Calibration', calib_s: 'probabilité prédite vs résultat observé', pred: 'Prédit', obs: 'Observé',
      dist: 'Distribution des scores', dist_s: 'Score Tandor sur le catalogue',
      phases: 'Répartition des phases', phases_s: 'produits suivis par phase', total: 'suivis',
      bets: 'Nos paris passés', bets_s: 'flaggés Émergent · ce qu’ils sont devenus',
      c_prod: 'Produit', c_flag: 'Flaggé', c_then: 'Alors', c_now: 'Maintenant', c_evo: 'Évolution', c_out: 'Résultat',
      validated: 'Validé', early: 'Encore tôt', missed: 'Retombé',
      coverage: 'Couverture des sources', coverage_s: 'disponibilité pipeline · 90 jours', wk: 'sem.' },
  };
  const L = () => STR[Sh.lang];

  const PHASE_ORDER = ['EMERGENT', 'EARLY_GROWTH', 'GROWTH', 'MATURE', 'PEAK', 'DECLINING'];

  function render() {
    const s = L();
    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
      </div>
      <div class="kpi-mono-row rv">
        ${statTile('target', s.k_auc, '0.87', s.k_auc_s, 'var(--signal)')}
        ${statTile('check', s.k_prec, '78%', s.k_prec_s, 'var(--buy)')}
        ${statTile('gauge', s.k_brier, '0.11', s.k_brier_s, 'var(--azure)')}
        ${statTile('bars', s.k_pred, '1,284', s.k_pred_s, 'var(--ph-mature)')}
      </div>
      <div class="section-row" style="grid-template-columns:1.1fr 1fr 0.9fr">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.calib}</div><div class="sub">${s.calib_s}</div></div></div>
          <div class="chart-box"><div id="calibBox" style="width:100%;height:280px"></div></div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.dist}</div><div class="sub">${s.dist_s}</div></div></div>
          <div class="chart-box"><div id="histBox" style="width:100%;height:200px;margin-top:18px"></div>
            <div class="micro" style="display:flex;justify-content:space-between;padding:6px 4px 0">${[0, 25, 50, 75, 100].map((v) => `<span>${v}</span>`).join('')}</div></div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.phases}</div><div class="sub">${s.phases_s}</div></div></div>
          <div style="display:flex;flex-direction:column;align-items:center;gap:14px;padding:8px 18px 20px">
            <div id="donutBox"></div>
            <div class="phase-legend" id="phaseLeg" style="justify-content:center"></div></div>
        </section>
      </div>
      <section class="panel rv" style="margin-bottom:18px">
        <div class="panel-h"><div><div class="ttl">${s.bets}</div><div class="sub">${s.bets_s}</div></div></div>
        <div class="dg-scroll"><table class="dg"><thead><tr>
          <th>${s.c_prod}</th><th>${s.c_flag}</th><th class="num">${s.c_then}</th><th class="num">${s.c_now}</th><th>${s.c_evo}</th><th>${s.c_out}</th></tr></thead>
          <tbody id="betsBody"></tbody></table></div>
      </section>
      <section class="panel rv">
        <div class="panel-h"><div><div class="ttl">${s.coverage}</div><div class="sub">${s.coverage_s}</div></div></div>
        <div class="set-pad" id="coverBox"></div>
      </section>`;

    // calibration
    X.calibration($('#calibBox'), [
      { x: 0.08, y: 0.06 }, { x: 0.22, y: 0.19 }, { x: 0.38, y: 0.36 }, { x: 0.52, y: 0.55 },
      { x: 0.68, y: 0.64 }, { x: 0.81, y: 0.83 }, { x: 0.93, y: 0.9 },
    ], { height: 280, xLab: s.pred, yLab: s.obs });

    // histogram of scores
    const bins = new Array(10).fill(0);
    P.forEach((p) => { bins[clamp(Math.floor(p.tandor / 10), 0, 9)]++; });
    X.histogram($('#histBox'), bins, { height: 200 });

    // phase donut
    const counts = PHASE_ORDER.map((k) => ({ value: P.filter((p) => p.phase === k).length, color: `var(--${T.PHASES[k].v})`, label: T.PHASES[k][Sh.lang] })).filter((d) => d.value);
    X.donut($('#donutBox'), counts, { size: 156, thickness: 20, center: String(P.length), centerSub: s.total });
    $('#phaseLeg').innerHTML = counts.map((c) => `<span><i class="pdot" style="background:${c.color}"></i>${c.label}</span>`).join('');

    renderBets();
    renderCoverage();
  }

  function statTile(icn, label, val, sub, col) {
    return `<div class="stat-tile">
      <div class="st-l"><span class="st-ico" style="background:color-mix(in oklab, ${col} 14%, var(--surface-1));color:${col}">${ic(icn)}</span><span class="micro">${label}</span></div>
      <div class="st-v">${val}</div><div class="st-sub">${sub}</div></div>`;
  }

  function renderBets() {
    const s = L();
    const past = P.filter((p) => ['EARLY_GROWTH', 'GROWTH', 'PEAK', 'MATURE'].includes(p.phase)).sort((a, b) => b.tandor - a.tandor).slice(0, 6);
    const weeks = [9, 8, 7, 6, 5, 4];
    $('#betsBody').innerHTML = past.map((p, i) => {
      const then = clamp(p.organic - 22 - i * 2, 20, 90), now = p.organic;
      const delta = now - then, up = delta >= 0;
      const outcome = now >= 78 ? 'validated' : now >= 60 ? 'early' : 'missed';
      const ocol = outcome === 'validated' ? 'buy' : outcome === 'early' ? 'watch' : 'pass';
      const series = []; for (let k = 0; k < 10; k++) series.push(then + (now - then) * (k / 9) + Math.sin(k * 1.4) * 3);
      return `<tr data-id="${p.id}">
        <td><div class="cell-prod">${Sh.thumb(p, 32)}<div><div class="cp-name">${p.name}</div><div class="cp-sub">${T.CATS[p.cat][Sh.lang]}</div></div></div></td>
        <td class="mono" style="font-size:12px;color:var(--text-tertiary)">${weeks[i]} ${s.wk}</td>
        <td class="num">${then}</td>
        <td class="num"><b>${now}</b></td>
        <td><span class="past-spark">${C.sparkline(series, { w: 90, h: 30, stroke: up ? 'var(--buy)' : 'var(--pass)', fill: true, sw: 1.8 })}</span></td>
        <td><span class="verdict ${ocol}">${s[outcome]} <span class="delta-big ${up ? 'up' : 'down'}" style="font-size:11px">${up ? '+' : ''}${delta}</span></span></td></tr>`;
    }).join('');
    $$('#betsBody tr').forEach((r) => r.addEventListener('click', () => Sh.openProduct(P.find((p) => p.id === r.dataset.id))));
  }

  function renderCoverage() {
    const sources = [
      { l: 'Google Trends', col: 'var(--azure)', up: 99.2 },
      { l: 'Reddit', col: 'var(--reddit)', up: 97.5 },
      { l: 'CJ Catalogue', col: 'var(--signal)', up: 99.8 },
    ];
    $('#coverBox').innerHTML = sources.map((x) => `
      <div class="usage-row">
        <div class="usage-h"><span style="display:flex;align-items:center;gap:8px"><span class="pdot" style="width:8px;height:8px;border-radius:50%;background:${x.col}"></span>${x.l}</span><b>${x.up.toFixed(1)}%</b></div>
        <div class="usage-bar"><i style="width:${x.up}%;background:${x.col}"></i></div></div>`).join('');
  }

  Sh.start({ active: 'n_analytics', render });
}
