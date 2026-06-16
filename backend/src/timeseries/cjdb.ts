/**
 * Lecteur de l'univers complet du moteur (`scripts/organic_engine/data/cj.db`).
 *
 * cj.db est la base de TRAVAIL du scraper Python : on l'ouvre **en lecture seule**
 * pour ne jamais gêner ses écritures (WAL → lectures concurrentes sûres).
 *
 * Tables exploitées :
 *  - cj_products  : dimension (pid, name, category, image, first_seen, ...)
 *  - cj_snapshots : time-series brute déjà tenue par le moteur (price, listed_num)
 *
 * On consolide : tout l'univers (5000+ produits) + les scores overlay venant de
 * products.json (sellability/organic/phase/verdict... pour le sous-ensemble enrichi).
 */
import Database from 'better-sqlite3';
import path from 'node:path';
import fs from 'node:fs';
import type { RawProduct } from './types';

export const DEFAULT_CJ_DB_PATH = path.join(
  __dirname, '..', '..', '..', 'scripts', 'organic_engine', 'data', 'cj.db',
);

export function cjDbPath(): string {
  return process.env.CJ_DB_PATH || DEFAULT_CJ_DB_PATH;
}

export function cjDbExists(): boolean {
  return fs.existsSync(cjDbPath());
}

function openCjDb(): Database.Database {
  return new Database(cjDbPath(), { readonly: true, fileMustExist: true });
}

function daysBetween(fromIso: string | null | undefined, toMs: number): number | null {
  if (!fromIso) return null;
  const t = Date.parse(fromIso);
  if (Number.isNaN(t)) return null;
  return Math.max(0, Math.floor((toMs - t) / 86_400_000));
}

interface CjProduct { pid: string; name: string | null; category: string | null; image: string | null; first_seen: string | null; }
interface CjLatest { pid: string; price: number | null; listed_num: number | null; }

/** Fusionne 1 produit cj.db + (optionnel) son overlay scoré en un RawProduct. */
function merge(p: CjProduct, latest: CjLatest | undefined, overlay: RawProduct | undefined, nowMs: number): RawProduct {
  return {
    id: p.pid,
    name: p.name,
    cat: p.category,
    source: 'cj',
    cost: latest?.price ?? null,            // prix fournisseur CJ
    listed: latest?.listed_num ?? null,     // nb de vendeurs (saturation)
    age: daysBetween(p.first_seen, nowMs),
    // Scores : présents uniquement pour le sous-ensemble enrichi (overlay products.json)
    retail: overlay?.retail ?? null,
    net: overlay?.net ?? null,
    sellability: overlay?.sellability ?? null,
    organic: overlay?.organic ?? null,
    growth: overlay?.growth ?? null,
    confidence: overlay?.confidence ?? null,
    volatility: overlay?.volatility ?? null,
    redditScore: overlay?.redditScore ?? null,
    trendsScore: overlay?.trendsScore ?? null,
    ebayScore: overlay?.ebayScore ?? null,
    salesScore: overlay?.salesScore ?? null,
    seasonPeak: overlay?.seasonPeak ?? null,
    seasonMult: overlay?.seasonMult ?? null,
    detectedHrs: overlay?.detectedHrs ?? null,
    phase: overlay?.phase ?? null,
    verdict: overlay?.verdict ?? null,
    reason: overlay?.reason ?? null,
    dossier: overlay?.dossier ?? null,
    enriched: overlay != null,
  };
}

/** Univers complet à l'instant T : tous les produits + dernier prix/vendeurs connu. */
export function readUniverse(overlayProducts: RawProduct[] = []): RawProduct[] {
  const db = openCjDb();
  try {
    const latestRows = db.prepare(`
      SELECT s.pid AS pid, s.price AS price, s.listed_num AS listed_num
      FROM cj_snapshots s
      JOIN (SELECT pid, MAX(observed_at) mo FROM cj_snapshots GROUP BY pid) m
        ON m.pid = s.pid AND m.mo = s.observed_at
    `).all() as CjLatest[];
    const latest = new Map(latestRows.map((r) => [r.pid, r]));

    const products = db.prepare(
      `SELECT pid, name, category, image, first_seen FROM cj_products`,
    ).all() as CjProduct[];

    // products.json expose un id court = pid[-7:] (cf. export_dashboard.py).
    // Ce suffixe peut collisionner sur l'univers complet → on n'attache les scores
    // QUE lorsqu'un suffixe désigne un seul produit (sinon on n'invente rien).
    const overlay = new Map(overlayProducts.map((p) => [String(p.id), p]));
    const suffixCount = new Map<string, number>();
    for (const p of products) {
      const sfx = p.pid.slice(-7);
      suffixCount.set(sfx, (suffixCount.get(sfx) ?? 0) + 1);
    }
    const now = Date.now();
    return products.map((p) => {
      const sfx = p.pid.slice(-7);
      const ov = suffixCount.get(sfx) === 1 ? overlay.get(sfx) : undefined;
      return merge(p, latest.get(p.pid), ov, now);
    });
  } finally {
    db.close();
  }
}

export interface BackfillRow { date: string; product: RawProduct; observedAt: string; }

/**
 * Reconstruit l'historique BRUT déjà présent dans cj_snapshots : pour chaque
 * (produit, jour), la dernière observation (price, listed_num). Pas de scores
 * (ils n'existent pas rétroactivement). Sert à amorcer la base avec l'historique
 * que le moteur a déjà accumulé.
 */
export function readBackfillRows(): BackfillRow[] {
  const db = openCjDb();
  try {
    const dims = db.prepare(`SELECT pid, name, category, first_seen FROM cj_products`).all() as CjProduct[];
    const dim = new Map(dims.map((d) => [d.pid, d]));

    // Dernière observation par (pid, jour).
    const rows = db.prepare(`
      SELECT s.pid AS pid, substr(s.observed_at,1,10) AS day, s.price AS price,
             s.listed_num AS listed_num, s.observed_at AS observed_at
      FROM cj_snapshots s
      JOIN (
        SELECT pid, substr(observed_at,1,10) AS day, MAX(observed_at) AS mo
        FROM cj_snapshots GROUP BY pid, substr(observed_at,1,10)
      ) m ON m.pid = s.pid AND m.day = substr(s.observed_at,1,10) AND m.mo = s.observed_at
    `).all() as Array<{ pid: string; day: string; price: number | null; listed_num: number | null; observed_at: string }>;

    return rows.map((r) => {
      const d = dim.get(r.pid);
      const observedMs = Date.parse(r.observed_at) || Date.now();
      const product: RawProduct = {
        id: r.pid,
        name: d?.name ?? null,
        cat: d?.category ?? null,
        source: 'cj',
        cost: r.price,
        listed: r.listed_num,
        age: daysBetween(d?.first_seen, observedMs),
      };
      return { date: r.day, product, observedAt: r.observed_at };
    });
  } finally {
    db.close();
  }
}
