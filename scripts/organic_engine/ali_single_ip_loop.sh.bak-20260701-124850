#!/usr/bin/env bash
# ali_single_ip_loop.sh — collecte AliExpress sur UNE SEULE IP (pas de VPN).
#
# Faits prouvés en live (mémoire projet, tests 2026-06-17) :
#   - Pas de pool VPN exploitable (les "14 IP" = fiction, 0 rotation réelle).
#   - Blocage x5sec = état PAR IP ; plafond dur ~250 requêtes/jour sur une IP.
#   - Pacing soutenable PROUVÉ = 1 req / 5-6 min (le burst de 3-4 risque de
#     tripper le bucket ; inutile de toute façon).
#   - Reprober PENDANT un blocage réarme le timer → si punish, on se TAIT ~35 min.
#
# Le vrai levier n'est donc PAS le débit mais l'EXTRACTION-MAX : chaque requête
# passe par ali_page_parser → ~60 produits + ventes (vs 1 résumé avant). Donc :
#   goutte-à-goutte régulier (1 req / 6 min) × 60 produits = max de valeur, sûr.
#
# Démarré par watchdog/@reboot. Resumable (état en cj.db). Aucun root requis.
set -uo pipefail
ENGINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ENGINE/.venv/bin/python3"
LOG="$HOME/tandor-ali.log"

DRIP=360          # 6 min entre requêtes : pacing soutenable prouvé (1 req/5-6min)
HEAL=2100         # 35 min de silence après un punish (ou au démarrage) — l'IP guérit
EMPTY=3600        # 1 h si la file Ali est à jour (rien à faire)

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

log "=== Démarrage boucle Ali single-IP (goutte-à-goutte 1 req/${DRIP}s, extraction-max) — repos initial ${HEAL}s pour laisser l'IP guérir ==="
sleep "$HEAL"

while true; do
    # --budget 1 : UNE requête extraction-max par réveil (pas de burst).
    "$PY" "$ENGINE/ali_burst_worker.py" --budget 1 --batch 60 >> "$LOG" 2>&1
    rc=$?
    case "$rc" in
        0) log "file Ali à jour → repos $((EMPTY/60)) min"; sleep "$EMPTY" ;;
        2) log "punish → silence $((HEAL/60)) min (ne pas réarmer le timer)"; sleep "$HEAL" ;;
        *) sleep "$DRIP" ;;
    esac
done
