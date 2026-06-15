/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-alerts.js   (Alerts)
   No-code rule builder with live natural-language preview, the
   rules list (toggle / frequency / last fired) and a trigger log.
   ============================================================ */
export function mountAlerts() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic;

  const STR = {
    en: { title: 'Alerts', sub: 'rules · channels · trigger log',
      builder: 'New rule', when: 'When', then: 'then notify', create: 'Create rule',
      m_score: 'Tandor score', m_growth: 'Monthly growth', m_phase: 'Phase change', m_new: 'New product in',
      o_above: 'rises above', o_below: 'falls below', o_enters: 'enters', o_appears: 'appears in',
      ch_app: 'In-app', ch_email: 'Email', ch_webhook: 'Webhook',
      rules: 'Active rules', rules_s: 'toggle, frequency, last fired',
      log: 'Trigger log', log_s: 'recently fired alerts', triggers: 'triggers', fired: 'last fired', never: 'never',
      nl_pre: 'When a product’s', nl_post: ', notify me', and: 'and',
      created: 'Rule created', day: 'd ago', hr: 'h ago' },
    fr: { title: 'Alertes', sub: 'règles · canaux · journal',
      builder: 'Nouvelle règle', when: 'Quand', then: 'alors notifier', create: 'Créer la règle',
      m_score: 'Score Tandor', m_growth: 'Croissance mensuelle', m_phase: 'Changement de phase', m_new: 'Nouveau produit en',
      o_above: 'dépasse', o_below: 'passe sous', o_enters: 'entre en', o_appears: 'apparaît en',
      ch_app: 'In-app', ch_email: 'Email', ch_webhook: 'Webhook',
      rules: 'Règles actives', rules_s: 'activation, fréquence, dernier déclenchement',
      log: 'Journal des déclenchements', log_s: 'alertes récemment déclenchées', triggers: 'déclenchements', fired: 'dernier', never: 'jamais',
      nl_pre: 'Quand le', nl_post: ', me notifier', and: 'et',
      created: 'Règle créée', day: 'j', hr: 'h' },
  };
  const L = () => STR[Sh.lang];

  const METRICS = ['m_score', 'm_growth', 'm_phase', 'm_new'];
  function opsFor(m) { return m === 'm_phase' ? ['o_enters'] : m === 'm_new' ? ['o_appears'] : ['o_above', 'o_below']; }
  let bm = 'm_score', bop = 'o_above', bval = '80', chans = { app: true, email: true, webhook: false };

  const RULES = [
    { metric: 'm_score', op: 'o_above', val: '80', chans: { app: true, email: true }, freq: 12, hrs: 18, on: true },
    { metric: 'm_growth', op: 'o_above', val: '50%', chans: { app: true, webhook: true }, freq: 31, hrs: 3, on: true },
    { metric: 'm_phase', op: 'o_enters', val: 'EMERGENT', chans: { app: true }, freq: 7, hrs: 26, on: true },
    { metric: 'm_new', op: 'o_appears', val: 'WELLNESS', chans: { app: true, email: true }, freq: 4, hrs: 73, on: false },
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
    renderBuilder(); renderRules(); renderLog();
    $('#createBtn').addEventListener('click', () => {
      const r = { metric: bm, op: bop, val: bval, chans: Object.assign({}, chans), freq: 0, hrs: null, on: true };
      const rl = getRules(); rl.unshift(r); setRules(rl); Sh.toast(s.created); renderRules();
    });
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
    const top = P.slice().sort((a, b) => a.detectedHrs - b.detectedHrs).slice(0, 7);
    const ruleTxt = { en: ['crossed velocity threshold', 'entered Emergent', 'Tandor score above 80', 'growth above 50%'], fr: ['seuil de vélocité franchi', 'entré en Émergent', 'score Tandor > 80', 'croissance > 50%'] };
    $('#logList').innerHTML = top.map((p, i) => {
      const col = `var(--${T.PHASES[p.phase].v})`;
      const ago = p.detectedHrs < 24 ? `${p.detectedHrs}${s.hr === 'h' ? 'h' : ' h'} ${Sh.lang === 'fr' ? '' : 'ago'}` : `${Math.round(p.detectedHrs / 24)}${s.day}`;
      const rt = ruleTxt[Sh.lang][i % 4];
      return `<div class="log-row" data-id="${p.id}">
        <span class="log-ico" style="background:${col}">${ic('zap')}</span>
        <div class="log-t"><b>${p.name}</b> — ${rt}</div>
        <span class="log-time">${ago}</span></div>`;
    }).join('');
    $$('#logList .log-row').forEach((r) => r.addEventListener('click', () => Sh.openProduct(P.find((p) => p.id === r.dataset.id))));
  }

  Sh.start({ active: 'n_alerts', render });
}
