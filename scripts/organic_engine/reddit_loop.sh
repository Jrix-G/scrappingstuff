#!/usr/bin/env bash
# Worker Reddit (mentions RSS) — un passage borné par run, reprenable.
# Couvre progressivement tout l'univers Amazon en empilant des snapshots datés dans
# reddit_snapshots. Le worker s'arrête seul (budget atteint, file à jour, ou RSS KO).
# Source RSS publique (domaine de rate-limit distinct des marketplaces) : cadence
# polie gérée dans reddit_mentions (cache TTL 6 h + intervalle mini 3 s + backoff).
# Appelé depuis tandor_scrape.sh (et/ou cron). Logue dans ~/tandor-reddit.log.
set -uo pipefail

ENGINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ENGINE/.venv/bin/python3"
LOG="$HOME/tandor-reddit.log"

# Budget par passage. ~8000 mots-clés / 2 shards ≈ 4000 par nœud ; à 200/run et
# 2 runs/jour (cron 08h+20h) → ~400/jour → univers couvert en ~10 jours.
REDDIT_BUDGET="${REDDIT_BUDGET:-200}"
MIN_AGE_H="${REDDIT_MIN_AGE_H:-168}"

cd "$ENGINE"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

echo "[$(ts)] === reddit_loop : début (budget=$REDDIT_BUDGET, min-age=${MIN_AGE_H}h) ===" >> "$LOG"

# Sauvegarde DB avant écriture (règle projet : cp avant toute écriture).
cp "$ENGINE/data/cj.db" "$ENGINE/data/cj.db.bak-reddit-$(date +%Y%m%d-%H%M)" 2>>"$LOG" || \
    echo "[$(ts)] backup DB échoué (toléré)" >> "$LOG"
# Ne garder que les 8 sauvegardes reddit les plus récentes (évite de remplir le disque).
ls -1t "$ENGINE"/data/cj.db.bak-reddit-* 2>/dev/null | tail -n +9 | xargs -r rm -f

"$PY" "$ENGINE/reddit_worker.py" --budget "$REDDIT_BUDGET" --min-age-h "$MIN_AGE_H" >> "$LOG" 2>&1 || \
    echo "[$(ts)] reddit worker exit non-zéro (toléré)" >> "$LOG"

echo "[$(ts)] === reddit_loop : fin ===" >> "$LOG"
