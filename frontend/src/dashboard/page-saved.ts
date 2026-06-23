/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-saved.js   (Saved Products)
   Personal library: curated cards with notes, grouping and
   search. Save state persists in localStorage.
   ============================================================ */
export function mountSaved() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic;
  const money = Sh.money, pct = Sh.pct;

  const STR = {
    en: { title: 'Saved', sub: 'your research library', search: 'Search saved…',
      group: 'Group', g_none: 'None', g_cat: 'Category', count: 'saved products',
      add_note: 'Add note', to_watch: 'To watchlist', remove: 'Remove',
      empty_t: 'Nothing saved yet', empty_s: 'Save products from Discovery or the radar to build a private shortlist — with your own notes and tags.', explore: 'Explore Discovery',
      sort: 'Sort', s_recent: 'Recently saved', s_score: 'Tandor score', s_growth: 'Growth',
      trap: 'Money trap', risky: 'Risky', viable: 'Viable',
      sold: 'sold', median: 'median', no_demand: 'No demand data', no_hist: 'History building' },
    fr: { title: 'Sauvegardés', sub: 'votre bibliothèque de recherche', search: 'Rechercher…',
      group: 'Grouper', g_none: 'Aucun', g_cat: 'Catégorie', count: 'produits sauvegardés',
      add_note: 'Ajouter une note', to_watch: 'Vers watchlist', remove: 'Retirer',
      empty_t: 'Rien de sauvegardé', empty_s: 'Sauvegardez des produits depuis Discovery ou le radar pour bâtir une liste privée — avec vos notes et tags.', explore: 'Explorer Discovery',
      sort: 'Tri', s_recent: 'Récemment ajoutés', s_score: 'Score Tandor', s_growth: 'Croissance',
      trap: 'Piège à fric', risky: 'Risqué', viable: 'Viable',
      sold: 'vendus', median: 'médiane', no_demand: 'Pas de données de demande', no_hist: 'Historique en cours' },
  };
  const L = () => STR[Sh.lang];

  const DEFAULT_SAVED = ['CJ-4471', 'CJ-3344', 'CJ-1130', 'CJ-2289', 'CJ-3380', 'CJ-2255', 'CJ-9988', 'CJ-3702', 'CJ-1907'];
  const NOTES = {
    en: { 'CJ-4471': 'Test angle: desk workers 30–45. Hook on the “2-min reset” ritual.', 'CJ-1130': 'Margin is the story here — bundle 2-pack to lift AOV.', 'CJ-3344': 'Very early. Watch seller count weekly before committing ad budget.' },
    fr: { 'CJ-4471': 'Angle test : employés de bureau 30–45 ans. Accroche sur le rituel « reset 2 min ».', 'CJ-1130': 'La marge est l’argument — bundle x2 pour augmenter le panier.', 'CJ-3344': 'Très précoce. Surveiller le nombre de vendeurs chaque semaine avant d’engager du budget pub.' },
  };

  function getSaved() { try { const v = Sh.LS.get('saved', null); return v ? JSON.parse(v) : DEFAULT_SAVED.slice(); } catch (e) { return DEFAULT_SAVED.slice(); } }
  function setSaved(a) { Sh.LS.set('saved', JSON.stringify(a)); }
  let group = 'none', q = '', sort = 's_recent';

  function items() {
    const ids = getSaved();
    let arr = ids.map((id) => P.find((p) => p.id === id)).filter(Boolean);
    const ql = q.trim().toLowerCase();
    if (ql) arr = arr.filter((p) => p.name.toLowerCase().includes(ql) || T.CATS[p.cat][Sh.lang].toLowerCase().includes(ql));
    if (sort === 's_score') arr.sort((a, b) => b.tandor - a.tandor);
    else if (sort === 's_growth') arr.sort((a, b) => b.growth - a.growth);
    return arr;
  }

  function render() {
    const s = L();
    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
        <div class="tbar" style="margin:0">
          <div class="search-inp" style="min-width:200px">${ic('search')}<input id="qInp" placeholder="${s.search}" value="${q}" /></div>
          <div class="sel-wrap"><select class="sel" id="sortSel">${['s_recent', 's_score', 's_growth'].map((k) => `<option value="${k}" ${k === sort ? 'selected' : ''}>${s.sort} · ${s[k]}</option>`).join('')}</select></div>
          <div class="seg-inline" id="groupSeg">${['none', 'cat'].map((g) => `<button data-g="${g}" class="${g === group ? 'on' : ''}">${g === 'none' ? s.g_none : s.g_cat}</button>`).join('')}</div>
        </div>
      </div>
      <div class="rv" id="savedBody"></div>`;
    $('#qInp').addEventListener('input', (e) => { q = e.target.value; renderBody(); });
    $('#sortSel').addEventListener('change', (e) => { sort = e.target.value; renderBody(); });
    $$('#groupSeg button').forEach((b) => b.addEventListener('click', () => { group = b.dataset.g; $$('#groupSeg button').forEach((x) => x.classList.toggle('on', x === b)); renderBody(); }));
    renderBody();
  }

  function renderBody() {
    const s = L(), arr = items();
    if (!arr.length) {
      $('#savedBody').innerHTML = `<div class="dg-wrap"><div class="empty">
        <div class="e-art">${ic('bookmark')}</div><div class="e-t">${s.empty_t}</div><div class="e-s">${s.empty_s}</div>
        <div class="e-actions"><a class="btn-pri" href="Tandor Discovery.html">${ic('compass')}${s.explore}</a></div></div></div>`;
      return;
    }
    let html = `<div style="margin-bottom:14px" class="count mono">${arr.length} ${s.count}</div>`;
    if (group === 'cat') {
      const cats = {}; arr.forEach((p) => { (cats[p.cat] = cats[p.cat] || []).push(p); });
      Object.keys(cats).forEach((c) => {
        html += `<div class="micro" style="margin:18px 0 10px">${T.CATS[c][Sh.lang]} · ${cats[c].length}</div><div class="card-grid">${cats[c].map(card).join('')}</div>`;
      });
    } else {
      html += `<div class="card-grid">${arr.map(card).join('')}</div>`;
    }
    $('#savedBody').innerHTML = html;
    wire();
  }

  function trapTag(p) {
    const s = L();
    if (p.trapVerdict === 'TRAP')   return { lbl: s.trap,   cls: 'pass',  col: 'var(--pass)' };
    if (p.trapVerdict === 'RISKY')  return { lbl: s.risky,  cls: 'watch', col: 'var(--watch)' };
    if (p.trapVerdict === 'VIABLE') return { lbl: s.viable, cls: 'buy',   col: 'var(--buy)' };
    return null;
  }
  function soldText(p) {
    const s = L();
    if (p.aliExpressSold == null) return null;
    let t = `${Sh.fmt(p.aliExpressSold)} ${s.sold}`;
    if (p.aliExpressMedianSold != null) t += ` · ${Sh.fmt(p.aliExpressMedianSold)} ${s.median}`;
    return t;
  }

  function card(p) {
    const s = L(), up = p.growth >= 0, col = `var(--${T.PHASES[p.phase].v})`;
    const hue = p.catHue, a = `oklch(0.7 0.1 ${hue})`, b = `oklch(0.52 0.12 ${hue})`;
    const note = NOTES[Sh.lang][p.id];
    const trap = trapTag(p);
    const ringCol = trap ? trap.col : (p.verdict === 'BUY' ? col : p.verdict === 'WATCH' ? 'var(--watch)' : 'var(--pass)');
    const sold = soldText(p);
    const demandLine = sold
      ? `<div class="pcard-meta" style="margin-top:2px"><b style="color:var(--text-secondary)">${sold}</b>${p.salesScore != null ? ` · ${s.s_growth}: ${p.salesScore}` : ''}</div>`
      : `<div class="pcard-meta" style="margin-top:2px;color:var(--text-tertiary)">${s.no_demand}</div>`;
    const sparkRow = p.hasRealHistory
      ? `<div style="margin:8px 0 2px">${C.sparkline(p.trend, { w: 220, h: 26, stroke: up ? 'var(--buy)' : 'var(--pass)', fill: true, sw: 1.6 })}</div>`
      : `<div class="pcard-meta" style="margin:8px 0 2px;color:var(--text-tertiary);font-size:11px">— ${s.no_hist}</div>`;
    return `<div class="pcard" data-id="${p.id}">
      <div class="pcard-media">
        <div class="ph-stripe" style="background:repeating-linear-gradient(135deg, ${a} 0 7px, ${b} 7px 14px);opacity:.9"></div>
        <span class="pcard-phase"><span class="badge phase-badge" style="background:var(--surface-1)"><span class="pdot" style="background:${col}"></span>${T.PHASES[p.phase][Sh.lang]}</span></span>
        <span class="pcard-ring">${C.ring(p.tandor, ringCol, 40, 3.5)}<b>${p.tandor}</b></span>
      </div>
      <div class="pcard-body">
        <div class="pcard-name">${p.name}</div>
        <div class="pcard-meta">${T.CATS[p.cat][Sh.lang]} · ${p.id}</div>
        ${demandLine}
        ${note ? `<div class="note-block">${ic('note')}<span>${note}</span></div>` : ''}
        ${sparkRow}
        <div class="pcard-kpi">
          <span class="mg-margin">${money(p.net, 1)} <span style="color:var(--text-tertiary);font-weight:500">${pct(p.margin_pct * 100)}</span></span>
          <span class="micro mono" style="color:var(--text-tertiary)">CPA ≤ ${p.breakevenCpa != null ? money(p.breakevenCpa, 0) : '—'}</span>
        </div>
        <div class="pcard-foot">
          ${trap ? `<span class="verdict ${trap.cls}">${trap.lbl}</span>` : `<span class="verdict ${T.VERDICTS[p.verdict].v}">${T.VERDICTS[p.verdict][Sh.lang]}</span>`}
          <span style="display:flex;gap:6px">
            <button class="icon-btn" data-act="watch" title="${s.to_watch}">${ic('plus')}</button>
            <button class="icon-btn on" data-act="remove" title="${s.remove}">${ic('heart')}</button>
          </span>
        </div>
      </div></div>`;
  }

  function wire() {
    $$('#savedBody .pcard').forEach((c) => c.addEventListener('click', (e) => {
      if (e.target.closest('[data-act]')) return;
      Sh.openProduct(P.find((p) => p.id === c.dataset.id));
    }));
    $$('#savedBody [data-act="remove"]').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation(); const id = b.closest('.pcard').dataset.id;
      setSaved(getSaved().filter((x) => x !== id));
      Sh.toast(Sh.lang === 'fr' ? 'Retiré de la bibliothèque' : 'Removed from library');
      renderBody();
    }));
    $$('#savedBody [data-act="watch"]').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation(); location.href = 'Tandor Watchlists.html';
    }));
  }

  Sh.start({ active: 'n_saved', render });
}
