#!/usr/bin/env bash
# Démarre l'API Tandor (uvicorn) en arrière-plan, sans sudo.
# Appelé au boot par cron (@reboot). Idempotent : ne relance pas si déjà en route.
set -a; source "$HOME/tandor.env" 2>/dev/null; set +a
export TANDOR_CORS_ORIGINS="${TANDOR_CORS_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000}"
cd "$HOME/scrappingstuff/scripts/organic_engine" || exit 1

# Déjà en cours ? on ne fait rien.
if pgrep -f "uvicorn api.server:app" >/dev/null; then
    echo "API déjà en cours." >> "$HOME/tandor-api.log"
    exit 0
fi

source .venv/bin/activate
nohup .venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000 \
    >> "$HOME/tandor-api.log" 2>&1 &
echo "API démarrée (pid $!) à $(date -Is)" >> "$HOME/tandor-api.log"
