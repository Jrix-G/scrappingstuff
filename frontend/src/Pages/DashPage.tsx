import React, { useEffect } from 'react';
import '../dashboard/app.css';
import '../dashboard/pages.css';
import { authedFetch } from '../auth/api';
import { auth } from '../auth/firebase';

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

    const FIRST_BATCH = 60;

    const tryFetch = async (base: string): Promise<boolean> => {
      try {
        const res = await authedFetch(`${base}/api/products?limit=${FIRST_BATCH}&offset=0`);
        if (!res.ok) return false;
        const json = await res.json();
        if (!Array.isArray(json.products) || !json.products.length) return false;
        (window as any).__TANDOR_BASE__ = json.products;
        (window as any).__TANDOR_PAGE__ = {
          apiBase: base,
          limit: FIRST_BATCH,
          total: json.total != null ? json.total : json.products.length,
          nextOffset: json.next_offset != null ? json.next_offset : null,
          hasMore: !!json.has_more,
        };
        return true;
      } catch {
        return false;
      }
    };

    const loadData = async () => {
      const urls = [
        // Même origine d'abord : en dev via le proxy CRA (src/setupProxy.js), en
        // preview via preview_server.js. /api est servi par la page elle-même →
        // aucune requête cross-origin, donc pas de CORS et indépendance totale
        // vis-à-vis du tunnel Cloudflare (éphémère). Si aucun proxy n'est présent,
        // /api/products renvoie l'index HTML → res.json() échoue → on tombe sur
        // les URLs absolues suivantes (tunnel / IP LAN).
        window.location.origin,
        process.env.REACT_APP_API_URL,
        process.env.REACT_APP_API_URL_LOCAL,
      ].filter(Boolean).map((u) => u!.replace(/\/$/, ''));

      for (const base of urls) {
        const ok = await tryFetch(base);
        if (ok) return;
        console.warn(`[Tandor] API indisponible : ${base}`);
      }
      console.warn('[Tandor] Toutes les URLs API ont échoué — fallback JSON bundlé.');
    };

    (window as any).__TANDOR_USER__ = auth.currentUser;

    loadData()
      .then(() => Promise.all([import('../dashboard/data'), import('../dashboard/charts'), import('../dashboard/charts-x')]))
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
