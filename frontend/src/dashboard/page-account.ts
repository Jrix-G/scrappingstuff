/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-account.js   (Account)
   Profile, security (password / 2FA / sessions), API keys,
   data export & account deletion (danger zone).
   ============================================================ */
export function mountAccount() {
  'use strict';
  const Sh = window.Shell;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic;

  const STR = {
    en: { title: 'Account', sub: 'profile · security · API',
      profile: 'Profile', profile_s: 'How you appear across Tandor',
      name: 'Full name', email: 'Email', role: 'Role', role_v: 'Owner',
      sec: 'Security', sec_s: 'Password, 2FA and active sessions',
      pwd: 'Password', pwd_s: 'Last changed 3 months ago', pwd_btn: 'Change password',
      twofa: 'Two-factor authentication', twofa_s: 'Authenticator app · adds a second step at sign-in',
      sessions: 'Active sessions', this_device: 'This device', revoke: 'Revoke',
      api: 'API & keys', api_s: 'Tokens for JSON export and webhooks', new_key: 'Generate key', key_created: 'New key generated', copied: 'Copied to clipboard',
      data: 'Data', data_s: 'Export or delete your account data', export: 'Export my data (GDPR)', export_s: 'Full JSON archive of your account',
      danger: 'Delete account', danger_s: 'Permanently remove your account, watchlists and history. This cannot be undone.', delete_btn: 'Delete account',
      save: 'Save', saved: 'Profile saved', revoked: 'Session revoked', exporting: 'Preparing export' },
    fr: { title: 'Compte', sub: 'profil · sécurité · API',
      profile: 'Profil', profile_s: 'Votre identité dans Tandor',
      name: 'Nom complet', email: 'Email', role: 'Rôle', role_v: 'Propriétaire',
      sec: 'Sécurité', sec_s: 'Mot de passe, 2FA et sessions actives',
      pwd: 'Mot de passe', pwd_s: 'Modifié il y a 3 mois', pwd_btn: 'Changer le mot de passe',
      twofa: 'Authentification à deux facteurs', twofa_s: 'Application authentificateur · ajoute une étape à la connexion',
      sessions: 'Sessions actives', this_device: 'Cet appareil', revoke: 'Révoquer',
      api: 'API & clés', api_s: 'Jetons pour l’export JSON et les webhooks', new_key: 'Générer une clé', key_created: 'Nouvelle clé générée', copied: 'Copié dans le presse-papiers',
      data: 'Données', data_s: 'Exporter ou supprimer les données de votre compte', export: 'Exporter mes données (RGPD)', export_s: 'Archive JSON complète de votre compte',
      danger: 'Supprimer le compte', danger_s: 'Supprime définitivement votre compte, vos watchlists et votre historique. Action irréversible.', delete_btn: 'Supprimer le compte',
      save: 'Enregistrer', saved: 'Profil enregistré', revoked: 'Session révoquée', exporting: 'Préparation de l’export' },
  };
  const L = () => STR[Sh.lang];

  const KEYS = [
    { name: 'production', key: 'tnd_live_8f3a••••••••••••••••2b91', created: '12 Apr 2026' },
    { name: 'ci-export', key: 'tnd_live_4c0e••••••••••••••••7d22', created: '2 Jun 2026' },
  ];
  const SESSIONS = {
    en: [['Chrome · macOS', 'Paris, FR · now', true], ['Safari · iPhone', 'Paris, FR · 2h ago', false], ['Firefox · Windows', 'Lyon, FR · 3d ago', false]],
    fr: [['Chrome · macOS', 'Paris, FR · maintenant', true], ['Safari · iPhone', 'Paris, FR · il y a 2 h', false], ['Firefox · Windows', 'Lyon, FR · il y a 3 j', false]],
  };

  function render() {
    const s = L();
    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
      </div>
      <div class="set-stack rv" style="max-width:760px">
        <section class="set-card">
          <div class="set-card-h"><div class="ttl">${s.profile}</div><div class="sub">${s.profile_s}</div></div>
          <div class="set-pad" style="display:flex;gap:18px;align-items:center">
            <div class="avatar-lg">A</div>
            <div style="flex:1;display:grid;grid-template-columns:1fr 1fr;gap:14px">
              <div class="field"><span class="field-lbl">${s.name}</span><input class="inp" value="Alex Morel" /></div>
              <div class="field"><span class="field-lbl">${s.role}</span><input class="inp" value="${s.role_v}" disabled style="opacity:.7" /></div>
              <div class="field" style="grid-column:1/-1"><span class="field-lbl">${s.email}</span><input class="inp" value="alex@tandor.io" /></div>
            </div>
          </div>
          <div class="set-foot"><button class="btn-pri" data-toast="saved">${s.save}</button></div>
        </section>

        <section class="set-card">
          <div class="set-card-h"><div class="ttl">${s.sec}</div><div class="sub">${s.sec_s}</div></div>
          <div class="set-body">
            <div class="set-line"><div><div class="sl-l">${s.pwd}</div><div class="sl-s">${s.pwd_s}</div></div><div class="sl-ctl"><button class="btn-ghost" data-toast="pwd_btn">${ic('lock')}${s.pwd_btn}</button></div></div>
            <div class="set-line"><div><div class="sl-l">${s.twofa}</div><div class="sl-s">${s.twofa_s}</div></div><div class="sl-ctl"><div class="switch on" id="twofa"></div></div></div>
          </div>
          <div class="set-card-h" style="border-top:1px solid var(--border-subtle)"><div class="ttl" style="font-size:13.5px">${s.sessions}</div></div>
          <div class="set-body" id="sessions"></div>
        </section>

        <section class="set-card">
          <div class="set-card-h" style="display:flex;align-items:center;justify-content:space-between"><div><div class="ttl">${s.api}</div><div class="sub">${s.api_s}</div></div><button class="btn-ghost btn-sm" id="newKey">${ic('plus')}${s.new_key}</button></div>
          <div id="keys"></div>
        </section>

        <section class="set-card">
          <div class="set-card-h"><div class="ttl">${s.data}</div><div class="sub">${s.data_s}</div></div>
          <div class="set-line set-pad" style="padding-top:18px;padding-bottom:18px;border:none"><div><div class="sl-l">${s.export}</div><div class="sl-s">${s.export_s}</div></div><div class="sl-ctl"><button class="btn-ghost" data-toast="exporting">${ic('download')}${s.export.split(' ')[0]}</button></div></div>
        </section>

        <section class="set-card danger-zone">
          <div class="set-card-h"><div class="ttl" style="color:var(--red)">${s.danger}</div></div>
          <div class="set-line set-pad" style="padding-top:16px;padding-bottom:16px;border:none"><div><div class="sl-s" style="max-width:520px">${s.danger_s}</div></div><div class="sl-ctl"><button class="btn-ghost btn-danger" id="delBtn">${ic('trash')}${s.delete_btn}</button></div></div>
        </section>
      </div>`;
    renderSessions(); renderKeys(); wire();
  }

  function renderSessions() {
    const s = L();
    $('#sessions').innerHTML = SESSIONS[Sh.lang].map(([dev, loc, cur], i) => `
      <div class="set-line">
        <div style="display:flex;align-items:center;gap:11px"><span style="width:30px;height:30px;border-radius:8px;background:var(--bg-sunken);display:grid;place-items:center;color:var(--text-secondary)">${ic('globe')}</span>
          <div><div class="sl-l">${dev} ${cur ? `<span class="status-pill active" style="margin-left:6px">${s.this_device}</span>` : ''}</div><div class="sl-s">${loc}</div></div></div>
        <div class="sl-ctl">${cur ? '' : `<button class="btn-ghost btn-sm" data-revoke="${i}">${s.revoke}</button>`}</div></div>`).join('');
    $$('#sessions [data-revoke]').forEach((b) => b.addEventListener('click', () => { b.closest('.set-line').style.opacity = '.4'; b.disabled = true; Sh.toast(L().revoked); }));
  }

  let keys = KEYS.slice();
  function renderKeys() {
    const s = L();
    $('#keys').innerHTML = keys.map((k, i) => `
      <div class="key-row">
        <div style="flex:none;width:90px"><div class="sl-l" style="font-size:13px">${k.name}</div><div class="sl-s">${k.created}</div></div>
        <span class="key-mono">${k.key}</span>
        <button class="icon-btn" data-copy="${i}" title="copy">${ic('copy')}</button>
        <button class="icon-btn" data-revk="${i}" title="revoke">${ic('trash')}</button>
      </div>`).join('');
    $$('#keys [data-copy]').forEach((b) => b.addEventListener('click', () => Sh.toast(L().copied)));
    $$('#keys [data-revk]').forEach((b) => b.addEventListener('click', () => { keys.splice(+b.dataset.revk, 1); renderKeys(); }));
  }

  function wire() {
    const s = L();
    $$('[data-toast]').forEach((b) => b.addEventListener('click', () => Sh.toast(s[b.dataset.toast] === undefined ? s.saved : (b.dataset.toast === 'saved' ? s.saved : b.dataset.toast === 'exporting' ? s.exporting : s.saved))));
    $('#twofa').addEventListener('click', () => $('#twofa').classList.toggle('on'));
    $('#newKey').addEventListener('click', () => {
      const rnd = Math.random().toString(36).slice(2, 6);
      keys.unshift({ name: 'new-key', key: `tnd_live_${rnd}••••••••••••••••${Math.random().toString(36).slice(2, 6)}`, created: Sh.lang === 'fr' ? 'à l’instant' : 'just now' });
      renderKeys(); Sh.toast(s.key_created);
    });
    $('#delBtn').addEventListener('click', () => Sh.toast(L().danger + ' · ' + (Sh.lang === 'fr' ? 'confirmation requise' : 'confirmation required')));
  }

  Sh.start({ active: 'n_account', render });
}
