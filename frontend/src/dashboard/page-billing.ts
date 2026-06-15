/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-billing.js   (Billing)
   Current plan, usage gauges, plan comparison, invoices, payment.
   ============================================================ */
export function mountBilling() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic;
  const money = Sh.money;

  const STR = {
    en: { title: 'Billing', sub: 'plan · usage · invoices', period_m: 'Monthly', period_y: 'Annual',
      current: 'Current plan', cur_s: 'renews 1 Jul 2026', usage: 'Usage this cycle', manage: 'Manage payment',
      u_tracked: 'Products tracked', u_alerts: 'Active alerts', u_exports: 'Exports',
      plans: 'Plans', plans_s: 'upgrade or downgrade anytime', mo: '/mo', yr: '/yr', save2: 'save 2 months',
      cta_cur: 'Current plan', cta_up: 'Upgrade', cta_down: 'Downgrade', popular: 'Most popular',
      invoices: 'Invoices', inv_date: 'Date', inv_desc: 'Description', inv_amt: 'Amount', inv_status: 'Status', inv_dl: 'PDF', paid: 'Paid',
      pay: 'Payment method', pay_s: 'Visa ending 4242 · expires 09/27', update: 'Update',
      reassure: 'Secure payments by Stripe · cancel anytime · VAT invoices',
      f_scale: ['2,000 tracked products', 'Unlimited watchlists', 'Webhook + API access', 'Priority signal refresh', '5 team seats'],
      f_growth: ['600 tracked products', '20 watchlists', 'Email + in-app alerts', 'Daily signal refresh', '2 team seats'],
      f_starter: ['150 tracked products', '3 watchlists', 'In-app alerts', 'Weekly signal refresh', '1 seat'],
      changed: 'Plan change requested' },
    fr: { title: 'Facturation', sub: 'plan · usage · factures', period_m: 'Mensuel', period_y: 'Annuel',
      current: 'Plan actuel', cur_s: 'renouvellement 1 juil. 2026', usage: 'Usage ce cycle', manage: 'Gérer le paiement',
      u_tracked: 'Produits suivis', u_alerts: 'Alertes actives', u_exports: 'Exports',
      plans: 'Plans', plans_s: 'changez de plan à tout moment', mo: '/mois', yr: '/an', save2: '2 mois offerts',
      cta_cur: 'Plan actuel', cta_up: 'Passer au supérieur', cta_down: 'Rétrograder', popular: 'Le plus choisi',
      invoices: 'Factures', inv_date: 'Date', inv_desc: 'Description', inv_amt: 'Montant', inv_status: 'Statut', inv_dl: 'PDF', paid: 'Payée',
      pay: 'Moyen de paiement', pay_s: 'Visa se terminant par 4242 · expire 09/27', update: 'Modifier',
      reassure: 'Paiements sécurisés par Stripe · annulation à tout moment · factures TVA',
      f_scale: ['2 000 produits suivis', 'Watchlists illimitées', 'Accès Webhook + API', 'Rafraîchissement prioritaire', '5 sièges équipe'],
      f_growth: ['600 produits suivis', '20 watchlists', 'Alertes email + in-app', 'Rafraîchissement quotidien', '2 sièges équipe'],
      f_starter: ['150 produits suivis', '3 watchlists', 'Alertes in-app', 'Rafraîchissement hebdo', '1 siège'],
      changed: 'Changement de plan demandé' },
  };
  const L = () => STR[Sh.lang];
  let period = 'm';

  const PLANS = [
    { k: 'starter', name: 'Starter', m: 89, y: 890, fk: 'f_starter' },
    { k: 'growth', name: 'Growth', m: 229, y: 2290, fk: 'f_growth', popular: true },
    { k: 'scale', name: 'Scale', m: 449, y: 4490, fk: 'f_scale', current: true },
  ];

  function render() {
    const s = L();
    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
        <div class="seg" id="perSeg"><div class="seg-thumb"></div>
          <button data-p="m" class="${period === 'm' ? 'on' : ''}">${s.period_m}</button>
          <button data-p="y" class="${period === 'y' ? 'on' : ''}">${s.period_y}</button></div>
      </div>
      <div class="section-row grid-21">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.current}</div><div class="sub">${s.cur_s}</div></div>
            <span class="status-pill active">Scale</span></div>
          <div class="set-pad">
            <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px"><span class="mono" style="font-size:34px;font-weight:600;letter-spacing:-.02em">${money(period === 'm' ? 449 : 374, 0)}</span><span style="color:var(--text-tertiary)">${period === 'm' ? s.mo : s.mo + ' · ' + s.yr}</span></div>
            <div style="margin-top:14px" id="usageBox"></div>
          </div>
        </section>
        <aside class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.pay}</div></div></div>
          <div class="pay-card"><span class="pay-brand">VISA</span><div style="flex:1"><div style="font-size:13px;font-weight:600">•••• •••• •••• 4242</div><div style="font-size:11.5px;color:var(--text-tertiary)">${s.pay_s.split('·').slice(-1)}</div></div></div>
          <div class="set-pad" style="padding-top:0"><button class="btn-ghost" id="payBtn" style="width:100%">${ic('card')}${s.update}</button></div>
        </aside>
      </div>
      <section class="panel rv" style="margin:18px 0">
        <div class="panel-h"><div><div class="ttl">${s.plans}</div><div class="sub">${s.plans_s}${period === 'y' ? ' · ' + s.save2 : ''}</div></div></div>
        <div class="set-pad"><div class="plan-cards" id="planCards"></div>
          <div class="micro" style="text-align:center;margin-top:16px;text-transform:none;letter-spacing:0">${ic('lock')} ${s.reassure}</div></div>
      </section>
      <section class="panel rv">
        <div class="panel-h"><div><div class="ttl">${s.invoices}</div></div></div>
        <div class="dg-scroll"><table class="inv-table"><thead><tr>
          <th>${s.inv_date}</th><th>${s.inv_desc}</th><th class="num">${s.inv_amt}</th><th>${s.inv_status}</th><th></th></tr></thead>
          <tbody id="invBody"></tbody></table></div>
      </section>`;
    positionSeg();
    $$('#perSeg button').forEach((b) => b.addEventListener('click', () => { period = b.dataset.p; render(); }));
    renderUsage(); renderPlans(); renderInvoices();
    $('#payBtn').addEventListener('click', () => Sh.toast(L().update + ' · ' + (Sh.lang === 'fr' ? 'bientôt' : 'soon')));
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
    $('#planCards').innerHTML = PLANS.map((p) => {
      const price = period === 'm' ? p.m : Math.round(p.y / 12);
      const cta = p.current ? s.cta_cur : (p.k === 'starter' || p.k === 'growth') ? (p.current ? s.cta_cur : s.cta_down) : s.cta_up;
      const ctaCls = p.current ? 'btn-ghost' : p.popular ? 'btn-pri btn-signal' : 'btn-ghost';
      return `<div class="plan-card ${p.current ? 'cur' : ''}">
        ${p.popular ? `<span class="pc-tag">${s.popular}</span>` : ''}
        <div class="pc-name">${p.name}</div>
        <div><span class="pc-price">${money(price, 0)}</span><small>${s.mo}</small></div>
        <div class="pc-feats">${s[p.fk].map((f) => `<div class="pc-feat">${ic('check')}${f}</div>`).join('')}</div>
        <button class="${ctaCls}" data-k="${p.k}" ${p.current ? 'disabled style="opacity:.6;cursor:default"' : ''}>${cta}</button>
      </div>`;
    }).join('');
    $$('#planCards button:not([disabled])').forEach((b) => b.addEventListener('click', () => Sh.toast(L().changed)));
  }

  function renderInvoices() {
    const s = L();
    const months = Sh.lang === 'fr' ? ['1 juin 2026', '1 mai 2026', '1 avr. 2026', '1 mars 2026', '1 févr. 2026'] : ['Jun 1, 2026', 'May 1, 2026', 'Apr 1, 2026', 'Mar 1, 2026', 'Feb 1, 2026'];
    $('#invBody').innerHTML = months.map((m, i) => `<tr>
      <td class="mono">${m}</td>
      <td>Tandor Scale · ${Sh.lang === 'fr' ? 'mensuel' : 'monthly'}</td>
      <td class="num">${money(449, 0)}</td>
      <td><span class="status-pill paid">${s.paid}</span></td>
      <td class="num"><a class="panel-link" href="#" data-dl="${i}">${ic('download')} ${s.inv_dl}</a></td></tr>`).join('');
    $$('#invBody [data-dl]').forEach((a) => a.addEventListener('click', (e) => { e.preventDefault(); Sh.toast(s.inv_dl + ' · ' + (Sh.lang === 'fr' ? 'téléchargement' : 'downloading')); }));
    $$('#invBody .panel-link svg').forEach((sv) => sv.style.width = '13px');
  }

  Sh.start({ active: 'n_billing', render });
}
