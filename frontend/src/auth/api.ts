import { auth } from './firebase';

/**
 * fetch authentifié : attache l'ID token Firebase de l'utilisateur courant en
 * header `Authorization: Bearer <token>`. L'API du Pi le vérifie côté serveur
 * (api/auth.py) et applique le quota par plan. Sans token, les endpoints
 * protégés renvoient 401 — le dataset payant n'est plus en accès libre.
 *
 * getIdToken() renvoie un token en cache et le rafraîchit automatiquement s'il
 * a expiré, donc on peut l'appeler à chaque requête sans surcoût.
 */
export async function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const u = auth.currentUser;
  const token = u ? await u.getIdToken() : null;
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}
