#!/usr/bin/env bash
# vpn_warmer.sh — Remplit le cache AliExpress + Trends via rotation de VPN WireGuard.
#
# Usage : bash vpn_warmer.sh [--target aliexpress|trends|all] [--batch N]
#         bash vpn_warmer.sh --target aliexpress --batch 50
#
# Fonctionnement :
#   Pour chaque config WireGuard disponible (ordre aléatoire) :
#     1. Monte le VPN dans le namespace 'tandor-vpn' (trafic CJ non touché)
#     2. Lance vpn_warmer.py en batch — le script scrape au travers du VPN actif
#     3. Si l'IP est bloquée (exit 2) : coupe, cooldown, passe à la config suivante
#     4. Si tout est en cache (exit 0) : terminé — coupe et sort
#     5. Si batch partiel (exit 1)     : continue la boucle (mots-clés restants)
#
# Prérequis :
#   sudo bash vpn_setup.sh    (une seule fois — installe helpers + sudoers)
#
# Garanties :
#   - daily.sh / hourly.sh JAMAIS modifiés
#   - Namespace par défaut JAMAIS touché → scraping CJ à 04:12 et :30 non affecté
#   - Idempotent : les mots-clés déjà en cache sont sautés immédiatement

set -uo pipefail

ENGINE="$HOME/scrappingstuff/scripts/organic_engine"
WG_DIR="/etc/wireguard"
LOG="$HOME/tandor-vpn-warmer.log"

# -- Paramètres ---------------------------------------------------------------
TARGET="all"
BATCH=30
for arg in "$@"; do
    case "$arg" in
        --target=*) TARGET="${arg#*=}" ;;
        --target)   shift; TARGET="$1" ;;
        --batch=*)  BATCH="${arg#*=}" ;;
        --batch)    shift; BATCH="$1" ;;
    esac
done

COOLDOWN_BLOCKED=90    # secondes de cooldown après un blocage IP avant la prochaine config
COOLDOWN_BATCH=10      # secondes entre deux batches sur la même IP
MAX_ROTATIONS=14       # jamais plus de 14 rotations (= nb max de configs ProtonVPN)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# -- Sanity checks ------------------------------------------------------------
if ! command -v sudo &>/dev/null; then
    log "ERREUR : sudo non disponible"
    exit 1
fi

# Vérifie que les helpers sont installés (résultat de vpn_setup.sh)
if [[ ! -x /usr/local/bin/tandor-vpn-up ]]; then
    log "ERREUR : helpers non installés. Lance d'abord : sudo bash vpn_setup.sh"
    exit 1
fi

# -- Collecte des configs WireGuard (ordre aléatoire pour éviter l'usure) -----
mapfile -t CONFIGS < <(ls "$WG_DIR"/*.conf 2>/dev/null | shuf)
if [[ ${#CONFIGS[@]} -eq 0 ]]; then
    log "ERREUR : aucun .conf dans $WG_DIR"
    exit 1
fi
log "Warmer démarré | target=$TARGET batch=$BATCH | ${#CONFIGS[@]} configs VPN disponibles"

# Nettoyer le VPN à la sortie (ctrl-c, kill, erreur)
cleanup() {
    sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true
}
trap cleanup EXIT

# -- Boucle de rotation -------------------------------------------------------
rotations=0
config_idx=0
total_fetched=0

while [[ $rotations -lt $MAX_ROTATIONS ]] && [[ $config_idx -lt ${#CONFIGS[@]} ]]; do
    CONF="${CONFIGS[$config_idx]}"
    CONF_NAME=$(basename "$CONF" .conf)

    log "→ VPN $CONF_NAME (rotation $((rotations+1))/$MAX_ROTATIONS)"

    # Monter le VPN dans le namespace isolé
    if ! sudo /usr/local/bin/tandor-vpn-up "$CONF" >> "$LOG" 2>&1; then
        log "  ✗ Échec montage $CONF_NAME — on passe"
        ((config_idx++)) || true
        continue
    fi

    # Petite pause pour laisser WireGuard établir la connexion
    sleep 3

    # Boucle de batches sur cette IP
    while true; do
        sudo /usr/local/bin/tandor-vpn-exec-warmer \
            --target "$TARGET" \
            --batch "$BATCH" 2>>"$LOG"
        warmer_exit=$?

        case $warmer_exit in
            0)  # Cache complet — tout est chaud
                log "✓ Cache complet — travail terminé après $((rotations+1)) rotation(s)"
                exit 0
                ;;
            2)  # IP bloquée — rotation immédiate
                log "  ⚠ IP $CONF_NAME bloquée — cooldown ${COOLDOWN_BLOCKED}s puis rotation"
                break
                ;;
            1)  # Batch partiel — il reste des mots-clés, on continue avec la même IP
                log "  → Batch terminé — ${COOLDOWN_BATCH}s puis prochain batch"
                sleep "$COOLDOWN_BATCH"
                ;;
            *)  # Erreur inattendue — on passe quand même
                log "  ✗ Warmer exit $warmer_exit — on passe à la prochaine config"
                break
                ;;
        esac
    done

    sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true
    sleep "$COOLDOWN_BLOCKED"
    ((rotations++)) || true
    ((config_idx++)) || true
done

log "Warmer terminé : $rotations rotation(s) effectuée(s)"
