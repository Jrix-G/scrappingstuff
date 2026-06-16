/**
 * Service d'historisation : génère un snapshot quotidien de l'état des produits.
 *
 * Garanties :
 *  - Idempotent : clé primaire (product_id, snapshot_date) + UPSERT → relancer le
 *    même jour met à jour, ne duplique jamais.
 *  - Robuste aux erreurs partielles : chaque produit est normalisé/validé
 *    individuellement ; un produit invalide est ignoré (compté), les autres passent.
 *  - Observable : chaque run est tracé dans snapshot_runs + logs structurés.
 */
import type Database from 'better-sqlite3';
import { openDb } from './db';
import { loadCurrentProducts } from './source';
import { logger } from './logger';
import type { ProductRow, ProductSnapshotRow, RawProduct, SnapshotRunResult, RunStatus } from './types';

export const SCORE_VERSION = 1;

/** Date locale 'YYYY-MM-DD'. */
export function todayLocal(d = new Date()): string {
  const z = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

/** Coercition douce vers number|null (gère null/undefined/''/strings numériques). */
export function num(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

export function str(v: unknown): string | null {
  return typeof v === 'string' && v.length > 0 ? v : null;
}

export interface NormalizedRow {
  product: ProductRow;
  snapshot: ProductSnapshotRow;
}

/** Transforme un produit brut en lignes (dimension + snapshot) prêtes à écrire. */
export function normalize(p: RawProduct, snapshotDate: string, capturedAt: string): NormalizedRow {
  const id = p?.id != null ? String(p.id) : '';
  if (!id) throw new Error('produit sans id');

  const product: ProductRow = {
    product_id: id,
    source: str(p.source) ?? 'products.json',
    name: str(p.name),
    category: str(p.cat),
    first_seen_at: capturedAt, // ignoré en cas de conflit (préserve la 1re vue)
    last_seen_at: capturedAt,
    attrs: JSON.stringify({ reason: p.reason ?? null, dossier: p.dossier ?? null }),
  };

  const snapshot: ProductSnapshotRow = {
    product_id: id,
    snapshot_date: snapshotDate,
    captured_at: capturedAt,
    cost: num(p.cost),
    retail: num(p.retail),
    net: num(p.net),
    sellability: num(p.sellability),
    organic: num(p.organic),
    growth: num(p.growth),
    confidence: num(p.confidence),
    listed: num(p.listed),
    age: num(p.age),
    volatility: num(p.volatility),
    reddit_score: num(p.redditScore),
    trends_score: num(p.trendsScore),
    ebay_score: num(p.ebayScore),
    sales_score: num(p.salesScore),
    season_peak: num(p.seasonPeak),
    season_mult: num(p.seasonMult),
    detected_hrs: num(p.detectedHrs),
    phase: str(p.phase),
    verdict: str(p.verdict),
    score_version: SCORE_VERSION,
    raw: JSON.stringify(p),
  };

  return { product, snapshot };
}

/** Prépare les écritures UPSERT (réutilisé par le snapshot quotidien et le backfill). */
export function makeWriters(db: Database.Database) {
  const upsertProduct = db.prepare(`
    INSERT INTO products (product_id, source, name, category, first_seen_at, last_seen_at, attrs)
    VALUES (@product_id, @source, @name, @category, @first_seen_at, @last_seen_at, @attrs)
    ON CONFLICT(product_id) DO UPDATE SET
      source = excluded.source, name = excluded.name, category = excluded.category,
      last_seen_at = excluded.last_seen_at, attrs = excluded.attrs
  `);
  const upsertSnapshot = db.prepare(`
    INSERT INTO product_snapshots (
      product_id, snapshot_date, captured_at, cost, retail, net, sellability, organic,
      growth, confidence, listed, age, volatility, reddit_score, trends_score, ebay_score,
      sales_score, season_peak, season_mult, detected_hrs, phase, verdict, score_version, raw
    ) VALUES (
      @product_id, @snapshot_date, @captured_at, @cost, @retail, @net, @sellability, @organic,
      @growth, @confidence, @listed, @age, @volatility, @reddit_score, @trends_score, @ebay_score,
      @sales_score, @season_peak, @season_mult, @detected_hrs, @phase, @verdict, @score_version, @raw
    )
    ON CONFLICT(product_id, snapshot_date) DO UPDATE SET
      captured_at = excluded.captured_at, cost = excluded.cost, retail = excluded.retail,
      net = excluded.net, sellability = excluded.sellability, organic = excluded.organic,
      growth = excluded.growth, confidence = excluded.confidence, listed = excluded.listed,
      age = excluded.age, volatility = excluded.volatility, reddit_score = excluded.reddit_score,
      trends_score = excluded.trends_score, ebay_score = excluded.ebay_score,
      sales_score = excluded.sales_score, season_peak = excluded.season_peak,
      season_mult = excluded.season_mult, detected_hrs = excluded.detected_hrs,
      phase = excluded.phase, verdict = excluded.verdict, score_version = excluded.score_version,
      raw = excluded.raw
  `);
  const writeAll = db.transaction((items: NormalizedRow[]) => {
    for (const { product, snapshot } of items) {
      upsertProduct.run(product);
      upsertSnapshot.run(snapshot);
    }
  });
  return { writeAll };
}

export interface SnapshotOptions {
  /** Réutiliser une connexion existante (sinon une est ouverte/fermée par le job). */
  db?: Database.Database;
  /** Forcer la date du snapshot (backfill/tests). Défaut : aujourd'hui (local). */
  date?: string;
}

export async function runSnapshot(opts: SnapshotOptions = {}): Promise<SnapshotRunResult> {
  const ownDb = !opts.db;
  const db = opts.db ?? openDb();
  const snapshotDate = opts.date ?? todayLocal();
  const startedAt = new Date().toISOString();

  let origin = 'unknown';
  let total = 0;
  let written = 0;
  let errors = 0;
  let status: RunStatus = 'error';
  let message = '';

  try {
    const loaded = await loadCurrentProducts();
    origin = loaded.origin;
    total = loaded.products.length;
    logger.info('snapshot.start', { snapshotDate, origin, total });

    // 1) Normalisation/validation produit par produit (robustesse partielle).
    const capturedAt = new Date().toISOString();
    const rows: NormalizedRow[] = [];
    for (const p of loaded.products) {
      try {
        rows.push(normalize(p, snapshotDate, capturedAt));
      } catch (err) {
        errors++;
        logger.warn('snapshot.skip', { id: (p as RawProduct)?.id ?? null, err: String(err) });
      }
    }

    // 2) Écriture transactionnelle (UPSERT idempotent).
    makeWriters(db).writeAll(rows);
    written = rows.length;

    status = errors === 0 ? 'success' : written > 0 ? 'partial' : 'error';
    message = `${written} snapshot(s) écrit(s) pour ${snapshotDate} (${errors} ignoré(s))`;
  } catch (err) {
    status = 'error';
    message = `échec du snapshot : ${String(err)}`;
    logger.error('snapshot.error', { snapshotDate, err: String(err) });
  }

  const result: SnapshotRunResult = {
    snapshot_date: snapshotDate,
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    status,
    origin,
    products_total: total,
    snapshots_written: written,
    errors,
    message,
  };

  recordRun(db, result);
  logger.info('snapshot.done', { ...result });
  if (ownDb) db.close();
  return result;
}

/** Trace un run dans snapshot_runs (observabilité). */
export function recordRun(db: Database.Database, r: SnapshotRunResult): void {
  try {
    db.prepare(`
      INSERT INTO snapshot_runs (
        snapshot_date, started_at, finished_at, status, origin,
        products_total, snapshots_written, errors, message
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      r.snapshot_date, r.started_at, r.finished_at, r.status,
      r.origin, r.products_total, r.snapshots_written, r.errors, r.message,
    );
  } catch (err) {
    logger.error('snapshot.run_record_failed', { err: String(err) });
  }
}
