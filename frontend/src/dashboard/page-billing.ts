/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-billing.js   (Billing)
   Current plan, usage gauges, plan comparison, real Stripe checkout.
   ------------------------------------------------------------
   Le checkout est branché sur le contrat backend :
     POST /api/checkout  { plan: 'pro'|'scale' }  -> { url }
   - 200 + {url}  : redirection vers Stripe Checkout hébergé.
   - 503          : Stripe pas (encore) configuré côté serveur
                    (STRIPE_SECRET_KEY manquant). On affiche un message
                    HONNÊTE « bientôt / configuration requise », jamais
                    un faux succès de paiement.
   ============================================================ */
import { authedFetch } from '../auth/api';
import { auth } from '../auth/firebase';

export function mountBilling() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic;
  const money = Sh.money;

  const STR = {
    en: { title: 'Billing', sub: 'plan · usage · checkout', period_m: 'Monthly', period_y: 'Annual',
      current: 'Current plan', usage: 'Usage this cycle', manage: 'Manage payment',
      u_tracked: 'Products tracked', u_alerts: 'Active alerts', u_exports: 'Exports',
      plans: 'Plans', plans_s: 'upgrade anytime', mo: '/mo', yr: '/yr', save2: 'save 2 months',
      cta_cur: 'Current plan', cta_up: 'Upgrade', cta_down: 'Switch', popular: 'Most popular',
      pay: 'Payment method', no_pay: 'No payment method on file. Choose a plan to subscribe via Stripe.',
      reassure: 'Secure payments by Stripe · cancel anytime · VAT invoices',
      f_free: ['50 scored products / day', '1 watchlist · 7-day history', 'Tandor score & verdict', 'In-app only'],
      f_pro: ['2,000 scored products / day', 'Unlimited watchlists', 'Email + in-app alerts', 'Reddit, Trends & CSV export'],
      f_scale: ['Unlimited scored products', 'Multi-market & multi-seat', 'Webhook + API access', 'Full backtest · priority support'],
      free: 'Free', redirecting: 'Redirecting…',
      soon_t: 'Payments coming soon', soon_m: 'Online checkout is not active yet — Stripe configuration required. Your account is unchanged; nothing was charged.',
      soon_btn: 'Coming soon', err_net: 'Network error — please try again', err_pay: 'Payment unavailable right now', err_resp: 'Unexpected checkout response' },
    fr: { title: 'Facturation', sub: 'plan · usage · paiement', period_m: 'Mensuel', period_y: 'Annuel',
      current: 'Plan actuel', usage: 'Usage ce cycle', manage: 'Gérer le paiement',
      u_tracked: 'Produits suivis', u_alerts: 'Alertes actives', u_exports: 'Exports',
      plans: 'Plans', plans_s: 'changez de plan à tout moment', mo: '/mois', yr: '/an', save2: '2 mois offerts',
      cta_cur: 'Plan actuel', cta_up: 'Passer au supérieur', cta_down: 'Changer', popular: 'Le plus choisi',
      pay: 'Moyen de paiement', no_pay: 'Aucun moyen de paiement enregistré. Choisissez un plan pour vous abonner via Stripe.',
      reassure: 'Paiements sécurisés par Stripe · annulation à tout moment · factures TVA',
      f_free: ['50 produits scorés / jour', '1 watchlist · historique 7 j', 'Score Tandor & verdict', 'In-app uniquement'],
      f_pro: ['2 000 produits scorés / jour', 'Watchlists illimitées', 'Alertes email + in-app', 'Reddit, Trends & export CSV'],
      f_scale: ['Produits scorés illimités', 'Multi-marchés & multi-sièges', 'Accès Webhook + API', 'Backtest complet · support prioritaire'],
      free: 'Gratuit', redirecting: 'Redirection…',
      soon_t: 'Paiement bientôt disponible', soon_m: 'Le paiement en ligne n’est pas encore actif — configuration Stripe requise. Votre compte est inchangé ; rien n’a été débité.',
      soon_btn: 'Bientôt', err_net: 'Erreur réseau — réessayez', err_pay: 'Paiement indisponible pour le moment', err_resp: 'Réponse de paiement inattendue' },
  };
  const L = () => STR[Sh.lang];
  let period = 'm';

  // Plans alignés sur le contrat backend : seuls 'pro' et 'scale' sont des
  // plans de checkout valides. 'free' n'a pas de checkout (plan par défaut).
  const PLANS = [
    { k: 'free',  name: 'Free',  m: 0,   y: 0,    fk: 'f_free',  co: null },
    { k: 'pro',   name: 'Pro',   m: 49,  y: 490,  fk: 'f_pro',   co: 'pro',   popular: true },
    { k: 'scale', name: 'Scale', m: 149, y: 1490, fk: 'f_scale', co: 'scale' },
  ];

  // Plan courant : claim `plan` du token Firebase si présent, sinon 'free'.
  // Le mapping ramène les anciens libellés ('starter', 'growth', 'agency'…)
  // vers les clés connues, sans inventer de plan.
  let curPlan = 'free';
  let stripeSoon = false; // passe à true si le backend renvoie 503
  let busy = false;

  function normPlan(p) {
    const v = String(p || '').toLowerCase();
    if (v === 'scale' || v === 'agency' || v === 'agence') return 'scale';
    if (v === 'pro' || v === 'growth' || v === 'starter') return 'pro';
    return 'free';
  }

  async function loadPlan() {
    try {
      const u = auth.currentUser;
      if (u) {
        const r = await u.getIdTokenResult();
        if (r && r.claims && r.claims.plan) curPlan = normPlan(r.claims.plan);
      }
    } catch (_) { /* token indisponible -> on garde 'free' */ }
  }

  function planByKey(k) { return PLANS.find((p) => p.k === k) || PLANS[0]; }
  function rank(k) { return PLANS.findIndex((p) => p.k === k); }

  async function checkout(plan, btn) {
    if (busy || !plan) return;
    busy = true;
    const s = L();
    const orig = btn ? btn.innerHTML : '';
    if (btn) { btn.disabled = true; btn.innerHTML = s.redirecting; }
    let redirected = false;
    try {
      const res = await authedFetch('/api/checkout', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ plan }),
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        if (data && data.url) { redirected = true; window.location.href = data.url; return; }
        Sh.toast(s.err_resp);
      } else if (res.status === 503) {
        // Stripe pas configuré : message honnête, AUCUN faux succès.
        stripeSoon = true;
        Sh.toast(s.soon_t + ' · ' + (Sh.lang === 'fr' ? 'config requise' : 'config required'));
        render();
        return;
      } else {
        const d = await res.json().catch(() => ({}));
        Sh.toast((d && d.detail) ? d.detail : s.err_pay);
      }
    } catch (_) {
      Sh.toast(s.err_net);
    } finally {
      busy = false;
      if (btn && !redirected) { btn.disabled = false; btn.innerHTML = orig; }
    }
  }

  function render() {
    const s = L();
    const cur = planByKey(curPlan);
    const curPrice = period === 'm' ? cur.m : Math.round(cur.y / 12);
    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
        <div class="seg" id="perSeg"><div class="seg-thumb"></div>
          <button data-p="m" class="${period === 'm' ? 'on' : ''}">${s.period_m}</button>
          <button data-p="y" class="${period === 'y' ? 'on' : ''}">${s.period_y}</button></div>
      </div>
      ${stripeSoon ? `<div class="panel rv" style="margin-bottom:14px;border-color:var(--warn,#caa23a)">
        <div class="set-pad" style="display:flex;gap:10px;align-items:flex-start">
          <span style="flex:0 0 auto;margin-top:1px">${ic('lock')}</span>
          <div><div style="font-weight:600">${s.soon_t}</div>
          <div class="sub" style="margin-top:2px">${s.soon_m}</div></div>
        </div></div>` : ''}
      <div class="section-row grid-21">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.current}</div></div>
            <span class="status-pill active">${cur.k === 'free' ? s.free : cur.name}</span></div>
          <div class="set-pad">
            <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px"><span class="mono" style="font-size:34px;font-weight:600;letter-spacing:-.02em">${cur.k === 'free' ? s.free : money(curPrice, 0)}</span>${cur.k === 'free' ? '' : `<span style="color:var(--text-tertiary)">${s.mo}</span>`}</div>
            <div style="margin-top:14px" id="usageBox"></div>
          </div>
        </section>
        <aside class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.pay}</div></div></div>
          <div class="set-pad"><div class="sub" style="margin-bottom:12px">${s.no_pay}</div>
            <button class="btn-ghost" id="payBtn" style="width:100%" ${stripeSoon ? 'disabled style="opacity:.6;cursor:default;width:100%"' : ''}>${ic('card')}${stripeSoon ? s.soon_btn : s.manage}</button></div>
        </aside>
      </div>
      <section class="panel rv" style="margin:18px 0">
        <div class="panel-h"><div><div class="ttl">${s.plans}</div><div class="sub">${s.plans_s}${period === 'y' ? ' · ' + s.save2 : ''}</div></div></div>
        <div class="set-pad"><div class="plan-cards" id="planCards"></div>
          <div class="micro" style="text-align:center;margin-top:16px;text-transform:none;letter-spacing:0">${ic('lock')} ${s.reassure}</div></div>
      </section>`;
    positionSeg();
    $$('#perSeg button').forEach((b) => b.addEventListener('click', () => { period = b.dataset.p; render(); }));
    renderUsage(); renderPlans();
    const payBtn = $('#payBtn');
    if (payBtn && !stripeSoon) {
      // « Gérer le paiement » = ouvrir un checkout pour le plan payant courant,
      // ou Pro par défaut si l'utilisateur est en Free.
      payBtn.addEventListener('click', () => checkout(curPlan === 'free' ? 'pro' : (planByKey(curPlan).co || 'pro'), payBtn));
    }
  }
  function positionSeg() { const seg = $('#perSeg'), on = $('.on', seg), th = $('.seg-thumb', seg); if (on && th) { th.style.left = on.offsetLeft + 'px'; th.style.width = on.offsetWidth + 'px'; } }

  function renderUsage() {
    const s = L();
    const rows = [[s.u_tracked, 1240, 2000], [s.u_alerts, 18, 50], [s.u_exports, 42, 100]];
    $('#usageBox').innerHTML = rows.map(([l, a, b]) => {
      const pc = Math.round(a / b * 100), warn = pc > 80;
      return `<div class="usage-row"><div class="usage-h"><span>${l}</span><b>${Sh.fmt(a)} / ${Sh.fmt(b)}</b></div><div class="usage-bar"><i class="${warn ? 'warn' : ''}" style="width:${pc}%"></i></div></div>`;
    }).join('');
  }

  function renderPlans() {
    const s = L();
    const curRank = rank(curPlan);
    $('#planCards').innerHTML = PLANS.map((p) => {
      const price = period === 'm' ? p.m : Math.round(p.y / 12);
      const isCur = p.k === curPlan;
      const cta = isCur ? s.cta_cur : (rank(p.k) > curRank ? s.cta_up : s.cta_down);
      const ctaCls = isCur ? 'btn-ghost' : p.popular ? 'btn-pri btn-signal' : 'btn-ghost';
      // Bouton désactivé si : plan courant, plan free (pas de checkout), ou Stripe pas configuré.
      const disabled = isCur || !p.co || stripeSoon;
      const label = (stripeSoon && !isCur && p.co) ? s.soon_btn : cta;
      return `<div class="plan-card ${isCur ? 'cur' : ''}">
        ${p.popular ? `<span class="pc-tag">${s.popular}</span>` : ''}
        <div class="pc-name">${p.name}</div>
        <div><span class="pc-price">${p.k === 'free' ? s.free : money(price, 0)}</span>${p.k === 'free' ? '' : `<small>${s.mo}</small>`}</div>
        <div class="pc-feats">${s[p.fk].map((f) => `<div class="pc-feat">${ic('check')}${f}</div>`).join('')}</div>
        <button class="${ctaCls}" data-co="${p.co || ''}" ${disabled ? 'disabled style="opacity:.6;cursor:default"' : ''}>${label}</button>
      </div>`;
    }).join('');
    $$('#planCards button:not([disabled])').forEach((b) => b.addEventListener('click', () => {
      const co = b.dataset.co;
      if (co) checkout(co, b);
    }));
  }

  Sh.start({ active: 'n_billing', render });
  // Récupère le plan réel puis re-render (async, sans bloquer le premier paint).
  loadPlan().then(() => render());
}
