/**
 * Test de validation autonome (sans framework) — exécute dans une DB in-memory
 * pour ne pas polluer la base réelle.
 *
 *   npm run snapshot:validate
 *
 * Vérifie : connexion DB, insertion snapshot, lecture historique, idempotence.
 */
import { openDb } from './db';
import { runSnapshot } from './snapshot';

let failures = 0;
function check(name: string, ok: boolean, detail?: unknown): void {
  if (ok) {
    console.log(`  ✓ ${name}`);
  } else {
    failures++;
    console.error(`  ✗ ${name}${detail !== undefined ? ' → ' + JSON.stringify(detail) : ''}`);
  }
}

async function main(): Promise<void> {
  const DATE = '2026-06-16';
  console.log('▶ Validation time-series (DB in-memory)\n');

  // 1) Connexion DB + schéma.
  const db = openDb(':memory:');
  const tables = db
    .prepare(`SELECT name FROM sqlite_master WHERE type='table'`)
    .all()
    .map((r: any) => r.name);
  check('connexion DB + schéma créé', ['products', 'product_snapshots', 'signals', 'snapshot_runs'].every((t) => tables.includes(t)), tables);

  // 2) Insertion snapshot.
  const first = await runSnapshot({ db, date: DATE });
  check('insertion snapshot (status ≠ error)', first.status !== 'error', first.status);
  check('au moins un snapshot écrit', first.snapshots_written > 0, first.snapshots_written);

  const countAfterFirst = (db.prepare(`SELECT COUNT(*) c FROM product_snapshots WHERE snapshot_date = ?`).get(DATE) as any).c;
  check('lignes présentes pour la date', countAfterFirst === first.snapshots_written, { countAfterFirst, written: first.snapshots_written });

  // 3) Lecture historique d'un produit.
  const sample = db.prepare(`SELECT product_id FROM product_snapshots WHERE snapshot_date = ? LIMIT 1`).get(DATE) as any;
  const history = db
    .prepare(`SELECT snapshot_date, sellability, organic, phase FROM product_snapshots WHERE product_id = ? ORDER BY snapshot_date DESC`)
    .all(sample.product_id);
  check('lecture historique produit', history.length >= 1, { product_id: sample.product_id, rows: history.length });

  // 4) Idempotence : relancer le même jour ne duplique pas.
  const second = await runSnapshot({ db, date: DATE });
  const countAfterSecond = (db.prepare(`SELECT COUNT(*) c FROM product_snapshots WHERE snapshot_date = ?`).get(DATE) as any).c;
  check('idempotence : pas de doublon après relance', countAfterSecond === countAfterFirst, { countAfterFirst, countAfterSecond });

  const distinct = (db.prepare(`SELECT COUNT(DISTINCT product_id) c FROM product_snapshots WHERE snapshot_date = ?`).get(DATE) as any).c;
  check('1 snapshot max par (produit, jour)', distinct === countAfterSecond, { distinct, countAfterSecond });

  const runs = (db.prepare(`SELECT COUNT(*) c FROM snapshot_runs`).get() as any).c;
  check('runs tracés (observabilité)', runs === 2, runs);

  db.close();

  console.log(`\n${failures === 0 ? '✅ TOUS LES TESTS PASSENT' : `❌ ${failures} test(s) en échec`}`);
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((err) => {
  console.error('Erreur fatale de validation :', err);
  process.exit(1);
});
