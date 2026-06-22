#!/usr/bin/env bash
# watchdog.sh — surveillance Tandor (cron */5).
#
# IMPORTANT : le demand_runner est géré par systemd (tandor-demand.service,
# Restart=always). On NE le surveille donc PAS ici, sinon on créerait des
# doublons en course avec systemd. Ce watchdog ne couvre que l'API uvicorn,
# qui n'a aucun superviseur (lancée seulement au boot par start_all.sh).
ENGINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ENGINE" || exit 1

if ! pgrep -f "uvicorn api.server:app" >/dev/null; then
    bash "$ENGINE/start_api.sh" >> "$HOME/tandor-api.log" 2>&1
    echo "[$(date '+%F %T')] watchdog: API morte → relancée" >> "$HOME/tandor-api.log"
fi

# Boucle Ali single-IP (pas de superviseur dédié, pas de root) → on la garde vivante.
if ! pgrep -f "ali_single_ip_loop.sh" >/dev/null; then
    setsid bash "$ENGINE/ali_single_ip_loop.sh" < /dev/null >> "$HOME/tandor-ali.log" 2>&1 &
    echo "[$(date '+%F %T')] watchdog: boucle Ali morte → relancée" >> "$HOME/tandor-ali.log"
fi
