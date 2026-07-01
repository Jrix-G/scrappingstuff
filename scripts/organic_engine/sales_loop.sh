#!/usr/bin/env bash
# Worker ventes secondaires (eBay sold + DHgate sold) — un passage borné par run.
# Single-IP discipliné : budget modeste, le worker s'arrête seul (budget atteint,
# file à jour, ou IP épuisée). Domaines distincts d'AliExpress → buckets indépendants.
# Lancé par cron quelques fois/jour (cf. crontab). Logue dans ~/tandor-sales.log.
set -euo pipefail

ENGINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ENGINE/.venv/bin/python3"
LOG="$HOME/tandor-sales.log"

# Budget par source et par passage (ceiling single-IP ~30-40/jour/source).
EBAY_BUDGET="${EBAY_BUDGET:-25}"
DHGATE_BUDGET="${DHGATE_BUDGET:-40}"

cd "$ENGINE"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

echo "[$(ts)] === sales_loop : début (ebay=$EBAY_BUDGET, dhgate=$DHGATE_BUDGET) ===" >> "$LOG"

# DHgate d'abord (seuil de blocage plus tolérant), puis eBay. Séquentiel : on évite
# de saturer la bande passante du Pi, et chaque source a sa propre destination.
"$PY" "$ENGINE/sales_worker.py" --source dhgate --budget "$DHGATE_BUDGET" >> "$LOG" 2>&1 || \
    echo "[$(ts)] dhgate worker exit non-zéro (toléré)" >> "$LOG"

"$PY" "$ENGINE/sales_worker.py" --source ebay --budget "$EBAY_BUDGET" >> "$LOG" 2>&1 || \
    echo "[$(ts)] ebay worker exit non-zéro (toléré)" >> "$LOG"

echo "[$(ts)] === sales_loop : fin ===" >> "$LOG"
