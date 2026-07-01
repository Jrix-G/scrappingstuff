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

# Valeurs de repli (utilisées seulement si le pacer AIMD est indisponible).
DRIP=360          # 6 min entre requêtes : pacing soutenable prouvé (1 req/5-6min)
HEAL=2100         # 35 min de silence après un punish (ou au démarrage) — l'IP guérit
EMPTY=3600        # 1 h si la file Ali est à jour (rien à faire)

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

# La cadence n'est plus figée : ali_pacer.py apprend en AIMD la cadence sûre par IP
# (succès → on accélère un peu ; punish → on recule fort + on guérit plus longtemps).
# pace_get renvoie la valeur du pacer, ou le repli fourni si le pacer échoue.
pace_get() {  # $1=interval|cooldown  $2=valeur de repli
    local v
    v="$("$PY" "$ENGINE/ali_pacer.py" get "$1" 2>/dev/null)"
    case "$v" in
        ''|*[!0-9]*) echo "$2" ;;   # vide ou non-numérique → repli
        *)           echo "$v"  ;;
    esac
}

INIT_HEAL="$(pace_get cooldown "$HEAL")"
log "=== Démarrage boucle Ali single-IP (cadence AIMD adaptative, extraction-max) — repos initial ${INIT_HEAL}s pour laisser l'IP guérir ==="
sleep "$INIT_HEAL"

while true; do
    # --budget 1 : UNE requête extraction-max par réveil (pas de burst).
    # Le worker appelle ali_pacer.observe(success|punish) → l'état de cadence est
    # à jour AVANT qu'on lise la recommandation ci-dessous.
    "$PY" "$ENGINE/ali_burst_worker.py" --budget 1 --batch 60 >> "$LOG" 2>&1
    rc=$?
    case "$rc" in
        0) log "file Ali à jour → repos $((EMPTY/60)) min"; sleep "$EMPTY" ;;
        2) c="$(pace_get cooldown "$HEAL")"
           log "punish → silence $((c/60)) min AIMD (ne pas réarmer le timer)"; sleep "$c" ;;
        *) d="$(pace_get interval "$DRIP")"
           log "succès → prochaine requête dans $((d/60)) min AIMD"; sleep "$d" ;;
    esac
done
