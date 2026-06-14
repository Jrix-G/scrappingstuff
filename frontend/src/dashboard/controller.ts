/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR DASHBOARD — app.js  (vanilla, no framework)
   ============================================================ */
let _mounted = false;
export function mountDashboard() {
  'use strict';
  if (_mounted) return; _mounted = true;
  const T = window.TANDOR, C = window.Charts;
  const P = T.PRODUCTS;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const mean = (a) => a.reduce((s, v) => s + v, 0) / a.length;
  const median = (a) => { const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- icons (lucide-style) ---------- */
  const PATHS = {
    search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>',
    radar: '<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8"/><path d="M12 4v4M12 12l5-3"/>',
    trend: '<path d="M3 17l5-5 4 3 8-9"/><path d="M16 6h5v5"/>',
    reddit: '<circle cx="12" cy="13" r="7"/><circle cx="9.5" cy="13" r="1"/><circle cx="14.5" cy="13" r="1"/><path d="M9 16c1.8 1.2 4.2 1.2 6 0M12 6l1-3 3 .8"/><circle cx="16" cy="3.8" r="1.2"/>',
    signal: '<path d="M3 12h3l2.5-7 5 16 2.5-9H21"/>',
    bars: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    bookmark: '<path d="M7 4h10a1 1 0 0 1 1 1v15l-6-3.5L6 20V5a1 1 0 0 1 1-1z"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 7 19.4l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
    card: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
    gauge: '<path d="M12 14 16 9"/><circle cx="12" cy="14" r="1.6"/><path d="M4 18a8 8 0 1 1 16 0"/>',
    coins: '<circle cx="9" cy="9" r="6"/><path d="M16.5 5.2A6 6 0 1 1 15 16.7"/>',
    sparkles: '<path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6z"/><path d="M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    sliders: '<path d="M4 6h11M19 6h1M4 12h2M10 12h10M4 18h7M15 18h5"/><circle cx="17" cy="6" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="13" cy="18" r="2"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    arrowUR: '<path d="M7 17 17 7M8 7h9v9"/>',
    ext: '<path d="M15 3h6v6M10 14 21 3M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/>',
    chev: '<path d="m6 9 6 6 6-6"/>',
    zap: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    download: '<path d="M12 3v12M7 11l5 5 5-5M4 21h16"/>',
    hash: '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
    flame: '<path d="M12 3c0 4-4 5-4 9a4 4 0 0 0 8 0c0-2-2-3-2-5 2 1 4 3 4 6a6 6 0 1 1-12 0c0-5 6-6 6-10z"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5"/>',
  };
  const ic = (n, cls) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"${cls ? ' class="' + cls + '"' : ''}>${PATHS[n] || ''}</svg>`;

  /* ---------- accents ---------- */
  const ACCENTS = {
    indigo: { s: 'oklch(0.52 0.16 264)', ss: 'oklch(0.44 0.16 264)', tint: 'oklch(0.955 0.03 264)', glow: 'oklch(0.52 0.16 264 / .22)' },
    teal: { s: 'oklch(0.6 0.115 180)', ss: 'oklch(0.5 0.1 182)', tint: 'oklch(0.955 0.035 182)', glow: 'oklch(0.6 0.115 180 / .25)' },
    amber: { s: 'oklch(0.68 0.135 66)', ss: 'oklch(0.56 0.12 58)', tint: 'oklch(0.96 0.04 72)', glow: 'oklch(0.68 0.135 66 / .25)' },
  };

  /* ---------- state / persistence ---------- */
  const TWEAKS = /*EDITMODE-BEGIN*/{
    "accent": "indigo",
    "density": "comfort"
  }/*EDITMODE-END*/;
  const LS = {
    get(k, d) { try { const v = localStorage.getItem('tandor_' + k); return v == null ? d : v; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('tandor_' + k, v); } catch (e) {} },
  };
  let lang = LS.get('lang', null);
  if (!lang) { lang = (navigator.language || 'en').toLowerCase().startsWith('fr') ? 'fr' : 'en'; }
  let accent = LS.get('accent', TWEAKS.accent);
  let density = LS.get('density', TWEAKS.density);
  let collapsed = LS.get('collapsed', '0') === '1';
  let period = '7d';
  const S = () => T.STR[lang];

  /* ============================================================
     Tooltip
     ============================================================ */
  const tipEl = $('#tip');
  window.Tip = {
    show(html, e) { tipEl.innerHTML = html; tipEl.classList.add('show'); this.move(e); },
    move(e) { if (!e) return; const r = tipEl.getBoundingClientRect(); let x = e.clientX + 14, y = e.clientY + 14; if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14; if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14; tipEl.style.left = x + 'px'; tipEl.style.top = y + 'px'; },
    hide() { tipEl.classList.remove('show'); },
  };

  /* ============================================================
     Toast
     ============================================================ */
  function toast(msg) {
    const t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = `<span class="t-ico">${ic('check')}</span><span>${msg}</span>`;
    $('#toasts').appendChild(t);
    requestAnimationFrame(() => t.classList.add('show'));
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 250); }, 3200);
  }

  /* ============================================================
     count-up
     ============================================================ */
  function countUp(el, to, dec, prefix, suffix) {
    prefix = prefix || ''; suffix = suffix || ''; dec = dec || 0;
    if (reduced) { el.textContent = prefix + to.toFixed(dec) + suffix; return; }
    const dur = 750, t0 = performance.now();
    const fmt = (v) => prefix + v.toLocaleString(lang === 'fr' ? 'fr-FR' : 'en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suffix;
    function step(t) {
      const k = clamp((t - t0) / dur, 0, 1);
      const e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(to * e);
      if (k < 1) requestAnimationFrame(step); else el.textContent = fmt(to);
    }
    requestAnimationFrame(step);
    // fallback in case rAF is throttled (offscreen capture) — guarantee final value
    setTimeout(() => { el.textContent = fmt(to); }, dur + 250);
  }

  /* ---------- thumbnail placeholder ---------- */
  function thumb(p) {
    const hue = p.catHue;
    const a = `oklch(0.7 0.1 ${hue})`, b = `oklch(0.52 0.12 ${hue})`;
    const tag = T.CATS[p.cat].en.slice(0, 3).toUpperCase();
    return `<div class="thumb">
      <div class="ph-stripe" style="background:
        repeating-linear-gradient(135deg, ${a} 0 6px, ${b} 6px 12px);opacity:.92"></div>
      <span class="ph-tag">${tag}</span>
    </div>`;
  }

  /* ============================================================
     METRICS (per period)
     ============================================================ */
  const buyCount = P.filter((p) => p.verdict === 'BUY').length;
  const avgScore = mean(P.map((p) => p.tandor));
  const medMargin = median(P.map((p) => p.net));
  const emergCount = P.filter((p) => p.phase === 'EMERGENT').length;
  const phaseOrder = ['EMERGENT', 'EARLY_GROWTH', 'GROWTH', 'MATURE', 'PEAK', 'DECLINING'];
  const phaseCount = {}; phaseOrder.forEach((k) => phaseCount[k] = P.filter((p) => p.phase === k).length);

  const PERIOD_DELTA = {
    '24h': { active: 2, score: 1.1, margin: 0.5, emerg: 1 },
    '7d': { active: 5, score: 2.3, margin: 1.2, emerg: 2 },
    '30d': { active: 9, score: 4.0, margin: 2.1, emerg: 3 },
  };
  // synthetic 14-pt sparkline series for KPI score & margin
  function synth(base, rise, n) { const out = []; for (let i = 0; i < n; i++) { const f = i / (n - 1); out.push(base - rise + rise * f + Math.sin(i * 1.7) * rise * 0.18); } return out; }
  const scoreSeries = synth(avgScore, 5, 14);
  const marginSeries = synth(medMargin, 2.4, 14);

  /* ============================================================
     SIDEBAR
     ============================================================ */
  const NAV = [
    { g: 'nav_disc', items: [['home', 'n_home', true], ['compass', 'n_discovery'], ['radar', 'n_radar']] },
    { g: 'nav_analysis', items: [['trend', 'n_trends'], ['reddit', 'n_reddit'], ['signal', 'n_market'], ['bars', 'n_analytics']] },
    { g: 'nav_space', items: [['bookmark', 'n_saved'], ['list', 'n_watch'], ['bell', 'n_alerts']] },
  ];
  const FOOT_NAV = [['settings', 'n_settings'], ['card', 'n_billing'], ['user', 'n_account']];

  function renderSidebar() {
    const s = S();
    let h = '';
    NAV.forEach((grp) => {
      h += `<div class="sb-group">${s[grp.g]}</div>`;
      grp.items.forEach(([icn, key, on]) => {
        h += `<a class="sb-item${on ? ' on' : ''}" data-key="${key}" title="${s[key]}">${ic(icn)}<span class="sb-label">${s[key]}</span></a>`;
      });
    });
    h += `<div class="sb-group">&nbsp;</div>`;
    FOOT_NAV.forEach(([icn, key]) => { h += `<a class="sb-item" data-key="${key}" title="${s[key]}">${ic(icn)}<span class="sb-label">${s[key]}</span></a>`; });
    $('#sbNav').innerHTML = h;
    $$('#sbNav .sb-item').forEach((a) => a.addEventListener('click', () => {
      if (a.classList.contains('on')) return;
      toast(`${a.dataset.key && s[a.dataset.key]} · ${s.soon}`);
    }));

    $('#sbPlan').innerHTML = `
      <div class="sb-plan-h"><b>${s.plan}</b><span class="sb-plan-tag">PRO</span></div>
      <div class="sb-plan-usage">${s.plan_usage('1,240', '2,000')}</div>
      <div class="sb-plan-bar"><i style="width:62%"></i></div>
      <button class="sb-up">${s.upgrade}</button>`;
    $('#sbPlan .sb-up').addEventListener('click', () => toast(`${s.upgrade} · ${s.soon}`));
  }

  /* ============================================================
     TOPBAR
     ============================================================ */
  function renderTopbar() {
    const s = S();
    $('#searchPh').textContent = s.search_ph;
    const mk = T.MARKETS.find((m) => m.code === (LS.get('market', 'FR'))) || T.MARKETS[0];
    $('#marketBtn').innerHTML = `<span class="flag">${mk.flag}</span><span class="mname">${mk.code}</span>${ic('chev')}`;
    $('#marketBtn').querySelector('svg').style.width = '13px';
    $('#liveLabel').textContent = `${s.live} · ${s.live_ago}`;
    $$('#langToggle button').forEach((b) => b.classList.toggle('on', b.dataset.l === lang));
  }

  /* ============================================================
     HEADER + PERIOD
     ============================================================ */
  function renderHeader() {
    const s = S();
    $('#pageTitle').textContent = `${s.greeting}, Alex`;
    $('#pageSub').textContent = s.sub_n(7);
    const seg = $('#periodSeg');
    seg.innerHTML = `<div class="seg-thumb"></div>` +
      ['24h', '7d', '30d'].map((p) => `<button data-p="${p}" class="${p === period ? 'on' : ''}">${s['p_' + (p === '24h' ? '24h' : p === '7d' ? '7d' : '30d')]}</button>`).join('');
    $$('#periodSeg button').forEach((b) => b.addEventListener('click', () => { period = b.dataset.p; $$('#periodSeg button').forEach((x) => x.classList.toggle('on', x === b)); positionSeg(seg); renderKPIs(); }));
    positionSeg(seg);
  }
  function positionSeg(seg) {
    const on = $('.on', seg); const thumb = $('.seg-thumb', seg);
    if (!on || !thumb) return;
    thumb.style.left = on.offsetLeft + 'px'; thumb.style.width = on.offsetWidth + 'px';
  }

  /* ============================================================
     KPI CARDS
     ============================================================ */
  function renderKPIs() {
    const s = S(), d = PERIOD_DELTA[period];
    const phaseBar = phaseOrder.map((k) => `<i style="flex:${phaseCount[k] || 0.0001};background:var(--${T.PHASES[k].v})"></i>`).join('');
    const phaseLegend = ['EMERGENT', 'EARLY_GROWTH', 'GROWTH'].map((k) => `<span><i class="pdot" style="background:var(--${T.PHASES[k].v})"></i>${T.PHASES[k][lang]}</span>`).join('');
    const cards = [
      { ico: 'target', label: s.kpi_active, val: buyCount, dec: 0, delta: d.active, deltaTxt: '+' + d.active, kind: 'spark', series: P.map((p) => p.tandor).slice(0, 14), col: 'var(--signal)' },
      { ico: 'gauge', label: s.kpi_score, val: avgScore, dec: 0, delta: d.score, deltaTxt: '+' + d.score.toFixed(1), kind: 'spark', series: scoreSeries, col: 'var(--buy)' },
      { ico: 'coins', label: s.kpi_margin, val: medMargin, dec: 1, unit: '€', delta: d.margin, deltaTxt: '+' + d.margin.toFixed(1) + '€', kind: 'spark', series: marginSeries, col: 'var(--signal)' },
      { ico: 'sparkles', label: s.kpi_emerg, val: emergCount, dec: 0, delta: d.emerg, deltaTxt: '+' + d.emerg, kind: 'phase' },
    ];
    $('#kpiRow').innerHTML = cards.map((c) => `
      <div class="kpi">
        <div class="k-label"><span class="k-ico">${ic(c.ico)}</span><span class="micro">${c.label}</span></div>
        <div class="k-val"><span class="cv" data-to="${c.val}" data-dec="${c.dec}">0</span>${c.unit ? `<span class="unit">${c.unit}</span>` : ''}</div>
        <div class="k-foot">
          <span class="k-delta up">${ic('arrowUR')}${c.deltaTxt}<span class="vs">${s.vs_prev}</span></span>
          ${c.kind === 'spark' ? `<span class="k-spark">${C.sparkline(c.series, { w: 108, h: 30, stroke: c.col, dot: true })}</span>` : ''}
        </div>
        ${c.kind === 'phase' ? `<div class="phase-bar">${phaseBar}</div><div class="phase-legend">${phaseLegend}</div>` : ''}
      </div>`).join('');
    $$('#kpiRow .k-delta svg').forEach((sv) => sv.style.width = '13px');
    $$('#kpiRow .cv').forEach((el) => countUp(el, +el.dataset.to, +el.dataset.dec));
  }

  /* ============================================================
     OPPORTUNITY FEED
     ============================================================ */
  function renderFeed() {
    const s = S();
    const champion = P.slice().sort((a, b) => b.tandor - a.tandor)[0];
    const rest = P.filter((p) => p.id !== champion.id).sort((a, b) => a.detectedHrs - b.detectedHrs).slice(0, 7);
    const list = [champion, ...rest];
    let rows = list.map((p, i) => {
      const ph = T.PHASES[p.phase], col = `var(--${ph.v})`;
      const up = p.growth >= 0;
      const ago = p.detectedHrs < 24 ? `${p.detectedHrs}${s.hr}` : `${Math.round(p.detectedHrs / 24)}${s.day}`;
      const ringCol = p.verdict === 'BUY' ? col : p.verdict === 'WATCH' ? 'var(--watch)' : 'var(--pass)';
      return `<div class="feed-row${i === 0 ? ' champion' : ''}" data-id="${p.id}">
        ${thumb(p)}
        <div class="feed-meta">
          <div class="feed-name">${i === 0 ? `<span class="champ-star">${ic('flame')}</span>` : ''}${p.name}</div>
          <div class="feed-sub2">
            <span class="badge phase-badge"><span class="pdot" style="background:${col}"></span>${ph[lang]}</span>
            <span>${T.CATS[p.cat][lang]}</span><span>·</span>
            <span>${s.detected} ${s.ago} ${ago}</span>
          </div>
        </div>
        <div class="feed-kpis">
          <span class="feed-spark">${C.sparkline(p.trend, { w: 64, h: 26, stroke: up ? 'var(--buy)' : 'var(--pass)', fill: false, sw: 1.6 })}</span>
          <span class="feed-growth ${up ? 'up' : 'down'}">${up ? '▲' : '▼'} ${up ? '+' : ''}${Math.round(p.growth * 100)}%<span style="color:var(--text-tertiary);font-weight:500">${s.growth_mo}</span></span>
          <span class="verdict ${T.VERDICTS[p.verdict].v}">${T.VERDICTS[p.verdict][lang]}</span>
        </div>
        <div class="feed-score" title="${s.score} ${p.tandor}">
          ${C.ring(p.tandor, ringCol, 40, 3.5)}<b>${p.tandor}</b>
        </div>
      </div>`;
    }).join('');
    $('#feedPanel').innerHTML = `
      <div class="panel-h">
        <div><div class="ttl">${s.feed}</div><div class="sub">${s.feed_sub}</div></div>
        <a class="panel-link" data-soon="${s.feed}">${s.view_all} ${ic('arrowUR')}</a>
      </div>
      <div class="feed-list">${rows}</div>`;
    $('#feedPanel .panel-link svg').style.width = '13px';
    $('#feedPanel .panel-link').addEventListener('click', () => toast(`${s.n_discovery} · ${s.soon}`));
    $$('#feedPanel .feed-row').forEach((r) => r.addEventListener('click', () => {
      const p = P.find((x) => x.id === r.dataset.id);
      toast(`${p.name} · ${s.open_detail} · ${s.soon}`);
    }));
  }

  /* ============================================================
     RADAR EXPRESS + SIGNALS
     ============================================================ */
  function renderRadarPanel() {
    const s = S();
    $('#radarPanel').innerHTML = `
      <div class="panel-h"><div><div class="ttl">${s.radar}</div><div class="sub">${s.radar_sub}</div></div></div>
      <div class="radar-wrap"><div class="radar-box" id="radarBox"></div></div>
      <div class="signals" id="signals"></div>`;
    C.renderRadar($('#radarBox'), P, { lang, onSelect: (p) => toast(`${p.name} · ${s.open_detail} · ${s.soon}`) });
    renderSignals();
  }
  function renderSignals() {
    const s = S();
    const topTrends = P.slice().sort((a, b) => b.trendsScore - a.trendsScore)[0];
    const topReddit = P.slice().sort((a, b) => b.redditScore - a.redditScore)[0];
    const topCorro = P.slice().sort((a, b) => (Math.min(b.trendsScore, b.redditScore)) - (Math.min(a.trendsScore, a.redditScore)))[0];
    const corroN = [topCorro.trendsScore > 60, topCorro.redditScore > 60, topCorro.growthScore > 60].filter(Boolean).length;
    const cards = [
      { ico: 'G', col: 'var(--azure)', kind: s.top_trends, name: topTrends.name, val: '+' + topTrends.trendsScore },
      { ico: 'r/', col: 'var(--reddit)', kind: s.top_reddit, name: topReddit.name, val: '+' + Math.round(topReddit.growth * 100) + '%' },
      { ico: '✓', col: 'var(--signal)', kind: s.top_corro, name: topCorro.name, val: corroN + '×' },
    ];
    $('#signals').innerHTML = `<div class="signals-h">${s.signals}</div>` + cards.map((c) => `
      <div class="sig-card">
        <span class="sig-ico" style="background:${c.col}">${c.ico}</span>
        <div class="sig-body"><div class="sig-kind">${c.kind}</div><div class="sig-name">${c.name}</div></div>
        <span class="sig-val" style="color:${c.col}">${c.val}</span>
      </div>`).join('');
  }

  /* ============================================================
     TREEMAP + HEATMAP
     ============================================================ */
  function renderBottom() {
    const s = S();
    $('#treePanel').innerHTML = `<div class="panel-h"><div><div class="ttl">${s.cat_dist}</div><div class="sub">${s.cat_sub}</div></div></div><div class="chart-box"><div class="tm-box" id="tmBox"></div></div>`;
    $('#heatPanel').innerHTML = `<div class="panel-h"><div><div class="ttl">${s.season}</div><div class="sub">${s.season_sub}</div></div></div><div class="chart-box"><div class="hm-box" id="hmBox"></div></div>`;
    C.renderTreemap($('#tmBox'), P, { lang, onCat: (cat) => toast(`${T.CATS[cat][lang]} · ${s.n_discovery} · ${s.soon}`) });
    C.renderHeatmap($('#hmBox'), { lang });
  }

  /* ============================================================
     COMMAND PALETTE
     ============================================================ */
  let cmdkSel = 0, cmdkItems = [];
  function buildCmdk(q) {
    const s = S();
    q = (q || '').toLowerCase().trim();
    const pages = [...NAV.flatMap((g) => g.items), ...FOOT_NAV].map(([icn, key]) => ({ type: 'page', icn, label: s[key], key }));
    const prods = P.map((p) => ({ type: 'product', label: p.name, sub: T.CATS[p.cat][lang], score: p.tandor, id: p.id }));
    const actions = [
      { type: 'action', icn: 'list', label: s.a_new_watch },
      { type: 'action', icn: 'bell', label: s.a_new_alert },
      { type: 'action', icn: 'download', label: s.a_export },
      { type: 'action', icn: 'sliders', label: s.a_toggle_theme, act: 'density' },
    ];
    const f = (arr) => q ? arr.filter((i) => i.label.toLowerCase().includes(q) || (i.sub || '').toLowerCase().includes(q)) : arr;
    const groups = [
      [s.cmd_products, f(prods)], [s.cmd_pages, f(pages)], [s.cmd_actions, f(actions)],
    ];
    let h = '', flat = [];
    groups.forEach(([title, arr]) => {
      if (!arr.length) return;
      h += `<div class="cmdk-group">${title}</div>`;
      arr.forEach((i) => {
        const idx = flat.length; flat.push(i);
        const icoHtml = i.type === 'product'
          ? `<span class="ci-ico" style="background:var(--${T.PHASES[P.find((p) => p.id === i.id).phase].v});color:#fff">${i.label.slice(0, 1)}</span>`
          : `<span class="ci-ico">${ic(i.icn)}</span>`;
        h += `<div class="cmdk-item" data-idx="${idx}">
          ${icoHtml}
          <div class="ci-main"><div class="ci-t">${i.label}</div>${i.sub ? `<div class="ci-s">${i.sub}</div>` : ''}</div>
          ${i.score != null ? `<span class="ci-r">${i.score}</span>` : i.type === 'page' ? `<span class="ci-s">↵</span>` : ''}
        </div>`;
      });
    });
    cmdkItems = flat; cmdkSel = 0;
    $('#cmdkList').innerHTML = h || `<div class="cmdk-group">${lang === 'fr' ? 'Aucun résultat' : 'No results'}</div>`;
    $$('#cmdkList .cmdk-item').forEach((it) => {
      it.addEventListener('mouseenter', () => { cmdkSel = +it.dataset.idx; highlightCmdk(); });
      it.addEventListener('click', () => runCmdk(+it.dataset.idx));
    });
    highlightCmdk();
  }
  function highlightCmdk() { $$('#cmdkList .cmdk-item').forEach((it) => it.classList.toggle('sel', +it.dataset.idx === cmdkSel)); }
  function runCmdk(idx) {
    const i = cmdkItems[idx]; if (!i) return; const s = S();
    closeAll();
    if (i.type === 'product') toast(`${i.label} · ${s.open_detail} · ${s.soon}`);
    else if (i.type === 'action' && i.act === 'density') { setDensity(density === 'comfort' ? 'compact' : 'comfort'); }
    else toast(`${i.label} · ${s.soon}`);
  }
  function openCmdk() {
    $('#scrim').classList.add('show'); $('#cmdk').classList.add('show');
    $('#cmdkInput').value = ''; buildCmdk(''); setTimeout(() => $('#cmdkInput').focus(), 30);
  }

  /* ============================================================
     NOTIFICATIONS
     ============================================================ */
  function renderNotif() {
    const s = S();
    $('#notifTitle').textContent = s.notif;
    $('#notifSub').textContent = `3 ${s.notif_unread}`;
    $('#markRead').textContent = s.mark_read;
    const items = lang === 'fr' ? [
      { ic: 'flame', col: 'var(--signal)', t: '<b>Cervical Neck Massager</b> a franchi votre seuil de vélocité.', time: 'il y a 18 min', unread: true },
      { ic: 'sparkles', col: 'var(--ph-emergent)', t: '<b>LED Dog Collar</b> est passé en phase <b>Émergent</b>.', time: 'il y a 1 h', unread: true },
      { ic: 'signal', col: 'var(--watch)', t: 'Alerte saturation : <b>Sunset Projection Lamp</b> — vendeurs +14%.', time: 'il y a 3 h', unread: true },
      { ic: 'list', col: 'var(--azure)', t: 'Votre watchlist <b>Wellness FR</b> a gagné +2,4 de score moyen.', time: 'il y a 6 h', unread: false },
      { ic: 'check', col: 'var(--buy)', t: 'Collecte CJ terminée — 412 produits réévalués.', time: 'il y a 8 h', unread: false },
    ] : [
      { ic: 'flame', col: 'var(--signal)', t: '<b>Cervical Neck Massager</b> crossed your velocity threshold.', time: '18 min ago', unread: true },
      { ic: 'sparkles', col: 'var(--ph-emergent)', t: '<b>LED Dog Collar</b> moved into the <b>Emergent</b> phase.', time: '1 h ago', unread: true },
      { ic: 'signal', col: 'var(--watch)', t: 'Saturation alert: <b>Sunset Projection Lamp</b> — sellers +14%.', time: '3 h ago', unread: true },
      { ic: 'list', col: 'var(--azure)', t: 'Your watchlist <b>Wellness FR</b> gained +2.4 avg score.', time: '6 h ago', unread: false },
      { ic: 'check', col: 'var(--buy)', t: 'CJ collection finished — 412 products re-scored.', time: '8 h ago', unread: false },
    ];
    $('#notifBody').innerHTML = items.map((n) => `
      <div class="notif-item${n.unread ? ' unread' : ''}">
        <span class="notif-ico" style="background:${n.col}">${ic(n.ic)}</span>
        <div><div class="notif-t">${n.t}</div><div class="notif-time">${n.time}</div></div>
      </div>`).join('');
  }

  /* ============================================================
     POPOVERS
     ============================================================ */
  function placePop(pop, anchor, align) {
    const r = anchor.getBoundingClientRect();
    pop.style.top = (r.bottom + 8) + 'px';
    if (align === 'right') pop.style.left = Math.max(8, r.right - pop.offsetWidth) + 'px';
    else pop.style.left = r.left + 'px';
  }
  function buildMarketPop() {
    const s = S(), cur = LS.get('market', 'FR');
    $('#marketPop').innerHTML = `<div class="pop-h">${lang === 'fr' ? 'Marché' : 'Market'}</div>` + T.MARKETS.map((m) => `
      <div class="pop-item${m.code === cur ? ' on' : ''}" data-m="${m.code}"><span style="font-size:15px">${m.flag}</span>${m[lang]}<span style="margin-left:auto;font-family:var(--font-mono);font-size:11px;color:var(--text-tertiary)">${m.code}</span>${m.code === cur ? `<span class="pop-check" style="margin-left:6px">${ic('check')}</span>` : ''}</div>`).join('');
    $$('#marketPop .pop-item').forEach((it) => it.addEventListener('click', () => { LS.set('market', it.dataset.m); renderTopbar(); closeAll(); buildMarketPop(); }));
    $$('#marketPop .pop-check svg').forEach((sv) => sv.style.width = '15px');
  }
  function buildLivePop() {
    const s = S();
    $('#livePop').innerHTML = `<div class="pop-h">${s.live_pipeline}</div>
      ${[['run_cj', 'ok', s.ok], ['run_trends', 'warn', s.limited], ['run_reddit', 'ok', s.ok]].map(([k, st, lbl]) => `
        <div class="pipe-row"><span class="name">${k === 'run_reddit' ? 'r/' : k === 'run_trends' ? 'G' : 'CJ'} ${s[k]}</span><span class="st ${st}"><span class="pdot"></span>${lbl}</span></div>`).join('')}
      <div class="pop-sep"></div>
      <div class="pipe-row"><span class="name">${ic('refresh')}${s.next_run}</span><span class="st" style="color:var(--text-secondary)">${s.in_min}</span></div>`;
    $('#livePop .pipe-row svg').style.width = '14px';
  }
  function buildAvatarPop() {
    const s = S();
    $('#avatarPop').innerHTML = `
      <div style="padding:8px 10px 10px;display:flex;gap:10px;align-items:center;border-bottom:1px solid var(--border-subtle);margin-bottom:5px">
        <div class="tb-avatar" style="cursor:default">A</div>
        <div><div style="font-size:13px;font-weight:700">Alex Morel</div><div style="font-size:11px;color:var(--text-tertiary)">alex@tandor.io</div></div>
      </div>
      <div class="pop-item" data-act="account">${ic('user')}${s.n_account}</div>
      <div class="pop-item" data-act="settings">${ic('settings')}${s.n_settings}</div>
      <div class="pop-item" data-act="billing">${ic('card')}${s.n_billing}</div>
      <div class="pop-sep"></div>
      <div class="pop-item" data-act="lang">${ic('hash')}${lang === 'fr' ? 'Langue : Français' : 'Language: English'}</div>`;
    $$('#avatarPop .pop-item').forEach((it) => it.addEventListener('click', () => {
      const a = it.dataset.act; closeAll();
      if (a === 'lang') setLang(lang === 'fr' ? 'en' : 'fr');
      else toast(`${s['n_' + a]} · ${s.soon}`);
    }));
    $$('#avatarPop .pop-item svg').forEach((sv) => sv.style.width = '16px');
  }
  function togglePop(pop, anchor, align, builder) {
    const open = pop.classList.contains('show');
    closeAll();
    if (!open) { builder(); pop.classList.add('show'); placePop(pop, anchor, align); }
  }

  /* ============================================================
     TABBAR (mobile)
     ============================================================ */
  function renderTabbar() {
    const s = S();
    const tabs = [['home', 'n_home', true], ['compass', 'n_discovery'], ['radar', 'n_radar'], ['bookmark', 'n_saved'], ['bell', 'n_alerts']];
    $('#tabbar').innerHTML = tabs.map(([icn, key, on]) => `<button class="tab${on ? ' on' : ''}" data-key="${key}">${ic(icn)}<span>${s[key]}</span></button>`).join('');
    $$('#tabbar .tab').forEach((t) => t.addEventListener('click', () => { if (!t.classList.contains('on')) toast(`${s[t.dataset.key]} · ${s.soon}`); }));
  }

  /* ============================================================
     CLOSE / OVERLAY HANDLING
     ============================================================ */
  function closeAll() {
    $('#scrim').classList.remove('show');
    $('#cmdk').classList.remove('show');
    $('#notifDrawer').classList.remove('show');
    $$('.popover').forEach((p) => p.classList.remove('show'));
  }

  /* ============================================================
     TWEAKS (host protocol)
     ============================================================ */
  function applyAccent(a) {
    const c = ACCENTS[a] || ACCENTS.indigo;
    const r = document.documentElement.style;
    r.setProperty('--signal', c.s); r.setProperty('--signal-strong', c.ss);
    r.setProperty('--signal-tint', c.tint); r.setProperty('--signal-glow', c.glow);
  }
  function setAccent(a, persist) {
    accent = a; applyAccent(a); LS.set('accent', a);
    $$('#twkAccent .twk-sw').forEach((sw) => sw.classList.toggle('on', sw.dataset.a === a));
    // re-render charts that bake colours
    renderRadarPanel(); renderBottom();
    if (persist) postTweak({ accent: a });
  }
  function setDensity(d, persist) {
    density = d; document.body.classList.toggle('dense', d === 'compact'); LS.set('density', d);
    $$('#twkDensity button').forEach((b) => b.classList.toggle('on', b.dataset.d === d));
    requestAnimationFrame(() => { positionSeg($('#periodSeg')); reflowCharts(); });
    if (persist) postTweak({ density: d });
  }
  function buildTweaks() {
    const s = S();
    $('#twkAccentLbl').textContent = lang === 'fr' ? 'Couleur d’accent' : 'Signal accent';
    $('#twkDensityLbl').textContent = lang === 'fr' ? 'Densité' : 'Card density';
    const sw = { indigo: 'oklch(0.52 0.16 264)', teal: 'oklch(0.6 0.115 180)', amber: 'oklch(0.68 0.135 66)' };
    $('#twkAccent').innerHTML = Object.keys(sw).map((k) => `<button class="twk-sw${k === accent ? ' on' : ''}" data-a="${k}" style="background:${sw[k]}" title="${k}"></button>`).join('');
    $$('#twkAccent .twk-sw').forEach((b) => b.addEventListener('click', () => setAccent(b.dataset.a, true)));
    const dens = lang === 'fr' ? { comfort: 'Confort', compact: 'Compact' } : { comfort: 'Comfort', compact: 'Compact' };
    $('#twkDensity').innerHTML = Object.keys(dens).map((k) => `<button class="${k === density ? 'on' : ''}" data-d="${k}">${dens[k]}</button>`).join('');
    $$('#twkDensity button').forEach((b) => b.addEventListener('click', () => setDensity(b.dataset.d, true)));
  }
  function postTweak(edits) { try { window.parent.postMessage({ type: '__edit_mode_set_keys', edits }, '*'); } catch (e) {} }
  // host protocol
  window.addEventListener('message', (e) => {
    const t = e && e.data && e.data.type;
    if (t === '__activate_edit_mode') $('#twk').classList.add('show');
    else if (t === '__deactivate_edit_mode') $('#twk').classList.remove('show');
  });
  try { window.parent.postMessage({ type: '__edit_mode_available' }, '*'); } catch (e) {}
  $('#twkClose').addEventListener('click', () => { $('#twk').classList.remove('show'); try { window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*'); } catch (e) {} });

  /* ============================================================
     LANG
     ============================================================ */
  function setLang(l) { lang = l; LS.set('lang', l); document.documentElement.lang = l; renderAll(); }

  /* ============================================================
     resize → reflow charts
     ============================================================ */
  let rt;
  function reflowCharts() {
    if ($('#radarBox')) C.renderRadar($('#radarBox'), P, { lang, onSelect: (p) => toast(`${p.name} · ${S().open_detail} · ${S().soon}`) });
    if ($('#tmBox')) C.renderTreemap($('#tmBox'), P, { lang, onCat: (cat) => toast(`${T.CATS[cat][lang]} · ${S().n_discovery} · ${S().soon}`) });
    if ($('#hmBox')) C.renderHeatmap($('#hmBox'), { lang });
  }
  addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { positionSeg($('#periodSeg')); reflowCharts(); }, 180); });

  /* ============================================================
     RENDER ALL
     ============================================================ */
  function renderAll() {
    renderSidebar(); renderTopbar(); renderHeader(); renderKPIs();
    renderFeed(); renderRadarPanel(); renderBottom(); renderNotif(); renderTabbar(); buildTweaks();
  }

  /* ============================================================
     WIRE STATIC CONTROLS
     ============================================================ */
  function wire() {
    $('#collapseBtn').innerHTML = ic('list');
    $('#collapseBtn').querySelector('svg').style.width = '16px';
    $('#app').classList.toggle('collapsed', collapsed);
    $('#collapseBtn').addEventListener('click', () => { collapsed = !collapsed; $('#app').classList.toggle('collapsed', collapsed); LS.set('collapsed', collapsed ? '1' : '0'); requestAnimationFrame(reflowCharts); });

    $('#searchBtn').addEventListener('click', openCmdk);
    $('#bellBtn').addEventListener('click', (e) => { e.stopPropagation(); const open = $('#notifDrawer').classList.contains('show'); closeAll(); if (!open) { $('#scrim').classList.add('show'); $('#notifDrawer').classList.add('show'); } });
    $('#notifClose').addEventListener('click', closeAll);
    $('#markRead').addEventListener('click', () => { $$('#notifBody .notif-item').forEach((n) => n.classList.remove('unread')); $('#bellBadge').style.display = 'none'; $('#notifSub').textContent = '0 ' + S().notif_unread; });
    $('#marketBtn').addEventListener('click', (e) => { e.stopPropagation(); togglePop($('#marketPop'), $('#marketBtn'), 'left', buildMarketPop); });
    $('#liveBtn').addEventListener('click', (e) => { e.stopPropagation(); togglePop($('#livePop'), $('#liveBtn'), 'left', buildLivePop); });
    $('#avatarBtn').addEventListener('click', (e) => { e.stopPropagation(); togglePop($('#avatarPop'), $('#avatarBtn'), 'right', buildAvatarPop); });
    $$('#langToggle button').forEach((b) => b.addEventListener('click', () => setLang(b.dataset.l)));

    $('#scrim').addEventListener('click', closeAll);
    $('#cmdkInput').addEventListener('input', (e) => buildCmdk(e.target.value));
    $('#cmdkInput').addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); cmdkSel = Math.min(cmdkSel + 1, cmdkItems.length - 1); highlightCmdk(); scrollSel(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); cmdkSel = Math.max(cmdkSel - 1, 0); highlightCmdk(); scrollSel(); }
      else if (e.key === 'Enter') { e.preventDefault(); runCmdk(cmdkSel); }
    });
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); const open = $('#cmdk').classList.contains('show'); if (open) closeAll(); else openCmdk(); }
      else if (e.key === 'Escape') closeAll();
    });
    // close popovers on outside click / scroll
    $('#main').addEventListener('scroll', () => $$('.popover').forEach((p) => p.classList.remove('show')));
    document.addEventListener('click', (e) => { if (!e.target.closest('.popover') && !e.target.closest('#marketBtn,#liveBtn,#avatarBtn')) $$('.popover').forEach((p) => p.classList.remove('show')); });
  }
  function scrollSel() { const el = $('#cmdkList .cmdk-item.sel'); if (el) { const list = $('#cmdkList'); const r = el.getBoundingClientRect(), lr = list.getBoundingClientRect(); if (r.bottom > lr.bottom) list.scrollTop += r.bottom - lr.bottom; if (r.top < lr.top) list.scrollTop -= lr.top - r.top; } }

  /* ============================================================
     reveal entrance
     ============================================================ */
  function revealObserve() {
    if (reduced) return;
    $$('.rv').forEach((el, i) => { el.style.setProperty('--rvd', (i * 60) + 'ms'); });
  }

  /* ============================================================
     INIT
     ============================================================ */
  document.documentElement.lang = lang;
  applyAccent(accent);
  if (density === 'compact') document.body.classList.add('dense');
  wire();
  renderAll();
  revealObserve();
}
