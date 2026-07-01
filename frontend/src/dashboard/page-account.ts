/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — page-account.ts   (Account)
   Profile, security and data export — branchés sur le SDK
   Firebase Auth (plus aucune action cosmétique).
   ============================================================ */
import { auth } from '../auth/firebase';
import { updateProfile, sendPasswordResetEmail, signOut } from 'firebase/auth';

export function mountAccount() {
  'use strict';
  const Sh = window.Shell;
  const $ = Sh.$, $$ = Sh.$$, ic = Sh.ic;

  const STR = {
    en: { title: 'Account', sub: 'profile · security · data',
      profile: 'Profile', profile_s: 'How you appear across Tandor',
      name: 'Full name', email: 'Email', member_since: 'Member since', unknown: 'unknown',
      sec: 'Security', sec_s: 'Password and sign-in',
      pwd: 'Password', pwd_s: 'We email you a secure reset link', pwd_btn: 'Change password',
      twofa: 'Two-factor authentication', twofa_s: 'Not available on this plan yet', na: 'Unavailable',
      sessions: 'Active sessions', sessions_na: 'Session management is not available from the browser.',
      data: 'Data', data_s: 'Export or delete your account data', export: 'Export my data (GDPR)', export_s: 'Full JSON archive of your account',
      danger: 'Delete account', danger_s: 'Permanently remove your account, watchlists and history. This cannot be undone.', delete_btn: 'Delete account',
      save: 'Save', saved: 'Profile saved', save_err: 'Could not save profile', save_empty: 'Please enter a name',
      pwd_sent: 'Reset link sent to', pwd_err: 'Could not send reset email',
      exporting: 'Export downloaded', signout: 'Sign out', signout_err: 'Sign out failed',
      del_soon: 'confirmation required — contact support',
      not_signed_t: 'Not signed in', not_signed_s: 'Sign in to manage your account.', go_login: 'Go to sign in' },
    fr: { title: 'Compte', sub: 'profil · sécurité · données',
      profile: 'Profil', profile_s: 'Votre identité dans Tandor',
      name: 'Nom complet', email: 'Email', member_since: 'Membre depuis', unknown: 'inconnu',
      sec: 'Sécurité', sec_s: 'Mot de passe et connexion',
      pwd: 'Mot de passe', pwd_s: 'Nous vous envoyons un lien de réinitialisation sécurisé', pwd_btn: 'Changer le mot de passe',
      twofa: 'Authentification à deux facteurs', twofa_s: 'Pas encore disponible sur cette offre', na: 'Indisponible',
      sessions: 'Sessions actives', sessions_na: 'La gestion des sessions n’est pas accessible depuis le navigateur.',
      data: 'Données', data_s: 'Exporter ou supprimer les données de votre compte', export: 'Exporter mes données (RGPD)', export_s: 'Archive JSON complète de votre compte',
      danger: 'Supprimer le compte', danger_s: 'Supprime définitivement votre compte, vos watchlists et votre historique. Action irréversible.', delete_btn: 'Supprimer le compte',
      save: 'Enregistrer', saved: 'Profil enregistré', save_err: 'Échec de l’enregistrement du profil', save_empty: 'Veuillez saisir un nom',
      pwd_sent: 'Lien de réinitialisation envoyé à', pwd_err: 'Échec de l’envoi de l’email',
      exporting: 'Export téléchargé', signout: 'Se déconnecter', signout_err: 'Échec de la déconnexion',
      del_soon: 'confirmation requise — contactez le support',
      not_signed_t: 'Non connecté', not_signed_s: 'Connectez-vous pour gérer votre compte.', go_login: 'Aller à la connexion' },
  };
  const L = () => STR[Sh.lang];

  function fmtDate(iso) {
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return null;
      return d.toLocaleDateString(Sh.lang === 'fr' ? 'fr-FR' : 'en-US', { year: 'numeric', month: 'long', day: 'numeric' });
    } catch (e) { return null; }
  }

  function user() { return auth.currentUser; }

  /* ---------- état non connecté ---------- */
  function renderSignedOut() {
    const s = L();
    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
      </div>
      <div class="set-stack rv" style="max-width:760px">
        <section class="set-card">
          <div class="set-pad" style="padding:40px;text-align:center">
            <div class="sl-l" style="font-size:16px;margin-bottom:6px">${s.not_signed_t}</div>
            <div class="sl-s" style="margin-bottom:18px">${s.not_signed_s}</div>
            <button class="btn-pri" id="goLogin">${s.go_login}</button>
          </div>
        </section>
      </div>`;
    $('#goLogin').addEventListener('click', () => { window.location.href = '/login'; });
  }

  /* ---------- état connecté ---------- */
  function render() {
    const u = user();
    if (!u) { renderSignedOut(); return; }

    const s = L();
    const email = u.email || '';
    const displayName = u.displayName || (email ? email.split('@')[0] : '');
    const avatarInitial = (displayName[0] || email[0] || '?').toUpperCase();
    const created = fmtDate(u.metadata && u.metadata.creationTime) || s.unknown;
    const avatar = u.photoURL
      ? `<img src="${u.photoURL}" alt="" class="avatar-lg" style="object-fit:cover;padding:0" />`
      : `<div class="avatar-lg">${avatarInitial}</div>`;

    $('#canvas').innerHTML = `
      <div class="page-head rv">
        <div><h1 class="page-title">${s.title}</h1>
          <div class="page-sub"><span class="live-dot"></span><span>${s.sub}</span></div></div>
        <button class="btn-ghost" id="signoutBtn">${ic('lock')}${s.signout}</button>
      </div>
      <div class="set-stack rv" style="max-width:760px">
        <section class="set-card">
          <div class="set-card-h"><div class="ttl">${s.profile}</div><div class="sub">${s.profile_s}</div></div>
          <div class="set-pad" style="display:flex;gap:18px;align-items:center">
            ${avatar}
            <div style="flex:1;display:grid;grid-template-columns:1fr 1fr;gap:14px">
              <div class="field"><span class="field-lbl">${s.name}</span><input class="inp" id="inpName" value="${displayName.replace(/"/g, '&quot;')}" /></div>
              <div class="field"><span class="field-lbl">${s.member_since}</span><input class="inp" value="${created}" disabled style="opacity:.7" /></div>
              <div class="field" style="grid-column:1/-1"><span class="field-lbl">${s.email}</span><input class="inp" value="${email}" readonly style="opacity:.8" /></div>
            </div>
          </div>
          <div class="set-foot"><button class="btn-pri" id="saveBtn">${s.save}</button></div>
        </section>

        <section class="set-card">
          <div class="set-card-h"><div class="ttl">${s.sec}</div><div class="sub">${s.sec_s}</div></div>
          <div class="set-body">
            <div class="set-line"><div><div class="sl-l">${s.pwd}</div><div class="sl-s">${s.pwd_s}</div></div><div class="sl-ctl"><button class="btn-ghost" id="pwdBtn">${ic('lock')}${s.pwd_btn}</button></div></div>
            <div class="set-line"><div><div class="sl-l">${s.twofa}</div><div class="sl-s">${s.twofa_s}</div></div><div class="sl-ctl"><span class="status-pill" style="opacity:.7">${s.na}</span></div></div>
          </div>
          <div class="set-card-h" style="border-top:1px solid var(--border-subtle)"><div class="ttl" style="font-size:13.5px">${s.sessions}</div></div>
          <div class="set-body"><div class="set-line" style="border:none"><div class="sl-s">${s.sessions_na}</div></div></div>
        </section>

        <section class="set-card">
          <div class="set-card-h"><div class="ttl">${s.data}</div><div class="sub">${s.data_s}</div></div>
          <div class="set-line set-pad" style="padding-top:18px;padding-bottom:18px;border:none"><div><div class="sl-l">${s.export}</div><div class="sl-s">${s.export_s}</div></div><div class="sl-ctl"><button class="btn-ghost" id="exportBtn">${ic('download')}${s.export.split(' ')[0]}</button></div></div>
        </section>

        <section class="set-card danger-zone">
          <div class="set-card-h"><div class="ttl" style="color:var(--red)">${s.danger}</div></div>
          <div class="set-line set-pad" style="padding-top:16px;padding-bottom:16px;border:none"><div><div class="sl-s" style="max-width:520px">${s.danger_s}</div></div><div class="sl-ctl"><button class="btn-ghost btn-danger" id="delBtn">${ic('trash')}${s.delete_btn}</button></div></div>
        </section>
      </div>`;

    wire();
  }

  /* ---------- actions réelles ---------- */
  async function doSave() {
    const s = L();
    const u = user();
    if (!u) { renderSignedOut(); return; }
    const name = ($('#inpName').value || '').trim();
    if (!name) { Sh.toast(s.save_empty); return; }
    try {
      await updateProfile(u, { displayName: name });
      try { window.__TANDOR_USER__ = auth.currentUser; } catch (e) {}
      Sh.toast(s.saved);
    } catch (e) {
      console.error('[account] updateProfile', e);
      Sh.toast(s.save_err);
    }
  }

  async function doPasswordReset() {
    const s = L();
    const u = user();
    if (!u || !u.email) { renderSignedOut(); return; }
    try {
      await sendPasswordResetEmail(auth, u.email);
      Sh.toast(`${s.pwd_sent} ${u.email}`);
    } catch (e) {
      console.error('[account] sendPasswordResetEmail', e);
      Sh.toast(s.pwd_err);
    }
  }

  function lsJSON(key) {
    try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : null; }
    catch (e) { return null; }
  }

  function doExport() {
    const s = L();
    const u = user();
    if (!u) { renderSignedOut(); return; }
    const payload = {
      exported_at: new Date().toISOString(),
      account: {
        uid: u.uid,
        email: u.email || null,
        displayName: u.displayName || null,
        photoURL: u.photoURL || null,
        emailVerified: !!u.emailVerified,
        createdAt: (u.metadata && u.metadata.creationTime) || null,
        lastSignInAt: (u.metadata && u.metadata.lastSignInTime) || null,
        providers: (u.providerData || []).map((p) => p && p.providerId).filter(Boolean),
      },
      saved: lsJSON('tandor_saved'),
      watchlist: lsJSON('tandor_watchlist'),
    };
    try {
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tandor-export-${(u.email || u.uid || 'account').replace(/[^a-z0-9]+/gi, '-')}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      Sh.toast(s.exporting);
    } catch (e) {
      console.error('[account] export', e);
      Sh.toast(L().pwd_err);
    }
  }

  async function doSignOut() {
    const s = L();
    try {
      await signOut(auth);
      window.location.href = '/login';
    } catch (e) {
      console.error('[account] signOut', e);
      Sh.toast(s.signout_err);
    }
  }

  function wire() {
    const s = L();
    $('#saveBtn').addEventListener('click', doSave);
    $('#pwdBtn').addEventListener('click', doPasswordReset);
    $('#exportBtn').addEventListener('click', doExport);
    $('#signoutBtn').addEventListener('click', doSignOut);
    $('#delBtn').addEventListener('click', () => Sh.toast(`${s.danger} · ${s.del_soon}`));
  }

  Sh.start({ active: 'n_account', render });
}
