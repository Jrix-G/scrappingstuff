/* eslint-disable */
// @ts-nocheck
/**
 * firebase-handler — Remplace la démo auth.ts par de vrais appels Firebase Auth.
 *
 * Injecte window.TandorAuth.handle, détecté par auth.ts juste avant la soumission.
 * auth.ts continue de gérer la validation + UX. Seule la soumission finale change.
 *
 * (Le fichier s'appelle encore supabase-handler.ts pour ne pas toucher PublicPage.tsx)
 */
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  confirmPasswordReset,
  updateProfile,
} from 'firebase/auth';
import { doc, setDoc, serverTimestamp } from 'firebase/firestore';
import { auth, db } from './firebase';

function showError(btn: any, msg: string) {
  btn.setAttribute('data-state', '');
  const errTarget =
    document.querySelector<HTMLElement>('.auth-form .fld.err .fld-msg') ||
    document.querySelector<HTMLElement>('.auth-form .fld-msg');
  if (errTarget) {
    errTarget.textContent = msg;
    errTarget.closest('.fld')?.classList.add('err');
  } else {
    alert(msg);
  }
}

// Traduit les codes d'erreur Firebase en français
function friendlyError(code: string): string {
  const map: Record<string, string> = {
    'auth/wrong-password':        'Mot de passe incorrect.',
    'auth/user-not-found':        'Aucun compte trouvé avec cet email.',
    'auth/email-already-in-use':  'Un compte existe déjà avec cet email.',
    'auth/weak-password':         'Mot de passe trop faible (min. 6 caractères).',
    'auth/invalid-email':         'Adresse email invalide.',
    'auth/too-many-requests':     'Trop de tentatives. Réessaie dans quelques minutes.',
    'auth/network-request-failed':'Erreur réseau. Vérifie ta connexion.',
    'auth/expired-action-code':   'Lien expiré. Refais une demande.',
    'auth/invalid-action-code':   'Lien invalide.',
  };
  return map[code] ?? 'Une erreur est survenue.';
}

// Récupère le oobCode depuis l'URL (lien de reset Firebase)
function getOobCode(): string {
  return new URLSearchParams(window.location.search).get('oobCode') ?? '';
}

(window as any).TandorAuth = {
  handle: async (
    kind: string,
    data: { email: string; password: string; name: string; next: string },
    btn: HTMLButtonElement,
  ) => {
    btn.setAttribute('data-state', 'loading');

    try {
      if (kind === 'login') {
        await signInWithEmailAndPassword(auth, data.email, data.password);
        btn.setAttribute('data-state', 'done');
        setTimeout(() => { window.location.href = data.next || '/dashboard'; }, 700);

      } else if (kind === 'register') {
        const cred = await createUserWithEmailAndPassword(auth, data.email, data.password);
        if (data.name) await updateProfile(cred.user, { displayName: data.name });
        // Crée le document Firestore users/{uid}
        await setDoc(doc(db, 'users', cred.user.uid), {
          plan: 'free',
          stripe_customer_id: null,
          subscription_active: false,
          created_at: serverTimestamp(),
        });
        btn.setAttribute('data-state', 'done');
        setTimeout(() => { window.location.href = '/verify'; }, 700);

      } else if (kind === 'forgot') {
        await sendPasswordResetEmail(auth, data.email, {
          url: window.location.origin + '/login',
        });
        btn.setAttribute('data-state', 'done');

      } else if (kind === 'reset') {
        const code = getOobCode();
        if (!code) { showError(btn, 'Lien de réinitialisation invalide.'); return; }
        await confirmPasswordReset(auth, code, data.password);
        btn.setAttribute('data-state', 'done');
        setTimeout(() => { window.location.href = '/login'; }, 800);
      }
    } catch (err: any) {
      showError(btn, friendlyError(err?.code ?? '') || err?.message || 'Erreur inconnue.');
    }
  },
};
