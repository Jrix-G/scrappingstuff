/* eslint-disable */
// @ts-nocheck
/* ============================================================
   TANDOR — watchlist.ts   (Watchlist persistence layer)
   Per-user persistence for pinned products that the user wants
   to monitor (in-app decline alerts are handled by another UI
   agent). When signed in (Firebase auth) the data lives in
   Firestore at users/{uid}/watchlist (one doc per product).
   When signed out, it falls back to localStorage.
   This module owns ONLY persistence + change subscription.
   ============================================================ */
import {
  doc,
  getDoc,
  getDocs,
  collection,
  setDoc,
  deleteDoc,
  onSnapshot,
  serverTimestamp,
} from 'firebase/firestore';
import { auth, db } from '../auth/firebase';

// localStorage key — kept stable so data survives across sessions
// and could be migrated to Firestore later (migration not required).
const LS_KEY = 'tandor_watchlist';

// Soft cap on watchlist size. Beyond this, addToWatchlist no-ops
// (free vs pro plans can refine/lift this later).
const MAX_ITEMS = 50;

// ---- localStorage helpers --------------------------------------------------

function lsRead(): string[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter((x) => typeof x === 'string') : [];
  } catch (e) {
    console.warn('[watchlist] localStorage read failed', e);
    return [];
  }
}

function lsWrite(ids: string[]): void {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(ids));
  } catch (e) {
    console.warn('[watchlist] localStorage write failed', e);
  }
}

// ---- internal listener registry (used in localStorage mode) ----------------

const localListeners = new Set<() => void>();

function emitLocalChange(): void {
  localListeners.forEach((fn) => {
    try {
      fn();
    } catch (e) {
      console.warn('[watchlist] listener threw', e);
    }
  });
}

// ---- Firestore path helpers ------------------------------------------------

function watchlistColl(uid: string) {
  return collection(db, 'users', uid, 'watchlist');
}

function watchDoc(uid: string, productId: string) {
  return doc(db, 'users', uid, 'watchlist', productId);
}

// ===========================================================================
// Public API (frozen contract — do not change signatures)
// ===========================================================================

export async function getWatchlist(): Promise<string[]> {
  const user = auth.currentUser;
  if (!user) return lsRead();
  try {
    const snap = await getDocs(watchlistColl(user.uid));
    return snap.docs.map((d) => d.id);
  } catch (e) {
    console.warn('[watchlist] getWatchlist (Firestore) failed', e);
    return [];
  }
}

export async function isWatched(productId: string): Promise<boolean> {
  if (!productId) return false;
  const user = auth.currentUser;
  if (!user) return lsRead().includes(productId);
  try {
    const snap = await getDoc(watchDoc(user.uid, productId));
    return snap.exists();
  } catch (e) {
    console.warn('[watchlist] isWatched (Firestore) failed', e);
    return false;
  }
}

export async function addToWatchlist(productId: string): Promise<void> {
  if (!productId) return;
  const user = auth.currentUser;

  if (!user) {
    const ids = lsRead();
    if (ids.includes(productId)) return;
    // Soft cap: no-op beyond MAX_ITEMS.
    if (ids.length >= MAX_ITEMS) {
      console.warn('[watchlist] soft cap reached (' + MAX_ITEMS + '), add ignored');
      return;
    }
    ids.push(productId);
    lsWrite(ids);
    emitLocalChange();
    return;
  }

  try {
    // Soft cap: count existing docs before writing.
    const current = await getDocs(watchlistColl(user.uid));
    const alreadyThere = current.docs.some((d) => d.id === productId);
    if (!alreadyThere && current.size >= MAX_ITEMS) {
      console.warn('[watchlist] soft cap reached (' + MAX_ITEMS + '), add ignored');
      return;
    }
    await setDoc(watchDoc(user.uid, productId), {
      productId,
      addedAt: serverTimestamp(),
    });
  } catch (e) {
    console.warn('[watchlist] addToWatchlist (Firestore) failed', e);
  }
}

export async function removeFromWatchlist(productId: string): Promise<void> {
  if (!productId) return;
  const user = auth.currentUser;

  if (!user) {
    const ids = lsRead().filter((x) => x !== productId);
    lsWrite(ids);
    emitLocalChange();
    return;
  }

  try {
    await deleteDoc(watchDoc(user.uid, productId));
  } catch (e) {
    console.warn('[watchlist] removeFromWatchlist (Firestore) failed', e);
  }
}

export async function toggleWatch(productId: string): Promise<boolean> {
  if (!productId) return false;
  const watched = await isWatched(productId);
  if (watched) {
    await removeFromWatchlist(productId);
    return false;
  }
  await addToWatchlist(productId);
  // Re-check so the soft cap (where add may no-op) is reflected honestly.
  return isWatched(productId);
}

export function onWatchlistChange(listener: () => void): () => void {
  const user = auth.currentUser;

  if (user) {
    // Firestore live subscription. onSnapshot already returns an unsubscribe.
    try {
      const unsub = onSnapshot(
        watchlistColl(user.uid),
        () => {
          try {
            listener();
          } catch (e) {
            console.warn('[watchlist] listener threw', e);
          }
        },
        (err) => console.warn('[watchlist] onSnapshot error', err)
      );
      return unsub;
    } catch (e) {
      console.warn('[watchlist] onWatchlistChange (Firestore) failed', e);
      return () => {};
    }
  }

  // localStorage mode: internal registry triggered by add/remove/toggle.
  localListeners.add(listener);
  return () => {
    localListeners.delete(listener);
  };
}
