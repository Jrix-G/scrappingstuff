#!/usr/bin/env bash
# start_all.sh — Commande unique de démarrage Tandor sur le Raspberry Pi.
#
# Usage :
#   bash start_all.sh          # démarre tout ce qui n'est pas déjà actif
#   bash start_all.sh --status # affiche l'état sans rien démarrer
#
# Idempotent : peut être relancé à tout moment sans tuer ce qui tourne.
# Ajouter au crontab pour le boot automatique :
#   @reboot bash ~/scrappingstuff/scripts/organic_engine/start_all.sh >> ~/tandor-start.log 2>&1

set -euo pipefail

ENGINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="$HOME"
VENV="$ENGINE/.venv"
ENV_FILE="$HOME_DIR/tandor.env"
LOG_DIR="$HOME_DIR"
STATUS_ONLY=false

[[ "${1:-}" == "--status" ]] && STATUS_ONLY=true

# ── Couleurs ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; }
info() { echo -e "  · $*"; }

echo ""
echo "═══════════════════════════════════════════"
echo "  Tandor — démarrage complet"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════"
echo ""

# ── 1. Vérifications préalables ───────────────────────────────────────────────

if [[ ! -f "$ENV_FILE" ]]; then
    fail "Fichier manquant : $ENV_FILE"
    echo "     Crée-le avec : CJ_EMAIL=... / CJ_API_KEY=... / TANDOR_CORS_ORIGINS=..."
    exit 1
fi
set -a; source "$ENV_FILE"; set +a
ok "Credentials chargés ($ENV_FILE)"

if [[ ! -d "$VENV" ]]; then
    fail "venv absent : $VENV"
    echo "     Lance d'abord : python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi
ok "venv trouvé"

if [[ -z "${CJ_EMAIL:-}" ]] || [[ -z "${CJ_API_KEY:-}" ]]; then
    fail "CJ_EMAIL ou CJ_API_KEY manquant dans $ENV_FILE"
    exit 1
fi
ok "Credentials CJ présents"

if $STATUS_ONLY; then
    echo ""
    echo "── État des processus ───────────────────────"
    pgrep -f "uvicorn api.server:app" >/dev/null && ok "API uvicorn : en cours" || fail "API uvicorn : arrêtée"
    pgrep -f "demand_runner.py"       >/dev/null && ok "demand_runner : en cours" || warn "demand_runner : arrêté"
    echo ""
    echo "── Crons installés ──────────────────────────"
    crontab -l 2>/dev/null | grep -E "daily\.sh|hourly\.sh|tandor_scrape|start_all" || warn "Aucun cron Tandor trouvé"
    echo ""
    exit 0
fi

# ── 2. Init base de données (idempotent) ──────────────────────────────────────

info "Initialisation de la DB..."
cd "$ENGINE"
"$VENV/bin/python3" - <<'PYEOF'
import sys, pathlib
sys.path.insert(0, str(pathlib.Path('.').resolve()))
from collect_cj import init_db
conn = init_db()
conn.close()
print("    DB initialisée (WAL activé)")
PYEOF
ok "cj.db prête"

# ── 3. API uvicorn ────────────────────────────────────────────────────────────

if pgrep -f "uvicorn api.server:app" >/dev/null; then
    ok "API déjà en cours (pas de redémarrage)"
else
    info "Démarrage de l'API..."
    export TANDOR_CORS_ORIGINS="${TANDOR_CORS_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000}"
    nohup "$VENV/bin/uvicorn" api.server:app --host 0.0.0.0 --port 8000 \
        >> "$LOG_DIR/tandor-api.log" 2>&1 &
    API_PID=$!
    echo "$API_PID" > "$HOME_DIR/.tandor-api.pid"
    ok "API démarrée (pid $API_PID) → log : $LOG_DIR/tandor-api.log"
fi

# ── 4. Health check API ───────────────────────────────────────────────────────

info "Attente API health check..."
MAX_WAIT=30
for i in $(seq 1 $MAX_WAIT); do
    if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
        ok "API répond sur :8000 (${i}s)"
        break
    fi
    if [[ $i -eq $MAX_WAIT ]]; then
        warn "API ne répond pas après ${MAX_WAIT}s — vérifie $LOG_DIR/tandor-api.log"
    fi
    sleep 1
done

# ── 5. Demand runner (Amazon + AliExpress 24/7) ───────────────────────────────

if pgrep -f "demand_runner.py" >/dev/null; then
    ok "demand_runner déjà en cours (pas de redémarrage)"
else
    info "Démarrage du demand runner..."
    nohup "$VENV/bin/python3" "$ENGINE/demand_runner.py" \
        >> "$LOG_DIR/tandor-demand.log" 2>&1 &
    DEMAND_PID=$!
    echo "$DEMAND_PID" > "$HOME_DIR/.tandor-demand.pid"
    ok "demand_runner démarré (pid $DEMAND_PID) → log : $LOG_DIR/tandor-demand.log"
fi

# ── 6. Crons (daily + hourly + scrape nightly + reboot) ──────────────────────

info "Vérification des crons..."

# Lit le crontab actuel (vide si absent)
CURRENT_CRON=$(crontab -l 2>/dev/null || true)
CRON_CHANGED=false

_ensure_cron() {
    local marker="$1"
    local line="$2"
    if echo "$CURRENT_CRON" | grep -qF "$marker"; then
        : # déjà présent
    else
        CURRENT_CRON="${CURRENT_CRON}"$'\n'"${line}"
        CRON_CHANGED=true
        info "  Ajout cron : $marker"
    fi
}

_ensure_cron "daily.sh"      "12 4 * * * bash $ENGINE/daily.sh >> $LOG_DIR/tandor-daily.log 2>&1"
_ensure_cron "hourly.sh"     "30 * * * * bash $ENGINE/hourly.sh >> $LOG_DIR/tandor-hourly.log 2>&1"
_ensure_cron "tandor_scrape" "0 20 * * * bash $ENGINE/tandor_scrape.sh >> $LOG_DIR/tandor-scrape.log 2>&1"
_ensure_cron "start_all"     "@reboot bash $ENGINE/start_all.sh >> $LOG_DIR/tandor-start.log 2>&1"

if $CRON_CHANGED; then
    echo "$CURRENT_CRON" | crontab -
    ok "Crontab mis à jour (4 entrées Tandor)"
else
    ok "Crons déjà en place"
fi

# ── 7. Résumé final ───────────────────────────────────────────────────────────

API_OK=false
DEMAND_OK=false

pgrep -f "uvicorn api.server:app" >/dev/null && API_OK=true
pgrep -f "demand_runner.py"       >/dev/null && DEMAND_OK=true

echo ""
echo "═══════════════════════════════════════════"
echo "  Statut Tandor"
echo "═══════════════════════════════════════════"
$API_OK    && ok   "API FastAPI       → http://localhost:8000/api/health" \
           || fail "API FastAPI       → non démarrée"
$DEMAND_OK && ok   "Demand runner     → Amazon + AliExpress 24/7" \
           || warn "Demand runner     → non démarré"
ok "Cron daily        → 04:12 (collecte CJ + rebuild cache)"
ok "Cron hourly       → :30 (refresh univers)"
ok "Cron nightly      → 20:00 (AliExpress + Trends via VPN)"
ok "Cron @reboot      → relance automatique au démarrage"
echo ""
echo "  Logs :"
echo "    API       : tail -f $LOG_DIR/tandor-api.log"
echo "    Demand    : tail -f $LOG_DIR/tandor-demand.log"
echo "    Daily     : tail -f $LOG_DIR/tandor-daily.log"
echo "    Nightly   : tail -f $LOG_DIR/tandor-scrape.log"
echo ""

# ── 8. Notification Discord ────────────────────────────────────────────────────
if [[ -n "${DISCORD_WEBHOOK_URL:-}" ]]; then
    COMPONENTS=""
    $API_OK    && COMPONENTS="${COMPONENTS}API FastAPI ✓\n" || COMPONENTS="${COMPONENTS}API FastAPI ✗\n"
    $DEMAND_OK && COMPONENTS="${COMPONENTS}Demand Runner ✓\n" || COMPONENTS="${COMPONENTS}Demand Runner ✗\n"
    COMPONENTS="${COMPONENTS}Crons (daily/hourly/nightly/reboot) ✓"

    python3 - <<PYEOF
import os, json, requests, datetime
url = os.environ["DISCORD_WEBHOOK_URL"]
embed = {
    "title": "Tandor Pi — Démarrage",
    "description": "$(echo -e "$COMPONENTS")",
    "color": 0xF1C40F,
    "timestamp": datetime.datetime.utcnow().isoformat(),
    "footer": {"text": "Raspberry Pi"},
}
try:
    requests.post(url, json={"embeds": [embed]}, timeout=10)
except Exception as e:
    print(f"[Discord silenced] {e}")
PYEOF
fi
