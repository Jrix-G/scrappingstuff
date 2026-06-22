#!/usr/bin/env bash
# Job quotidien Tandor (cron 04:12). Collecte CJ + rebuild cache + warm Trends/Reddit.
set -a; source "$HOME/tandor.env"; set +a
ENGINE="$HOME/scrappingstuff/scripts/organic_engine"
cd "$ENGINE" || exit 1
source .venv/bin/activate

LOG="$HOME/tandor-daily.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

log "=== Début job quotidien ==="

# 1. Collecte CJ : 200 pages ≈ 10 000 nouveaux produits/jour.
#    --no-refresh : le refresh est géré par hourly.sh (étalé sur 24h).
#    --limit 60   : top 60 enrichi Trends/Reddit (heure creuse → anti-429)
log "Collecte CJ (200 pages)..."
python3 run_daily.py --pages 200 --no-refresh --limit 60 >> "$LOG" 2>&1
log "Collecte CJ terminée."

# 2. Warm Reddit sur les top 200 mots-clés (RSS public, pas de rate-limit agressif).
#    Préchauffe le cache pour que /api/validate réponde instantanément sur ces keywords.
log "Warm Reddit (top 200 keywords)..."
python3 - >> "$LOG" 2>&1 <<'PYEOF'
import sys, pathlib, sqlite3, time
sys.path.insert(0, str(pathlib.Path('.').resolve()))
from collect_cj import DB_PATH
from enrich import keyword_from_name
from collectors.reddit_mentions import reddit_raw_signal

try:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    rows = conn.execute(
        "SELECT name FROM cj_products WHERE name IS NOT NULL ORDER BY rowid DESC LIMIT 400"
    ).fetchall()
    conn.close()
    keywords = list({keyword_from_name(r[0]) for r in rows if keyword_from_name(r[0])})[:200]
    print(f"  {len(keywords)} mots-clés à préchauffer Reddit", flush=True)
    for i, kw in enumerate(keywords):
        try:
            sig = reddit_raw_signal(kw)
            if sig.values:
                print(f"  [{i+1}/{len(keywords)}] {kw} → {len(sig.values)} pts", flush=True)
        except Exception as e:
            print(f"  [{i+1}] {kw} erreur : {e}", flush=True)
        time.sleep(1)
except Exception as e:
    print(f"  Warm Reddit échoué : {e}", flush=True)
PYEOF
log "Warm Reddit terminé."

# 3. Vérification demand_runner (géré par systemd, Restart=always — on ne relance
#    pas à la main pour éviter un doublon non géré ; on ne fait que constater l'état)
if systemctl is-active --quiet tandor-demand.service; then
    log "demand_runner géré par systemd (actif)."
elif pgrep -f "demand_runner.py" >/dev/null; then
    log "demand_runner actif (hors systemd)."
else
    log "⚠ demand_runner inactif — systemd devrait le relancer sous 10s."
fi

# 4. Snapshot time-series (backend Node.js)
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
cd "$HOME/scrappingstuff/backend" && npm run --silent snapshot:once >> "$LOG" 2>&1

log "=== Job quotidien terminé ==="

# 5. Purge du cache HTML > 48h (le signal est déjà en base, le HTML ne sert plus)
#    Plafonne .amazon_cache pour ne pas saturer les 16 Go libres du Pi.
find "$ENGINE/.amazon_cache" -name '*.html' -mtime +2 -delete 2>/dev/null
find "$ENGINE/.aliexpress_cache" -name '*.html' -mtime +2 -delete 2>/dev/null
log "Purge cache HTML > 48h effectuée."

# 6. Rapport Discord (via le bot existant — notify_discord.py, même salon que le runner)
cd "$ENGINE" && python3 - >> "$LOG" 2>&1 <<'PYEOF'
import sqlite3, datetime, os
from pathlib import Path
import notify_discord as notify

db = Path.home() / "scrappingstuff/scripts/organic_engine/data/cj.db"
collected = new_today = 0
err = ""
try:
    con = sqlite3.connect(db)
    collected = con.execute("SELECT COUNT(*) FROM cj_products").fetchone()[0]
    today = datetime.date.today().isoformat()
    new_today = con.execute(
        "SELECT COUNT(*) FROM cj_products WHERE DATE(created_at)=?", (today,)
    ).fetchone()[0]
    con.close()
except Exception as e:
    err = str(e)
demand_ok = bool(os.popen("pgrep -f demand_runner.py").read().strip())
free = os.popen("df -h / | awk 'NR==2{print $4}'").read().strip()
msg = (f"📊 **Rapport quotidien Tandor** — {collected:,} produits CJ "
       f"(+{new_today:,} aujourd'hui) · runner {'✅' if demand_ok else '❌'} · {free} dispo"
       + (f" · ⚠ {err}" if err else ""))
notify.send(msg, ping=True)   # rapport quotidien = notifiant
PYEOF
