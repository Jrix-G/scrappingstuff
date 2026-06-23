import React, { useEffect } from 'react';
import '../dashboard/app.css';
import '../dashboard/pages.css';

/**
 * DashPage — coquille générique pour les 12 pages internes du dashboard Tandor
 * (Discovery, Radar, Trends, Reddit, Market, Analytics, Saved, Watchlists,
 * Alerts, Settings, Billing, Account).
 *
 * Le prototype d'origine est en JS vanilla : `shell.js` construit la chrome
 * partagée (sidebar/topbar/overlays) dans `#app`, puis chaque `page-*.js`
 * appelle `Shell.start({active, render})`. On reproduit fidèlement ce flux :
 *   1) on tente l'API live du Pi (REACT_APP_API_URL) → window.__TANDOR_BASE__,
 *      sinon fallback sur le JSON bundlé (products.json),
 *   2) on importe data/charts pour leurs effets de bord (window.TANDOR/Charts),
 *   3) on importe shell.ts (pose window.Shell),
 *   4) on importe le module de page et on appelle son `mount*()`.
 *
 * `loader` renvoie `{ mount }` — la fonction de montage de la page courante.
 */
export default function DashPage({ loader }: { loader: () => Promise<{ mount: () => void }> }) {
  useEffect(() => {
    let cancelled = false;

    const api = process.env.REACT_APP_API_URL;
    // 1er lot volontairement petit : l'infinite scroll (page-discovery) charge la
    // suite à la demande via window.TANDOR.loadMore(). On pose aussi le curseur de
    // pagination (__TANDOR_PAGE__) lu par data.ts pour connaître offset/total.
    const FIRST_BATCH = 60;
    const loadData = async () => {
      if (!api) return;
      const base = api.replace(/\/$/, '');
      try {
        const res = await fetch(`${base}/api/products?limit=${FIRST_BATCH}&offset=0`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (Array.isArray(json.products) && json.products.length) {
          (window as any).__TANDOR_BASE__ = json.products;
          (window as any).__TANDOR_PAGE__ = {
            apiBase: base,
            limit: FIRST_BATCH,
            total: json.total != null ? json.total : json.products.length,
            nextOffset: json.next_offset != null ? json.next_offset : null,
            hasMore: !!json.has_more,
          };
        }
      } catch (err) {
        console.warn('[Tandor] API indisponible, fallback JSON bundlé :', err);
      }
    };

    loadData()
      .then(() => Promise.all([import('../dashboard/data'), import('../dashboard/charts')]))
      .then(() => import('../dashboard/shell'))
      .then(() => loader())
      .then((mod) => { if (!cancelled) mod.mount(); });

    return () => { cancelled = true; };
  }, [loader]);

  return (
    <div className="tandor-dash">
      <div className="app" id="app"></div>
    </div>
  );
}
