/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-watch.ts   (Watchlist v1)
   A real watchlist of PINNED products from the catalogue.
   For each pinned product we surface its REAL decline status,
   read from `lossFlags` (the flag whose name === 'déclin'):
     red   → en déclin
     amber → déclin soupçonné
     green → demande stable
     —     → inconnu
   Persistence is delegated to ./watchlist (async, Firestore or
   localStorage). No synthetic lists, no fake sparklines.
   ============================================================ */
import * as WL from './watchlist';

export function mountWatch() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, C = window.Charts, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic;

  const STR = {
    en: { title: 'Watchlist', sub: 'pinned products · live decline status', count: 'watched',
      open: 'Open', remove: 'Remove', removed: 'Removed from watchlist',
      empty_t: 'No products watched yet', empty_s: 'Pin a product from Discovery to track its demand and get an in-app alert the moment it goes into proven decline.', explore: 'Explore Discovery',
      st_red: 'In decline', st_amber: 'Decline suspected', st_green: 'Stable demand', st_unknown: 'Status unknown',
      trap: 'Money trap', risky: 'Risky', viable: 'Viable',
      score: 'Score', alerts_active: 'active decline alert', alerts_active_pl: 'active decline alerts',
      need_data: 'Decline signal needs ≥2 nights of data', building: 'History building',
      sold: 'sold', median: 'median' },
    fr: { title: 'Watchlist', sub: 'produits épinglés · statut de déclin en direct', count: 'surveillés',
      open: 'Ouvrir', remove: 'Retirer', removed: 'Retiré de la watchlist',
      empty_t: 'Aucun produit surveillé', empty_s: 'Épingle un produit depuis la Découverte pour suivre sa demande et recevoir une alerte in-app dès qu’il passe en déclin prouvé.', explore: 'Explorer la Découverte',
      st_red: 'En déclin', st_amber: 'Déclin soupçonné', st_green: 'Demande stable', st_unknown: 'Statut inconnu',
      trap: 'Piège à fric', risky: 'Risqué', viable: 'Viable',
      score: 'Score', alerts_active: 'alerte de déclin active', alerts_active_pl: 'alertes de déclin actives',
      need_data: 'Le signal de déclin nécessite ≥2 nuits de données', building: 'Historique en cours',
      sold: 'vendus', median: 'médiane' },
  };
  const L = () => STR[Sh.lang];

  /* ---- decline status, read from the product's lossFlags ---- */
  function declineFlag(p) {
    return (p.lossFlags || []).find((f) => f && f.name === 'déclin') || null;
  }
  function declineMeta(p) {
    const s = L();
    const f = declineFlag(p);
    const level = f ? f.level : 'unknown';
    const map = {
      red:     { lbl: s.st_red,     col: 'var(--ph-decline)', cls: 'red' },
      amber:   { lbl: s.st_amber,   col: 'var(--watch)',      cls: 'amber' },
      green:   { lbl: s.st_green,   col: 'var(--buy)',        cls: 'green' },
      unknown: { lbl: s.st_unknown, col: 'var(--text-tertiary)', cls: 'unknown' },
    };
    const meta = map[level] || map.unknown;
    return { level, reason: f ? f.reason : '', lbl: meta.lbl, col: meta.col, cls: meta.cls };
  }
  function trapTag(p) {
    const s = L();
    if (p.trapVerdict === 'TRAP') return { lbl: s.trap, col: 'var(--pass)', cls: 'pass' };
    if (p.trapVerdict === 'RISKY') return { lbl: s.risky, col: 'var(--watch)', cls: 'watch' };
    if (p.trapVerdict === 'VIABLE') return { lbl: s.viable, col: 'var(--buy)', cls: 'buy' };
    return null;
  }

  function thumbInner(p) {
    const hue = p.catHue, a = `oklch(0.7 0.1 ${hue})`, b = `oklch(0.52 0.12 ${hue})`;
    return `<div class="ph-stripe" style="background:repeating-linear-gradient(135deg, ${a} 0 6px, ${b} 6px 12px);opacity:.92"></div>`;
  }

  let watchedIds = [];

  /* products in the watchlist, decline-red first */
  function items() {
    const arr = watchedIds.map((id) => P.find((p) => p.id === id)).filter(Boolean);
    const rank = { red: 0, amber: 1, unknown: 2, green: 3 };
    return arr.sort((a, b) => {
      const ra = rank[declineMeta(a).level] ?? 2, rb = rank[declineMeta(b).level] ?? 2;
      if (ra !== rb) return ra - rb;
      return (b.tandor || 0) - (a.tandor || 0);
    });
  }

  function render() {
    const s = L(), arr = items();
    const alerts = arr.filter((p) => declineMeta(p).level === 'red').length;
    const alertLine = alerts
      ? ` · <span style="color:var(--ph-decline);font-weight:600">${alerts} ${alerts > 1 ? s.alerts_active_pl : s.alerts_active}</span>`
      : '';
    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${arr.length} ${s.count}${alertLine}</span></div></div>
      </div>
      <div class="rv" id="watchBody"></div>`;
    renderBody();
  }

  function renderBody() {
    const s = L(), arr = items();
    if (!arr.length) {
      $('#watchBody').innerHTML = `<div class="dg-wrap"><div class="empty">
        <div class="e-art">${ic('eye')}</div><div class="e-t">${s.empty_t}</div><div class="e-s">${s.empty_s}</div>
        <div class="e-actions"><a class="btn-pri" href="/discovery">${ic('compass')}${s.explore}</a></div></div></div>`;
      return;
    }
    $('#watchBody').innerHTML = `<div class="card-grid">${arr.map(card).join('')}</div>`;
    wire();
  }

  function soldText(p) {
    const s = L();
    if (p.aliExpressSold == null) return null;
    let t = `${Sh.fmt(p.aliExpressSold)} ${s.sold}`;
    if (p.aliExpressMedianSold != null) t += ` · ${Sh.fmt(p.aliExpressMedianSold)} ${s.median}`;
    return t;
  }

  function card(p) {
    const s = L(), d = declineMeta(p), trap = trapTag(p);
    const sold = soldText(p);
    // Real demand curve when available; otherwise an honest "needs ≥2 nights" empty-state.
    const demandBlock = p.hasRealHistory
      ? `<div style="margin:8px 0 2px">${C.sparkline(p.trend, { w: 220, h: 30, stroke: d.col, fill: true, sw: 1.7 })}</div>`
      : `<div class="wl-reason" style="margin:8px 0 2px;font-size:11.5px;color:var(--text-tertiary);line-height:1.4">— ${s.building} · ${s.need_data}</div>`;
    return `<div class="pcard wl-row" data-id="${p.id}" style="border-left:3px solid ${d.col}">
      <div class="pcard-media" style="height:90px">
        <span class="thumb" style="position:absolute;inset:0;border-radius:0">${thumbInner(p)}</span>
        <span class="pcard-ring">${C.ring(p.tandor, d.col, 40, 3.5)}<b>${p.tandor}</b></span>
      </div>
      <div class="pcard-body">
        <div class="pcard-name">${p.name}</div>
        <div class="pcard-meta">${T.CATS[p.cat][Sh.lang]} · ${p.id}${sold ? ` · ${sold}` : ''}</div>
        <div class="wl-status" style="display:flex;align-items:center;gap:7px;margin:10px 0 2px">
          <span class="pdot" style="background:${d.col};width:9px;height:9px;border-radius:50%;flex:none"></span>
          <b style="color:${d.col};font-size:13px">${d.lbl}</b>
          ${trap ? `<span class="verdict ${trap.cls}" style="margin-left:auto">${trap.lbl}</span>` : ''}
        </div>
        ${d.reason ? `<div class="wl-reason" style="font-size:12px;color:var(--text-secondary);line-height:1.4">${d.reason}</div>` : ''}
        ${demandBlock}
        <div class="pcard-foot" style="margin-top:12px">
          <span class="micro mono">${s.score} ${p.tandor}</span>
          <span style="display:flex;gap:6px">
            <button class="icon-btn" data-act="open" title="${s.open}">${ic('arrowUR')}</button>
            <button class="icon-btn on" data-act="remove" title="${s.remove}">${ic('eye')}</button>
          </span>
        </div>
      </div></div>`;
  }

  function wire() {
    const s = L();
    $$('#watchBody .pcard').forEach((c) => c.addEventListener('click', (e) => {
      if (e.target.closest('[data-act]')) return;
      Sh.openProduct(P.find((p) => p.id === c.dataset.id));
    }));
    $$('#watchBody [data-act="open"]').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation(); Sh.openProduct(P.find((p) => p.id === b.closest('.pcard').dataset.id));
    }));
    $$('#watchBody [data-act="remove"]').forEach((b) => b.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = b.closest('.pcard').dataset.id;
      await WL.removeFromWatchlist(id);
      Sh.toast(s.removed);
      // optimistic: drop locally; onWatchlistChange will reconcile.
      watchedIds = watchedIds.filter((x) => x !== id);
      render();
    }));
  }

  async function refresh() {
    try { watchedIds = await WL.getWatchlist(); } catch (e) { watchedIds = []; }
    render();
  }

  let unsub = null;
  function start() {
    if (unsub) { try { unsub(); } catch (e) {} unsub = null; }
    refresh();
    unsub = WL.onWatchlistChange(() => { refresh(); });
  }

  Sh.start({ active: 'n_watch', render: start });
}
