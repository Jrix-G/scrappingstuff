#!/usr/bin/env bash
# tandor_scrape.sh — collecte nocturne Tandor (sources gratuites, SANS VPN)
#
# Lancé chaque soir à 20h via cron. VPN abandonné (IPs blacklistées) → tout passe
# par l'IP maison, sur des sources qui la tolèrent en cadence disciplinée.
#
# Pipeline :
#   [1] AliExpress → délégué à ali_single_ip_loop.sh (boucle dédiée, ne rien faire ici)
#   [2] TikTok     → IP maison (m.tiktok.com challenge endpoint)
#   [3] Ventes     → eBay sold + DHgate sold via sales_loop.sh (single-IP, budget borné)
#   [4] Trends     → TODO : collecteur autocomplete à écrire (l'ancien dépendait du VPN)

set -uo pipefail

ENGINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ENGINE/.venv/bin/python3"
LOG="$HOME/tandor-scrape.log"
BATCH_SIZE=400        # mots-clés TikTok/nuit — couvre la croissance de l'univers

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ── [1] ALIEXPRESS — délégué ─────────────────────────────────────────────────
log "=== [1/3] AliExpress → délégué à ali_single_ip_loop.sh (rien ici) ==="

# ── [2] TIKTOK — IP maison ───────────────────────────────────────────────────
log "=== [2/3] TikTok (IP maison) ==="
"$PY" "$ENGINE/vpn_warmer.py" \
    --target tiktok \
    --batch "$BATCH_SIZE" \
    --max-keywords 4000 \
    >> "$LOG" 2>&1
log "  TikTok terminé (exit $?)"

# ── [3] VENTES — eBay + DHgate (single-IP, sans VPN) ─────────────────────────
log "=== [3/3] Ventes secondaires (eBay sold + DHgate sold) ==="
bash "$ENGINE/sales_loop.sh" >> "$LOG" 2>&1
log "  sales_loop terminé (exit $?)"

log "=== Scraping nuit terminé ==="
