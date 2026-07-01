/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-discovery.ts   (Product Discovery)
   Dense filterable catalogue: filter rail (sent to the backend),
   sortable-by-Tandor data-grid or card grid, search, and an
   INDEXED pagination of 30 products per page over the Top 2000
   by Tandor score. Click → product dossier drawer.

   Pagination : on n'utilise plus l'infinite scroll. Chaque page
   (30 produits) est récupérée via T.fetchPage({page, pageSize,
   filters, sort}) qui interroge le backend (ou pagine côté client
   hors-ligne). Les filtres — recherche, catégorie, verdict, phase,
   score min. — partent au backend. La barre de pagination utilise
   meta.page_count / meta.total. Aucun chiffre fabriqué : empty-state
   explicite quand 0 résultat ou quand l'historique manque.
   ============================================================ */
export function mountDiscovery() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic, clamp = Sh.clamp;
  const PAGE_SIZE = 30;

  const STR = {
    en: { title: 'Product Discovery', sub: 'Top 2000 by Tandor score · live signal', search: 'Filter by name or category…',
      filters: 'Filters', reset: 'Reset', verdict: 'Verdict', phase: 'Phase', category: 'Category',
      min_score: 'Min Tandor score', all: 'All',
      results: 'products', sort_note: 'Sorted by Tandor score', view_table: 'Table', view_cards: 'Cards',
      c_prod: 'Product', c_score: 'Score', c_verdict: 'Verdict', c_phase: 'Phase', c_margin: 'Margin', c_sat: 'Sellers', c_pot: 'Potential', c_trend: '30d',
      empty_t: 'No product matches', empty_s: 'Your filters are too tight. Loosen the most restrictive one to see more opportunities.', loosen: 'Loosen filters',
      mo: '/mo', clearall: 'Clear all',
      trap: 'Money trap', risky: 'Risky', viable: 'Viable',
      sold: 'AliExpress sold', no_demand: 'No demand data', no_hist: 'History building', no_hist_s: 'Not enough nights collected yet',
      sold_unit: 'sold', median: 'median',
      page: 'Page', of: 'of', prev: 'Previous', next: 'Next' },
    fr: { title: 'Product Discovery', sub: 'Top 2000 par score Tandor · signal en direct', search: 'Filtrer par nom ou catégorie…',
      filters: 'Filtres', reset: 'Réinitialiser', verdict: 'Verdict', phase: 'Phase', category: 'Catégorie',
      min_score: 'Score Tandor min.', all: 'Tous',
      results: 'produits', sort_note: 'Trié par score Tandor', view_table: 'Tableau', view_cards: 'Cartes',
      c_prod: 'Produit', c_score: 'Score', c_verdict: 'Verdict', c_phase: 'Phase', c_margin: 'Marge', c_sat: 'Vendeurs', c_pot: 'Potentiel', c_trend: '30j',
      empty_t: 'Aucun produit ne correspond', empty_s: 'Vos filtres sont trop stricts. Assouplissez le plus restrictif pour voir plus d’opportunités.', loosen: 'Assouplir les filtres',
      mo: '/mois', clearall: 'Tout effacer',
      trap: 'Piège à fric', risky: 'Risqué', viable: 'Viable',
      sold: 'Vendus AliExpress', no_demand: 'Pas de données de demande', no_hist: 'Historique en cours', no_hist_s: 'Pas encore assez de nuits collectées',
      sold_unit: 'vendus', median: 'médiane',
      page: 'Page', of: 'sur', prev: 'Précédent', next: 'Suivant' },
  };
  const L = () => STR[Sh.lang];
  const money = Sh.money, pct = Sh.pct, fmt = Sh.fmt;

  const PHASE_ORDER = ['EMERGENT', 'EARLY_GROWTH', 'GROWTH', 'MATURE', 'PEAK', 'DECLINING'];

  let state = {
    verdicts: new Set(), phases: new Set(), cats: new Set(),
    minScore: 0, q: '', view: 'table',
    page: 1, loading: true, meta: null, items: [],
  };
  let reqSeq = 0;          // jeton anti-réponse-périmée (la dernière requête gagne)
  let qTimer = null;       // debounce de la recherche

  function curFilters() {
    return {
      q: state.q.trim(),
      minScore: state.minScore,
      cats: [...state.cats],
      verdicts: [...state.verdicts],
      phases: [...state.phases],
    };
  }

  /* Charge une page donnée (30 produits) avec les filtres courants. */
  function load(page) {
    state.page = Math.max(1, page);
    state.loading = true;
    renderSkeleton();
    const seq = ++reqSeq;
    T.fetchPage({ page: state.page, pageSize: PAGE_SIZE, filters: curFilters(), sort: 'tandor' })
      .then((res) => {
        if (seq !== reqSeq) return;           // une requête plus récente a pris le relais
        state.loading = false;
        state.items = res.products || [];
        state.meta = res.meta || null;
        // si le backend a clampé la page, on resynchronise l'état
        if (state.meta && state.meta.page) state.page = state.meta.page;
        updateResults();
      })
      .catch(() => {
        if (seq !== reqSeq) return;
        state.loading = false; state.items = []; state.meta = null; updateResults();
      });
  }

  function render() {
    const s = L();
    const cats = Object.keys(T.CATS);   // liste canonique complète (pas de comptage partiel)
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
          <span class="count mono" style="color:var(--text-tertiary)">${s.sort_note}</span>
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
              <div class="pill-row" id="verdictPills">${[['VIABLE', s.viable], ['RISKY', s.risky], ['TRAP', s.trap]].map(([v, lbl]) => `<button class="pill ${state.verdicts.has(v) ? 'on' : ''}" data-v="${v}">${lbl}</button>`).join('')}</div>
            </div>
            <div class="flt-sec">
              <div class="flt-sec-h">${s.phase}</div>
              <div class="chk-list" id="phaseChks">${PHASE_ORDER.map((ph) => `<label class="chk ${state.phases.has(ph) ? 'on' : ''}" data-ph="${ph}"><span class="chk-dot" style="background:var(--${T.PHASES[ph].v})"></span>${T.PHASES[ph][Sh.lang]}</label>`).join('')}</div>
            </div>
            <div class="flt-sec">
              <div class="flt-sec-h">${s.min_score}</div>
              <div class="range-wrap"><div class="range-val"><span>0</span><b id="scoreVal">${state.minScore}</b><span>100</span></div>
                <input type="range" class="rng" id="scoreRng" min="0" max="100" step="1" value="${state.minScore}" /></div>
            </div>
            <div class="flt-sec">
              <div class="flt-sec-h">${s.category}</div>
              <div class="chk-list" id="catChks">${cats.map((c) => `<label class="chk ${state.cats.has(c) ? 'on' : ''}" data-c="${c}"><span class="box">${ic('check')}</span>${T.CATS[c][Sh.lang]}</label>`).join('')}</div>
            </div>
            <div class="flt-foot"><button class="btn-ghost" id="resetBtn">${s.reset}</button></div>
          </div>
        </aside>
        <div class="rv">
          <div class="chips" id="chips"></div>
          <div id="results"></div>
        </div>
      </div>`;

    // wire toolbar / rail (chaque changement de filtre repart en page 1)
    $$('#viewSeg button').forEach((b) => b.addEventListener('click', () => { state.view = b.dataset.v; $$('#viewSeg button').forEach((x) => x.classList.toggle('on', x === b)); updateResults(); }));
    $('#qInp').addEventListener('input', (e) => {
      state.q = e.target.value;
      clearTimeout(qTimer);
      qTimer = setTimeout(() => load(1), 300);     // debounce réseau
    });
    $$('#verdictPills .pill').forEach((b) => b.addEventListener('click', () => { toggle(state.verdicts, b.dataset.v); b.classList.toggle('on'); load(1); }));
    $$('#phaseChks .chk').forEach((b) => b.addEventListener('click', () => { toggle(state.phases, b.dataset.ph); b.classList.toggle('on'); load(1); }));
    $$('#catChks .chk').forEach((b) => b.addEventListener('click', () => { toggle(state.cats, b.dataset.c); b.classList.toggle('on'); load(1); }));
    $('#scoreRng').addEventListener('input', (e) => { state.minScore = +e.target.value; $('#scoreVal').textContent = state.minScore; });
    $('#scoreRng').addEventListener('change', () => load(1));     // fetch au relâchement
    $('#resetBtn').addEventListener('click', resetAll);

    load(state.page);
  }

  function toggle(set, v) { set.has(v) ? set.delete(v) : set.add(v); }
  function resetAll() {
    state.verdicts.clear(); state.phases.clear(); state.cats.clear();
    state.minScore = 0; state.q = '';
    render();
  }

  function chipList() {
    const s = L(); const chips = [];
    const trapLbl = { VIABLE: s.viable, RISKY: s.risky, TRAP: s.trap };
    state.verdicts.forEach((v) => chips.push([`${s.verdict}: ${trapLbl[v] || v}`, () => state.verdicts.delete(v)]));
    state.phases.forEach((v) => chips.push([T.PHASES[v][Sh.lang], () => state.phases.delete(v)]));
    state.cats.forEach((v) => chips.push([T.CATS[v][Sh.lang], () => state.cats.delete(v)]));
    if (state.minScore > 0) chips.push([`${s.c_score} ≥ ${state.minScore}`, () => state.minScore = 0]);
    return chips;
  }

  function updateResults() {
    const s = L();
    const total = state.meta ? state.meta.total : 0;
    // chips (filtres actifs) — sinon compteur de l'univers filtré
    const chips = chipList();
    $('#chips').innerHTML = chips.length
      ? chips.map((c, i) => `<span class="fchip" data-i="${i}">${c[0]}<button>${ic('x')}</button></span>`).join('') + `<button class="clear-all" id="clearAll">${s.clearall}</button>`
      : `<span class="count mono">${fmt(total)} ${s.results}</span>`;
    $$('#chips .fchip button').forEach((b) => b.addEventListener('click', () => { chips[+b.parentElement.dataset.i][1](); load(1); }));
    if ($('#clearAll')) $('#clearAll').addEventListener('click', resetAll);

    if (state.loading) { renderSkeleton(); return; }
    if (!state.items.length) { renderEmpty(); return; }

    if (state.view === 'table') renderTable(state.items);
    else renderCards(state.items);
  }

  function ringCol(p) { return p.trapVerdict === 'VIABLE' ? `var(--${T.PHASES[p.phase].v})` : p.trapVerdict === 'RISKY' ? 'var(--watch)' : 'var(--pass)'; }

  /* ---- REAL trap verdict (TRAP|RISKY|VIABLE) — the honest buy signal ---- */
  function trapTag(p) {
    const s = L();
    if (p.trapVerdict === 'TRAP')   return { lbl: s.trap,   cls: 'pass',  col: 'var(--pass)' };
    if (p.trapVerdict === 'RISKY')  return { lbl: s.risky,  cls: 'watch', col: 'var(--watch)' };
    if (p.trapVerdict === 'VIABLE') return { lbl: s.viable, cls: 'buy',   col: 'var(--buy)' };
    return null;
  }
  /* ---- REAL demand evidence: AliExpress sold (null = empty-state) ---- */
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

  function renderTable(slice) {
    const s = L();
    const head = `
      <th>${s.c_prod}</th>
      <th class="num">${s.c_score}</th>
      <th>${s.c_verdict}</th>
      <th>${s.c_phase}</th>
      <th class="num">${s.c_margin}</th>
      <th class="num">${s.sold}</th>
      <th class="num">${s.c_sat}</th>
      <th class="num">${s.c_pot}</th>
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
        ${pagerFoot()}
      </div>`;
    wireRows(); wirePager();
  }

  function renderCards(slice) {
    const s = L();
    const cards = slice.map((p) => {
      const up = p.growth >= 0, col = `var(--${T.PHASES[p.phase].v})`;
      const hue = p.catHue, a = `oklch(0.7 0.1 ${hue})`, b = `oklch(0.52 0.12 ${hue})`;
      const trap = trapTag(p);
      const sold = soldText(p);
      const demandLine = sold
        ? `<div class="pcard-meta" style="margin-top:2px"><b style="color:var(--text-secondary)">${sold}</b>${p.salesScore != null ? ` · ${p.salesScore}` : ''}</div>`
        : `<div class="pcard-meta" style="margin-top:2px;color:var(--text-tertiary)">${s.no_demand}</div>`;
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
    $('#results').innerHTML = `<div class="card-grid">${cards}</div><div class="dg-wrap" style="margin-top:16px;background:none;border:none;box-shadow:none">${pagerFoot()}</div>`;
    wireRows(); wirePager();
  }
  function L0(k) { return T.STR[Sh.lang][k]; }

  function renderSkeleton() {
    const rows = Array.from({ length: 8 }).map(() => `<tr class="dg-skel">
      <td><div class="cell-prod"><div class="sk" style="width:36px;height:36px;border-radius:8px"></div><div style="flex:1"><div class="sk" style="width:60%"></div><div class="sk" style="width:34%;margin-top:6px;height:10px"></div></div></div></td>
      <td><div class="sk" style="width:48px;margin-left:auto"></div></td><td><div class="sk" style="width:50px"></div></td>
      <td><div class="sk" style="width:74px"></div></td><td><div class="sk" style="width:64px;margin-left:auto"></div></td>
      <td><div class="sk" style="width:48px;margin-left:auto"></div></td><td><div class="sk" style="width:30px;margin-left:auto"></div></td>
      <td><div class="sk" style="width:30px;margin-left:auto"></div></td><td><div class="sk" style="width:56px;margin-left:auto"></div></td></tr>`).join('');
    const r = $('#results');
    if (r) r.innerHTML = `<div class="dg-wrap"><div class="dg-scroll"><table class="dg"><tbody>${rows}</tbody></table></div></div>`;
  }
  function renderEmpty() {
    const s = L();
    $('#results').innerHTML = `<div class="dg-wrap"><div class="empty">
      <div class="e-art">${ic('compass')}</div>
      <div class="e-t">${s.empty_t}</div><div class="e-s">${s.empty_s}</div>
      <div class="e-actions"><button class="btn-ghost" id="loosenBtn">${s.loosen}</button></div></div></div>`;
    $('#loosenBtn').addEventListener('click', () => {
      // drop the most restrictive filter heuristically, then reload page 1
      if (state.minScore > 0) state.minScore = 0; else if (state.cats.size) state.cats.clear();
      else if (state.phases.size) state.phases.clear(); else if (state.verdicts.size) state.verdicts.clear();
      else state.q = '';
      render();
    });
  }

  /* ---- barre de pagination indexée : « page X / Y », prev/next + numéros ---- */
  function pageNumbers(cur, count) {
    // fenêtre compacte avec ellipses : 1 … c-1 c c+1 … N
    const out = [];
    const add = (v) => out.push(v);
    const window = 1;
    const lo = Math.max(2, cur - window), hi = Math.min(count - 1, cur + window);
    add(1);
    if (lo > 2) add('…');
    for (let p = lo; p <= hi; p++) add(p);
    if (hi < count - 1) add('…');
    if (count > 1) add(count);
    return out;
  }
  function pagerFoot() {
    const s = L();
    const m = state.meta || { page: 1, page_count: 1, total: state.items.length };
    const cur = m.page || 1, count = Math.max(1, m.page_count || 1), total = m.total || 0;
    const info = `<span class="pinfo mono">${s.page} ${cur} ${s.of} ${count} · ${fmt(total)} ${s.results}</span>`;
    if (count <= 1) {
      return `<div class="pager" style="justify-content:center;gap:10px">${info}</div>`;
    }
    const prevDis = cur <= 1 ? 'disabled' : '';
    const nextDis = cur >= count ? 'disabled' : '';
    const nums = pageNumbers(cur, count).map((p) => p === '…'
      ? `<span class="pg-ell" style="padding:0 4px;color:var(--text-tertiary)">…</span>`
      : `<button class="pg-num btn-ghost btn-sm ${p === cur ? 'on' : ''}" data-page="${p}" ${p === cur ? 'aria-current="page"' : ''}>${p}</button>`).join('');
    return `<div class="pager" style="justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center">
      ${info}
      <div class="pg-ctrls" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
        <button class="btn-ghost btn-sm" id="pgPrev" ${prevDis}>${ic('chevL')}${s.prev}</button>
        ${nums}
        <button class="btn-ghost btn-sm" id="pgNext" ${nextDis}>${s.next}${ic('chevR')}</button>
      </div>
    </div>`;
  }
  function wirePager() {
    const m = state.meta || { page: 1, page_count: 1 };
    const cur = m.page || 1, count = Math.max(1, m.page_count || 1);
    $$('#results .pg-num').forEach((b) => b.addEventListener('click', () => { const p = +b.dataset.page; if (p !== cur) goPage(p); }));
    if ($('#pgPrev')) $('#pgPrev').addEventListener('click', () => { if (cur > 1) goPage(cur - 1); });
    if ($('#pgNext')) $('#pgNext').addEventListener('click', () => { if (cur < count) goPage(cur + 1); });
  }
  function goPage(p) {
    load(p);
    // remonte en haut de la zone de résultats pour une navigation lisible
    const main = $('#main'); if (main) main.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function wireRows() {
    $$('#results [data-id]').forEach((r) => r.addEventListener('click', () => {
      const p = state.items.find((x) => x.id === r.dataset.id) || T.PRODUCTS.find((x) => x.id === r.dataset.id);
      if (p) Sh.openProduct(p);
    }));
  }

  Sh.start({ active: 'n_discovery', render });
}
