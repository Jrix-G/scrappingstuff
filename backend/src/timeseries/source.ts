/**
 * Source des produits à historiser.
 *
 * Modes (env SNAPSHOT_SOURCE) :
 *   'auto'     (défaut) → univers complet cj.db si présent, sinon products.json
 *   'universe'          → univers complet cj.db (5000+ produits) + overlay scores
 *   'json'              → uniquement products.json / API (top ~60 enrichi)
 *
 * On ne fait que LIRE : cj.db en read-only, products.json jamais réécrit.
 */
import path from 'node:path';
import fs from 'node:fs';
import { logger } from './logger';
import { cjDbExists, readUniverse } from './cjdb';
import type { RawProduct } from './types';

export const DEFAULT_JSON_PATH = path.join(
  __dirname, '..', '..', '..', 'frontend', 'src', 'dashboard', 'products.json',
);

function extractArray(json: unknown): RawProduct[] {
  if (Array.isArray(json)) return json as RawProduct[];
  if (json && typeof json === 'object') {
    const arr = (json as { products?: unknown }).products;
    if (Array.isArray(arr)) return arr as RawProduct[];
  }
  return [];
}

export interface LoadedProducts {
  products: RawProduct[];
  origin: string;
}

/** Top ~60 enrichi (scores/verdicts) : API live si configurée, sinon products.json local. */
async function loadJson(): Promise<LoadedProducts> {
  const api = process.env.PRODUCTS_API_URL;
  if (api) {
    const url = `${api.replace(/\/$/, '')}/api/products?limit=1000`;
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(15_000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const products = extractArray(await res.json());
      if (products.length) return { products, origin: url };
      logger.warn('source.api_empty', { url });
    } catch (err) {
      logger.warn('source.api_failed', { url, err: String(err) });
    }
  }
  const jsonPath = process.env.PRODUCTS_JSON_PATH || DEFAULT_JSON_PATH;
  try {
    const products = extractArray(JSON.parse(fs.readFileSync(jsonPath, 'utf8')));
    return { products, origin: jsonPath };
  } catch (err) {
    logger.warn('source.json_failed', { jsonPath, err: String(err) });
    return { products: [], origin: jsonPath };
  }
}

export async function loadCurrentProducts(): Promise<LoadedProducts> {
  const mode = (process.env.SNAPSHOT_SOURCE || 'auto').toLowerCase();
  const overlay = await loadJson(); // scores du top enrichi (sert d'overlay)

  if (mode === 'json') return overlay;

  if (mode === 'universe' || (mode === 'auto' && cjDbExists())) {
    if (!cjDbExists()) {
      logger.warn('source.cjdb_missing_fallback_json');
      return overlay;
    }
    const products = readUniverse(overlay.products);
    const enriched = products.filter((p) => (p as { enriched?: boolean }).enriched).length;
    return { products, origin: `cj.db (univers=${products.length}, scores overlay=${enriched})` };
  }

  return overlay;
}
