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
    en: { title: 'Analytics', sub: 'catalogue coverage · real-history proof',
      k_tracked: 'Tracked products', k_real: 'With real history', k_corro: 'Corroborated', k_last: 'Last collection',
      k_tracked_s: 'in the catalogue', k_real_s: '≥2 demand snapshots', k_corro_s: 'Trends + Reddit > 60', k_last_s: 'real DB timestamp',
      calib: 'Calibration', calib_s: 'no backtest persisted yet', pred: 'Predicted', obs: 'Observed',
      dist: 'Score distribution', dist_s: 'Tandor score across the catalogue',
      phases: 'Phase mix', phases_s: 'tracked products by phase', total: 'tracked',
      bets: 'Past-bet validation', bets_s: 'requires prediction history — not persisted yet',
      coverage: 'Source coverage', coverage_s: 'demand-history coverage by source',
      soon: 'coming soon', soon_s: 'This metric needs a persisted prediction/backtest history, which the engine does not store yet — shown as “—” rather than a fabricated number.',
      cover_real: 'with real demand curve' },
    fr: { title: 'Analytics', sub: 'couverture du catalogue · preuve d’historique réel',
      k_tracked: 'Produits suivis', k_real: 'Avec historique réel', k_corro: 'Corroborés', k_last: 'Dernière collecte',
      k_tracked_s: 'dans le catalogue', k_real_s: '≥2 snapshots de demande', k_corro_s: 'Trends + Reddit > 60', k_last_s: 'horodatage réel DB',
      calib: 'Calibration', calib_s: 'aucun backtest persisté pour l’instant', pred: 'Prédit', obs: 'Observé',
      dist: 'Distribution des scores', dist_s: 'Score Tandor sur le catalogue',
      phases: 'Répartition des phases', phases_s: 'produits suivis par phase', total: 'suivis',
      bets: 'Validation des paris passés', bets_s: 'nécessite un historique de prédictions — pas encore persisté',
      coverage: 'Couverture des sources', coverage_s: 'couverture de l’historique de demande par source',
      soon: 'bientôt', soon_s: 'Cette métrique nécessite un historique de prédictions/backtest persisté, que le moteur ne stocke pas encore — affiché « — » plutôt qu’un chiffre fabriqué.',
      cover_real: 'avec courbe de demande réelle' },
  };
  const L = () => STR[Sh.lang];

  const PHASE_ORDER = ['EMERGENT', 'EARLY_GROWTH', 'GROWTH', 'MATURE', 'PEAK', 'DECLINING'];

  // Honest "il y a Xh/Xj" from a real ISO timestamp; null → handled by caller.
  function agoFromISO(iso) {
    if (!iso) return null;
    const t = Date.parse(iso); if (isNaN(t)) return null;
    const mins = Math.max(0, Math.round((Date.now() - t) / 60000)), fr = Sh.lang === 'fr';
    if (mins < 60) return fr ? `il y a ${mins} min` : `${mins} min ago`;
    const hrs = Math.round(mins / 60);
    if (hrs < 48) return fr ? `il y a ${hrs} h` : `${hrs} h ago`;
    const days = Math.round(hrs / 24);
    return fr ? `il y a ${days} j` : `${days} d ago`;
  }

  function render() {
    const s = L();
    // REAL counts from the catalogue.
    const tracked = P.length;
    const withReal = P.filter((p) => p.hasRealHistory).length;
    const corro = P.filter((p) => p.redditScore > 60 && p.trendsScore > 60).length;
    const lastVal = agoFromISO(P.length ? P[0].lastCollection : null) || (Sh.lang === 'fr' ? '—' : '—');

    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
      </div>
      <div class="kpi-mono-row rv">
        ${statTile('bars', s.k_tracked, Sh.fmt(tracked), s.k_tracked_s, 'var(--signal)')}
        ${statTile('activity', s.k_real, Sh.fmt(withReal), s.k_real_s, 'var(--buy)')}
        ${statTile('check', s.k_corro, Sh.fmt(corro), s.k_corro_s, 'var(--azure)')}
        ${statTile('clock', s.k_last, lastVal, s.k_last_s, 'var(--ph-mature)')}
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
        <div id="betsBody"></div>
      </section>
      <section class="panel rv">
        <div class="panel-h"><div><div class="ttl">${s.coverage}</div><div class="sub">${s.coverage_s}</div></div></div>
        <div class="set-pad" id="coverBox"></div>
      </section>`;

    // calibration — no real backtest/outcome pairs are persisted, so we do NOT
    // draw a fabricated calibration curve; honest empty-state instead.
    $('#calibBox').innerHTML = `<div class="empty" style="padding:48px 0"><div class="e-art">${ic('target')}</div><div class="e-t">${s.soon}</div><div class="e-s">${s.soon_s}</div></div>`;

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
    // Past-bet validation needs a persisted prediction history (then-score,
    // outcome) that the engine does not store. We refuse to fabricate it.
    $('#betsBody').innerHTML = `<div class="empty" style="padding:40px 0"><div class="e-art">${ic('bars')}</div><div class="e-t">${s.soon}</div><div class="e-s">${s.soon_s}</div></div>`;
  }

  function renderCoverage() {
    // REAL coverage: how many tracked products carry a real demand history,
    // split by source (Amazon vs AliExpress). Uptime % is not measured, so we
    // do not invent it.
    const total = P.length || 1;
    const amazon = P.filter((p) => p.realHistory && p.realHistory.amazon).length;
    const ali = P.filter((p) => p.realHistory && p.realHistory.sales).length;
    const sources = [
      { l: 'Amazon', col: 'var(--signal)', n: amazon },
      { l: 'AliExpress', col: 'var(--amber)', n: ali },
    ];
    const cr = L().cover_real;
    $('#coverBox').innerHTML = sources.map((x) => {
      const pctv = Math.round(x.n / total * 100);
      return `<div class="usage-row">
        <div class="usage-h"><span style="display:flex;align-items:center;gap:8px"><span class="pdot" style="width:8px;height:8px;border-radius:50%;background:${x.col}"></span>${x.l} <span class="micro" style="color:var(--text-tertiary)">· ${cr}</span></span><b>${x.n}/${P.length} (${pctv}%)</b></div>
        <div class="usage-bar"><i style="width:${pctv}%;background:${x.col}"></i></div></div>`;
    }).join('');
  }

  Sh.start({ active: 'n_analytics', render });
}
