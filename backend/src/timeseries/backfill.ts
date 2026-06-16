/**
 * Backfill : amorce la base d'historique avec l'historique BRUT déjà accumulé par
 * le moteur dans cj_snapshots (price, listed_num par jour). Idempotent (UPSERT).
 *
 *   npm run snapshot:backfill
 *
 * Note : les scores (sellability/organic/phase/verdict) ne sont PAS reconstruits —
 * ils n'existent pas rétroactivement. Le backfill pose le socle brut ; à partir
 * d'aujourd'hui, le snapshot quotidien ajoute les scores du jour.
 */
import type Database from 'better-sqlite3';
import { openDb } from './db';
import { readBackfillRows } from './cjdb';
import { makeWriters, normalize, recordRun } from './snapshot';
import { logger } from './logger';
import type { NormalizedRow } from './snapshot';
import type { SnapshotRunResult } from './types';

export interface BackfillResult {
  status: 'success' | 'partial' | 'error';
  days: number;
  rows_written: number;
  errors: number;
  message: string;
}

export function runBackfillFromCjDb(opts: { db?: Database.Database } = {}): BackfillResult {
  const ownDb = !opts.db;
  const db = opts.db ?? openDb();
  const startedAt = new Date().toISOString();
  let written = 0;
  let errors = 0;
  let days = 0;

  try {
    const source = readBackfillRows();
    const normalized: NormalizedRow[] = [];
    const daySet = new Set<string>();
    for (const r of source) {
      try {
        normalized.push(normalize(r.product, r.date, r.observedAt));
        daySet.add(r.date);
      } catch (err) {
        errors++;
        logger.warn('backfill.skip', { id: r.product?.id ?? null, err: String(err) });
      }
    }
    makeWriters(db).writeAll(normalized);
    written = normalized.length;
    days = daySet.size;
    logger.info('backfill.done', { days, written, errors });
  } catch (err) {
    logger.error('backfill.error', { err: String(err) });
    const result: BackfillResult = { status: 'error', days: 0, rows_written: 0, errors: errors + 1, message: String(err) };
    if (ownDb) db.close();
    return result;
  }

  const status = errors === 0 ? 'success' : written > 0 ? 'partial' : 'error';
  const message = `backfill : ${written} ligne(s) brute(s) sur ${days} jour(s) (${errors} ignoré(s))`;

  // Tracé comme un run spécial (snapshot_date = 'backfill') pour l'observabilité.
  const run: SnapshotRunResult = {
    snapshot_date: 'backfill', started_at: startedAt, finished_at: new Date().toISOString(),
    status, origin: 'cj.db/cj_snapshots', products_total: written, snapshots_written: written,
    errors, message,
  };
  recordRun(db, run);

  if (ownDb) db.close();
  return { status, days, rows_written: written, errors, message };
}
