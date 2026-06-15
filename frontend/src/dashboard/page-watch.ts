/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-watch.js   (Watchlists)
   Themed lists tracked over time: avg score + trend sparkline,
   member previews, last activity, create / delete management.
   Persisted in localStorage.
   ============================================================ */
export function mountWatch() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic;

  const STR = {
    en: { title: 'Watchlists', sub: 'themed lists tracked over time', count: 'lists',
      members: 'products', avg: 'Avg score', activity: 'last activity', dynamic: 'Dynamic', manual: 'Manual',
      newl: 'New watchlist', create: 'Create', name_ph: 'Watchlist name', colour: 'Colour', cancel: 'Cancel', open: 'Open',
      d_ago: 'd ago', h_ago: 'h ago', deleted: 'Watchlist deleted', created: 'Watchlist created' },
    fr: { title: 'Watchlists', sub: 'listes thématiques suivies dans le temps', count: 'listes',
      members: 'produits', avg: 'Score moyen', activity: 'dernière activité', dynamic: 'Dynamique', manual: 'Manuelle',
      newl: 'Nouvelle watchlist', create: 'Créer', name_ph: 'Nom de la watchlist', colour: 'Couleur', cancel: 'Annuler', open: 'Ouvrir',
      d_ago: 'j', h_ago: 'h', deleted: 'Watchlist supprimée', created: 'Watchlist créée' },
  };
  const L = () => STR[Sh.lang];
  const COLORS = ['oklch(0.52 0.16 264)', 'oklch(0.6 0.13 152)', 'oklch(0.58 0.14 250)', 'oklch(0.64 0.18 35)', 'oklch(0.7 0.13 178)', 'oklch(0.72 0.15 70)'];

  const DEFAULTS = [
    { id: 'w1', name: 'Wellness FR', color: COLORS[4], dynamic: true, members: ['CJ-4471', 'CJ-2741', 'CJ-1907'], trend: 1, hrs: 6 },
    { id: 'w2', name: 'Q4 Gifting', color: COLORS[5], dynamic: false, members: ['CJ-7782', 'CJ-3380', 'CJ-6033', 'CJ-2255'], trend: 1, hrs: 22 },
    { id: 'w3', name: 'Low-saturation bets', color: COLORS[0], dynamic: true, members: ['CJ-3344', 'CJ-1130', 'CJ-3380'], trend: 1, hrs: 2 },
    { id: 'w4', name: 'Beauty rituals', color: COLORS[3], dynamic: false, members: ['CJ-2289', 'CJ-2255', 'CJ-8801'], trend: -1, hrs: 49 },
  ];

  function getLists() { try { const v = Sh.LS.get('watchlists', null); return v ? JSON.parse(v) : DEFAULTS.slice(); } catch (e) { return DEFAULTS.slice(); } }
  function setLists(a) { Sh.LS.set('watchlists', JSON.stringify(a)); }
  let creating = false, newColor = COLORS[0];

  function avgScore(w) { const ps = w.members.map((id) => P.find((p) => p.id === id)).filter(Boolean); return ps.length ? Math.round(ps.reduce((s, p) => s + p.tandor, 0) / ps.length) : 0; }
  function synthTrend(base, dir) { const out = []; for (let i = 0; i < 14; i++) { const f = i / 13; out.push(base - dir * 5 + dir * 8 * f + Math.sin(i * 1.5) * 2); } return out; }

  function render() {
    const s = L(), lists = getLists();
    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${lists.length} ${s.count} · ${s.sub}</span></div></div>
        <button class="btn-pri" id="newBtn">${ic('plus')}${s.newl}</button>
      </div>
      <div class="wl-grid rv" id="wlGrid"></div>`;
    $('#newBtn').addEventListener('click', () => { creating = true; renderGrid(); });
    renderGrid();
  }

  function renderGrid() {
    const s = L(), lists = getLists();
    let cards = lists.map((w) => {
      const avg = avgScore(w), up = w.trend >= 0;
      const ps = w.members.map((id) => P.find((p) => p.id === id)).filter(Boolean).slice(0, 4);
      const ago = w.hrs < 24 ? `${w.hrs}${s.h_ago}` : `${Math.round(w.hrs / 24)}${s.d_ago}`;
      return `<div class="wl-card" data-id="${w.id}">
        <div class="wl-h"><span class="wl-swatch" style="background:${w.color}"></span><span class="wl-name">${w.name}</span>
          <span class="wl-tag">${w.dynamic ? s.dynamic : s.manual}</span></div>
        <div class="wl-stats">
          <div class="wl-stat"><div class="ws-n mono">${avg}</div><div class="ws-l">${s.avg}</div></div>
          <span class="wl-spark">${C.sparkline(synthTrend(avg, w.trend), { w: 96, h: 34, stroke: up ? 'var(--buy)' : 'var(--pass)', fill: true, sw: 1.8, dot: true })}</span>
        </div>
        <div class="wl-foot">
          <span style="display:flex;align-items:center;gap:6px">${ps.map((p) => `<span class="thumb" style="width:22px;height:22px;border-radius:6px">${thumbInner(p)}</span>`).join('')}<span style="margin-left:4px">${w.members.length} ${s.members}</span></span>
          <span class="wl-trend ${up ? 'up' : 'down'}">${up ? '+' : ''}${(w.trend * (2 + avg % 3)).toFixed(1)} · ${ago}</span>
        </div>
        <div style="display:flex;gap:6px;margin-top:12px">
          <button class="icon-btn" data-act="rename" title="rename">${ic('edit')}</button>
          <button class="icon-btn" data-act="delete" title="delete">${ic('trash')}</button>
        </div>
      </div>`;
    }).join('');
    if (creating) cards += newCardForm();
    else cards += `<div class="wl-card new" id="addCard">${ic('plus')}<span>${s.newl}</span></div>`;
    $('#wlGrid').innerHTML = cards;
    wire();
  }

  function thumbInner(p) { const hue = p.catHue, a = `oklch(0.7 0.1 ${hue})`, b = `oklch(0.52 0.12 ${hue})`; return `<div class="ph-stripe" style="background:repeating-linear-gradient(135deg, ${a} 0 5px, ${b} 5px 10px);opacity:.92"></div>`; }

  function newCardForm() {
    const s = L();
    return `<div class="wl-card" style="display:flex;flex-direction:column;gap:12px" id="newForm">
      <input class="inp" id="nlName" placeholder="${s.name_ph}" />
      <div><div class="micro" style="margin-bottom:8px">${s.colour}</div>
        <div style="display:flex;gap:8px">${COLORS.map((c) => `<button class="wl-color-sw" data-c="${c}" style="width:26px;height:26px;border-radius:7px;background:${c};border:2px solid ${c === newColor ? 'var(--text-primary)' : 'transparent'}"></button>`).join('')}</div></div>
      <div style="display:flex;gap:8px;margin-top:auto">
        <button class="btn-pri btn-sm" id="createBtn" style="flex:1">${s.create}</button>
        <button class="btn-ghost btn-sm" id="cancelBtn">${s.cancel}</button></div></div>`;
  }

  function wire() {
    const s = L();
    $$('#wlGrid .wl-card[data-id]').forEach((c) => c.addEventListener('click', (e) => {
      if (e.target.closest('[data-act]')) return;
      const w = getLists().find((x) => x.id === c.dataset.id);
      const first = w.members.map((id) => P.find((p) => p.id === id)).filter(Boolean)[0];
      if (first) Sh.openProduct(first);
    }));
    $$('#wlGrid [data-act="delete"]').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); const id = b.closest('[data-id]').dataset.id; setLists(getLists().filter((x) => x.id !== id)); Sh.toast(s.deleted); render(); }));
    $$('#wlGrid [data-act="rename"]').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); Sh.toast(Sh.lang === 'fr' ? 'Renommer · bientôt' : 'Rename · soon'); }));
    if ($('#addCard')) $('#addCard').addEventListener('click', () => { creating = true; renderGrid(); });
    if ($('#newForm')) {
      $$('#newForm .wl-color-sw').forEach((b) => b.addEventListener('click', () => { newColor = b.dataset.c; renderGrid(); setTimeout(() => $('#nlName') && $('#nlName').focus(), 0); }));
      $('#cancelBtn').addEventListener('click', () => { creating = false; renderGrid(); });
      $('#createBtn').addEventListener('click', () => {
        const name = ($('#nlName').value || '').trim() || (Sh.lang === 'fr' ? 'Sans titre' : 'Untitled');
        const lists = getLists();
        lists.push({ id: 'w' + Date.now(), name, color: newColor, dynamic: false, members: [], trend: 1, hrs: 0 });
        setLists(lists); creating = false; Sh.toast(s.created); render();
      });
      setTimeout(() => $('#nlName') && $('#nlName').focus(), 30);
    }
  }

  Sh.start({ active: 'n_watch', render });
}
