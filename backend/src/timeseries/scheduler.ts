/**
 * Scheduler — job quotidien d'historisation (node-cron).
 *
 *   npm run snapshot:cron        # process long-vivant, déclenche le snapshot chaque jour
 *
 * Config (env) :
 *   SNAPSHOT_CRON   expression cron        (défaut '0 3 * * *' = 03:00 chaque jour)
 *   SNAPSHOT_TZ     timezone               (défaut 'Europe/Paris')
 *   SNAPSHOT_RUN_ON_START  '1' → exécute un snapshot immédiatement au démarrage
 *
 * Alternative sans process long-vivant : appeler `npm run snapshot:once` depuis le
 * cron système (crontab) — le job est idempotent, les deux approches sont sûres.
 */
import cron from 'node-cron';
import { runSnapshot } from './snapshot';
import { logger } from './logger';

const expr = process.env.SNAPSHOT_CRON || '0 3 * * *';
const timezone = process.env.SNAPSHOT_TZ || 'Europe/Paris';

if (!cron.validate(expr)) {
  logger.error('scheduler.invalid_cron', { expr });
  process.exit(1);
}

async function tick(trigger: string): Promise<void> {
  logger.info('scheduler.trigger', { trigger, expr, timezone });
  try {
    await runSnapshot();
  } catch (err) {
    logger.error('scheduler.tick_failed', { err: String(err) });
  }
}

cron.schedule(expr, () => void tick('cron'), { timezone });
logger.info('scheduler.started', { expr, timezone });

if (process.env.SNAPSHOT_RUN_ON_START === '1') {
  void tick('startup');
}

// Garde le process vivant + arrêt propre.
process.on('SIGINT', () => { logger.info('scheduler.stopping', { signal: 'SIGINT' }); process.exit(0); });
process.on('SIGTERM', () => { logger.info('scheduler.stopping', { signal: 'SIGTERM' }); process.exit(0); });
