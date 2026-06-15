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

  const STR = {
    en: { title: 'Trend Analysis', sub: 'Google Trends demand · velocity · seasonality',
      compare: 'Compare keywords', add: 'Add product', win_3m: '3m', win_12m: '12m', win_5y: '5y',
      interest: 'Search interest', interest_s: 'Relative interest 0–100 · geo',
      velocity: 'Velocity readout', vel_velocity: 'Velocity', vel_growth: 'Growth', vel_accel: 'Acceleration', vel_r2: 'Fit (R²)',
      accel: 'Growth acceleration', accel_s: 'Second derivative — above 0 = accelerating', accel_pos: 'ACCELERATING', accel_neg: 'cooling',
      season: 'Seasonality', season_s: 'Demand multiplier · month × category',
      related: 'Related catalogue products', related_s: 'keyword joins to scored products',
      c_prod: 'Product', c_trends: 'Trends score', c_vel: 'Velocity', c_peak: 'Peak month', open: 'Open in Discovery',
      pick: 'Add a product to compare', perday: '/day', month: 'mo' },
    fr: { title: 'Analyse de tendances', sub: 'Demande Google Trends · vélocité · saisonnalité',
      compare: 'Comparer des mots-clés', add: 'Ajouter un produit', win_3m: '3m', win_12m: '12m', win_5y: '5a',
      interest: 'Intérêt de recherche', interest_s: 'Intérêt relatif 0–100 · geo',
      velocity: 'Lecture de vélocité', vel_velocity: 'Vélocité', vel_growth: 'Croissance', vel_accel: 'Accélération', vel_r2: 'Ajustement (R²)',
      accel: 'Accélération de croissance', accel_s: 'Dérivée seconde — au-dessus de 0 = en accélération', accel_pos: 'EXPLOSE', accel_neg: 'ralentit',
      season: 'Saisonnalité', season_s: 'Multiplicateur de demande · mois × catégorie',
      related: 'Produits liés du catalogue', related_s: 'jointure mot-clé → produits scorés',
      c_prod: 'Produit', c_trends: 'Score Trends', c_vel: 'Vélocité', c_peak: 'Mois de pic', open: 'Ouvrir dans Discovery',
      pick: 'Ajoutez un produit à comparer', perday: '/jour', month: 'mois' },
  };
  const L = () => STR[Sh.lang];
  const COLORS = ['var(--azure)', 'var(--signal)', 'var(--reddit)', 'var(--buy)', 'var(--watch)'];
  const WINDOWS = { '3m': 12, '12m': 22, '5y': 30 };

  let selected = P.slice().sort((a, b) => b.trendsScore - a.trendsScore).slice(0, 3).map((p) => p.id);
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
    $('#canvas').innerHTML = `
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
    const avail = P.filter((p) => !selected.includes(p.id)).sort((a, b) => b.trendsScore - a.trendsScore);
    if (!avail.length) return;
    // lightweight inline picker via cmdk-like popover reusing market popover styling
    const pop = $('#marketPop');
    pop.innerHTML = `<div class="pop-h">${L().add}</div>` + avail.slice(0, 10).map((p) => `<div class="pop-item" data-id="${p.id}"><span class="ci-ico" style="width:24px;height:24px;border-radius:6px;background:var(--${T.PHASES[p.phase].v});color:#fff;display:grid;place-items:center;font-family:var(--font-mono);font-size:11px;font-weight:700">${p.name[0]}</span>${p.name}<span style="margin-left:auto;font-family:var(--font-mono);font-size:11px;color:var(--text-tertiary)">${p.trendsScore}</span></div>`).join('');
    pop.classList.add('show');
    const r = $('#kwAdd').getBoundingClientRect(); pop.style.top = (r.bottom + 8) + 'px'; pop.style.left = Math.min(r.left, innerWidth - 230) + 'px';
    $$('#marketPop .pop-item').forEach((it) => it.addEventListener('click', () => { selected.push(it.dataset.id); pop.classList.remove('show'); render(); }));
  }

  function drawChart() {
    const vis = selected.filter((id) => !hidden.has(id));
    const series = vis.map((id) => { const p = P.find((x) => x.id === id); return { name: p.name, color: colorFor(id), values: sliceSeries(p.trend) }; });
    if (!series.length) { $('#bigChart').innerHTML = `<div class="empty" style="padding:60px 0"><div class="e-art">${ic('trend')}</div><div class="e-t">${L().pick}</div></div>`; return; }
    const n = series[0].values.length;
    X.lineChart($('#bigChart'), series, { xlabels: xLabels(n), yMin: 0, yMax: 100, area: vis.length <= 2, height: 320 });
  }
  function drawAccel() {
    const id = selected.find((x) => !hidden.has(x)) || selected[0];
    if (!id) { $('#accelBox').innerHTML = ''; return; }
    const p = P.find((x) => x.id === id), v = sliceSeries(p.trend);
    const acc = []; for (let i = 0; i < v.length; i++) { const prev = v[i - 1] != null ? v[i - 1] : v[i]; const next = v[i + 1] != null ? v[i + 1] : v[i]; acc.push((next - 2 * v[i] + prev)); }
    const s = L();
    X.divergingArea($('#accelBox'), acc, { xlabels: xLabels(v.length), height: 180, posLabel: s.accel_pos, negLabel: s.accel_neg, label: s.vel_accel });
  }
  function renderVel() {
    const s = L();
    $('#velGrid').innerHTML = selected.map((id) => {
      const p = P.find((x) => x.id === id), v = p.trend, vel = ((v[v.length - 1] - v[0]) / v.length);
      const accel = (v[v.length - 1] - 2 * v[Math.floor(v.length / 2)] + v[0]) / 2;
      const r2 = clamp(1 - p.volatility, 0, 1);
      const up = p.growth >= 0;
      return `<div class="vel-card">
        <div class="vc-h"><span class="vc-dot" style="background:${colorFor(id)}"></span>${p.name}</div>
        <div class="vc-rows">
          <div class="vc-row"><span>${s.vel_velocity}</span><b class="${vel >= 0 ? 'up' : 'down'}">${vel >= 0 ? '+' : ''}${vel.toFixed(2)} ${s.perday}</b></div>
          <div class="vc-row"><span>${s.vel_growth}</span><b class="${up ? 'up' : 'down'}">${up ? '+' : ''}${Math.round(p.growth * 100)}% /${s.month}</b></div>
          <div class="vc-row"><span>${s.vel_accel}</span><b>${accel >= 0 ? '+' : ''}${accel.toFixed(2)}</b></div>
          <div class="vc-row"><span>${s.vel_r2}</span><b>${r2.toFixed(2)}</b></div>
        </div></div>`;
    }).join('');
  }
  function renderRelated() {
    const s = L();
    const rows = P.slice().sort((a, b) => b.trendsScore - a.trendsScore).slice(0, 8).map((p) => {
      const v = p.trend, vel = ((v[v.length - 1] - v[0]) / v.length), up = vel >= 0;
      return `<tr data-id="${p.id}">
        <td><div class="cell-prod">${Sh.thumb(p, 32)}<div><div class="cp-name">${p.name}</div><div class="cp-sub">${T.CATS[p.cat][Sh.lang]}</div></div></div></td>
        <td class="num">${p.trendsScore}</td>
        <td class="num"><span class="vel ${up ? 'up' : 'down'}">${up ? '+' : ''}${vel.toFixed(2)}</span></td>
        <td>${T.MONTHS[Sh.lang][p.seasonPeak - 1]}</td>
        <td class="num"><a class="panel-link" href="Tandor Discovery.html">${s.open} ${ic('arrowUR')}</a></td></tr>`;
    }).join('');
    $('#relBody').innerHTML = rows;
    $$('#relBody tr').forEach((r) => r.addEventListener('click', (e) => { if (e.target.closest('a')) return; Sh.openProduct(P.find((p) => p.id === r.dataset.id)); }));
    $$('#relBody .panel-link svg').forEach((sv) => sv.style.width = '12px');
  }

  Sh.start({ active: 'n_trends', render });
}
