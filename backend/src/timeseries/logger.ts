/**
 * Logger structuré minimal (JSON lines). Pas de dépendance.
 * Chaque ligne : {ts, level, msg, ...fields} — exploitable par grep/jq ou un
 * collecteur de logs plus tard.
 */
type Level = 'info' | 'warn' | 'error';

function emit(level: Level, msg: string, fields?: Record<string, unknown>): void {
  const line = JSON.stringify({ ts: new Date().toISOString(), level, msg, ...(fields ?? {}) });
  if (level === 'error') console.error(line);
  else console.log(line);
}

export const logger = {
  info: (msg: string, fields?: Record<string, unknown>) => emit('info', msg, fields),
  warn: (msg: string, fields?: Record<string, unknown>) => emit('warn', msg, fields),
  error: (msg: string, fields?: Record<string, unknown>) => emit('error', msg, fields),
};
