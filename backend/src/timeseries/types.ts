/**
 * Types du système d'historisation time-series (Phase 0).
 * Voir docs/ARCHITECTURE.md §1.
 */

/** Produit brut tel qu'exporté par le moteur (products.json / API live). */
export interface RawProduct {
  id: string;
  name?: string | null;
  cat?: string | null;
  source?: string | null;
  cost?: number | null;
  retail?: number | null;
  net?: number | null;
  sellability?: number | null;
  organic?: number | null;
  growth?: number | null;
  confidence?: number | null;
  listed?: number | null;
  age?: number | null;
  volatility?: number | null;
  redditScore?: number | null;
  trendsScore?: number | null;
  ebayScore?: number | null;
  salesScore?: number | null;
  seasonPeak?: number | null;
  seasonMult?: number | null;
  detectedHrs?: number | null;
  phase?: string | null;
  verdict?: string | null;
  reason?: unknown;
  dossier?: unknown;
  [k: string]: unknown;
}

/** Dimension : un produit (attributs lents). */
export interface ProductRow {
  product_id: string;
  source: string;
  name: string | null;
  category: string | null;
  first_seen_at: string;
  last_seen_at: string;
  attrs: string | null;
}

/** Fait : l'état d'un produit un jour donné (clé d'idempotence : product_id + snapshot_date). */
export interface ProductSnapshotRow {
  product_id: string;
  snapshot_date: string; // 'YYYY-MM-DD'
  captured_at: string; // ISO timestamp
  cost: number | null;
  retail: number | null;
  net: number | null;
  sellability: number | null;
  organic: number | null;
  growth: number | null;
  confidence: number | null;
  listed: number | null;
  age: number | null;
  volatility: number | null;
  reddit_score: number | null;
  trends_score: number | null;
  ebay_score: number | null;
  sales_score: number | null;
  season_peak: number | null;
  season_mult: number | null;
  detected_hrs: number | null;
  phase: string | null;
  verdict: string | null;
  score_version: number;
  raw: string;
}

/** (Préparé) signal brut générique — base des features ML futures. */
export interface SignalRow {
  ts: string;
  product_id: string | null;
  source: string | null;
  signal_type: string | null;
  value: number | null;
  meta: string | null;
}

export type RunStatus = 'success' | 'partial' | 'error';

/** Résultat d'une exécution de snapshot (tracé dans snapshot_runs). */
export interface SnapshotRunResult {
  snapshot_date: string;
  started_at: string;
  finished_at: string;
  status: RunStatus;
  origin: string;
  products_total: number;
  snapshots_written: number;
  errors: number;
  message: string;
}
