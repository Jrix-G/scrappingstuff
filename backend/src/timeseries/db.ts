/**
 * Couche DB — SQLite embarqué (better-sqlite3).
 * Un seul fichier, zéro serveur, zéro Docker. Schéma + index créés à l'ouverture
 * (migration idempotente). Voir docs/ARCHITECTURE.md §1.
 */
import Database from 'better-sqlite3';
import path from 'node:path';
import fs from 'node:fs';

/** backend/data/timeseries.db par défaut (dossier `data/` déjà gitignoré). */
export const DEFAULT_DB_PATH = path.join(__dirname, '..', '..', 'data', 'timeseries.db');

export function resolveDbPath(override?: string): string {
  return override || process.env.TIMESERIES_DB_PATH || DEFAULT_DB_PATH;
}

export function openDb(dbPath?: string): Database.Database {
  const resolved = resolveDbPath(dbPath);
  if (resolved !== ':memory:') {
    fs.mkdirSync(path.dirname(resolved), { recursive: true });
  }
  const db = new Database(resolved);
  db.pragma('journal_mode = WAL'); // lectures concurrentes, écritures sûres
  db.pragma('foreign_keys = ON');
  migrate(db);
  return db;
}

/** Crée le schéma s'il n'existe pas. Sûr à relancer (IF NOT EXISTS). */
export function migrate(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS products (
      product_id    TEXT PRIMARY KEY,
      source        TEXT NOT NULL,
      name          TEXT,
      category      TEXT,
      first_seen_at TEXT NOT NULL,
      last_seen_at  TEXT NOT NULL,
      attrs         TEXT
    );

    CREATE TABLE IF NOT EXISTS product_snapshots (
      product_id    TEXT NOT NULL,
      snapshot_date TEXT NOT NULL,          -- 'YYYY-MM-DD' (jour) : clé d'idempotence
      captured_at   TEXT NOT NULL,          -- ISO timestamp réel
      cost          REAL,
      retail        REAL,
      net           REAL,
      sellability   REAL,
      organic       REAL,
      growth        REAL,
      confidence    REAL,
      listed        INTEGER,
      age           INTEGER,
      volatility    REAL,
      reddit_score  REAL,
      trends_score  REAL,
      ebay_score    REAL,
      sales_score   REAL,
      season_peak   INTEGER,
      season_mult   REAL,
      detected_hrs  REAL,
      phase         TEXT,
      verdict       TEXT,
      score_version INTEGER NOT NULL DEFAULT 1,
      raw           TEXT NOT NULL,
      PRIMARY KEY (product_id, snapshot_date),
      FOREIGN KEY (product_id) REFERENCES products(product_id)
    );
    CREATE INDEX IF NOT EXISTS idx_snap_date         ON product_snapshots (snapshot_date);
    CREATE INDEX IF NOT EXISTS idx_snap_product_date ON product_snapshots (product_id, snapshot_date DESC);

    -- (Préparé) journal de signaux bruts pour le ML futur.
    CREATE TABLE IF NOT EXISTS signals (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      ts          TEXT NOT NULL,
      product_id  TEXT,
      source      TEXT,
      signal_type TEXT,
      value       REAL,
      meta        TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_signals_product_ts ON signals (product_id, ts);

    -- Observabilité : une ligne par exécution du job.
    CREATE TABLE IF NOT EXISTS snapshot_runs (
      id                INTEGER PRIMARY KEY AUTOINCREMENT,
      snapshot_date     TEXT NOT NULL,
      started_at        TEXT NOT NULL,
      finished_at       TEXT,
      status            TEXT NOT NULL,
      origin            TEXT,
      products_total    INTEGER NOT NULL DEFAULT 0,
      snapshots_written INTEGER NOT NULL DEFAULT 0,
      errors            INTEGER NOT NULL DEFAULT 0,
      message           TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_runs_date ON snapshot_runs (snapshot_date DESC);
  `);
}
