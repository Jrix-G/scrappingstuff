/**
 * CLI manuel pour le système time-series.
 *
 *   npm run snapshot:once                 # snapshot du jour (idempotent)
 *   npm run snapshot:once -- --date 2026-06-10
 *   npm run snapshot:history -- <productId> [--limit 30]
 *   npm run snapshot:history              # derniers runs si pas d'id
 */
import { openDb } from './db';
import { runSnapshot } from './snapshot';
import { runBackfillFromCjDb } from './backfill';
import { logger } from './logger';

function arg(name: string): string | undefined {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : undefined;
}

async function main(): Promise<void> {
  const cmd = process.argv[2] ?? 'run';

  if (cmd === 'run') {
    const result = await runSnapshot({ date: arg('date') });
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
    process.exit(result.status === 'error' ? 1 : 0);
  }

  if (cmd === 'backfill') {
    const result = runBackfillFromCjDb();
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
    process.exit(result.status === 'error' ? 1 : 0);
  }

  if (cmd === 'history') {
    const db = openDb();
    const limit = Number(arg('limit') ?? 30);
    const productId = process.argv[3] && !process.argv[3].startsWith('--') ? process.argv[3] : undefined;

    if (productId) {
      const rows = db
        .prepare(
          `SELECT snapshot_date, sellability, organic, growth, net, listed, phase, verdict
           FROM product_snapshots WHERE product_id = ? ORDER BY snapshot_date DESC LIMIT ?`,
        )
        .all(productId, limit);
      process.stdout.write(JSON.stringify({ product_id: productId, history: rows }, null, 2) + '\n');
    } else {
      const runs = db
        .prepare(`SELECT * FROM snapshot_runs ORDER BY id DESC LIMIT ?`)
        .all(limit);
      process.stdout.write(JSON.stringify({ runs }, null, 2) + '\n');
    }
    db.close();
    process.exit(0);
  }

  logger.error('cli.unknown_command', { cmd });
  process.stdout.write('Usage: run [--date YYYY-MM-DD] | history [productId] [--limit N]\n');
  process.exit(1);
}

main().catch((err) => {
  logger.error('cli.fatal', { err: String(err) });
  process.exit(1);
});
