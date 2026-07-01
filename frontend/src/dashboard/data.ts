/* eslint-disable */
// @ts-nocheck
import REAL_PRODUCTS from './products.json';
import { authedFetch } from '../auth/api';
/* ============================================================
   TANDOR — app-data.js
   Demo dataset mapped to the JSON contract + i18n + helpers.
   All numbers are illustrative placeholders.
   ============================================================ */
(function () {
  'use strict';

  /* ---------- small helpers ---------- */
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const round = Math.round;
  // deterministic pseudo-random from a string seed (stable across reloads)
  function seeded(seed) {
    let h = 1779033703 ^ seed.length;
    for (let i = 0; i < seed.length; i++) {
      h = Math.imul(h ^ seed.charCodeAt(i), 3432918353);
      h = (h << 13) | (h >>> 19);
    }
    return function () {
      h = Math.imul(h ^ (h >>> 16), 2246822507);
      h = Math.imul(h ^ (h >>> 13), 3266489909);
      h ^= h >>> 16;
      return (h >>> 0) / 4294967296;
    };
  }

  /* ---------- phases ---------- */
  const PHASES = {
    EMERGENT:     { en: 'Emergent',     fr: 'Émergent',     v: 'ph-emergent' },
    EARLY_GROWTH: { en: 'Early growth', fr: 'Début crois.', v: 'ph-early' },
    GROWTH:       { en: 'Growth',       fr: 'Croissance',   v: 'ph-growth' },
    MATURE:       { en: 'Mature',       fr: 'Mature',       v: 'ph-mature' },
    PEAK:         { en: 'Peak',         fr: 'Pic',          v: 'ph-peak' },
    DECLINING:    { en: 'Declining',    fr: 'En déclin',    v: 'ph-decline' },
  };

  const VERDICTS = {
    BUY:   { en: 'Buy',   fr: 'Acheter',    v: 'buy' },
    WATCH: { en: 'Watch', fr: 'Surveiller', v: 'watch' },
    PASS:  { en: 'Pass',  fr: 'Passer',     v: 'pass' },
  };

  // Verdict anti-perte = SEULE source de vérité affichée (pivot Tandor). Le champ
  // `verdict` (BUY/WATCH/PASS, ancien moteur « trouve un gagnant ») ne doit plus
  // piloter l'UI : il valait BUY pour 100% des produits → message trompeur.
  const TRAP_VERDICTS = {
    VIABLE: { en: 'Viable',  fr: 'Viable',  v: 'buy' },
    RISKY:  { en: 'Risky',   fr: 'Risqué',  v: 'watch' },
    TRAP:   { en: 'Trap',    fr: 'Piège',   v: 'pass' },
  };
  // Mappe un produit -> { v(css), label, coverage } depuis trapVerdict.
  // `coverage` qualifie un verdict non étayé (ex. « 2/5 signaux mesurés ») : vide
  // si l'export ne fournit pas encore la couverture (rétro-compat ancien JSON).
  function trapMeta(p, lang) {
    const m = TRAP_VERDICTS[p && p.trapVerdict] || { en: '—', fr: '—', v: 'pass' };
    let coverage = '';
    if (p && p.trapCoverageTotal) {
      const meas = p.trapCoverageMeasured || 0, tot = p.trapCoverageTotal;
      coverage = lang === 'fr'
        ? `${meas}/${tot} signaux mesurés`
        : `${meas}/${tot} signals measured`;
    }
    return { v: m.v, label: m[lang] || m.en, coverage };
  }

  const CATS = {
    WELLNESS: { en: 'Wellness',   fr: 'Bien-être' },
    HOME:     { en: 'Home',       fr: 'Maison' },
    TECH:     { en: 'Tech',       fr: 'Tech' },
    BEAUTY:   { en: 'Beauty',     fr: 'Beauté' },
    PETS:     { en: 'Pets',       fr: 'Animaux' },
    OUTDOOR:  { en: 'Outdoor',    fr: 'Plein air' },
    KITCHEN:  { en: 'Kitchen',    fr: 'Cuisine' },
    FITNESS:  { en: 'Fitness',    fr: 'Fitness' },
    APPAREL:  { en: 'Apparel',    fr: 'Mode' },
    BABY:     { en: 'Baby',       fr: 'Bébé' },
  };

  /* hue per category — used to tint thumbnail placeholders */
  const CAT_HUE = {
    WELLNESS: 175, HOME: 40, TECH: 250, BEAUTY: 330, PETS: 95,
    OUTDOOR: 145, KITCHEN: 25, FITNESS: 200, APPAREL: 300, BABY: 355,
  };

  /* ---------- build one product from compact base ---------- */
  function build(base) {
    const rnd = seeded(base.id);
    const gross = +(base.retail - base.cost).toFixed(2);
    const margin_pct = gross / base.retail;
    const tandor = round(0.55 * base.organic + 0.45 * base.sellability);
    // Drapeaux de mesure : un signal null (backend honnête) ne doit jamais être
    // re-fabriqué ni affiché comme mesuré. gNeutral = 0 sert UNIQUEMENT aux maths
    // internes du radar (momentum/maturité), jamais à un affichage de croissance.
    const hasGrowth = base.growth != null;
    const hasReddit = base.redditScore != null;
    const hasTrends = base.trendsScore != null;
    const gNeutral = hasGrowth ? base.growth : 0;
    // growth score (affichage) : null si la croissance n'est pas mesurée.
    const growthScore = hasGrowth ? round(clamp((base.growth + 0.5) / 2.0, 0, 1) * 100) : null;
    const growthScoreCalc = round(clamp((gNeutral + 0.5) / 2.0, 0, 1) * 100);
    // risk: low confidence OR high volatility OR no sellers → risk up
    let riskN = 0;
    if (base.confidence < 0.6) riskN += 1.4;
    if (base.confidence < 0.45) riskN += 1;
    if (base.volatility > 0.6) riskN += 1.2;
    if (base.listed === 0) riskN += 1.5;
    if (base.listed > 70) riskN += 0.6;
    const risk = riskN >= 2.2 ? 'high' : riskN >= 1 ? 'mod' : 'low';

    // momentum (0..100) for radar: velocity + acceleration blend
    // (utilise growthScoreCalc neutre pour ne jamais propager un null dans les maths)
    const momentum = round(clamp(growthScoreCalc * 0.7 + base.organic * 0.3, 0, 100));
    // maturity (0..100): saturation proxy from listed sellers + age
    const maturity = round(clamp(base.listed * 0.7 + (base.age / 120) * 30, 0, 100));

    /* ---------- séries RÉELLES depuis le backend ----------
       base.history.{sales,amazon} = bloc {points,dates,days,values,spanDays}
       ou null tant qu'il n'y a pas ≥2 snapshots. Amazon = meilleur signal demande. */
    const hist = base.history || {};
    const realSales  = hist.sales  && (hist.sales.values  || []).length >= 2 ? hist.sales  : null;
    const realAmazon = hist.amazon && (hist.amazon.values || []).length >= 2 ? hist.amazon : null;
    const realDemand = realAmazon || realSales;          // priorité Amazon
    const hasRealHistory = !!realDemand;

    /* time series : RÉEL si dispo (normalisé 0..100 pour le sparkline), sinon repli
       procédural. Les pages affichent « pas de données » quand hasRealHistory est faux. */
    const trend = hasRealHistory
      ? normalize100(realDemand.values)
      : series(base.organic, gNeutral, base.volatility, 30, rnd, 8, 96);
    // Pas de série Reddit/CJ réelle par produit en DB -> procédural, marqué non-réel.
    // Vide si redditScore non mesuré (ne pas fabriquer une courbe depuis null).
    const reddit = hasReddit
      ? series(base.redditScore, gNeutral * 0.9, base.volatility * 1.2, 12, rnd, 2, 40, true)
      : [];
    const cj = ramp(Math.max(1, base.listed - round(base.growth * 14)), base.listed, 12, rnd);

    return Object.assign({}, base, {
      gross, margin_pct, tandor, growthScore, risk, momentum, maturity,
      // Drapeaux de transparence : true seulement si le signal est réellement mesuré.
      hasGrowth, hasReddit, hasTrends,
      catHue: CAT_HUE[base.cat], trend, reddit, cj,
      // vraies données exposées aux pages (à brancher) + drapeau de transparence
      realHistory: { sales: realSales, amazon: realAmazon, demand: realDemand, reddit: null, cj: null },
      hasRealHistory,
      seriesReal: { trend: hasRealHistory, reddit: false, cj: false },
      lastCollection: base.lastCollection || null,
    });
  }

  // normalise une courbe réelle vers 0..100 (préserve la forme) pour le sparkline.
  function normalize100(arr) {
    const lo = Math.min.apply(null, arr), hi = Math.max.apply(null, arr);
    if (hi === lo) return arr.map(() => 50);
    return arr.map((v) => +(((v - lo) / (hi - lo)) * 92 + 4).toFixed(1));
  }

  // smooth-ish rising series ending near `level`
  function series(level, growth, vol, n, rnd, lo, hi, integer) {
    const out = [];
    const start = clamp(level - growth * 38, 4, 92);
    for (let i = 0; i < n; i++) {
      const f = i / (n - 1);
      // ease the rise
      const base = start + (level - start) * Math.pow(f, 1 - clamp(growth, 0, 0.8) * 0.5);
      const noise = (rnd() - 0.5) * vol * 18;
      let v = clamp(base + noise, lo, hi);
      out.push(integer ? Math.max(0, round(v / 6)) : +v.toFixed(1));
    }
    return out;
  }
  function ramp(from, to, n, rnd) {
    const out = [];
    for (let i = 0; i < n; i++) {
      const f = i / (n - 1);
      out.push(round(from + (to - from) * f + (rnd() - 0.5) * 2));
    }
    return out;
  }

  /* ---------- compact base records ----------
     id, name, cat, cost, retail, sellability, organic, phase, verdict,
     growth(monthly, frac), confidence, listed, age(days), volatility,
     net (net after cpa €/sale), redditScore, trendsScore, seasonPeak(1-12),
     seasonMult(current month), reason{en,fr}, detectedHrs (for feed order)
  ----------------------------------------------------------------- */
  // Données live injectées par Dashboard.tsx / DashPage.tsx (fetch API du Pi) si
  // dispo, sinon fallback sur le JSON bundlé dans le build (mode hors-ligne).
  const BASE = ((window as any).__TANDOR_BASE__ as any[]) || (REAL_PRODUCTS as any[]);

  // PRODUCTS est MUTÉ en place par appendBase() (infinite scroll) : les pages
  // gardent la même référence de tableau et y voient les nouveaux produits.
  const PRODUCTS = BASE.map(build);

  // Curseur de pagination posé par DashPage.tsx d'après la 1re réponse de l'API
  // ({ total, next_offset, has_more, apiBase }). Sert à charger les lots suivants.
  const PAGER = ((window as any).__TANDOR_PAGE__ as any) || {
    apiBase: '', total: PRODUCTS.length, nextOffset: null, hasMore: false, limit: 60,
  };
  // Anti double-fetch concurrent.
  let _loadingMore = false;

  // Dédup : on ne ré-insère jamais un produit déjà présent (par id).
  const _seenIds = new Set(PRODUCTS.map((p) => p.id));

  /* Mappe des enregistrements BASE bruts (forme API) et les pousse dans PRODUCTS
     SANS recréer le tableau (référence stable pour les pages). Renvoie le nombre
     réellement ajouté (après dédup). */
  function appendBase(rawArr) {
    let added = 0;
    (rawArr || []).forEach((raw) => {
      if (!raw || raw.id == null || _seenIds.has(raw.id)) return;
      _seenIds.add(raw.id);
      PRODUCTS.push(build(raw));
      added += 1;
    });
    return added;
  }

  /* Charge le lot suivant depuis l'API (offset = PAGER.nextOffset) et l'ajoute.
     Renvoie une promesse { added, hasMore }. Idempotent / non concurrent :
     si un chargement est déjà en cours ou s'il n'y a plus de page, no-op. */
  function loadMore() {
    if (_loadingMore || !PAGER.hasMore || PAGER.nextOffset == null || !PAGER.apiBase) {
      return Promise.resolve({ added: 0, hasMore: !!PAGER.hasMore });
    }
    _loadingMore = true;
    const url = `${String(PAGER.apiBase).replace(/\/$/, '')}/api/products?limit=${PAGER.limit}&offset=${PAGER.nextOffset}`;
    return authedFetch(url)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((json) => {
        const added = appendBase(Array.isArray(json.products) ? json.products : []);
        PAGER.total = json.total != null ? json.total : PAGER.total;
        PAGER.hasMore = !!json.has_more;
        PAGER.nextOffset = json.next_offset != null ? json.next_offset : null;
        return { added, hasMore: PAGER.hasMore };
      })
      .catch((err) => {
        console.warn('[Tandor] loadMore a échoué :', err);
        return { added: 0, hasMore: PAGER.hasMore };
      })
      .finally(() => { _loadingMore = false; });
  }

  /* ============================================================
     PAGINATION INDEXÉE (30/page) — Top 2000 par score Tandor.
     fetchPage({page, pageSize, filters, sort}) renvoie une promesse
     { products: [...built], meta: {...} }. Les filtres (q, min_score,
     catégorie, verdict, phase) sont envoyés au backend (contrat
     /api/products). En l'absence d'API (mode hors-ligne / JSON bundlé)
     ou si le réseau échoue, on pagine/filtre côté client sur PRODUCTS.

     Note d'honnêteté : on ne re-filtre JAMAIS côté client par-dessus une
     page renvoyée par le backend (cela fausserait le compteur total /
     page_count). On fait confiance à meta. Le filtre verdict est mappé
     sur le param `verdict` avec la valeur trapVerdict (VIABLE/RISKY/TRAP)
     — source de vérité du pivot anti-perte. ============================ */
  const CATS_FOR_SEARCH = CATS;

  function buildPageUrl(base, opts) {
    const sp = new URLSearchParams();
    sp.set('limit', String(opts.pageSize));
    sp.set('page', String(opts.page));
    sp.set('sort', opts.sort || 'tandor');
    const f = opts.filters || {};
    if (f.q) sp.set('q', f.q);
    if (f.minScore) sp.set('min_score', String(f.minScore));
    if (f.cats && f.cats.length) sp.set('cat', f.cats.join(','));
    if (f.verdicts && f.verdicts.length) sp.set('verdict', f.verdicts.join(','));
    if (f.phases && f.phases.length) sp.set('phase', f.phases.join(','));
    return `${base}/api/products?${sp.toString()}`;
  }

  // Filtre + tri (Tandor décroissant) côté client sur PRODUCTS (repli hors-ligne).
  function clientFilterSort(opts) {
    const f = opts.filters || {};
    const q = (f.q || '').trim().toLowerCase();
    const arr = PRODUCTS.filter((p) => {
      if (f.verdicts && f.verdicts.length && !f.verdicts.includes(p.trapVerdict)) return false;
      if (f.phases && f.phases.length && !f.phases.includes(p.phase)) return false;
      if (f.cats && f.cats.length && !f.cats.includes(p.cat)) return false;
      if (f.minScore && p.tandor < f.minScore) return false;
      if (q) {
        const c = CATS_FOR_SEARCH[p.cat] || {};
        const hit = p.name.toLowerCase().includes(q)
          || (c.en || '').toLowerCase().includes(q)
          || (c.fr || '').toLowerCase().includes(q);
        if (!hit) return false;
      }
      return true;
    });
    arr.sort((a, b) => b.tandor - a.tandor);
    return arr;
  }

  function clientPage(opts) {
    const arr = clientFilterSort(opts);
    const total = arr.length;
    const pageSize = opts.pageSize;
    const pageCount = Math.max(1, Math.ceil(total / pageSize));
    const page = Math.min(Math.max(1, opts.page), pageCount);
    const offset = (page - 1) * pageSize;
    const slice = arr.slice(offset, offset + pageSize);
    return {
      products: slice,
      meta: {
        total, page, page_size: pageSize, page_count: pageCount,
        offset, limit: pageSize, returned: slice.length,
        has_more: page < pageCount,
        next_offset: page < pageCount ? offset + pageSize : null,
      },
    };
  }

  // Normalise la meta backend (acceptée à plat OU sous json.meta) + valeurs sûres.
  function normalizeMeta(meta, opts, returned) {
    meta = meta || {};
    const pageSize = meta.page_size != null ? meta.page_size : opts.pageSize;
    const total = meta.total != null ? meta.total : returned;
    const pageCount = meta.page_count != null ? meta.page_count : Math.max(1, Math.ceil(total / (pageSize || 1)));
    const page = meta.page != null ? meta.page : opts.page;
    return {
      total, page, page_size: pageSize, page_count: pageCount,
      offset: meta.offset != null ? meta.offset : (page - 1) * pageSize,
      limit: meta.limit != null ? meta.limit : pageSize,
      returned: meta.returned != null ? meta.returned : returned,
      has_more: meta.has_more != null ? meta.has_more : page < pageCount,
      next_offset: meta.next_offset != null ? meta.next_offset : null,
    };
  }

  // Intègre une liste brute (forme API) dans PRODUCTS (dédup) et renvoie les
  // produits BÂTIS correspondants, dans l'ordre reçu (réf. stables pour openProduct).
  function mergeRaw(rawArr) {
    return (rawArr || []).map((raw) => {
      if (!raw || raw.id == null) return raw ? build(raw) : null;
      const existing = PRODUCTS.find((p) => p.id === raw.id);
      if (existing) return existing;
      const built = build(raw);
      _seenIds.add(raw.id);
      PRODUCTS.push(built);
      return built;
    }).filter(Boolean);
  }

  function fetchPage(opts) {
    opts = opts || {};
    opts.page = Math.max(1, opts.page || 1);
    opts.pageSize = opts.pageSize || 30;
    opts.sort = opts.sort || 'tandor';
    const base = PAGER.apiBase ? String(PAGER.apiBase).replace(/\/$/, '') : '';
    if (!base) return Promise.resolve(clientPage(opts));
    return authedFetch(buildPageUrl(base, opts))
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((json) => {
        const raw = Array.isArray(json.products) ? json.products : [];
        const built = mergeRaw(raw);
        const meta = normalizeMeta(json.meta || json, opts, built.length);
        if (meta.total != null) PAGER.total = meta.total;
        return { products: built, meta };
      })
      .catch((err) => {
        console.warn('[Tandor] fetchPage a échoué, repli client :', err);
        return clientPage(opts);
      });
  }

  /* ============================================================
     ALERTES + DÉTAIL PRODUIT — données RÉELLES du backend.
     Règle d'honnêteté : tout échec réseau / endpoint absent renvoie
     [] ou null. On n'invente JAMAIS d'alerte ni d'historique.
     Base API = __TANDOR_PAGE__.apiBase (injectée par DashPage) sinon
     l'origine courante (proxy CRA en dev → /api).
     ============================================================ */
  function apiBase() {
    try {
      const pg = (window as any).__TANDOR_PAGE__;
      const b = pg && pg.apiBase;
      return (b ? String(b) : window.location.origin).replace(/\/$/, '');
    } catch (e) { return ''; }
  }

  // GET /api/alerts -> tableau d'alertes (jamais inventé). [] si échec/absent.
  // Chaque alerte : { id, type, product_id, product_name, message,
  //                   severity:'info'|'warn'|'high', created_at, delivered }.
  function fetchAlerts() {
    return authedFetch(`${apiBase()}/api/alerts`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => (j && Array.isArray(j.alerts) ? j.alerts : []))
      .catch((err) => { console.warn('[Tandor] fetchAlerts a échoué :', err); return []; });
  }

  // GET /api/product/{id} -> { score, history } ou null.
  // Tolère la forme « contrat » ({score,history}) ET la forme à plat (produit
  // complet avec un champ `history`). history.{sales,amazon} = bloc
  // {points,dates,days,values,spanDays} ou null. N'invente jamais d'historique.
  function fetchProductDetail(id) {
    if (id == null) return Promise.resolve(null);
    return authedFetch(`${apiBase()}/api/product/${encodeURIComponent(id)}`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => {
        if (!j || typeof j !== 'object') return null;
        const score = j.score && typeof j.score === 'object' ? j.score : j;
        const history = j.history || (j.score && j.score.history) || null;
        return { score, history };
      })
      .catch((err) => { console.warn('[Tandor] fetchProductDetail a échoué :', err); return null; });
  }

  /* ---------- markets ---------- */
  const MARKETS = [
    { code: 'FR', flag: '🇫🇷', en: 'France', fr: 'France' },
    { code: 'EU', flag: '🇪🇺', en: 'Europe', fr: 'Europe' },
    { code: 'US', flag: '🇺🇸', en: 'United States', fr: 'États-Unis' },
    { code: 'UK', flag: '🇬🇧', en: 'United Kingdom', fr: 'Royaume-Uni' },
    { code: 'DE', flag: '🇩🇪', en: 'Germany', fr: 'Allemagne' },
    { code: 'WW', flag: '🌍', en: 'World', fr: 'Monde' },
  ];

  /* ---------- i18n strings ---------- */
  const STR = {
    en: {
      greeting: 'Good morning', sub_n: (n) => `${n} new opportunities detected since yesterday`,
      p_24h: '24h', p_7d: '7d', p_30d: '30d',
      kpi_active: 'Active opportunities', kpi_score: 'Market avg. score',
      kpi_margin: 'Median net margin', kpi_emerg: 'Emerging products',
      vs_prev: 'vs previous', this_period: 'this period',
      feed: 'Opportunity feed', feed_sub: 'Recent detections, newest first',
      champion: 'Champion of the day', detected: 'detected', ago: 'ago',
      hr: 'h', day: 'd', view_all: 'View all', growth_mo: '/mo',
      radar: 'Express radar', radar_sub: 'Momentum × maturity · last 20',
      q_emerg: 'Emergent · high potential', q_growth: 'Growing', q_sat: 'Saturated', q_avoid: 'Avoid',
      momentum: 'Momentum', maturity: 'Maturity',
      signals: 'Signals of the day', top_trends: 'Top Google Trends',
      top_reddit: 'Top Reddit velocity', top_corro: 'Strongest corroboration',
      corro_by: 'corroborated by', sources: 'sources',
      cat_dist: 'Category distribution', cat_sub: 'Buy verdicts by category · colour = avg score',
      season: 'Seasonality', season_sub: 'Demand multiplier · month × category',
      risk_low: 'Low risk', risk_mod: 'Moderate risk', risk_high: 'High risk',
      risk: 'Risk', conf: 'Confidence', score: 'Tandor score', verdict: 'Verdict',
      live: 'Data up to date', live_ago: '2h ago', live_pipeline: 'Pipeline status',
      run_cj: 'CJ catalogue', run_trends: 'Google Trends', run_reddit: 'Reddit',
      next_run: 'Next collection', in_min: 'in 41 min', ok: 'OK', limited: 'rate-limited',
      search_ph: 'Search a product, category, signal…',
      notif: 'Notifications', notif_unread: 'unread', mark_read: 'Mark all read',
      nav_disc: 'Discovery', nav_analysis: 'Analysis', nav_space: 'My space',
      n_home: 'Home', n_discovery: 'Product Discovery', n_radar: 'Opportunity Radar',
      n_trends: 'Trend Analysis', n_reddit: 'Reddit Intelligence', n_market: 'Market Signals', n_analytics: 'Analytics',
      n_saved: 'Saved', n_watch: 'Watchlists', n_alerts: 'Alerts',
      n_settings: 'Settings', n_billing: 'Billing', n_account: 'Account',
      plan: 'Scale', plan_usage: (a, b) => `${a} / ${b} products tracked`, upgrade: 'Upgrade',
      cmd_pages: 'Pages', cmd_products: 'Products', cmd_actions: 'Actions',
      a_new_watch: 'Create a watchlist', a_new_alert: 'Create an alert', a_export: 'Export today’s feed', a_toggle_theme: 'Toggle density',
      collapse: 'Collapse', soon: 'Coming soon', soon_msg: 'This page is on the roadmap — Dashboard Home is the live prototype.',
      saved_toast: 'Saved to your library', period_changed: 'Period',
      why: 'Why this score', open_detail: 'Open product dossier',
    },
    fr: {
      greeting: 'Bonjour', sub_n: (n) => `${n} nouvelles opportunités détectées depuis hier`,
      p_24h: '24h', p_7d: '7j', p_30d: '30j',
      kpi_active: 'Opportunités actives', kpi_score: 'Score moyen du marché',
      kpi_margin: 'Marge nette médiane', kpi_emerg: 'Produits émergents',
      vs_prev: 'vs période préc.', this_period: 'sur la période',
      feed: 'Flux d’opportunités', feed_sub: 'Détections récentes, les plus récentes d’abord',
      champion: 'Champion du jour', detected: 'détecté', ago: 'il y a',
      hr: 'h', day: 'j', view_all: 'Tout voir', growth_mo: '/mois',
      radar: 'Radar express', radar_sub: 'Momentum × maturité · 20 derniers',
      q_emerg: 'Émergent · fort potentiel', q_growth: 'En croissance', q_sat: 'Saturé', q_avoid: 'À éviter',
      momentum: 'Momentum', maturity: 'Maturité',
      signals: 'Signaux du jour', top_trends: 'Top Google Trends',
      top_reddit: 'Top vélocité Reddit', top_corro: 'Meilleure corroboration',
      corro_by: 'corroboré par', sources: 'sources',
      cat_dist: 'Répartition par catégorie', cat_sub: 'Verdicts Acheter par catégorie · couleur = score moyen',
      season: 'Saisonnalité', season_sub: 'Multiplicateur de demande · mois × catégorie',
      risk_low: 'Risque faible', risk_mod: 'Risque modéré', risk_high: 'Risque élevé',
      risk: 'Risque', conf: 'Confiance', score: 'Score Tandor', verdict: 'Verdict',
      live: 'Données à jour', live_ago: 'il y a 2 h', live_pipeline: 'État du pipeline',
      run_cj: 'Catalogue CJ', run_trends: 'Google Trends', run_reddit: 'Reddit',
      next_run: 'Prochaine collecte', in_min: 'dans 41 min', ok: 'OK', limited: 'limité',
      search_ph: 'Rechercher un produit, une catégorie, un signal…',
      notif: 'Notifications', notif_unread: 'non lues', mark_read: 'Tout marquer lu',
      nav_disc: 'Découverte', nav_analysis: 'Analyse', nav_space: 'Mon espace',
      n_home: 'Accueil', n_discovery: 'Product Discovery', n_radar: 'Opportunity Radar',
      n_trends: 'Analyse de tendances', n_reddit: 'Reddit Intelligence', n_market: 'Signaux marché', n_analytics: 'Analytics',
      n_saved: 'Sauvegardés', n_watch: 'Watchlists', n_alerts: 'Alertes',
      n_settings: 'Réglages', n_billing: 'Facturation', n_account: 'Compte',
      plan: 'Scale', plan_usage: (a, b) => `${a} / ${b} produits suivis`, upgrade: 'Upgrade',
      cmd_pages: 'Pages', cmd_products: 'Produits', cmd_actions: 'Actions',
      a_new_watch: 'Créer une watchlist', a_new_alert: 'Créer une alerte', a_export: 'Exporter le flux du jour', a_toggle_theme: 'Changer la densité',
      collapse: 'Replier', soon: 'Bientôt disponible', soon_msg: 'Cette page est sur la feuille de route — l’Accueil est le prototype actif.',
      saved_toast: 'Ajouté à votre bibliothèque', period_changed: 'Période',
      why: 'Pourquoi ce score', open_detail: 'Ouvrir le dossier produit',
    },
  };

  const MONTHS = {
    en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    fr: ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'],
  };

  // seasonality matrix month×category (multiplier) — procedural from peak months
  function seasonMatrix() {
    const cats = ['WELLNESS', 'HOME', 'BEAUTY', 'TECH', 'FITNESS', 'OUTDOOR', 'PETS', 'KITCHEN'];
    const peaks = { WELLNESS: 11, HOME: 12, BEAUTY: 12, TECH: 12, FITNESS: 1, OUTDOOR: 6, PETS: 4, KITCHEN: 11 };
    return cats.map((c) => {
      const pk = peaks[c];
      const row = [];
      for (let m = 1; m <= 12; m++) {
        const d = Math.min(Math.abs(m - pk), 12 - Math.abs(m - pk));
        row.push(+(0.72 + 0.6 * Math.cos((d / 6) * Math.PI / 2)).toFixed(2));
      }
      return { cat: c, vals: row };
    });
  }

  window.TANDOR = {
    PRODUCTS, PHASES, VERDICTS, TRAP_VERDICTS, trapMeta, CATS, CAT_HUE, MARKETS, STR, MONTHS,
    seasonMatrix, clamp,
    // current month index (0-based) — June for the demo
    CUR_MONTH: 5,
    // Pagination / infinite scroll : curseur + chargeur de lots suivants.
    PAGER, appendBase, loadMore,
    // Pagination INDEXÉE (30/page) utilisée par Discovery : fetchPage renvoie
    // { products, meta } pour une page donnée + filtres (backend ou repli client).
    fetchPage,
    // Alertes RÉELLES (GET /api/alerts) + détail produit avec historique réel
    // (GET /api/product/{id}). [] / null en cas d'échec — aucune donnée inventée.
    fetchAlerts, fetchProductDetail,
    get hasMore() { return !!PAGER.hasMore; },
    get total() { return PAGER.total; },
  };
})();
