import React, { useEffect } from 'react';
import '../Styles/base.css';
import '../auth/auth.css';

/**
 * PublicPage — pages publiques (pré-login) : Login, Register, Forgot/Reset
 * Password, Verify Email, Pricing.
 *
 * Le markup exact du prototype est injecté tel quel (fidélité pixel), puis on
 * exécute le runtime porté : `public.ts` (nav/reveal/langue FR-EN/toggle pricing)
 * et, pour les écrans d'auth, `auth.ts` (validation, force du mot de passe,
 * submit → loading → done — démo, pas d'auth réelle). Les liens `Tandor *.html`
 * ont été remappés vers les routes React (/login, /register, /pricing, …).
 */
export default function PublicPage({ html, className, auth }: { html: string; className?: string; auth?: boolean }) {
  useEffect(() => {
    let cancelled = false;
    (async () => {
      await import('../auth/public');
      if (cancelled) return;
      if (auth) await import('../auth/auth');
    })();
    return () => { cancelled = true; };
  }, [html, auth]);

  return <div className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
