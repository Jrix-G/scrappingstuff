/* eslint-disable */
// @ts-nocheck
import REAL_PRODUCTS from './products.json';
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
    // growth score: map monthly_growth [-0.5 .. +1.5] → 0..100
    const growthScore = round(clamp((base.growth + 0.5) / 2.0, 0, 1) * 100);
    // risk: low confidence OR high volatility OR no sellers → risk up
    let riskN = 0;
    if (base.confidence < 0.6) riskN += 1.4;
    if (base.confidence < 0.45) riskN += 1;
    if (base.volatility > 0.6) riskN += 1.2;
    if (base.listed === 0) riskN += 1.5;
    if (base.listed > 70) riskN += 0.6;
    const risk = riskN >= 2.2 ? 'high' : riskN >= 1 ? 'mod' : 'low';

    // momentum (0..100) for radar: velocity + acceleration blend
    const momentum = round(clamp(growthScore * 0.7 + base.organic * 0.3, 0, 100));
    // maturity (0..100): saturation proxy from listed sellers + age
    const maturity = round(clamp(base.listed * 0.7 + (base.age / 120) * 30, 0, 100));

    /* time series (procedural, stable) */
    const trend = series(base.organic, base.growth, base.volatility, 30, rnd, 8, 96);
    const reddit = series(base.redditScore, base.growth * 0.9, base.volatility * 1.2, 12, rnd, 2, 40, true);
    const cj = ramp(Math.max(1, base.listed - round(base.growth * 14)), base.listed, 12, rnd);

    return Object.assign({}, base, {
      gross, margin_pct, tandor, growthScore, risk, momentum, maturity,
      catHue: CAT_HUE[base.cat], trend, reddit, cj,
    });
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
  // Données live injectées par Dashboard.tsx (fetch API du Pi) si dispo,
  // sinon fallback sur le JSON bundlé dans le build (mode hors-ligne).
  const BASE = ((window as any).__TANDOR_BASE__ as any[]) || (REAL_PRODUCTS as any[]);

  const PRODUCTS = BASE.map(build);

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
    PRODUCTS, PHASES, VERDICTS, CATS, CAT_HUE, MARKETS, STR, MONTHS,
    seasonMatrix, clamp,
    // current month index (0-based) — June for the demo
    CUR_MONTH: 5,
  };
})();
