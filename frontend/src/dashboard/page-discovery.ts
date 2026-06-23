/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-discovery.js   (Product Discovery)
   Dense filterable catalogue: filter rail, sortable data-grid or
   card grid, search, pagination, click → product dossier drawer.
   ============================================================ */
export function mountDiscovery() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic, clamp = Sh.clamp;
  // Infinite scroll : taille du lot ajouté à chaque fois que la sentinelle entre
  // dans le viewport. Quand la fenêtre locale approche du bout des produits déjà
  // chargés en mémoire, on déclenche T.loadMore() (fetch API du lot suivant).
  const WINDOW = 24;
  let io = null;          // IntersectionObserver courant (réinitialisé à chaque render)
  let fetching = false;   // garde anti double-fetch réseau

  const STR = {
    en: { title: 'Product Discovery', sub: 'scored catalogue · live signal', search: 'Filter by name or category…',
      filters: 'Filters', reset: 'Reset', verdict: 'Verdict', phase: 'Phase', category: 'Category',
      min_score: 'Min Tandor score', min_margin: 'Min net margin', all: 'All',
      results: 'products', sort: 'Sort', view_table: 'Table', view_cards: 'Cards',
      s_score: 'Tandor score', s_growth: 'Growth', s_margin: 'Margin', s_potential: 'Potential', s_reddit: 'Reddit', s_trends: 'Trends', s_recent: 'Recency', s_sat: 'Saturation',
      c_prod: 'Product', c_score: 'Score', c_verdict: 'Verdict', c_phase: 'Phase', c_margin: 'Margin', c_vel: 'Velocity', c_sat: 'Sellers', c_pot: 'Potential', c_trend: '30d',
      empty_t: 'No product matches', empty_s: 'Your filters are too tight. Loosen the most restrictive one to see more opportunities.', loosen: 'Loosen filters',
      mo: '/mo', clearall: 'Clear all', detected: 'detected',
      trap: 'Money trap', risky: 'Risky', viable: 'Viable',
      sold: 'AliExpress sold', no_demand: 'No demand data', no_hist: 'History building', no_hist_s: 'Not enough nights collected yet',
      sold_unit: 'sold', median: 'median' },
    fr: { title: 'Product Discovery', sub: 'catalogue scoré · signal en direct', search: 'Filtrer par nom ou catégorie…',
      filters: 'Filtres', reset: 'Réinitialiser', verdict: 'Verdict', phase: 'Phase', category: 'Catégorie',
      min_score: 'Score Tandor min.', min_margin: 'Marge nette min.', all: 'Tous',
      results: 'produits', sort: 'Tri', view_table: 'Tableau', view_cards: 'Cartes',
      s_score: 'Score Tandor', s_growth: 'Croissance', s_margin: 'Marge', s_potential: 'Potentiel', s_reddit: 'Reddit', s_trends: 'Trends', s_recent: 'Récence', s_sat: 'Saturation',
      c_prod: 'Produit', c_score: 'Score', c_verdict: 'Verdict', c_phase: 'Phase', c_margin: 'Marge', c_vel: 'Vélocité', c_sat: 'Vendeurs', c_pot: 'Potentiel', c_trend: '30j',
      empty_t: 'Aucun produit ne correspond', empty_s: 'Vos filtres sont trop stricts. Assouplissez le plus restrictif pour voir plus d’opportunités.', loosen: 'Assouplir les filtres',
      mo: '/mois', clearall: 'Tout effacer', detected: 'détecté',
      trap: 'Piège à fric', risky: 'Risqué', viable: 'Viable',
      sold: 'Vendus AliExpress', no_demand: 'Pas de données de demande', no_hist: 'Historique en cours', no_hist_s: 'Pas encore assez de nuits collectées',
      sold_unit: 'vendus', median: 'médiane' },
  };
  const L = () => STR[Sh.lang];
  const money = Sh.money, pct = Sh.pct, fmt = Sh.fmt;

  const PHASE_ORDER = ['EMERGENT', 'EARLY_GROWTH', 'GROWTH', 'MATURE', 'PEAK', 'DECLINING'];
  const SORTS = [
    ['s_score', (p) => p.tandor], ['s_growth', (p) => p.growth], ['s_margin', (p) => p.net],
    ['s_potential', (p) => p.organic], ['s_reddit', (p) => p.redditScore], ['s_trends', (p) => p.trendsScore],
    ['s_recent', (p) => -p.detectedHrs], ['s_sat', (p) => -p.listed],
  ];

  let state = { verdicts: new Set(), phases: new Set(), cats: new Set(), minScore: 0, minMargin: 0, q: '', sortKey: 's_score', dir: -1, view: 'table', shown: WINDOW, loading: true };

  function filtered() {
    const q = state.q.trim().toLowerCase();
    let arr = P.filter((p) => {
      if (state.verdicts.size && !state.verdicts.has(p.trapVerdict)) return false;
      if (state.phases.size && !state.phases.has(p.phase)) return false;
      if (state.cats.size && !state.cats.has(p.cat)) return false;
      if (p.tandor < state.minScore) return false;
      if (p.net < state.minMargin) return false;
      if (q && !(p.name.toLowerCase().includes(q) || T.CATS[p.cat][Sh.lang].toLowerCase().includes(q) || T.CATS[p.cat].en.toLowerCase().includes(q))) return false;
      return true;
    });
    const sf = SORTS.find((s) => s[0] === state.sortKey)[1];
    arr.sort((a, b) => (sf(a) - sf(b)) * state.dir);
    return arr;
  }

  function render() {
    const s = L();
    const cats = Object.keys(T.CATS).filter((c) => P.some((p) => p.cat === c));
    const canvas = $('#canvas');
    canvas.innerHTML = `
      <div class="page-head rv">
        <div>
          <h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div>
        </div>
        <div class="tbar" style="margin:0">
          <div class="seg-view" id="viewSeg">
            <button data-v="table" class="${state.view === 'table' ? 'on' : ''}" title="${s.view_table}">${ic('rows')}</button>
            <button data-v="cards" class="${state.view === 'cards' ? 'on' : ''}" title="${s.view_cards}">${ic('grid')}</button>
          </div>
          <div class="sel-wrap">
            <select class="sel" id="sortSel">${SORTS.map(([k]) => `<option value="${k}" ${k === state.sortKey ? 'selected' : ''}>${s.sort} · ${s[k]}</option>`).join('')}</select>
          </div>
        </div>
      </div>
      <div class="layout-rail">
        <aside class="flt-rail rv">
          <div class="flt-card">
            <div class="flt-sec">
              <div class="search-inp">${ic('search')}<input id="qInp" placeholder="${s.search}" value="${state.q}" /></div>
            </div>
            <div class="flt-sec">
              <div class="flt-sec-h">${s.verdict}</div>
              <div class="pill-row" id="verdictPills">${[['VIABLE', s.viable], ['RISKY', s.risky], ['TRAP', s.trap]].map(([v, lbl]) => `<button class="pill ${state.verdicts.has(v) ? 'on' : ''}" data-v="${v}">${lbl}<span class="chk-cnt" style="margin:0">${P.filter((p) => p.trapVerdict === v).length}</span></button>`).join('')}</div>
            </div>
            <div class="flt-sec">
              <div class="flt-sec-h">${s.phase}</div>
              <div class="chk-list" id="phaseChks">${PHASE_ORDER.map((ph) => `<label class="chk ${state.phases.has(ph) ? 'on' : ''}" data-ph="${ph}"><span class="chk-dot" style="background:var(--${T.PHASES[ph].v})"></span>${T.PHASES[ph][Sh.lang]}<span class="chk-cnt">${P.filter((p) => p.phase === ph).length}</span></label>`).join('')}</div>
            </div>
            <div class="flt-sec">
              <div class="flt-sec-h">${s.min_score}</div>
              <div class="range-wrap"><div class="range-val"><span>0</span><b id="scoreVal">${state.minScore}</b><span>100</span></div>
                <input type="range" class="rng" id="scoreRng" min="0" max="100" step="1" value="${state.minScore}" /></div>
            </div>
            <div class="flt-sec">
              <div class="flt-sec-h">${s.min_margin}</div>
              <div class="range-wrap"><div class="range-val"><span>0€</span><b id="marginVal">${money(state.minMargin)}</b><span>20€</span></div>
                <input type="range" class="rng" id="marginRng" min="0" max="20" step="1" value="${state.minMargin}" /></div>
            </div>
            <div class="flt-sec">
              <div class="flt-sec-h">${s.category}</div>
              <div class="chk-list" id="catChks">${cats.map((c) => `<label class="chk ${state.cats.has(c) ? 'on' : ''}" data-c="${c}"><span class="box">${ic('check')}</span>${T.CATS[c][Sh.lang]}<span class="chk-cnt">${P.filter((p) => p.cat === c).length}</span></label>`).join('')}</div>
            </div>
            <div class="flt-foot"><button class="btn-ghost" id="resetBtn">${s.reset}</button></div>
          </div>
        </aside>
        <div class="rv">
          <div class="chips" id="chips"></div>
          <div id="results"></div>
        </div>
      </div>`;

    // wire toolbar
    $$('#viewSeg button').forEach((b) => b.addEventListener('click', () => { state.view = b.dataset.v; state.shown = WINDOW; render(); }));
    $('#sortSel').addEventListener('change', (e) => { state.sortKey = e.target.value; state.shown = WINDOW; updateResults(); });
    $('#qInp').addEventListener('input', (e) => { state.q = e.target.value; state.shown = WINDOW; updateResults(); });
    $$('#verdictPills .pill').forEach((b) => b.addEventListener('click', () => { toggle(state.verdicts, b.dataset.v); b.classList.toggle('on'); state.shown = WINDOW; updateResults(); }));
    $$('#phaseChks .chk').forEach((b) => b.addEventListener('click', () => { toggle(state.phases, b.dataset.ph); b.classList.toggle('on'); state.shown = WINDOW; updateResults(); }));
    $$('#catChks .chk').forEach((b) => b.addEventListener('click', () => { toggle(state.cats, b.dataset.c); b.classList.toggle('on'); state.shown = WINDOW; updateResults(); }));
    $('#scoreRng').addEventListener('input', (e) => { state.minScore = +e.target.value; $('#scoreVal').textContent = state.minScore; state.shown = WINDOW; updateResults(); });
    $('#marginRng').addEventListener('input', (e) => { state.minMargin = +e.target.value; $('#marginVal').textContent = money(state.minMargin); state.shown = WINDOW; updateResults(); });
    $('#resetBtn').addEventListener('click', resetAll);

    if (state.loading) { renderSkeleton(); setTimeout(() => { state.loading = false; updateResults(); }, 480); }
    else updateResults();
  }

  function toggle(set, v) { set.has(v) ? set.delete(v) : set.add(v); }
  function resetAll() { state.verdicts.clear(); state.phases.clear(); state.cats.clear(); state.minScore = 0; state.minMargin = 0; state.q = ''; state.shown = WINDOW; render(); }

  function chipList() {
    const s = L(); const chips = [];
    const trapLbl = { VIABLE: s.viable, RISKY: s.risky, TRAP: s.trap };
    state.verdicts.forEach((v) => chips.push([`${s.verdict}: ${trapLbl[v] || v}`, () => state.verdicts.delete(v)]));
    state.phases.forEach((v) => chips.push([T.PHASES[v][Sh.lang], () => state.phases.delete(v)]));
    state.cats.forEach((v) => chips.push([T.CATS[v][Sh.lang], () => state.cats.delete(v)]));
    if (state.minScore > 0) chips.push([`${s.s_score} ≥ ${state.minScore}`, () => state.minScore = 0]);
    if (state.minMargin > 0) chips.push([`${s.c_margin} ≥ ${money(state.minMargin)}`, () => state.minMargin = 0]);
    return chips;
  }

  function updateResults() {
    const s = L(), arr = filtered();
    // chips
    const chips = chipList();
    $('#chips').innerHTML = chips.length
      ? chips.map((c, i) => `<span class="fchip" data-i="${i}">${c[0]}<button>${ic('x')}</button></span>`).join('') + `<button class="clear-all" id="clearAll">${s.clearall}</button>`
      : `<span class="count mono">${arr.length} ${s.results}</span>`;
    $$('#chips .fchip button').forEach((b) => b.addEventListener('click', () => { chips[+b.parentElement.dataset.i][1](); render(); }));
    if ($('#clearAll')) $('#clearAll').addEventListener('click', resetAll);

    if (state.loading) { renderSkeleton(); return; }
    if (!arr.length) { renderEmpty(); return; }

    // Fenêtre infinie : on n'affiche que les `shown` premiers résultats filtrés.
    // La sentinelle en bas (IntersectionObserver) augmente `shown` et, si besoin,
    // déclenche un fetch API du lot suivant via T.loadMore().
    state.shown = clamp(state.shown, WINDOW, Math.max(WINDOW, arr.length));
    const slice = arr.slice(0, state.shown);
    // Reste-t-il des produits à montrer ? localement (déjà chargés) ou côté API.
    const moreLocal = state.shown < arr.length;
    const moreApi = !!(T.hasMore);
    const hasMore = moreLocal || moreApi;

    if (state.view === 'table') renderTable(slice, arr.length, hasMore);
    else renderCards(slice, arr.length, hasMore);

    setupSentinel();
  }

  /* ---- infinite scroll : sentinelle + chargement de lots ---- */
  function setupSentinel() {
    if (io) { io.disconnect(); io = null; }
    const sentinel = $('#scrollSentinel');
    if (!sentinel) return;
    // root = la zone scrollable principale du dashboard (#main).
    const root = $('#main') || null;
    io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) loadNext();
    }, { root, rootMargin: '600px 0px' });
    io.observe(sentinel);
  }

  function loadNext() {
    const arr = filtered();
    // 1. Encore des produits déjà chargés localement -> on agrandit la fenêtre.
    if (state.shown < arr.length) {
      state.shown += WINDOW;
      updateResults();
      return;
    }
    // 2. Fenêtre au bout du local : on tente de récupérer plus depuis l'API.
    if (T.hasMore && !fetching && typeof T.loadMore === 'function') {
      fetching = true;
      setLoaderBusy(true);
      T.loadMore().then((res) => {
        fetching = false;
        if (res && res.added > 0) {
          state.shown += WINDOW;   // révèle les nouveaux produits ajoutés à P
        }
        updateResults();
      }).catch(() => { fetching = false; updateResults(); });
    }
  }

  function setLoaderBusy(on) {
    const el = $('#scrollLoader');
    if (el) el.style.display = on ? '' : 'none';
  }

  function ringCol(p) { return p.verdict === 'BUY' ? `var(--${T.PHASES[p.phase].v})` : p.verdict === 'WATCH' ? 'var(--watch)' : 'var(--pass)'; }

  /* ---- REAL trap verdict (TRAP|RISKY|VIABLE) — the honest buy signal ---- */
  function trapTag(p) {
    const s = L();
    if (p.trapVerdict === 'TRAP')   return { lbl: s.trap,   cls: 'pass',  col: 'var(--pass)' };
    if (p.trapVerdict === 'RISKY')  return { lbl: s.risky,  cls: 'watch', col: 'var(--watch)' };
    if (p.trapVerdict === 'VIABLE') return { lbl: s.viable, cls: 'buy',   col: 'var(--buy)' };
    return null;
  }
  /* ---- REAL demand evidence: AliExpress sold + salesScore (null = empty-state) ---- */
  function soldText(p) {
    const s = L();
    if (p.aliExpressSold == null) return null;
    let t = `${fmt(p.aliExpressSold)} ${s.sold_unit}`;
    if (p.aliExpressMedianSold != null) t += ` · ${fmt(p.aliExpressMedianSold)} ${s.median}`;
    return t;
  }
  /* ---- per-product sparkline ONLY when a real demand curve exists ---- */
  function sparkCell(p, up, w, h) {
    if (!p.hasRealHistory) {
      return `<span class="row-spark micro" style="color:var(--text-tertiary);font-size:10px;white-space:nowrap" title="${L().no_hist_s}">— ${L().no_hist}</span>`;
    }
    return `<span class="row-spark">${C.sparkline(p.trend, { w, h, stroke: up ? 'var(--buy)' : 'var(--pass)', fill: false, sw: 1.6 })}</span>`;
  }

  function renderTable(slice, total, hasMore) {
    const s = L();
    const cols = [
      ['c_prod', 's_score', false, 'prod'], // header handled specially
    ];
    const head = `
      <th data-k="s_score" class="${sortable('s_score')}">${s.c_prod}</th>
      <th data-k="s_score" class="num ${sortable('s_score')}">${s.c_score}${ar('s_score')}</th>
      <th data-k="s_score" style="cursor:default">${s.c_verdict}</th>
      <th>${s.c_phase}</th>
      <th data-k="s_margin" class="num ${sortable('s_margin')}">${s.c_margin}${ar('s_margin')}</th>
      <th class="num" style="cursor:default">${s.sold}</th>
      <th data-k="s_sat" class="num ${sortable('s_sat')}">${s.c_sat}${ar('s_sat')}</th>
      <th data-k="s_potential" class="num ${sortable('s_potential')}">${s.c_pot}${ar('s_potential')}</th>
      <th class="num">${s.c_trend}</th>`;
    const rows = slice.map((p) => {
      const up = p.growth >= 0;
      const trap = trapTag(p);
      return `<tr data-id="${p.id}">
        <td><div class="cell-prod">${Sh.thumb(p, 36)}<div><div class="cp-name">${p.name}</div><div class="cp-sub">${p.id}</div></div></div></td>
        <td class="num"><span class="score-cell"><span class="mini-ring">${C.ring(p.tandor, ringCol(p), 26, 3)}</span><b>${p.tandor}</b></span></td>
        <td>${trap ? `<span class="verdict ${trap.cls}">${trap.lbl}</span>` : `<span class="verdict ${T.VERDICTS[p.verdict].v}">${T.VERDICTS[p.verdict][Sh.lang]}</span>`}</td>
        <td><span class="badge phase-badge"><span class="pdot" style="background:var(--${T.PHASES[p.phase].v})"></span>${T.PHASES[p.phase][Sh.lang]}</span></td>
        <td class="num">${money(p.net, 1)}<span style="color:var(--text-tertiary)"> · ${pct(p.margin_pct * 100)}</span></td>
        <td class="num">${soldText(p) ? `<span class="mono" title="${L().sold}">${soldText(p)}</span>` : `<span style="color:var(--text-tertiary)">—</span>`}</td>
        <td class="num">${p.listed}</td>
        <td class="num">${p.organic}</td>
        <td class="num">${sparkCell(p, up, 60, 22)}</td>
      </tr>`;
    }).join('');
    $('#results').innerHTML = `
      <div class="dg-wrap">
        <div class="dg-scroll"><table class="dg"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>
        ${scrollFoot(slice.length, total, hasMore)}
      </div>`;
    wireSort(); wireRows();
  }

  function renderCards(slice, total, hasMore) {
    const s = L();
    const cards = slice.map((p) => {
      const up = p.growth >= 0, col = `var(--${T.PHASES[p.phase].v})`;
      const hue = p.catHue, a = `oklch(0.7 0.1 ${hue})`, b = `oklch(0.52 0.12 ${hue})`;
      const trap = trapTag(p);
      // Demand evidence: real AliExpress sold + salesScore (honest empty-state when null).
      const sold = soldText(p);
      const demandLine = sold
        ? `<div class="pcard-meta" style="margin-top:2px"><b style="color:var(--text-secondary)">${sold}</b>${p.salesScore != null ? ` · ${s.s_growth}: ${p.salesScore}` : ''}</div>`
        : `<div class="pcard-meta" style="margin-top:2px;color:var(--text-tertiary)">${s.no_demand}</div>`;
      // Sparkline only when a real demand curve exists; else honest empty-state.
      const sparkRow = p.hasRealHistory
        ? `<div style="margin:8px 0 2px">${C.sparkline(p.trend, { w: 220, h: 26, stroke: up ? 'var(--buy)' : 'var(--pass)', fill: true, sw: 1.6 })}</div>`
        : `<div class="pcard-meta" style="margin:8px 0 2px;color:var(--text-tertiary);font-size:11px">— ${s.no_hist} · ${s.no_hist_s}</div>`;
      return `<div class="pcard" data-id="${p.id}">
        <div class="pcard-media">
          <div class="ph-stripe" style="background:repeating-linear-gradient(135deg, ${a} 0 7px, ${b} 7px 14px);opacity:.9"></div>
          <span class="pcard-phase"><span class="badge phase-badge" style="background:var(--surface-1)"><span class="pdot" style="background:${col}"></span>${T.PHASES[p.phase][Sh.lang]}</span></span>
          <span class="pcard-ring">${C.ring(p.tandor, ringCol(p), 40, 3.5)}<b>${p.tandor}</b></span>
        </div>
        <div class="pcard-body">
          <div class="pcard-name">${p.name}</div>
          <div class="pcard-meta">${T.CATS[p.cat][Sh.lang]} · ${p.listed} ${s.c_sat.toLowerCase()}</div>
          ${demandLine}
          ${sparkRow}
          <div class="pcard-kpi">
            <span class="mg-margin">${money(p.net, 1)} <span style="color:var(--text-tertiary);font-weight:500">${pct(p.margin_pct * 100)}</span></span>
            <span class="micro mono" style="color:var(--text-tertiary)">CPA ≤ ${p.breakevenCpa != null ? money(p.breakevenCpa, 0) : '—'}</span>
          </div>
          <div class="pcard-foot">
            ${trap ? `<span class="verdict ${trap.cls}">${trap.lbl}</span>` : `<span class="verdict ${T.VERDICTS[p.verdict].v}">${T.VERDICTS[p.verdict][Sh.lang]}</span>`}
            <span class="risk ${p.risk}"><span class="rdot"></span>${p.risk === 'low' ? L0('risk_low') : p.risk === 'mod' ? L0('risk_mod') : L0('risk_high')}</span>
          </div>
        </div>
      </div>`;
    }).join('');
    $('#results').innerHTML = `<div class="card-grid">${cards}</div><div class="dg-wrap" style="margin-top:16px;background:none;border:none;box-shadow:none">${scrollFoot(slice.length, total, hasMore)}</div>`;
    wireRows();
  }
  function L0(k) { return T.STR[Sh.lang][k]; }

  function renderSkeleton() {
    const rows = Array.from({ length: 7 }).map(() => `<tr class="dg-skel">
      <td><div class="cell-prod"><div class="sk" style="width:36px;height:36px;border-radius:8px"></div><div style="flex:1"><div class="sk" style="width:60%"></div><div class="sk" style="width:34%;margin-top:6px;height:10px"></div></div></div></td>
      <td><div class="sk" style="width:48px;margin-left:auto"></div></td><td><div class="sk" style="width:50px"></div></td>
      <td><div class="sk" style="width:74px"></div></td><td><div class="sk" style="width:64px;margin-left:auto"></div></td>
      <td><div class="sk" style="width:48px;margin-left:auto"></div></td><td><div class="sk" style="width:30px;margin-left:auto"></div></td>
      <td><div class="sk" style="width:30px;margin-left:auto"></div></td><td><div class="sk" style="width:56px;margin-left:auto"></div></td></tr>`).join('');
    $('#results').innerHTML = `<div class="dg-wrap"><div class="dg-scroll"><table class="dg"><tbody>${rows}</tbody></table></div></div>`;
  }
  function renderEmpty() {
    const s = L();
    $('#results').innerHTML = `<div class="dg-wrap"><div class="empty">
      <div class="e-art">${ic('compass')}</div>
      <div class="e-t">${s.empty_t}</div><div class="e-s">${s.empty_s}</div>
      <div class="e-actions"><button class="btn-ghost" id="loosenBtn">${s.loosen}</button></div></div></div>`;
    $('#loosenBtn').addEventListener('click', () => {
      // drop the most restrictive filter heuristically
      if (state.minScore > 0) state.minScore = 0; else if (state.minMargin > 0) state.minMargin = 0;
      else if (state.cats.size) state.cats.clear(); else if (state.phases.size) state.phases.clear(); else state.verdicts.clear();
      render();
    });
  }

  function sortable(k) { return state.sortKey === k ? 'sorted' : ''; }
  function ar(k) { return `<span class="sort-ar">${state.sortKey === k ? (state.dir < 0 ? '▾' : '▴') : '▾'}</span>`; }
  /* Pied de liste pour l'infinite scroll : compteur « affichés / total »,
     sentinelle observée, spinner de chargement, et message de fin de liste.
     Le total affiché est l'univers complet (T.total, fourni par l'API) quand on
     ne filtre pas ; sinon le nombre de résultats filtrés déjà chargés. */
  function scrollFoot(shownCount, filteredTotal, hasMore) {
    const s = L();
    const noFilter = !state.q && !state.verdicts.size && !state.phases.size
      && !state.cats.size && state.minScore === 0 && state.minMargin === 0;
    const universe = (noFilter && T.total) ? T.total : filteredTotal;
    const info = `<span class="pinfo mono">${shownCount} / ${universe} ${s.results}</span>`;
    const loader = `<span id="scrollLoader" class="scroll-loader" style="display:none">${ic('search')}<span>…</span></span>`;
    // La sentinelle n'est rendue que s'il reste des produits à charger.
    const sentinel = hasMore ? `<div id="scrollSentinel" style="height:1px"></div>` : '';
    const endMsg = hasMore ? '' : `<span class="pinfo" style="color:var(--text-tertiary)">— ${s.results} —</span>`;
    return `<div class="pager" style="flex-direction:column;gap:8px;align-items:center">
      ${info}${loader}${endMsg}${sentinel}
    </div>`;
  }
  function wireSort() {
    $$('#results thead th[data-k]').forEach((th) => { if (th.style.cursor === 'default') return; th.addEventListener('click', () => { const k = th.dataset.k; if (state.sortKey === k) state.dir *= -1; else { state.sortKey = k; state.dir = -1; } state.shown = WINDOW; $('#sortSel').value = k; updateResults(); }); });
  }
  function wireRows() { $$('#results [data-id]').forEach((r) => r.addEventListener('click', () => Sh.openProduct(P.find((p) => p.id === r.dataset.id)))); }

  Sh.start({ active: 'n_discovery', render });
}
