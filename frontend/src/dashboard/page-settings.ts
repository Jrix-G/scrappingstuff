/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-settings.js   (Settings)
   Preferences with a section sub-nav. The signature control is
   the CPA / markup widget that recomputes net margin + verdict
   live on a witness product.
   ============================================================ */
export function mountSettings() {
  'use strict';
  const Sh = window.Shell, T = window.TANDOR, P = T.PRODUCTS;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic, clamp = Sh.clamp;
  const money = Sh.money, pct = Sh.pct;

  const STR = {
    en: { title: 'Settings', sub: 'preferences · markets · sources',
      nav_gen: 'General', nav_mkt: 'Markets', nav_src: 'Sources', nav_disp: 'Display', nav_notif: 'Notifications',
      gen: 'General', gen_s: 'Language, appearance and timezone',
      lang: 'Language', lang_s: 'Interface and number formats', theme: 'Card density', theme_s: 'Information density across the app',
      tz: 'Timezone', tz_s: 'Used for timestamps and collection schedules',
      mkt: 'Markets', mkt_s: 'Default geography for Trends and context',
      def_mkt: 'Default market', def_mkt_s: 'Applied to new searches', geo: 'Trends geography', geo_s: 'Region for Google Trends interest',
      src: 'Sources & economics', src_s: 'Toggle signals and tune sellability inputs',
      s_trends: 'Google Trends', s_trends_s: 'Search-interest velocity signal', s_reddit: 'Reddit', s_reddit_s: 'Early social mention signal', s_cj: 'CJ Catalogue', s_cj_s: 'Supplier saturation & pricing',
      cpa: 'CPA & markup', cpa_s: 'Recompute net margin and verdicts live', cpa_lbl: 'Cost per acquisition', markup_lbl: 'Retail markup',
      witness: 'Live impact', w_cost: 'Cost', w_retail: 'Retail', w_net: 'Net / sale', w_verdict: 'Verdict',
      disp: 'Display', disp_s: 'Defaults for tables and cards',
      d_density: 'Default density', d_view: 'Default view', v_table: 'Table', v_cards: 'Cards',
      notif: 'Notifications', notif_s: 'How and when Tandor reaches you',
      n_email: 'Email digests', n_email_s: 'Daily summary of new opportunities', n_push: 'In-app alerts', n_push_s: 'Real-time threshold crossings', n_weekly: 'Weekly report', n_weekly_s: 'Portfolio performance recap',
      comfort: 'Comfort', compact: 'Compact', save: 'Save changes', saved: 'Preferences saved' },
    fr: { title: 'Réglages', sub: 'préférences · marchés · sources',
      nav_gen: 'Général', nav_mkt: 'Marchés', nav_src: 'Sources', nav_disp: 'Affichage', nav_notif: 'Notifications',
      gen: 'Général', gen_s: 'Langue, apparence et fuseau horaire',
      lang: 'Langue', lang_s: 'Interface et formats de nombres', theme: 'Densité', theme_s: 'Densité d’information dans l’app',
      tz: 'Fuseau horaire', tz_s: 'Pour les horodatages et plannings de collecte',
      mkt: 'Marchés', mkt_s: 'Géographie par défaut pour Trends et le contexte',
      def_mkt: 'Marché par défaut', def_mkt_s: 'Appliqué aux nouvelles recherches', geo: 'Géographie Trends', geo_s: 'Région pour l’intérêt Google Trends',
      src: 'Sources & économie', src_s: 'Activer les signaux et régler la vendabilité',
      s_trends: 'Google Trends', s_trends_s: 'Signal de vélocité de recherche', s_reddit: 'Reddit', s_reddit_s: 'Signal social précoce', s_cj: 'Catalogue CJ', s_cj_s: 'Saturation fournisseurs & prix',
      cpa: 'CPA & markup', cpa_s: 'Recalcule la marge nette et les verdicts en direct', cpa_lbl: 'Coût par acquisition', markup_lbl: 'Markup de vente',
      witness: 'Impact en direct', w_cost: 'Coût', w_retail: 'Prix', w_net: 'Net / vente', w_verdict: 'Verdict',
      disp: 'Affichage', disp_s: 'Valeurs par défaut des tableaux et cartes',
      d_density: 'Densité par défaut', d_view: 'Vue par défaut', v_table: 'Tableau', v_cards: 'Cartes',
      notif: 'Notifications', notif_s: 'Comment et quand Tandor vous contacte',
      n_email: 'Résumés email', n_email_s: 'Synthèse quotidienne des nouvelles opportunités', n_push: 'Alertes in-app', n_push_s: 'Franchissements de seuil en temps réel', n_weekly: 'Rapport hebdo', n_weekly_s: 'Récap de performance du portefeuille',
      comfort: 'Confort', compact: 'Compact', save: 'Enregistrer', saved: 'Préférences enregistrées' },
  };
  const L = () => STR[Sh.lang];

  const NAV = [['nav_gen', 'gen', 'settings'], ['nav_mkt', 'mkt', 'globe'], ['nav_src', 'src', 'layers'], ['nav_disp', 'disp', 'eye'], ['nav_notif', 'notif', 'bell']];
  let cpa = 10, markup = 4.2; // markup multiple
  const witnessId = 'CJ-4471';

  function render() {
    const s = L();
    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
      </div>
      <div class="settings-layout rv">
        <nav class="set-nav" id="setNav">${NAV.map(([k, id, icn], i) => `<a href="#sec-${id}" data-sec="${id}" class="${i === 0 ? 'on' : ''}">${ic(icn)}${s[k]}</a>`).join('')}</nav>
        <div class="set-stack" id="setStack"></div>
      </div>`;
    renderStack();
    wireNav();
  }

  function renderStack() {
    const s = L();
    const tz = Sh.lang === 'fr' ? 'Europe/Paris (UTC+1)' : 'Europe/Paris (UTC+1)';
    $('#setStack').innerHTML = `
      ${card('gen', s.gen, s.gen_s, `
        ${line(s.lang, s.lang_s, `<div class="seg-inline" id="langSeg"><button data-l="en" class="${Sh.lang === 'en' ? 'on' : ''}">EN</button><button data-l="fr" class="${Sh.lang === 'fr' ? 'on' : ''}">FR</button></div>`)}
        ${line(s.theme, s.theme_s, densitySeg())}
        ${line(s.tz, s.tz_s, `<div class="sel-wrap"><select class="sel">${['Europe/Paris (UTC+1)', 'Europe/London (UTC+0)', 'America/New_York (UTC−5)'].map((t) => `<option>${t}</option>`).join('')}</select></div>`)}
      `)}
      ${card('mkt', s.mkt, s.mkt_s, `
        ${line(s.def_mkt, s.def_mkt_s, marketSel())}
        ${line(s.geo, s.geo_s, `<div class="sel-wrap"><select class="sel">${T.MARKETS.map((m) => `<option>${m.flag} ${m[Sh.lang]}</option>`).join('')}</select></div>`)}
      `)}
      ${cardRaw('src', s.src, s.src_s, `
        <div class="set-body">
          ${line(s.s_trends, s.s_trends_s, switchEl('trends', true))}
          ${line(s.s_reddit, s.s_reddit_s, switchEl('reddit', true))}
          ${line(s.s_cj, s.s_cj_s, switchEl('cj', true))}
        </div>
        <div class="set-card-h" style="border-top:1px solid var(--border-subtle)"><div class="ttl" style="font-size:13.5px">${s.cpa}</div><div class="sub">${s.cpa_s}</div></div>
        <div class="cpa-impact">
          <div style="display:flex;flex-direction:column;gap:18px">
            <div class="range-wrap"><div class="range-val"><span>${s.cpa_lbl}</span><b id="cpaVal">${money(cpa, 1)}</b></div><input type="range" class="rng" id="cpaRng" min="0" max="25" step="0.5" value="${cpa}" /></div>
            <div class="range-wrap"><div class="range-val"><span>${s.markup_lbl}</span><b id="muVal">×${markup.toFixed(1)}</b></div><input type="range" class="rng" id="muRng" min="2" max="8" step="0.1" value="${markup}" /></div>
          </div>
          <div class="cpa-witness" id="witness"></div>
        </div>`)}
      ${cardRaw('disp', s.disp, s.disp_s, `<div class="set-body">
        ${line(s.d_density, '', densitySeg('2'))}
        ${line(s.d_view, '', `<div class="seg-inline"><button class="on">${s.v_table}</button><button>${s.v_cards}</button></div>`)}
      </div>`)}
      ${cardRaw('notif', s.notif, s.notif_s, `<div class="set-body">
        ${line(s.n_email, s.n_email_s, switchEl('em', true))}
        ${line(s.n_push, s.n_push_s, switchEl('pu', true))}
        ${line(s.n_weekly, s.n_weekly_s, switchEl('wk', false))}
      </div>
      <div class="set-foot"><button class="btn-pri" id="saveBtn">${s.save}</button></div>`)}
    `;
    renderWitness();
    wireControls();
  }

  function card(id, ttl, sub, body) { return `<section class="set-card" id="sec-${id}"><div class="set-card-h"><div class="ttl">${ttl}</div><div class="sub">${sub}</div></div><div class="set-body">${body}</div></section>`; }
  function cardRaw(id, ttl, sub, body) { return `<section class="set-card" id="sec-${id}"><div class="set-card-h"><div class="ttl">${ttl}</div><div class="sub">${sub}</div></div>${body}</section>`; }
  function line(l, s, ctl) { return `<div class="set-line"><div><div class="sl-l">${l}</div>${s ? `<div class="sl-s">${s}</div>` : ''}</div><div class="sl-ctl">${ctl}</div></div>`; }
  function switchEl(k, on) { return `<div class="switch ${on ? 'on' : ''}" data-sw="${k}"></div>`; }
  function densitySeg(suf) { const s = L(); return `<div class="seg-inline" id="densitySeg${suf || ''}"><button data-d="comfort" class="${Sh.density === 'comfort' ? 'on' : ''}">${s.comfort}</button><button data-d="compact" class="${Sh.density === 'compact' ? 'on' : ''}">${s.compact}</button></div>`; }
  function marketSel() { const cur = Sh.market(); return `<div class="sel-wrap"><select class="sel" id="mktSel">${T.MARKETS.map((m) => `<option value="${m.code}" ${m.code === cur ? 'selected' : ''}>${m.flag} ${m[Sh.lang]}</option>`).join('')}</select></div>`; }

  function renderWitness() {
    const s = L(), p = P.find((x) => x.id === witnessId);
    const retail = p.cost * markup;
    const gross = retail - p.cost;
    const net = Math.max(0, gross - cpa);
    const verdict = net >= 13 ? 'BUY' : net >= 6 ? 'WATCH' : 'PASS';
    $('#witness').innerHTML = `
      <div class="cpa-wit-name">${p.name}</div>
      <div class="cpa-wit-row"><span>${s.w_cost}</span><b>${money(p.cost, 1)}</b></div>
      <div class="cpa-wit-row"><span>${s.w_retail}</span><b>${money(retail, 1)}</b></div>
      <div class="cpa-wit-row"><span>${s.w_net}</span><b style="color:${net > 12 ? 'var(--buy)' : net > 6 ? 'var(--watch)' : 'var(--pass)'}">${money(net, 1)}</b></div>
      <div class="cpa-wit-verdict"><span style="font-size:12px;color:var(--text-tertiary)">${s.w_verdict}</span><span class="verdict ${T.VERDICTS[verdict].v}">${T.VERDICTS[verdict][Sh.lang]}</span></div>`;
  }

  function wireNav() {
    const obsTargets = $$('#setStack .set-card');
    $$('#setNav a').forEach((a) => a.addEventListener('click', (e) => {
      e.preventDefault();
      const el = $('#sec-' + a.dataset.sec);
      if (el) $('#main').scrollTo({ top: el.offsetTop - 70, behavior: 'smooth' });
      $$('#setNav a').forEach((x) => x.classList.toggle('on', x === a));
    }));
    // scroll-spy
    const io = new IntersectionObserver((ents) => {
      ents.forEach((en) => { if (en.isIntersecting) { const id = en.target.id.replace('sec-', ''); $$('#setNav a').forEach((x) => x.classList.toggle('on', x.dataset.sec === id)); } });
    }, { root: $('#main'), rootMargin: '-20% 0px -70% 0px', threshold: 0 });
    obsTargets.forEach((t) => io.observe(t));
  }

  function wireControls() {
    const s = L();
    $$('#langSeg button').forEach((b) => b.addEventListener('click', () => { if (b.dataset.l !== Sh.lang) Sh.setLang(b.dataset.l); }));
    $$('[id^="densitySeg"] button').forEach((b) => b.addEventListener('click', () => { Sh.setDensity(b.dataset.d, true); $$('[id^="densitySeg"] button').forEach((x) => x.classList.toggle('on', x.dataset.d === b.dataset.d)); }));
    $$('#setStack .switch').forEach((sw) => sw.addEventListener('click', () => sw.classList.toggle('on')));
    if ($('#mktSel')) $('#mktSel').addEventListener('change', (e) => { Sh.LS.set('market', e.target.value); Sh.toast(s.saved); });
    $('#cpaRng').addEventListener('input', (e) => { cpa = +e.target.value; $('#cpaVal').textContent = money(cpa, 1); renderWitness(); });
    $('#muRng').addEventListener('input', (e) => { markup = +e.target.value; $('#muVal').textContent = '×' + markup.toFixed(1); renderWitness(); });
    if ($('#saveBtn')) $('#saveBtn').addEventListener('click', () => Sh.toast(s.saved));
  }

  Sh.start({ active: 'n_settings', render });
}
