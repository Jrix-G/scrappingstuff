/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-trends.js   (Trend Analysis)
   Google Trends curves with multi-product comparison, time
   windows, velocity readouts, acceleration and seasonality.
   ============================================================ */
export function mountTrends() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts, X = window.ChartsX, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic, clamp = Sh.clamp;

  const isOffline = !((window as any).__TANDOR_PAGE__?.apiBase);

  const STR = {
    en: { title: 'Trend Analysis', sub: 'real demand curve · velocity · Trends score',
      compare: 'Compare keywords', add: 'Add product', win_3m: '3m', win_12m: '12m', win_5y: '5y',
      interest: 'Demand curve', interest_s: 'Real collected demand (Amazon/AliExpress) · normalized 0–100',
      velocity: 'Velocity readout', vel_velocity: 'Velocity', vel_growth: 'Growth', vel_accel: 'Acceleration', vel_r2: 'Fit (R²)',
      accel: 'Growth acceleration', accel_s: 'Second derivative — above 0 = accelerating', accel_pos: 'ACCELERATING', accel_neg: 'cooling',
      season: 'Seasonality', season_s: 'Demand multiplier · month × category',
      related: 'Related catalogue products', related_s: 'Trends score per scored product',
      c_prod: 'Product', c_trends: 'Trends score', c_vel: 'Velocity', c_peak: 'Peak month', open: 'Open in Discovery',
      pick: 'Add a product to compare', perday: '/day', month: 'mo',
      no_curve_t: 'No real curve yet', no_curve_s: 'No product in the selection has a real demand history yet — score numbers below are real, the curve is being built.',
      no_data: 'no data', score_real: 'Trends score (real)', curve_pending: 'curve in progress', nm: 'not measured' },
    fr: { title: 'Analyse de tendances', sub: 'courbe de demande réelle · vélocité · score Trends',
      compare: 'Comparer des mots-clés', add: 'Ajouter un produit', win_3m: '3m', win_12m: '12m', win_5y: '5a',
      interest: 'Courbe de demande', interest_s: 'Demande réelle collectée (Amazon/AliExpress) · normalisée 0–100',
      velocity: 'Lecture de vélocité', vel_velocity: 'Vélocité', vel_growth: 'Croissance', vel_accel: 'Accélération', vel_r2: 'Ajustement (R²)',
      accel: 'Accélération de croissance', accel_s: 'Dérivée seconde — au-dessus de 0 = en accélération', accel_pos: 'EXPLOSE', accel_neg: 'ralentit',
      season: 'Saisonnalité', season_s: 'Multiplicateur de demande · mois × catégorie',
      related: 'Produits liés du catalogue', related_s: 'score Trends par produit scoré',
      c_prod: 'Produit', c_trends: 'Score Trends', c_vel: 'Vélocité', c_peak: 'Mois de pic', open: 'Ouvrir dans Discovery',
      pick: 'Ajoutez un produit à comparer', perday: '/jour', month: 'mois',
      no_curve_t: 'Pas encore de courbe réelle', no_curve_s: 'Aucun produit de la sélection n’a encore d’historique de demande réel — les scores ci-dessous sont réels, la courbe est en cours de constitution.',
      no_data: 'pas de données', score_real: 'Score Trends (réel)', curve_pending: 'courbe en cours', nm: 'non mesuré' },
  };
  const L = () => STR[Sh.lang];
  const COLORS = ['var(--azure)', 'var(--signal)', 'var(--reddit)', 'var(--buy)', 'var(--watch)'];
  const WINDOWS = { '3m': 12, '12m': 22, '5y': 30 };

  // Tri par score Trends RÉEL ; les produits non mesurés (trendsScore null) coulent en bas.
  let selected = P.slice().sort((a, b) => (b.trendsScore ?? -1) - (a.trendsScore ?? -1)).slice(0, 3).map((p) => p.id);
  let win = '12m', hidden = new Set();

  function colorFor(id) { return COLORS[selected.indexOf(id) % COLORS.length]; }
  function sliceSeries(arr) { const n = WINDOWS[win]; return arr.slice(Math.max(0, arr.length - n)); }
  function xLabels(n) {
    const M = T.MONTHS[Sh.lang], cur = T.CUR_MONTH, out = [];
    const span = win === '3m' ? 3 : win === '12m' ? 12 : 60;
    for (let i = 0; i < n; i++) { const f = i / (n - 1); const monthsAgo = Math.round((1 - f) * span); const idx = ((cur - monthsAgo) % 12 + 12) % 12; out.push(win === '5y' ? `'${(26 - Math.round((1 - f) * 5))}` : M[idx]); }
    return out;
  }

  function render() {
    const s = L();
    const offlineBanner = isOffline
      ? `<div class="notice-bar" style="background:var(--bg-warn,#fff3cd);color:var(--text-warn,#856404);padding:8px 18px;font-size:12.5px;border-radius:8px;margin-bottom:12px">
          ${ic('alert')} ${Sh.lang === 'fr' ? 'API Pi indisponible — données statiques (60 produits). Configurez <b>REACT_APP_API_URL_LOCAL</b> pour pointer vers votre Pi en local.' : 'Pi API unavailable — showing static data (60 products). Set <b>REACT_APP_API_URL_LOCAL</b> to your Pi local IP to get live data.'}
         </div>`
      : '';
    $('#canvas').innerHTML = `
      ${offlineBanner}
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
        <div class="seg" id="winSeg"><div class="seg-thumb"></div>${Object.keys(WINDOWS).map((w) => `<button data-w="${w}" class="${w === win ? 'on' : ''}">${s['win_' + w]}</button>`).join('')}</div>
      </div>
      <div class="panel rv" style="margin-bottom:18px">
        <div class="panel-h"><div><div class="ttl">${s.interest}</div><div class="sub">${s.interest_s} · ${marketLabel()}</div></div></div>
        <div style="padding:6px 18px 0"><div class="kw-chips" id="kwChips"></div></div>
        <div class="chart-box"><div class="big-chart" id="bigChart"></div></div>
      </div>
      <div class="section-row grid-21">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.accel}</div><div class="sub">${s.accel_s}</div></div></div>
          <div class="chart-box"><div class="accel-box" id="accelBox"></div></div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.season}</div><div class="sub">${s.season_s}</div></div></div>
          <div class="chart-box"><div class="hm-box" id="hmBox" style="height:200px"></div></div>
        </section>
      </div>
      <div class="rv" style="margin:6px 0 18px"><div class="vel-grid" id="velGrid"></div></div>
      <section class="panel rv">
        <div class="panel-h"><div><div class="ttl">${s.related}</div><div class="sub">${s.related_s}</div></div></div>
        <div class="dg-scroll"><table class="dg"><thead><tr>
          <th>${s.c_prod}</th><th class="num">${s.c_trends}</th><th class="num">${s.c_vel}</th><th>${s.c_peak}</th><th></th></tr></thead>
          <tbody id="relBody"></tbody></table></div>
      </section>`;

    // window seg
    $$('#winSeg button').forEach((b) => b.addEventListener('click', () => { win = b.dataset.w; $$('#winSeg button').forEach((x) => x.classList.toggle('on', x === b)); positionSeg(); drawChart(); drawAccel(); }));
    positionSeg();
    renderChips(); drawChart(); drawAccel(); renderVel(); renderRelated();
    C.renderHeatmap($('#hmBox'), { lang: Sh.lang });
  }

  function positionSeg() { const seg = $('#winSeg'), on = $('.on', seg), th = $('.seg-thumb', seg); if (on && th) { th.style.left = on.offsetLeft + 'px'; th.style.width = on.offsetWidth + 'px'; } }
  function marketLabel() { const m = T.MARKETS.find((x) => x.code === Sh.market()) || T.MARKETS[0]; return m.flag + ' ' + m.code; }

  function renderChips() {
    const s = L();
    const chips = selected.map((id) => { const p = P.find((x) => x.id === id); const off = hidden.has(id); return `<span class="kw-chip" data-id="${id}" style="${off ? 'opacity:.5' : ''}"><span class="kw-dot" style="background:${colorFor(id)}"></span>${p.name}<button data-x="${id}">${ic('x')}</button></span>`; }).join('');
    const canAdd = selected.length < 5;
    $('#kwChips').innerHTML = chips + (canAdd ? `<button class="kw-add" id="kwAdd">${ic('plus')}${s.add}</button>` : '');
    $$('#kwChips .kw-chip').forEach((c) => c.addEventListener('click', (e) => { if (e.target.closest('[data-x]')) return; const id = c.dataset.id; if (hidden.has(id)) hidden.delete(id); else hidden.add(id); renderChips(); drawChart(); }));
    $$('#kwChips [data-x]').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); selected = selected.filter((x) => x !== b.dataset.x); hidden.delete(b.dataset.x); render(); }));
    if ($('#kwAdd')) $('#kwAdd').addEventListener('click', openAdd);
  }
  function openAdd() {
    const avail = P.filter((p) => !selected.includes(p.id)).sort((a, b) => (b.trendsScore ?? -1) - (a.trendsScore ?? -1));
    if (!avail.length) return;
    // lightweight inline picker via cmdk-like popover reusing market popover styling
    const pop = $('#marketPop');
    pop.innerHTML = `<div class="pop-h">${L().add}</div>` + avail.slice(0, 10).map((p) => `<div class="pop-item" data-id="${p.id}"><span class="ci-ico" style="width:24px;height:24px;border-radius:6px;background:var(--${T.PHASES[p.phase].v});color:#fff;display:grid;place-items:center;font-family:var(--font-mono);font-size:11px;font-weight:700">${p.name[0]}</span>${p.name}<span style="margin-left:auto;font-family:var(--font-mono);font-size:11px;color:var(--text-tertiary)">${p.hasTrends ? p.trendsScore : '—'}</span></div>`).join('');
    pop.classList.add('show');
    const r = $('#kwAdd').getBoundingClientRect(); pop.style.top = (r.bottom + 8) + 'px'; pop.style.left = Math.min(r.left, innerWidth - 230) + 'px';
    $$('#marketPop .pop-item').forEach((it) => it.addEventListener('click', () => { selected.push(it.dataset.id); pop.classList.remove('show'); render(); }));
  }

  // REAL demand curve only — never plot the procedural filler as if it were real.
  function realCurve(p) { return p.hasRealHistory && p.realHistory && p.realHistory.demand ? p.realHistory.demand.values : null; }

  function drawChart() {
    const s = L();
    const vis = selected.filter((id) => !hidden.has(id));
    if (!vis.length) { $('#bigChart').innerHTML = `<div class="empty" style="padding:60px 0"><div class="e-art">${ic('trend')}</div><div class="e-t">${s.pick}</div></div>`; return; }
    // Only products with a REAL demand history get a curve.
    const series = vis.map((id) => { const p = P.find((x) => x.id === id); const rc = realCurve(p); return rc ? { name: p.name, color: colorFor(id), values: sliceSeries(rc) } : null; }).filter(Boolean);
    if (!series.length) { $('#bigChart').innerHTML = `<div class="empty" style="padding:50px 0"><div class="e-art">${ic('trend')}</div><div class="e-t">${s.no_curve_t}</div><div class="e-s">${s.no_curve_s}</div></div>`; return; }
    const n = series[0].values.length;
    X.lineChart($('#bigChart'), series, { xlabels: xLabels(n), yMin: 0, yMax: 100, area: series.length <= 2, height: 320 });
  }
  function drawAccel() {
    const s = L();
    // Acceleration is only meaningful on a real curve.
    const id = selected.find((x) => !hidden.has(x) && realCurve(P.find((p) => p.id === x))) || selected.find((x) => realCurve(P.find((p) => p.id === x)));
    if (!id) { $('#accelBox').innerHTML = `<div class="empty" style="padding:40px 0"><div class="e-art">${ic('activity')}</div><div class="e-t">${s.no_curve_t}</div></div>`; return; }
    const p = P.find((x) => x.id === id), v = sliceSeries(realCurve(p));
    const acc = []; for (let i = 0; i < v.length; i++) { const prev = v[i - 1] != null ? v[i - 1] : v[i]; const next = v[i + 1] != null ? v[i + 1] : v[i]; acc.push((next - 2 * v[i] + prev)); }
    X.divergingArea($('#accelBox'), acc, { xlabels: xLabels(v.length), height: 180, posLabel: s.accel_pos, negLabel: s.accel_neg, label: s.vel_accel });
  }
  function renderVel() {
    const s = L();
    $('#velGrid').innerHTML = selected.map((id) => {
      const p = P.find((x) => x.id === id);
      // Velocity/acceleration are derived from the REAL curve only ; growth and
      // Trends score sont des scalaires affichés UNIQUEMENT s'ils sont mesurés
      // (drapeaux hasGrowth / hasTrends). Un null backend ne devient jamais « +0% ».
      const v = realCurve(p);
      let velRow, accelRow;
      if (v && v.length > 1) {
        const vel = ((v[v.length - 1] - v[0]) / v.length);
        const accel = (v[v.length - 1] - 2 * v[Math.floor(v.length / 2)] + v[0]) / 2;
        velRow = `<b class="${vel >= 0 ? 'up' : 'down'}">${vel >= 0 ? '+' : ''}${vel.toFixed(2)} ${s.perday}</b>`;
        accelRow = `<b>${accel >= 0 ? '+' : ''}${accel.toFixed(2)}</b>`;
      } else {
        velRow = `<b style="color:var(--text-tertiary)">—</b>`;
        accelRow = `<b style="color:var(--text-tertiary)">—</b>`;
      }
      const trendsCell = p.hasTrends
        ? `<b>${p.trendsScore}</b>`
        : `<b style="color:var(--text-tertiary)" title="${s.nm}">—</b>`;
      let growthCell;
      if (p.hasGrowth) {
        const up = p.growth >= 0;
        growthCell = `<b class="${up ? 'up' : 'down'}">${up ? '+' : ''}${Math.round(p.growth * 100)}% /${s.month}</b>`;
      } else {
        growthCell = `<b style="color:var(--text-tertiary)" title="${s.nm}">—</b>`;
      }
      return `<div class="vel-card">
        <div class="vc-h"><span class="vc-dot" style="background:${colorFor(id)}"></span>${p.name}</div>
        <div class="vc-rows">
          <div class="vc-row"><span>${s.score_real}</span>${trendsCell}</div>
          <div class="vc-row"><span>${s.vel_velocity}</span>${velRow}</div>
          <div class="vc-row"><span>${s.vel_growth}</span>${growthCell}</div>
          <div class="vc-row"><span>${s.vel_accel}</span>${accelRow}</div>
        </div></div>`;
    }).join('');
  }
  function renderRelated() {
    const s = L();
    // Seuls les produits réellement scorés en Trends ; tri descendant, non mesurés exclus.
    const rows = P.filter((p) => p.hasTrends).sort((a, b) => b.trendsScore - a.trendsScore).slice(0, 8).map((p) => {
      // Velocity only from the real demand curve; "—" when there's none yet.
      const v = realCurve(p);
      let velCell;
      if (v && v.length > 1) { const vel = ((v[v.length - 1] - v[0]) / v.length), up = vel >= 0; velCell = `<span class="vel ${up ? 'up' : 'down'}">${up ? '+' : ''}${vel.toFixed(2)}</span>`; }
      else velCell = `<span style="color:var(--text-tertiary)">—</span>`;
      return `<tr data-id="${p.id}">
        <td><div class="cell-prod">${Sh.thumb(p, 32)}<div><div class="cp-name">${p.name}</div><div class="cp-sub">${T.CATS[p.cat][Sh.lang]}</div></div></div></td>
        <td class="num">${p.trendsScore}</td>
        <td class="num">${velCell}</td>
        <td>${T.MONTHS[Sh.lang][p.seasonPeak - 1]}</td>
        <td class="num"><a class="panel-link" href="/discovery">${s.open} ${ic('arrowUR')}</a></td></tr>`;
    }).join('');
    $('#relBody').innerHTML = rows || `<tr><td colspan="5"><div class="empty" style="padding:36px 0"><div class="e-art">${ic('trend')}</div><div class="e-t">${s.no_curve_t}</div><div class="e-s">${s.nm}</div></div></td></tr>`;
    $$('#relBody tr').forEach((r) => r.addEventListener('click', (e) => { if (e.target.closest('a')) return; Sh.openProduct(P.find((p) => p.id === r.dataset.id)); }));
    $$('#relBody .panel-link svg').forEach((sv) => sv.style.width = '12px');
  }

  Sh.start({ active: 'n_trends', render });
}
