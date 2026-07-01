import React, { createContext, useContext, useEffect, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import type { User } from 'firebase/auth';
import { doc, getDoc, disableNetwork } from 'firebase/firestore';
import { auth, db } from './firebase';

export type Plan = 'free' | 'starter' | 'pro';

interface UserProfile {
  plan: Plan;
  stripe_customer_id: string | null;
  subscription_active: boolean;
}

interface AuthCtx {
  user: User | null;
  profile: UserProfile | null;
  loading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthCtx>({
  user: null,
  profile: null,
  loading: true,
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser]       = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      if (!firebaseUser) {
        setProfile(null);
        setLoading(false);
        return;
      }
      // BOOT NON BLOQUANT : dès que l'état d'auth est connu, on débloque le rendu
      // IMMÉDIATEMENT avec le plan `free` par défaut. Le profil Firestore exact est
      // récupéré EN ARRIÈRE-PLAN et met à jour le plan quand/si il arrive — il n'est
      // JAMAIS sur le chemin critique du premier paint.
      const fallback: UserProfile = { plan: 'free', stripe_customer_id: null, subscription_active: false };
      setProfile(fallback);
      setLoading(false);

      // Timeout dur : un bloqueur de pub (uBlock/Brave) retente le canal Firestore en
      // boucle et getDoc ne résout JAMAIS. On borne à 3 s, puis on coupe le réseau
      // Firestore pour stopper la tempête de retries (ERR_BLOCKED_BY_CLIENT) qui rame l'UI.
      const timeout = new Promise<never>((_, rej) =>
        setTimeout(() => rej(new Error('firestore-timeout')), 3000));
      Promise.race([getDoc(doc(db, 'users', firebaseUser.uid)), timeout])
        .then((snap) => {
          const data = snap.data() as UserProfile | undefined;
          if (data) setProfile(data);
        })
        .catch((err) => {
          console.warn('[Auth] profil Firestore indisponible, plan free conservé :', err);
          disableNetwork(db).catch(() => {});
        });
    });
    return unsub;
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      profile,
      loading,
      signOut: () => auth.signOut(),
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
