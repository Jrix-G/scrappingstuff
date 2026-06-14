import React, { useEffect } from 'react';
import '../dashboard/app.css';

/**
 * Dashboard Home — portage du prototype Tandor (HTML/JS vanilla) en React.
 * Le squelette est rendu en JSX (conteneurs vides), puis le contrôleur impératif
 * porté en TS (`dashboard/controller.ts`) les remplit. Les modules `data` et `charts`
 * sont importés pour leurs effets de bord (ils posent `window.TANDOR` / `window.Charts`).
 * Les données viennent de `dashboard/products.json` (export réel CJ + Trends + Reddit).
 */
export default function Dashboard() {
  useEffect(() => {
    let cancelled = false;

    // 1) Si une API est configurée (REACT_APP_API_URL → Pi local ou tunnel),
    //    on récupère les produits live AVANT d'importer data.ts, qui lira
    //    window.__TANDOR_BASE__. Sinon (ou en cas d'échec) : JSON bundlé.
    const api = process.env.REACT_APP_API_URL;
    const loadData = async () => {
      if (!api) return;
      try {
        const res = await fetch(`${api.replace(/\/$/, '')}/api/products?limit=200`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (Array.isArray(json.products) && json.products.length) {
          (window as any).__TANDOR_BASE__ = json.products;
        }
      } catch (err) {
        // silencieux : on retombe sur le JSON bundlé
        console.warn('[Tandor] API indisponible, fallback JSON bundlé :', err);
      }
    };

    loadData().then(() => Promise.all([
      import('../dashboard/data'),
      import('../dashboard/charts'),
    ])).then(() => import('../dashboard/controller'))
      .then((mod) => { if (!cancelled) mod.mountDashboard(); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="tandor-dash">
      <div className="app" id="app">
        {/* ===================== SIDEBAR ===================== */}
        <aside className="sidebar" id="sidebar">
          <div className="sb-brand">
            <span className="sb-mark">
              <svg width="14" height="14" viewBox="0 0 13 13" fill="none">
                <path d="M6.5 1.5v10M2 6h9M6.5 1.5 9 4M6.5 1.5 4 4" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span className="sb-name">Tandor<span className="dot">.</span></span>
            <button className="sb-collapse" id="collapseBtn" aria-label="Collapse"></button>
          </div>
          <nav className="sb-nav" id="sbNav"></nav>
          <div className="sb-plan" id="sbPlan"></div>
        </aside>

        {/* ===================== TOPBAR ===================== */}
        <header className="topbar">
          <button className="tb-search" id="searchBtn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
            </svg>
            <span className="ph" id="searchPh"></span>
            <kbd>⌘K</kbd>
          </button>
          <div className="tb-right">
            <button className="tb-btn tb-market" id="marketBtn"></button>
            <button className="tb-btn tb-live" id="liveBtn">
              <span className="dot" style={{ animation: 'livePulse 2.4s infinite' }}></span>
              <span id="liveLabel"></span>
            </button>
            <div className="lang-toggle" id="langToggle">
              <button data-l="en">EN</button>
              <button data-l="fr">FR</button>
            </div>
            <button className="tb-btn tb-icon" id="bellBtn" aria-label="Notifications">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
              </svg>
              <span className="tb-badge" id="bellBadge">3</span>
            </button>
            <div className="tb-avatar" id="avatarBtn">A</div>
          </div>
        </header>

        {/* ===================== MAIN ===================== */}
        <main className="main" id="main">
          <div className="canvas">
            <div className="page-head rv">
              <div>
                <h1 className="page-title" id="pageTitle"></h1>
                <div className="page-sub"><span className="live-dot"></span><span id="pageSub"></span></div>
              </div>
              <div className="seg" id="periodSeg"></div>
            </div>

            <div className="kpi-row rv" id="kpiRow"></div>

            <div className="cols">
              <section className="panel feed rv" id="feedPanel"></section>
              <aside className="panel rv" id="radarPanel"></aside>
            </div>

            <div className="bottom-row rv">
              <section className="panel" id="treePanel"></section>
              <section className="panel" id="heatPanel"></section>
            </div>
          </div>
        </main>

        {/* mobile tab bar */}
        <nav className="tabbar" id="tabbar"></nav>
      </div>

      {/* ===================== OVERLAYS ===================== */}
      <div className="tip" id="tip"></div>
      <div className="toasts" id="toasts"></div>
      <div className="scrim" id="scrim"></div>

      {/* command palette */}
      <div className="cmdk" id="cmdk" role="dialog" aria-modal="true">
        <div className="cmdk-in">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
          </svg>
          <input id="cmdkInput" type="text" autoComplete="off" spellCheck="false" />
          <kbd>esc</kbd>
        </div>
        <div className="cmdk-list" id="cmdkList"></div>
      </div>

      {/* notifications drawer */}
      <div className="drawer" id="notifDrawer">
        <div className="drawer-h">
          <div><b id="notifTitle"></b><div className="sub" id="notifSub"></div></div>
          <button className="twk-x" id="notifClose">✕</button>
        </div>
        <div className="drawer-body" id="notifBody"></div>
        <div className="drawer-foot"><button id="markRead"></button></div>
      </div>

      {/* popovers */}
      <div className="popover" id="marketPop"></div>
      <div className="popover" id="livePop"></div>
      <div className="popover" id="avatarPop"></div>

      {/* tweaks */}
      <div className="twk" id="twk">
        <div className="twk-hd"><b>Tweaks</b><button className="twk-x" id="twkClose">✕</button></div>
        <div className="twk-body">
          <div className="twk-row">
            <span className="twk-lbl" id="twkAccentLbl">Signal accent</span>
            <div className="twk-swatches" id="twkAccent"></div>
          </div>
          <div className="twk-row">
            <span className="twk-lbl" id="twkDensityLbl">Card density</span>
            <div className="twk-seg" id="twkDensity"></div>
          </div>
        </div>
      </div>
    </div>
  );
}
