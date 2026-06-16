#!/usr/bin/env bash
# tandor_scrape.sh — Script unique Tandor
#
# Première fois : sudo bash tandor_scrape.sh
# Ensuite        : se relance tout seul chaque soir à 20h via cron
#
# Ce qu'il fait automatiquement :
#   1. Installation (une seule fois) : namespace VPN, helpers, sudoers
#   2. Ajout au cron à 20h (une seule fois)
#   3. Rotation des VPN WireGuard + scraping AliExpress / Trends / TikTok
#      sur l'ensemble des mots-clés de l'univers CJ (~3400 keywords)

set -uo pipefail

ENGINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HOME/tandor-scrape.log"
CRON_HOUR=20

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ── 1. SETUP (une seule fois, nécessite root) ─────────────────────────────────

if [[ ! -x /usr/local/bin/tandor-vpn-up ]]; then
    if [[ $EUID -ne 0 ]]; then
        echo
        echo "  ┌─────────────────────────────────────────────────────┐"
        echo "  │  Premier lancement — setup requis                   │"
        echo "  │  Lance cette commande UNE SEULE FOIS :              │"
        echo "  │                                                     │"
        echo "  │    sudo bash $ENGINE/tandor_scrape.sh  │"
        echo "  │                                                     │"
        echo "  │  Ensuite tout est automatique via cron.             │"
        echo "  └─────────────────────────────────────────────────────┘"
        echo
        exit 1
    fi
    log "=== Premier lancement : installation ==="
    bash "$ENGINE/vpn_setup.sh"
    log "=== Installation terminée ==="
fi

# ── 2. CRON (s'auto-ajoute si absent) ────────────────────────────────────────

CRON_CMD="$CRON_HOUR 20 * * * bash $ENGINE/tandor_scrape.sh >> $LOG 2>&1"
CRON_MARK="tandor_scrape"

# Récupère l'utilisateur réel (même si lancé via sudo)
REAL_USER="${SUDO_USER:-$USER}"

if ! crontab -u "$REAL_USER" -l 2>/dev/null | grep -q "$CRON_MARK"; then
    ( crontab -u "$REAL_USER" -l 2>/dev/null; echo "0 $CRON_HOUR * * * bash $ENGINE/tandor_scrape.sh >> $LOG 2>&1  # $CRON_MARK" ) \
        | crontab -u "$REAL_USER" -
    log "Cron ajouté : tous les soirs à ${CRON_HOUR}h pour $REAL_USER"
fi

# ── 3. SCRAPING (rotation VPN + tous les mots-clés) ──────────────────────────

log "=== Démarrage scraping (rotation VPN + AliExpress + Trends + TikTok) ==="
log "Univers cible : ~3400 mots-clés | VPN : $(ls /etc/wireguard/*.conf 2>/dev/null | wc -l) configs"

WG_DIR="/etc/wireguard"
PY="$ENGINE/.venv/bin/python3"
NETNS="tandor-vpn"
WG_IF="wg-tnd"

COOLDOWN_BLOCKED=90
COOLDOWN_BATCH=10
MAX_ROTATIONS=20   # peut dépasser 14 (revient au début si tout bloqué une fois)

cleanup() { sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true; }
trap cleanup EXIT

# Mélange aléatoire des configs, avec possibilité de faire 2 tours si nécessaire
mapfile -t ALL_CONFIGS < <(ls "$WG_DIR"/*.conf 2>/dev/null)
CONFIGS=()
for c in "${ALL_CONFIGS[@]}"; do CONFIGS+=("$c"); done
for c in "${ALL_CONFIGS[@]}"; do CONFIGS+=("$c"); done  # 2 passages = 28 slots max
# Re-mélanger
mapfile -t CONFIGS < <(printf '%s\n' "${CONFIGS[@]}" | shuf)

rotations=0
config_idx=0
total_configs=${#CONFIGS[@]}

while [[ $rotations -lt $MAX_ROTATIONS ]] && [[ $config_idx -lt $total_configs ]]; do
    CONF="${CONFIGS[$config_idx]}"
    NAME=$(basename "$CONF" .conf)
    log "→ VPN $NAME (slot $((rotations+1))/$MAX_ROTATIONS)"

    # Nettoyage avant montage
    sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true

    if ! sudo /usr/local/bin/tandor-vpn-up "$CONF" >> "$LOG" 2>&1; then
        log "  ✗ Montage échoué — config suivante"
        ((config_idx++)) || true
        continue
    fi
    sleep 3

    # Boucle de batches sur cette IP
    while true; do
        sudo /usr/local/bin/tandor-vpn-exec-warmer \
            --target all \
            --batch 40 \
            --max-keywords 4000 \
            >> "$LOG" 2>&1
        exit_code=$?

        case $exit_code in
            0)
                log "✓ Tout le cache est chaud — scraping terminé"
                exit 0
                ;;
            2)
                log "  ⚠ IP $NAME bloquée — cooldown ${COOLDOWN_BLOCKED}s"
                break
                ;;
            1)
                log "  → Batch suivant dans ${COOLDOWN_BATCH}s"
                sleep $COOLDOWN_BATCH
                ;;
            *)
                log "  ✗ Erreur inattendue (exit $exit_code) — config suivante"
                break
                ;;
        esac
    done

    sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true
    sleep $COOLDOWN_BLOCKED
    ((rotations++)) || true
    ((config_idx++)) || true
done

log "=== Scraping terminé ($rotations rotations) ==="
