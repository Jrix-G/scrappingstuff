/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-alerts.js   (Alerts)
   No-code rule builder with live natural-language preview, the
   rules list (toggle / frequency / last fired) and a trigger log.
   ============================================================ */
import * as WL from './watchlist';

export function mountAlerts() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic;

  const STR = {
    en: { title: 'Alerts', sub: 'live decline alerts · rules · trigger log',
      builder: 'New rule', when: 'When', then: 'then notify', create: 'Create rule',
      m_score: 'Tandor score', m_growth: 'Monthly growth', m_phase: 'Phase change', m_new: 'New product in',
      o_above: 'rises above', o_below: 'falls below', o_enters: 'enters', o_appears: 'appears in',
      ch_app: 'In-app', ch_email: 'Email', ch_webhook: 'Webhook',
      rules: 'Active rules', rules_s: 'toggle, frequency, last fired',
      log: 'Trigger log', log_s: 'recently fired alerts', triggers: 'triggers', fired: 'last fired', never: 'never',
      nl_pre: 'When a product’s', nl_post: ', notify me', and: 'and',
      created: 'Rule created', day: 'd ago', hr: 'h ago',
      live: 'Active alerts', live_s: 'pinned products now in proven decline',
      decline: 'In decline', trap: 'Money trap', open: 'Open',
      empty_t: 'No active alerts', empty_s: 'When a watched product slides into proven decline, it shows up here. Pin products from Discovery to start monitoring.',
      explore: 'Explore Discovery',
      log_empty_t: 'No alerts fired yet', log_empty_s: 'The trigger log fills as your rules fire on real nightly collections.' },
    fr: { title: 'Alertes', sub: 'alertes de déclin en direct · règles · journal',
      builder: 'Nouvelle règle', when: 'Quand', then: 'alors notifier', create: 'Créer la règle',
      m_score: 'Score Tandor', m_growth: 'Croissance mensuelle', m_phase: 'Changement de phase', m_new: 'Nouveau produit en',
      o_above: 'dépasse', o_below: 'passe sous', o_enters: 'entre en', o_appears: 'apparaît en',
      ch_app: 'In-app', ch_email: 'Email', ch_webhook: 'Webhook',
      rules: 'Règles actives', rules_s: 'activation, fréquence, dernier déclenchement',
      log: 'Journal des déclenchements', log_s: 'alertes récemment déclenchées', triggers: 'déclenchements', fired: 'dernier', never: 'jamais',
      nl_pre: 'Quand le', nl_post: ', me notifier', and: 'et',
      created: 'Règle créée', day: 'j', hr: 'h',
      live: 'Alertes actives', live_s: 'produits épinglés actuellement en déclin prouvé',
      decline: 'En déclin', trap: 'Piège à fric', open: 'Ouvrir',
      empty_t: 'Aucune alerte active', empty_s: 'Quand un produit surveillé bascule en déclin prouvé, il apparaît ici. Épingle des produits depuis la Découverte pour les surveiller.',
      explore: 'Explorer la Découverte',
      log_empty_t: 'Aucune alerte déclenchée', log_empty_s: 'Le journal se remplit au fur et à mesure que tes règles se déclenchent sur les collectes nocturnes réelles.' },
  };
  const L = () => STR[Sh.lang];

  /* ---- live decline alerts derived from the watchlist ---- */
  let watchedIds = [];
  function declineFlag(p) { return (p.lossFlags || []).find((f) => f && f.name === 'déclin') || null; }
  function isDeclineAlert(p) { const f = declineFlag(p); return !!(f && f.level === 'red'); }
  function isTrapAlert(p) { return p.trapVerdict === 'TRAP'; }
  function watchedProducts() { return watchedIds.map((id) => P.find((p) => p.id === id)).filter(Boolean); }
  function activeAlerts() {
    // Decline-red is the primary alert; TRAP (without red decline) is secondary.
    const ps = watchedProducts();
    const decline = ps.filter(isDeclineAlert);
    const traps = ps.filter((p) => !isDeclineAlert(p) && isTrapAlert(p));
    return { decline, traps };
  }

  const METRICS = ['m_score', 'm_growth', 'm_phase', 'm_new'];
  function opsFor(m) { return m === 'm_phase' ? ['o_enters'] : m === 'm_new' ? ['o_appears'] : ['o_above', 'o_below']; }
  let bm = 'm_score', bop = 'o_above', bval = '80', chans = { app: true, email: true, webhook: false };

  // Starter rule templates. No fabricated fire history: freq=0, hrs=null
  // (never fired) until a real nightly collection triggers them.
  const RULES = [
    { metric: 'm_score', op: 'o_above', val: '80', chans: { app: true, email: true }, freq: 0, hrs: null, on: true },
    { metric: 'm_growth', op: 'o_above', val: '50%', chans: { app: true, webhook: true }, freq: 0, hrs: null, on: true },
    { metric: 'm_phase', op: 'o_enters', val: 'EMERGENT', chans: { app: true }, freq: 0, hrs: null, on: true },
    { metric: 'm_new', op: 'o_appears', val: 'WELLNESS', chans: { app: true, email: true }, freq: 0, hrs: null, on: false },
  ];
  function getRules() { try { const v = Sh.LS.get('alert_rules', null); return v ? JSON.parse(v) : RULES.slice(); } catch (e) { return RULES.slice(); } }
  function setRules(a) { Sh.LS.set('alert_rules', JSON.stringify(a)); }

  function valDisplay(m, v) { if (m === 'm_phase') return T.PHASES[v] ? T.PHASES[v][Sh.lang] : v; if (m === 'm_new') return T.CATS[v] ? T.CATS[v][Sh.lang] : v; return v; }
  function nl(r) {
    const s = L();
    const metricTxt = s[r.metric];
    const opTxt = s[r.op];
    const chTxt = Object.keys(r.chans).filter((k) => r.chans[k]).map((k) => s['ch_' + k]).join(` ${s.and} `);
    return `<span class="tok metric">${metricTxt}</span> ${opTxt} <span class="tok">${valDisplay(r.metric, r.val)}</span> — ${s.then.replace('then ', '').replace('alors ', '')} <span class="tok">${chTxt}</span>`;
  }

  function render() {
    const s = L();
    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
      </div>
      <section class="panel rv" style="margin-bottom:18px">
        <div class="panel-h"><div><div class="ttl">${s.live}</div><div class="sub">${s.live_s}</div></div></div>
        <div id="liveAlerts"></div>
      </section>
      <section class="panel rv" style="margin-bottom:18px">
        <div class="panel-h"><div><div class="ttl">${s.builder}</div></div></div>
        <div class="builder" id="builder"></div>
        <div class="nl-preview" id="nlPreview"></div>
        <div style="padding:0 18px 16px"><button class="btn-pri" id="createBtn">${ic('plus')}${s.create}</button></div>
      </section>
      <div class="section-row grid-2">
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.rules}</div><div class="sub">${s.rules_s}</div></div></div>
          <div id="rulesList"></div>
        </section>
        <section class="panel rv">
          <div class="panel-h"><div><div class="ttl">${s.log}</div><div class="sub">${s.log_s}</div></div></div>
          <div id="logList"></div>
        </section>
      </div>`;
    renderLiveAlerts(); renderBuilder(); renderRules(); renderLog();
    $('#createBtn').addEventListener('click', () => {
      const r = { metric: bm, op: bop, val: bval, chans: Object.assign({}, chans), freq: 0, hrs: null, on: true };
      const rl = getRules(); rl.unshift(r); setRules(rl); Sh.toast(s.created); renderRules();
    });
  }

  function renderLiveAlerts() {
    const s = L();
    if (!$('#liveAlerts')) return;
    const { decline, traps } = activeAlerts();
    if (!decline.length && !traps.length) {
      $('#liveAlerts').innerHTML = `<div style="padding:8px 18px 22px"><div class="empty" style="padding:18px 0">
        <div class="e-art">${ic('shield')}</div><div class="e-t">${s.empty_t}</div><div class="e-s">${s.empty_s}</div>
        <div class="e-actions"><a class="btn-pri" href="/discovery">${ic('compass')}${s.explore}</a></div></div></div>`;
      return;
    }
    const row = (p, kind) => {
      const isTrap = kind === 'trap';
      const col = isTrap ? 'var(--pass)' : 'var(--ph-decline)';
      const tag = isTrap ? s.trap : s.decline;
      const reason = isTrap ? (p.trapHeadline || '') : ((declineFlag(p) || {}).reason || '');
      return `<div class="log-row alert-live" data-id="${p.id}" style="cursor:pointer;border-left:3px solid ${col}">
        <span class="log-ico" style="background:${col}">${ic(isTrap ? 'flame' : 'activity')}</span>
        <div class="log-t"><b>${p.name}</b><span class="badge" style="margin-left:8px;color:${col};border:1px solid ${col}">${tag}</span>
          <div class="micro" style="margin-top:3px;color:var(--text-secondary)">${reason}</div></div>
        <button class="btn-ghost btn-sm" data-act="open">${ic('arrowUR')}${s.open}</button></div>`;
    };
    $('#liveAlerts').innerHTML =
      decline.map((p) => row(p, 'decline')).join('') +
      traps.map((p) => row(p, 'trap')).join('');
    $$('#liveAlerts .alert-live').forEach((r) => r.addEventListener('click', () => {
      Sh.openProduct(P.find((p) => p.id === r.dataset.id));
    }));
  }

  function renderBuilder() {
    const s = L();
    const ops = opsFor(bm);
    if (!ops.includes(bop)) bop = ops[0];
    let valCtl = '';
    if (bm === 'm_phase') valCtl = `<div class="sel-wrap"><select class="sel" id="bVal">${['EMERGENT', 'EARLY_GROWTH', 'GROWTH', 'PEAK'].map((p) => `<option value="${p}" ${bval === p ? 'selected' : ''}>${T.PHASES[p][Sh.lang]}</option>`).join('')}</select></div>`;
    else if (bm === 'm_new') valCtl = `<div class="sel-wrap"><select class="sel" id="bVal">${Object.keys(T.CATS).filter((c) => P.some((p) => p.cat === c)).map((c) => `<option value="${c}" ${bval === c ? 'selected' : ''}>${T.CATS[c][Sh.lang]}</option>`).join('')}</select></div>`;
    else valCtl = `<input class="inp" id="bVal" style="width:90px" value="${bval}" />`;
    $('#builder').innerHTML = `
      <span class="b-lbl">${s.when}</span>
      <div class="sel-wrap"><select class="sel" id="bMetric">${METRICS.map((m) => `<option value="${m}" ${m === bm ? 'selected' : ''}>${s[m]}</option>`).join('')}</select></div>
      ${bm === 'm_new' || bm === 'm_phase' ? `<span class="b-lbl">${s[ops[0]]}</span>` : `<div class="sel-wrap"><select class="sel" id="bOp">${ops.map((o) => `<option value="${o}" ${o === bop ? 'selected' : ''}>${s[o]}</option>`).join('')}</select></div>`}
      ${valCtl}
      <span class="b-lbl">${s.then}</span>
      <div style="display:flex;gap:6px">${[['app', 'ch_app'], ['email', 'ch_email'], ['webhook', 'ch_webhook']].map(([k, lbl]) => `<button class="btn-ghost btn-sm chan ${chans[k] ? 'on' : ''}" data-ch="${k}">${ic(k === 'webhook' ? 'webhook' : k === 'email' ? 'mail' : 'bell')}${s[lbl]}</button>`).join('')}</div>`;
    $('#bMetric').addEventListener('change', (e) => { bm = e.target.value; bval = bm === 'm_phase' ? 'EMERGENT' : bm === 'm_new' ? 'WELLNESS' : bm === 'm_growth' ? '50%' : '80'; renderBuilder(); updatePreview(); });
    if ($('#bOp')) $('#bOp').addEventListener('change', (e) => { bop = e.target.value; updatePreview(); });
    $('#bVal').addEventListener('input', (e) => { bval = e.target.value; updatePreview(); });
    $('#bVal').addEventListener('change', (e) => { bval = e.target.value; updatePreview(); });
    $$('#builder .chan').forEach((b) => b.addEventListener('click', () => { chans[b.dataset.ch] = !chans[b.dataset.ch]; b.classList.toggle('on'); updatePreview(); }));
    updatePreview();
  }
  function updatePreview() { $('#nlPreview').innerHTML = nl({ metric: bm, op: bop, val: bval, chans }); }

  function renderRules() {
    const s = L(), rules = getRules();
    $('#rulesList').innerHTML = rules.map((r, i) => {
      const ago = r.hrs == null ? s.never : r.hrs < 24 ? `${r.hrs}${s.hr === 'h' ? 'h' : ' h'}` : `${Math.round(r.hrs / 24)}${s.day}`;
      return `<div class="alert-rule">
        <div><div class="ar-nl">${nl(r)}</div>
          <div class="ar-meta"><span>${r.freq} ${s.triggers}</span><span>${s.fired}: ${ago}</span></div></div>
        <div class="ar-right">
          <div class="ar-chan">${[['app', 'bell'], ['email', 'mail'], ['webhook', 'webhook']].map(([k, icn]) => `<span class="${r.chans[k] ? 'on' : ''}">${ic(icn)}</span>`).join('')}</div>
          <div class="switch ${r.on ? 'on' : ''}" data-i="${i}"></div></div></div>`;
    }).join('');
    $$('#rulesList .switch').forEach((sw) => sw.addEventListener('click', () => { const i = +sw.dataset.i; const rl = getRules(); rl[i].on = !rl[i].on; setRules(rl); sw.classList.toggle('on'); }));
  }

  function renderLog() {
    const s = L();
    // No real fired-alert history exists yet (rules fire on nightly collections,
    // which aren't logged client-side). Show an honest empty-state rather than
    // fabricating a trigger feed from detectedHrs.
    $('#logList').innerHTML = `<div style="padding:8px 18px 22px"><div class="empty" style="padding:18px 0">
      <div class="e-art">${ic('zap')}</div>
      <div class="e-t">${s.log_empty_t}</div>
      <div class="e-s">${s.log_empty_s}</div></div></div>`;
  }

  async function refreshWatch() {
    try { watchedIds = await WL.getWatchlist(); } catch (e) { watchedIds = []; }
    if ($('#liveAlerts')) renderLiveAlerts(); else render();
  }

  let unsub = null;
  function start() {
    if (unsub) { try { unsub(); } catch (e) {} unsub = null; }
    render();
    refreshWatch();
    unsub = WL.onWatchlistChange(() => { refreshWatch(); });
  }

  Sh.start({ active: 'n_alerts', render: start });
}
