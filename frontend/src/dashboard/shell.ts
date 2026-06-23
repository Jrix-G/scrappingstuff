/* eslint-disable */
// @ts-nocheck
export {};
import * as WL from './watchlist';
/* ============================================================
   TANDOR DASHBOARD — shell.js  (shared app chrome, vanilla)
   Injects the same sidebar/topbar/overlays as the Home page and
   exposes utilities so every page renders inside one consistent
   shell. The Home page (app.js) is left untouched — this file is
   a generalised sibling used by all the other pages.
   ============================================================ */
(function () {
  'use strict';
  const T = window.TANDOR, C = window.Charts;
  const P = T.PRODUCTS;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- icons (lucide-style, superset of Home) ---------- */
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
    chevR: '<path d="m9 6 6 6-6 6"/>',
    chevL: '<path d="m15 6-6 6 6 6"/>',
    zap: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    download: '<path d="M12 3v12M7 11l5 5 5-5M4 21h16"/>',
    hash: '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
    flame: '<path d="M12 3c0 4-4 5-4 9a4 4 0 0 0 8 0c0-2-2-3-2-5 2 1 4 3 4 6a6 6 0 1 1-12 0c0-5 6-6 6-10z"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5"/>',
    filter: '<path d="M3 5h18l-7 8v6l-4 2v-8z"/>',
    sort: '<path d="M7 4v16M7 20l-3-3M7 20l3-3M17 20V4M17 4l-3 3M17 4l3 3"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    rows: '<rect x="3" y="4" width="18" height="4" rx="1"/><rect x="3" y="10" width="18" height="4" rx="1"/><rect x="3" y="16" width="18" height="4" rx="1"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    heart: '<path d="M12 20s-7-4.3-9.3-8.5C1 8.5 2.3 5.5 5.3 5.5c1.9 0 3 .9 3.7 2 0.7-1.1 1.8-2 3.7-2 3 0 4.3 3 2.6 6C19 15.7 12 20 12 20z"/>',
    eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    trash: '<path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/>',
    edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    webhook: '<path d="M18 16.98c-.71 0-1.36.27-1.85.71L12 14.5M9 7.5a3 3 0 1 1 4.5 2.6M7.5 12a3 3 0 1 0 3 4.5M16.5 14a3 3 0 1 1-3 5"/>',
    shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
    key: '<circle cx="8" cy="15" r="4"/><path d="M10.8 12.2 21 2M17 6l3 3M15 8l2 2"/>',
    lock: '<rect x="4" y="11" width="16" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    note: '<path d="M4 4h16v12l-4 4H4z"/><path d="M16 20v-4h4"/>',
    layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5M3 18l9 5 9-5"/>',
    activity: '<path d="M3 12h4l3 8 4-16 3 8h4"/>',
    bookmarkPlus: '<path d="M7 4h10a1 1 0 0 1 1 1v15l-6-3.5L6 20V5a1 1 0 0 1 1-1z"/><path d="M9.5 8.5h5M12 6v5"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    minus: '<path d="M5 12h14"/>',
    dollar: '<path d="M12 2v20M16.5 6.5C16 5 14.5 4 12 4 9 4 7.5 5.5 7.5 7.5S9 11 12 11s4.5 1.5 4.5 3.5S15 18 12 18c-2.5 0-4-1-4.5-2.5"/>',
  };
  const ic = (n, cls) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"${cls ? ' class="' + cls + '"' : ''}>${PATHS[n] || ''}</svg>`;

  const ACCENTS = {
    indigo: { s: 'oklch(0.52 0.16 264)', ss: 'oklch(0.44 0.16 264)', tint: 'oklch(0.955 0.03 264)', glow: 'oklch(0.52 0.16 264 / .22)' },
    teal: { s: 'oklch(0.6 0.115 180)', ss: 'oklch(0.5 0.1 182)', tint: 'oklch(0.955 0.035 182)', glow: 'oklch(0.6 0.115 180 / .25)' },
    amber: { s: 'oklch(0.68 0.135 66)', ss: 'oklch(0.56 0.12 58)', tint: 'oklch(0.96 0.04 72)', glow: 'oklch(0.68 0.135 66 / .25)' },
  };

  /* ---------- state / persistence (mirrors Home) ---------- */
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
  const S = () => T.STR[lang];

  /* page → file map (all 12 + Home) */
  const LINK = {
    n_home: '/dashboard',
    n_discovery: '/discovery',
    n_radar: '/radar',
    n_trends: '/trends',
    n_reddit: '/reddit',
    n_market: '/market',
    n_analytics: '/analytics',
    n_saved: '/saved',
    n_watch: '/watchlists',
    n_alerts: '/alerts',
    n_settings: '/settings',
    n_billing: '/billing',
    n_account: '/account',
  };

  /* page-runtime hooks */
  let pageRender = null, pageResize = null, activeKey = 'n_home';

  /* ---------- number helpers ---------- */
  const loc = () => (lang === 'fr' ? 'fr-FR' : 'en-US');
  function fmt(v, dec) { dec = dec || 0; return (+v).toLocaleString(loc(), { minimumFractionDigits: dec, maximumFractionDigits: dec }); }
  function money(v, dec) { dec = dec == null ? 0 : dec; return fmt(v, dec) + '\u202f€'; }
  function pct(v) { return fmt(v, 0) + '%'; }

  /* ---------- real last-collection helpers ----------
     PRODUCTS[0].lastCollection is a REAL ISO timestamp (same across all
     products) or null. We derive an honest "il y a Xh/Xj" from it instead
     of the old hardcoded "il y a 2 h". Never invent a value. */
  function lastCollectionISO() {
    try { return (P && P.length && P[0].lastCollection) || null; } catch (e) { return null; }
  }
  function agoFromISO(iso) {
    if (!iso) return null;
    const t = Date.parse(iso);
    if (isNaN(t)) return null;
    const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
    const fr = lang === 'fr';
    if (mins < 1) return fr ? "à l'instant" : 'just now';
    if (mins < 60) return fr ? `il y a ${mins} min` : `${mins} min ago`;
    const hrs = Math.round(mins / 60);
    if (hrs < 48) return fr ? `il y a ${hrs} h` : `${hrs} h ago`;
    const days = Math.round(hrs / 24);
    return fr ? `il y a ${days} j` : `${days} d ago`;
  }
  /* Human label for the live banner; honest fallback when never collected. */
  function liveAgoLabel() {
    const ago = agoFromISO(lastCollectionISO());
    if (ago) return ago;
    return lang === 'fr' ? 'pas encore collecté' : 'not collected yet';
  }

  /* ============================================================
     CHROME MARKUP — injected once into the page
     ============================================================ */
  function buildChrome() {
    document.documentElement.lang = lang;
    const app = $('#app');
    app.className = 'app tandor-dash' + (collapsed ? ' collapsed' : '') + (density === 'compact' ? '' : '');
    app.innerHTML = `
      <aside class="sidebar" id="sidebar">
        <div class="sb-brand">
          <span class="sb-mark">
            <svg width="14" height="14" viewBox="0 0 13 13" fill="none"><path d="M6.5 1.5v10M2 6h9M6.5 1.5 9 4M6.5 1.5 4 4" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </span>
          <a class="sb-name" href="/dashboard">Tandor<span class="dot">.</span></a>
          <button class="sb-collapse" id="collapseBtn" aria-label="Collapse"></button>
        </div>
        <nav class="sb-nav" id="sbNav"></nav>
        <div class="sb-plan" id="sbPlan"></div>
      </aside>
      <header class="topbar">
        <button class="tb-search" id="searchBtn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
          <span class="ph" id="searchPh"></span><kbd>⌘K</kbd>
        </button>
        <div class="tb-right">
          <button class="tb-btn tb-market" id="marketBtn"></button>
          <button class="tb-btn tb-live" id="liveBtn"><span class="dot" style="animation:livePulse 2.4s infinite"></span><span id="liveLabel"></span></button>
          <div class="lang-toggle" id="langToggle"><button data-l="en">EN</button><button data-l="fr">FR</button></div>
          <button class="tb-btn tb-icon" id="bellBtn" aria-label="Notifications">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
            <span class="tb-badge" id="bellBadge">3</span>
          </button>
          <div class="tb-avatar" id="avatarBtn">A</div>
        </div>
      </header>
      <main class="main" id="main"><div class="canvas" id="canvas"></div></main>
      <nav class="tabbar" id="tabbar"></nav>`;

    // overlays appended to body once
    if (!$('#tip')) document.body.insertAdjacentHTML('beforeend', `
      <div class="tip" id="tip"></div>
      <div class="toasts" id="toasts"></div>
      <div class="scrim" id="scrim"></div>
      <div class="cmdk" id="cmdk" role="dialog" aria-modal="true">
        <div class="cmdk-in">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
          <input id="cmdkInput" type="text" autocomplete="off" spellcheck="false" /><kbd>esc</kbd>
        </div>
        <div class="cmdk-list" id="cmdkList"></div>
      </div>
      <div class="drawer" id="notifDrawer">
        <div class="drawer-h"><div><b id="notifTitle"></b><div class="sub" id="notifSub"></div></div><button class="twk-x" id="notifClose">✕</button></div>
        <div class="drawer-body" id="notifBody"></div>
        <div class="drawer-foot"><button id="markRead"></button></div>
      </div>
      <div class="drawer pd-drawer" id="pdDrawer"></div>
      <div class="popover" id="marketPop"></div>
      <div class="popover" id="livePop"></div>
      <div class="popover" id="avatarPop"></div>
      <div class="twk" id="twk">
        <div class="twk-hd"><b>Tweaks</b><button class="twk-x" id="twkClose">✕</button></div>
        <div class="twk-body">
          <div class="twk-row"><span class="twk-lbl" id="twkAccentLbl">Signal accent</span><div class="twk-swatches" id="twkAccent"></div></div>
          <div class="twk-row"><span class="twk-lbl" id="twkDensityLbl">Card density</span><div class="twk-seg" id="twkDensity"></div></div>
        </div>
      </div>`);
  }

  /* ============================================================
     Tooltip / toast / count-up / thumbnail
     ============================================================ */
  const Tip = window.Tip = {
    el: null,
    show(html, e) { this.el = this.el || $('#tip'); this.el.innerHTML = html; this.el.classList.add('show'); this.move(e); },
    move(e) { if (!e || !this.el) return; const r = this.el.getBoundingClientRect(); let x = e.clientX + 14, y = e.clientY + 14; if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14; if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14; this.el.style.left = x + 'px'; this.el.style.top = y + 'px'; },
    hide() { if (this.el) this.el.classList.remove('show'); },
  };
  function toast(msg) {
    const t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = `<span class="t-ico">${ic('check')}</span><span>${msg}</span>`;
    $('#toasts').appendChild(t);
    requestAnimationFrame(() => t.classList.add('show'));
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 250); }, 3200);
  }
  function countUp(el, to, dec, prefix, suffix) {
    prefix = prefix || ''; suffix = suffix || ''; dec = dec || 0;
    const f = (v) => prefix + v.toLocaleString(loc(), { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suffix;
    if (reduced) { el.textContent = f(to); return; }
    const dur = 720, t0 = performance.now();
    function step(t) { const k = clamp((t - t0) / dur, 0, 1); const e = 1 - Math.pow(1 - k, 3); el.textContent = f(to * e); if (k < 1) requestAnimationFrame(step); else el.textContent = f(to); }
    requestAnimationFrame(step);
    setTimeout(() => { el.textContent = f(to); }, dur + 250);
  }
  function thumb(p, size) {
    const hue = p.catHue;
    const a = `oklch(0.7 0.1 ${hue})`, b = `oklch(0.52 0.12 ${hue})`;
    const tag = T.CATS[p.cat].en.slice(0, 3).toUpperCase();
    const st = size ? ` style="width:${size}px;height:${size}px"` : '';
    return `<div class="thumb"${st}>
      <div class="ph-stripe" style="background:repeating-linear-gradient(135deg, ${a} 0 6px, ${b} 6px 12px);opacity:.92"></div>
      <span class="ph-tag">${tag}</span></div>`;
  }

  /* ============================================================
     SIDEBAR / TOPBAR / TABBAR
     ============================================================ */
  const NAV = [
    { g: 'nav_disc', items: [['home', 'n_home'], ['compass', 'n_discovery'], ['radar', 'n_radar']] },
    { g: 'nav_analysis', items: [['trend', 'n_trends'], ['reddit', 'n_reddit'], ['signal', 'n_market'], ['bars', 'n_analytics']] },
    { g: 'nav_space', items: [['bookmark', 'n_saved'], ['list', 'n_watch'], ['bell', 'n_alerts']] },
  ];
  const FOOT_NAV = [['settings', 'n_settings'], ['card', 'n_billing'], ['user', 'n_account']];

  function navItem(icn, key) {
    const s = S(), on = key === activeKey, href = LINK[key];
    const a = href ? `href="${href}"` : '';
    const badge = key === 'n_alerts' ? `<span class="sb-badge" id="navAlertBadge" style="display:none"></span>` : '';
    return `<a class="sb-item${on ? ' on' : ''}" ${a} data-key="${key}" title="${s[key]}">${ic(icn)}<span class="sb-label">${s[key]}</span>${badge}</a>`;
  }

  /* ---- live decline-alert counter for the nav badge ---- */
  function declineAlertCount(ids) {
    let n = 0;
    ids.forEach((id) => {
      const p = P.find((x) => x.id === id);
      if (p && (p.lossFlags || []).some((f) => f && f.name === 'déclin' && f.level === 'red')) n++;
    });
    return n;
  }
  function paintAlertBadge(n) {
    const el = $('#navAlertBadge');
    if (!el) return;
    if (n > 0) { el.textContent = String(n); el.style.display = ''; }
    else { el.style.display = 'none'; }
  }
  async function refreshAlertBadge() {
    try { paintAlertBadge(declineAlertCount(await WL.getWatchlist())); }
    catch (e) { paintAlertBadge(0); }
  }
  function renderSidebar() {
    const s = S();
    let h = '';
    NAV.forEach((grp) => { h += `<div class="sb-group">${s[grp.g]}</div>`; grp.items.forEach(([icn, key]) => { h += navItem(icn, key); }); });
    h += `<div class="sb-group">&nbsp;</div>`;
    FOOT_NAV.forEach(([icn, key]) => { h += navItem(icn, key); });
    $('#sbNav').innerHTML = h;
    $('#sbPlan').innerHTML = `
      <div class="sb-plan-h"><b>${s.plan}</b><span class="sb-plan-tag">PRO</span></div>
      <div class="sb-plan-usage">${s.plan_usage('1,240', '2,000')}</div>
      <div class="sb-plan-bar"><i style="width:62%"></i></div>
      <a class="sb-up" href="/billing">${s.upgrade}</a>`;
  }
  function renderTopbar() {
    const s = S();
    $('#searchPh').textContent = s.search_ph;
    const mk = T.MARKETS.find((m) => m.code === (LS.get('market', 'FR'))) || T.MARKETS[0];
    $('#marketBtn').innerHTML = `<span class="flag">${mk.flag}</span><span class="mname">${mk.code}</span>${ic('chev')}`;
    $('#marketBtn').querySelector('svg').style.width = '13px';
    // REAL last-collection time (from PRODUCTS[0].lastCollection), not hardcoded.
    $('#liveLabel').textContent = `${s.live} · ${liveAgoLabel()}`;
    $$('#langToggle button').forEach((b) => b.classList.toggle('on', b.dataset.l === lang));
  }
  function renderTabbar() {
    const s = S();
    const tabs = [['home', 'n_home'], ['compass', 'n_discovery'], ['radar', 'n_radar'], ['bookmark', 'n_saved'], ['bell', 'n_alerts']];
    $('#tabbar').innerHTML = tabs.map(([icn, key]) => `<a class="tab${key === activeKey ? ' on' : ''}" href="${LINK[key]}">${ic(icn)}<span>${s[key]}</span></a>`).join('');
  }

  /* ============================================================
     NOTIFICATIONS / POPOVERS / CMDK  (ported from Home)
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
  function placePop(pop, anchor, align) {
    const r = anchor.getBoundingClientRect();
    pop.style.top = (r.bottom + 8) + 'px';
    if (align === 'right') pop.style.left = Math.max(8, r.right - pop.offsetWidth) + 'px';
    else pop.style.left = r.left + 'px';
  }
  function buildMarketPop() {
    const cur = LS.get('market', 'FR');
    $('#marketPop').innerHTML = `<div class="pop-h">${lang === 'fr' ? 'Marché' : 'Market'}</div>` + T.MARKETS.map((m) => `
      <div class="pop-item${m.code === cur ? ' on' : ''}" data-m="${m.code}"><span style="font-size:15px">${m.flag}</span>${m[lang]}<span style="margin-left:auto;font-family:var(--font-mono);font-size:11px;color:var(--text-tertiary)">${m.code}</span>${m.code === cur ? `<span class="pop-check" style="margin-left:6px">${ic('check')}</span>` : ''}</div>`).join('');
    $$('#marketPop .pop-item').forEach((it) => it.addEventListener('click', () => { LS.set('market', it.dataset.m); renderTopbar(); closeAll(); buildMarketPop(); if (pageRender) pageRender(); }));
    $$('#marketPop .pop-check svg').forEach((sv) => sv.style.width = '15px');
  }
  function buildLivePop() {
    const s = S();
    const fr = lang === 'fr';
    // Only the last-collection timestamp is REAL. The old per-source OK/limited
    // statuses and the precise "dans 41 min" countdown are not knowable from the
    // current export, so we drop them rather than fabricate. The next run is a
    // nightly estimate, labelled as such — no invented minute count.
    const lastLbl = fr ? 'Dernière collecte' : 'Last collection';
    const lastVal = agoFromISO(lastCollectionISO()) || (fr ? 'pas encore collecté' : 'not collected yet');
    const nextLbl = fr ? 'Prochaine collecte' : 'Next collection';
    const nextVal = fr ? 'cette nuit (estim.)' : 'overnight (est.)';
    $('#livePop').innerHTML = `<div class="pop-h">${s.live_pipeline}</div>
      <div class="pipe-row"><span class="name">${ic('clock')}${lastLbl}</span><span class="st" style="color:var(--text-secondary)">${lastVal}</span></div>
      <div class="pop-sep"></div>
      <div class="pipe-row"><span class="name">${ic('refresh')}${nextLbl}</span><span class="st" style="color:var(--text-secondary)">${nextVal}</span></div>`;
    $$('#livePop .pipe-row svg').forEach((sv) => sv.style.width = '14px');
  }
  function buildAvatarPop() {
    const s = S();
    $('#avatarPop').innerHTML = `
      <div style="padding:8px 10px 10px;display:flex;gap:10px;align-items:center;border-bottom:1px solid var(--border-subtle);margin-bottom:5px">
        <div class="tb-avatar" style="cursor:default">A</div>
        <div><div style="font-size:13px;font-weight:700">Alex Morel</div><div style="font-size:11px;color:var(--text-tertiary)">alex@tandor.io</div></div>
      </div>
      <a class="pop-item" href="/account">${ic('user')}${s.n_account}</a>
      <a class="pop-item" href="/settings">${ic('settings')}${s.n_settings}</a>
      <a class="pop-item" href="/billing">${ic('card')}${s.n_billing}</a>
      <div class="pop-sep"></div>
      <div class="pop-item" data-act="lang">${ic('hash')}${lang === 'fr' ? 'Langue : Français' : 'Language: English'}</div>`;
    $('#avatarPop [data-act="lang"]').addEventListener('click', () => { closeAll(); setLang(lang === 'fr' ? 'en' : 'fr'); });
    $$('#avatarPop .pop-item svg').forEach((sv) => sv.style.width = '16px');
  }
  function togglePop(pop, anchor, align, builder) {
    const open = pop.classList.contains('show');
    closeAll();
    if (!open) { builder(); pop.classList.add('show'); placePop(pop, anchor, align); }
  }

  /* command palette */
  let cmdkSel = 0, cmdkItems = [];
  function buildCmdk(q) {
    const s = S();
    q = (q || '').toLowerCase().trim();
    const pages = [...NAV.flatMap((g) => g.items), ...FOOT_NAV].map(([icn, key]) => ({ type: 'page', icn, label: s[key], key }));
    const prods = P.map((p) => ({ type: 'product', label: p.name, sub: T.CATS[p.cat][lang], score: p.tandor, id: p.id }));
    const actions = [
      { type: 'action', icn: 'list', label: s.a_new_watch, href: '/watchlists' },
      { type: 'action', icn: 'bell', label: s.a_new_alert, href: '/alerts' },
      { type: 'action', icn: 'download', label: s.a_export },
      { type: 'action', icn: 'sliders', label: s.a_toggle_theme, act: 'density' },
    ];
    const f = (arr) => q ? arr.filter((i) => i.label.toLowerCase().includes(q) || (i.sub || '').toLowerCase().includes(q)) : arr;
    const groups = [[s.cmd_products, f(prods)], [s.cmd_pages, f(pages)], [s.cmd_actions, f(actions)]];
    let h = '', flat = [];
    groups.forEach(([title, arr]) => {
      if (!arr.length) return;
      h += `<div class="cmdk-group">${title}</div>`;
      arr.forEach((i) => {
        const idx = flat.length; flat.push(i);
        const icoHtml = i.type === 'product'
          ? `<span class="ci-ico" style="background:var(--${T.PHASES[P.find((p) => p.id === i.id).phase].v});color:#fff">${i.label.slice(0, 1)}</span>`
          : `<span class="ci-ico">${ic(i.icn)}</span>`;
        h += `<div class="cmdk-item" data-idx="${idx}">${icoHtml}
          <div class="ci-main"><div class="ci-t">${i.label}</div>${i.sub ? `<div class="ci-s">${i.sub}</div>` : ''}</div>
          ${i.score != null ? `<span class="ci-r">${i.score}</span>` : i.type === 'page' ? `<span class="ci-s">↵</span>` : ''}</div>`;
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
    if (i.type === 'product') { closeAll(); const p = P.find((x) => x.id === i.id); openProduct(p); }
    else if (i.type === 'page' && LINK[i.key]) { location.href = LINK[i.key]; }
    else if (i.type === 'action' && i.href) { location.href = i.href; }
    else if (i.type === 'action' && i.act === 'density') { closeAll(); setDensity(density === 'comfort' ? 'compact' : 'comfort', true); }
    else { closeAll(); toast(`${i.label} · ${s.soon}`); }
  }
  function openCmdk() { $('#scrim').classList.add('show'); $('#cmdk').classList.add('show'); $('#cmdkInput').value = ''; buildCmdk(''); setTimeout(() => $('#cmdkInput').focus(), 30); }
  function scrollSel() { const el = $('#cmdkList .cmdk-item.sel'); if (el) { const list = $('#cmdkList'); const r = el.getBoundingClientRect(), lr = list.getBoundingClientRect(); if (r.bottom > lr.bottom) list.scrollTop += r.bottom - lr.bottom; if (r.top < lr.top) list.scrollTop -= lr.top - r.top; } }

  /* ============================================================
     PRODUCT DETAIL DRAWER (shared "dossier" preview)
     ============================================================ */
  function gaugeRow(label, val, col) {
    return `<div class="pd-gauge"><span class="pd-g-l">${label}</span>${C.microGauge(val, col)}<span class="pd-g-v mono">${Math.round(val)}</span></div>`;
  }
  function openProduct(p) {
    const s = S(), L = pdStr();
    const ph = T.PHASES[p.phase], col = `var(--${ph.v})`;
    const ringCol = p.verdict === 'BUY' ? col : p.verdict === 'WATCH' ? 'var(--watch)' : 'var(--pass)';
    const up = p.growth >= 0;
    const riskCls = p.risk, riskLbl = p.risk === 'low' ? s.risk_low : p.risk === 'mod' ? s.risk_mod : s.risk_high;
    const opp = p.tandor >= 78 ? L.high : p.tandor >= 60 ? L.med : L.low;
    const satInv = 100 - clamp(p.listed, 0, 100);
    // contribution bars
    const contribs = [
      { k: L.c_trends, v: (p.trendsScore - 50) / 50, col: 'var(--azure)' },
      { k: L.c_reddit, v: (p.redditScore - 50) / 50, col: 'var(--reddit)' },
      { k: L.c_growth, v: (p.growthScore - 50) / 50, col: 'var(--signal)' },
      { k: L.c_margin, v: (p.margin_pct - 0.45) / 0.45, col: 'var(--buy)' },
      { k: L.c_sat, v: (satInv - 50) / 50, col: 'var(--ph-mature)' },
    ];
    const economy = [
      { l: L.cost, v: money(p.cost, 1) }, { l: L.retail, v: money(p.retail, 1) },
      { l: L.gross, v: money(p.gross, 1) + ` · ${pct(p.margin_pct * 100)}` },
      { l: L.net, v: money(p.net, 1), hot: p.net > 15 },
    ];
    $('#pdDrawer').innerHTML = `
      <div class="pd-h">
        ${thumb(p, 52)}
        <div class="pd-h-meta"><div class="pd-h-name">${p.name}</div>
          <div class="pd-h-sub mono">${T.CATS[p.cat][lang]} · ${p.id} · ${L.detected} ${p.detectedHrs < 24 ? p.detectedHrs + 'h' : Math.round(p.detectedHrs / 24) + s.day}</div></div>
        <button class="twk-x" id="pdClose">✕</button>
      </div>
      <div class="pd-body">
        <div class="pd-hero">
          <div class="pd-ring">${C.ring(p.tandor, ringCol, 96, 7, p.confidence)}<div class="pd-ring-c"><b class="mono pd-ring-n">${p.tandor}</b><span class="micro">${L.tandor}</span></div></div>
          <div class="pd-facts">
            <div class="pd-fact"><span>${L.opportunity}</span><b style="color:${ringCol}">${opp} ${up ? '▲' : '▼'}</b></div>
            <div class="pd-fact"><span>${s.risk}</span><b class="risk ${riskCls}"><span class="rdot"></span>${riskLbl}</b></div>
            <div class="pd-fact"><span>${s.conf}</span><b class="mono">${pct(p.confidence * 100)}</b></div>
            <div class="pd-fact"><span>${L.phase}</span><b><span class="badge phase-badge"><span class="pdot" style="background:${col}"></span>${ph[lang]}</span></b></div>
            <div class="pd-fact"><span>${s.verdict}</span><b><span class="verdict ${T.VERDICTS[p.verdict].v}">${T.VERDICTS[p.verdict][lang]}</span></b></div>
          </div>
        </div>
        <div class="pd-econ">${economy.map((e) => `<div class="pd-econ-tile${e.hot ? ' hot' : ''}"><span class="micro">${e.l}</span><b class="mono">${e.v}</b></div>`).join('')}</div>

        <div class="pd-sec"><div class="pd-sec-t">${L.scores}</div>
          ${gaugeRow(L.c_growth, p.growthScore, 'var(--signal)')}
          ${gaugeRow(L.c_reddit, p.redditScore, 'var(--reddit)')}
          ${gaugeRow(L.c_trends, p.trendsScore, 'var(--azure)')}
          ${gaugeRow(L.c_potential, p.organic, 'var(--buy)')}
          ${gaugeRow(L.c_sat, satInv, 'var(--ph-mature)')}
        </div>

        <div class="pd-charts">
          <div class="pd-chart"><div class="pd-chart-h"><span class="micro">${L.trends90}</span><span class="feed-growth ${up ? 'up' : 'down'} mono">${up ? '+' : ''}${Math.round(p.growth * 100)}%</span></div>
            ${C.sparkline(p.trend, { w: 300, h: 60, stroke: 'var(--signal)', fill: true, sw: 2, dot: true })}</div>
          <div class="pd-chart"><div class="pd-chart-h"><span class="micro">${L.reddit12}</span></div>
            ${miniBars(p.reddit, 'var(--reddit)')}</div>
        </div>

        <div class="pd-sec"><div class="pd-sec-t">${s.why}</div>
          <p class="pd-reason">${p.reason[lang]}</p>
          <div class="pd-contribs">${contribs.map((c) => contribBar(c.k, c.v, c.col)).join('')}</div>
        </div>
      </div>
      <div class="pd-foot">
        <button class="btn-ghost" data-act="save">${ic('heart')}${L.save}</button>
        <button class="btn-ghost" id="pdWatchBtn" data-act="watch">${ic('eye')}${L.watch}</button>
        <button class="btn-ghost" data-act="alert">${ic('bell')}${L.alert}</button>
        <a class="btn-pri" href="#" data-act="cj">${ic('ext')}${L.cj}</a>
      </div>`;
    $('#scrim').classList.add('show');
    $('#pdDrawer').classList.add('show');
    $('#pdClose').addEventListener('click', closeAll);
    const acts = { save: L.t_saved, alert: L.t_alert, cj: L.t_cj };
    // Reflect current watch state on the dedicated button.
    const wbtn = $('#pdWatchBtn');
    WL.isWatched(p.id).then((on) => { if (wbtn) { wbtn.classList.toggle('on', on); wbtn.innerHTML = `${ic('eye')}${on ? L.watch_on : L.watch}`; } }).catch(() => {});
    $$('#pdDrawer [data-act]').forEach((b) => b.addEventListener('click', async (e) => {
      const act = b.dataset.act;
      if (act === 'cj') e.preventDefault();
      if (act === 'watch') {
        const nowOn = await WL.toggleWatch(p.id);
        if (wbtn) { wbtn.classList.toggle('on', nowOn); wbtn.innerHTML = `${ic('eye')}${nowOn ? L.watch_on : L.watch}`; }
        toast(`${p.name} · ${nowOn ? L.t_watch_add : L.t_watch_rm}`);
        return;
      }
      toast(`${p.name} · ${acts[act]}`);
    }));
  }
  function miniBars(vals, col) {
    const max = Math.max(...vals, 1), n = vals.length, w = 300, h = 60, gap = 3, bw = (w - gap * (n - 1)) / n;
    let bars = '';
    vals.forEach((v, i) => { const bh = (v / max) * (h - 6); bars += `<rect x="${i * (bw + gap)}" y="${h - bh}" width="${bw}" height="${bh}" rx="2" fill="${col}" fill-opacity="${0.4 + 0.5 * (v / max)}"/>`; });
    return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" class="mini-bars" aria-hidden="true">${bars}</svg>`;
  }
  function contribBar(label, v, col) {
    v = clamp(v, -1, 1);
    const w = Math.abs(v) * 50;
    const side = v >= 0 ? `left:50%;width:${w}%;background:${col}` : `right:50%;width:${w}%;background:var(--ph-decline)`;
    return `<div class="pd-contrib"><span class="pd-c-l">${label}</span><div class="pd-c-track"><i style="${side}"></i></div></div>`;
  }
  function pdStr() {
    return lang === 'fr' ? {
      detected: 'détecté il y a', tandor: 'Score', opportunity: 'Opportunité', phase: 'Phase', scores: 'Sous-scores',
      high: 'Élevée', med: 'Moyenne', low: 'Faible',
      cost: 'Coût', retail: 'Prix de vente', gross: 'Marge brute', net: 'Net après pub',
      c_growth: 'Croissance', c_reddit: 'Reddit', c_trends: 'Trends', c_potential: 'Potentiel', c_sat: 'Saturation inv.', c_margin: 'Marge',
      trends90: 'Google Trends · 90 j', reddit12: 'Mentions Reddit · 12 sem.',
      save: 'Sauvegarder', watch: 'Surveiller', watch_on: 'Surveillé', alert: 'Alerte', cj: 'Voir sur CJ',
      t_saved: 'ajouté à votre bibliothèque', t_watch_add: 'ajouté à la watchlist', t_watch_rm: 'retiré de la watchlist', t_alert: 'alerte créée', t_cj: 'ouverture de la fiche CJ',
    } : {
      detected: 'detected', tandor: 'Score', opportunity: 'Opportunity', phase: 'Phase', scores: 'Sub-scores',
      high: 'High', med: 'Medium', low: 'Low',
      cost: 'Cost', retail: 'Retail price', gross: 'Gross margin', net: 'Net after ads',
      c_growth: 'Growth', c_reddit: 'Reddit', c_trends: 'Trends', c_potential: 'Potential', c_sat: 'Saturation inv.', c_margin: 'Margin',
      trends90: 'Google Trends · 90d', reddit12: 'Reddit mentions · 12 wks',
      save: 'Save', watch: 'Watch', watch_on: 'Watching', alert: 'Alert', cj: 'View on CJ',
      t_saved: 'saved to your library', t_watch_add: 'added to your watchlist', t_watch_rm: 'removed from watchlist', t_alert: 'alert created', t_cj: 'opening CJ listing',
    };
  }

  /* ============================================================
     CLOSE / TWEAKS / LANG / DENSITY / ACCENT
     ============================================================ */
  function closeAll() {
    $('#scrim').classList.remove('show');
    $('#cmdk').classList.remove('show');
    $('#notifDrawer').classList.remove('show');
    $('#pdDrawer').classList.remove('show');
    $$('.popover').forEach((p) => p.classList.remove('show'));
  }
  function applyAccent(a) {
    const c = ACCENTS[a] || ACCENTS.indigo, r = document.documentElement.style;
    r.setProperty('--signal', c.s); r.setProperty('--signal-strong', c.ss); r.setProperty('--signal-tint', c.tint); r.setProperty('--signal-glow', c.glow);
  }
  function setAccent(a, persist) {
    accent = a; applyAccent(a); LS.set('accent', a);
    $$('#twkAccent .twk-sw').forEach((sw) => sw.classList.toggle('on', sw.dataset.a === a));
    if (pageRender) pageRender();
    if (persist) postTweak({ accent: a });
  }
  function setDensity(d, persist) {
    density = d; document.body.classList.toggle('dense', d === 'compact'); LS.set('density', d);
    $$('#twkDensity button').forEach((b) => b.classList.toggle('on', b.dataset.d === d));
    if (pageResize) requestAnimationFrame(pageResize);
    if (persist) postTweak({ density: d });
  }
  function buildTweaks() {
    $('#twkAccentLbl').textContent = lang === 'fr' ? 'Couleur d’accent' : 'Signal accent';
    $('#twkDensityLbl').textContent = lang === 'fr' ? 'Densité' : 'Card density';
    const sw = { indigo: 'oklch(0.52 0.16 264)', teal: 'oklch(0.6 0.115 180)', amber: 'oklch(0.68 0.135 66)' };
    $('#twkAccent').innerHTML = Object.keys(sw).map((k) => `<button class="twk-sw${k === accent ? ' on' : ''}" data-a="${k}" style="background:${sw[k]}" title="${k}"></button>`).join('');
    $$('#twkAccent .twk-sw').forEach((b) => b.addEventListener('click', () => setAccent(b.dataset.a, true)));
    const dens = { comfort: lang === 'fr' ? 'Confort' : 'Comfort', compact: 'Compact' };
    $('#twkDensity').innerHTML = Object.keys(dens).map((k) => `<button class="${k === density ? 'on' : ''}" data-d="${k}">${dens[k]}</button>`).join('');
    $$('#twkDensity button').forEach((b) => b.addEventListener('click', () => setDensity(b.dataset.d, true)));
  }
  function postTweak(edits) { try { window.parent.postMessage({ type: '__edit_mode_set_keys', edits }, '*'); } catch (e) {} }
  function setLang(l) { lang = l; LS.set('lang', l); document.documentElement.lang = l; renderChrome(); if (pageRender) pageRender(); }

  /* ============================================================
     WIRING
     ============================================================ */
  function renderChrome() { renderSidebar(); renderTopbar(); renderTabbar(); renderNotif(); buildTweaks(); refreshAlertBadge(); }
  function wire() {
    $('#collapseBtn').innerHTML = ic('list');
    $('#collapseBtn').querySelector('svg').style.width = '16px';
    $('#collapseBtn').addEventListener('click', () => { collapsed = !collapsed; $('#app').classList.toggle('collapsed', collapsed); LS.set('collapsed', collapsed ? '1' : '0'); if (pageResize) requestAnimationFrame(pageResize); });
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
    $('#main').addEventListener('scroll', () => $$('.popover').forEach((p) => p.classList.remove('show')));
    document.addEventListener('click', (e) => { if (!e.target.closest('.popover') && !e.target.closest('#marketBtn,#liveBtn,#avatarBtn')) $$('.popover').forEach((p) => p.classList.remove('show')); });

    // host protocol (tweaks)
    window.addEventListener('message', (e) => {
      const t = e && e.data && e.data.type;
      if (t === '__activate_edit_mode') $('#twk').classList.add('show');
      else if (t === '__deactivate_edit_mode') $('#twk').classList.remove('show');
    });
    try { window.parent.postMessage({ type: '__edit_mode_available' }, '*'); } catch (e) {}
    $('#twkClose').addEventListener('click', () => { $('#twk').classList.remove('show'); try { window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*'); } catch (e) {} });

    let rt;
    addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (pageResize) pageResize(); }, 180); });
  }

  /* ============================================================
     PUBLIC API
     ============================================================ */
  function start(opts) {
    activeKey = opts.active || 'n_home';
    pageRender = opts.render || null;
    pageResize = opts.resize || (opts.render ? opts.render : null);
    applyAccent(accent);
    if (density === 'compact') document.body.classList.add('dense');
    buildChrome();
    renderChrome();
    wire();
    if (pageRender) pageRender();
    // live decline-alert badge on the Alerts nav item
    refreshAlertBadge();
    try { WL.onWatchlistChange(() => refreshAlertBadge()); } catch (e) {}
  }

  window.Shell = {
    start, ic, LS, toast, countUp, thumb, openProduct, closeAll, fmt, money, pct,
    setLang, setDensity, setAccent,
    get lang() { return lang; }, get density() { return density; }, get accent() { return accent; },
    S, P, T, C, $, $$, clamp, miniBars,
    market() { return LS.get('market', 'FR'); },
  };
})();
