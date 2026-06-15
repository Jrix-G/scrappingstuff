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
