#!/usr/bin/env bash
# tandor_scrape.sh — Script unique Tandor
#
# Première fois : sudo bash tandor_scrape.sh
# Ensuite        : se relance tout seul chaque soir à 20h via cron
#
# Stratégie :
#   AliExpress + TikTok → IP maison d'abord (fonctionne, IPs VPN blacklistées)
#                       → fallback VPN automatique si l'IP maison se fait ban
#   Google Trends       → rotation VPN (Trends tolère mieux les IPs datacenter)
#
# Calibrage : ~400 keywords/nuit = rattrape la croissance (~300 nouveaux/nuit)
# Pacing intégré : 8s AliExpress, 15s TikTok, 10s Trends → ~5-6h pour 400 keywords

set -uo pipefail

ENGINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ENGINE/.venv/bin/python3"
WG_DIR="/etc/wireguard"
LOG="$HOME/tandor-scrape.log"
CRON_HOUR=20
BATCH_SIZE=400        # keywords/nuit — couvre la croissance de l'univers
COOLDOWN_BLOCKED=90   # secondes entre rotations VPN
COOLDOWN_BATCH=10
MAX_ROTATIONS=20

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ── 1. SETUP (une seule fois, nécessite root) ─────────────────────────────────

if [[ ! -x /usr/local/bin/tandor-vpn-up ]]; then
    if [[ $EUID -ne 0 ]]; then
        echo
        echo "  Premier lancement — lance cette commande UNE SEULE FOIS :"
        echo "    sudo bash $ENGINE/tandor_scrape.sh"
        echo
        exit 1
    fi
    log "=== Premier lancement : installation ==="
    bash "$ENGINE/vpn_setup.sh"
    log "=== Installation terminée ==="
fi

# ── 2. CRON (s'auto-ajoute si absent) ────────────────────────────────────────

REAL_USER="${SUDO_USER:-$USER}"
CRON_MARK="tandor_scrape"
if ! crontab -u "$REAL_USER" -l 2>/dev/null | grep -q "$CRON_MARK"; then
    ( crontab -u "$REAL_USER" -l 2>/dev/null
      echo "0 $CRON_HOUR * * * bash $ENGINE/tandor_scrape.sh >> $LOG 2>&1  # $CRON_MARK"
    ) | crontab -u "$REAL_USER" -
    log "Cron ajouté : tous les soirs à ${CRON_HOUR}h"
fi

# ── Helper : rotation VPN pour un target donné (fallback) ────────────────────

run_with_vpn_rotation() {
    local target="$1"
    log "  Fallback VPN pour '$target' — rotation des configs"

    mapfile -t ALL_CONFIGS < <(ls "$WG_DIR"/*.conf 2>/dev/null | shuf)
    # 2 passages sur les 14 configs = 28 slots max
    local CONFIGS=("${ALL_CONFIGS[@]}" "${ALL_CONFIGS[@]}")

    local rotations=0
    local idx=0

    cleanup_vpn() { sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true; }
    trap cleanup_vpn EXIT

    while [[ $rotations -lt $MAX_ROTATIONS ]] && [[ $idx -lt ${#CONFIGS[@]} ]]; do
        local CONF="${CONFIGS[$idx]}"
        local NAME
        NAME=$(basename "$CONF" .conf)
        log "  → VPN $NAME (slot $((rotations+1))/$MAX_ROTATIONS)"

        sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true
        if ! sudo /usr/local/bin/tandor-vpn-up "$CONF" >> "$LOG" 2>&1; then
            log "    ✗ Montage échoué — config suivante"
            ((idx++)) || true
            continue
        fi
        sleep 3

        while true; do
            sudo /usr/local/bin/tandor-vpn-exec-warmer \
                --target "$target" \
                --batch 40 \
                --max-keywords 4000 \
                >> "$LOG" 2>&1
            local ec=$?
            case $ec in
                0) log "  ✓ Cache '$target' complet via VPN"; sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true; return 0 ;;
                2) log "    ⚠ IP $NAME bloquée — rotation dans ${COOLDOWN_BLOCKED}s"; break ;;
                1) sleep $COOLDOWN_BATCH ;;
                *) break ;;
            esac
        done

        sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true
        sleep $COOLDOWN_BLOCKED
        ((rotations++)) || true
        ((idx++)) || true
    done
    log "  Fallback VPN '$target' terminé ($rotations rotations)"
}

# ── 3a. ALIEXPRESS — IP maison, fallback VPN ─────────────────────────────────

log "=== [1/3] AliExpress (IP maison) ==="
"$PY" "$ENGINE/vpn_warmer.py" \
    --target aliexpress \
    --batch "$BATCH_SIZE" \
    --max-keywords 4000 \
    >> "$LOG" 2>&1
ali_exit=$?

if [[ $ali_exit -eq 2 ]]; then
    log "  ⚠ IP maison bannie sur AliExpress → fallback VPN"
    run_with_vpn_rotation "aliexpress"
else
    log "  ✓ AliExpress OK (exit $ali_exit)"
fi

# ── 3b. TIKTOK — IP maison, fallback VPN ─────────────────────────────────────

log "=== [2/3] TikTok (IP maison) ==="
"$PY" "$ENGINE/vpn_warmer.py" \
    --target tiktok \
    --batch "$BATCH_SIZE" \
    --max-keywords 4000 \
    >> "$LOG" 2>&1
tiktok_exit=$?

if [[ $tiktok_exit -eq 2 ]]; then
    log "  ⚠ IP maison bannie sur TikTok → fallback VPN"
    run_with_vpn_rotation "tiktok"
else
    log "  ✓ TikTok OK (exit $tiktok_exit)"
fi

# ── 3c. TRENDS — rotation VPN directe ────────────────────────────────────────

log "=== [3/3] Google Trends (rotation VPN) ==="

mapfile -t ALL_CONFIGS < <(ls "$WG_DIR"/*.conf 2>/dev/null | shuf)
CONFIGS=("${ALL_CONFIGS[@]}" "${ALL_CONFIGS[@]}")

cleanup_final() { sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true; }
trap cleanup_final EXIT

rotations=0
config_idx=0

while [[ $rotations -lt $MAX_ROTATIONS ]] && [[ $config_idx -lt ${#CONFIGS[@]} ]]; do
    CONF="${CONFIGS[$config_idx]}"
    NAME=$(basename "$CONF" .conf)
    log "→ VPN $NAME (slot $((rotations+1))/$MAX_ROTATIONS)"

    sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true
    if ! sudo /usr/local/bin/tandor-vpn-up "$CONF" >> "$LOG" 2>&1; then
        log "  ✗ Montage échoué — config suivante"
        ((config_idx++)) || true
        continue
    fi
    sleep 3

    while true; do
        sudo /usr/local/bin/tandor-vpn-exec-warmer \
            --target trends \
            --batch 40 \
            --max-keywords 4000 \
            >> "$LOG" 2>&1
        ec=$?
        case $ec in
            0) log "✓ Trends complet — terminé"; exit 0 ;;
            2) log "  ⚠ IP $NAME bloquée — cooldown ${COOLDOWN_BLOCKED}s"; break ;;
            1) log "  → Batch suivant dans ${COOLDOWN_BATCH}s"; sleep $COOLDOWN_BATCH ;;
            *) break ;;
        esac
    done

    sudo /usr/local/bin/tandor-vpn-down >> "$LOG" 2>&1 || true
    sleep $COOLDOWN_BLOCKED
    ((rotations++)) || true
    ((config_idx++)) || true
done

log "=== Scraping nuit terminé ($rotations rotations VPN) ==="
