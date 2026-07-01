#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# start_preview.sh — met le site Tandor en ligne via un tunnel Cloudflare.
#
# Enchaîne : (1) tunnel cloudflared -> URL publique, (2) injecte cette URL
# dans frontend/.env.local (REACT_APP_API_URL), (3) build du front,
# (4) serveur de preview (build statique + proxy /api,/graphs -> uvicorn:8000).
#
# Une seule origine -> pas de CORS, et l'API live (uvicorn:8000) n'est pas touchée.
# Prérequis : l'API uvicorn doit déjà tourner sur le port 8000, et
#   ~/bin/cloudflared installé (binaire arm64).
#
# Usage :  bash scripts/start_preview.sh
# Arrêt :  bash scripts/start_preview.sh stop
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONT="$ROOT/frontend"
ENV_FILE="$FRONT/.env.local"
PORT=3000
CF="$HOME/bin/cloudflared"
RUN_DIR="$ROOT/.preview"
mkdir -p "$RUN_DIR"
CF_LOG="$RUN_DIR/cloudflared.log"
SRV_LOG="$RUN_DIR/preview_server.log"

stop() {
  echo "==> Arrêt des process de preview…"
  pkill -f "cloudflared tunnel --url http://localhost:$PORT" 2>/dev/null || true
  pkill -f "scripts/preview_server.js" 2>/dev/null || true
  echo "    fait."
}

if [[ "${1:-}" == "stop" ]]; then stop; exit 0; fi

command -v "$CF" >/dev/null 2>&1 || { echo "❌ cloudflared introuvable à $CF"; exit 1; }
curl -s --max-time 4 http://localhost:8000/api/products?limit=1 -o /dev/null \
  || echo "⚠️  L'API uvicorn ne répond pas sur :8000 — le front s'affichera mais sans données live."

# 0) on repart propre
stop
sleep 1

# 1) tunnel cloudflared -> URL publique
echo "==> Démarrage du tunnel Cloudflare…"
nohup "$CF" tunnel --url "http://localhost:$PORT" --no-autoupdate >"$CF_LOG" 2>&1 &
URL=""
for i in $(seq 1 30); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$CF_LOG" | head -1 || true)"
  [[ -n "$URL" ]] && break
  sleep 1
done
[[ -z "$URL" ]] && { echo "❌ Pas d'URL de tunnel obtenue (voir $CF_LOG)"; exit 1; }
echo "    URL publique : $URL"

# 2) injecter l'URL dans .env.local (REACT_APP_API_URL = même origine que le front)
echo "==> Mise à jour de $ENV_FILE (REACT_APP_API_URL)…"
if grep -q '^REACT_APP_API_URL=' "$ENV_FILE" 2>/dev/null; then
  sed -i "s#^REACT_APP_API_URL=.*#REACT_APP_API_URL=$URL#" "$ENV_FILE"
else
  printf '\nREACT_APP_API_URL=%s\n' "$URL" >>"$ENV_FILE"
fi

# 3) build du front
echo "==> Build du front (CI=false)…"
( cd "$FRONT" && CI=false npm run build )

# 4) serveur de preview
echo "==> Démarrage du serveur de preview sur :$PORT…"
nohup node "$ROOT/scripts/preview_server.js" >"$SRV_LOG" 2>&1 &
sleep 2

echo
echo "============================================================"
echo "✅ EN LIGNE :  $URL"
echo "============================================================"
echo "⚠️  Firebase : ajoute le domaine dans la console pour que le login marche :"
echo "    Authentication → Settings → Authorized domains → Add domain"
echo "    -> ${URL#https://}"
echo
echo "Logs    : $CF_LOG  |  $SRV_LOG"
echo "Arrêter : bash scripts/start_preview.sh stop"
