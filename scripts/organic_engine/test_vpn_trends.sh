#!/usr/bin/env bash
# Test ponctuel : une IP ProtonVPN gratuite passe-t-elle Google Trends ?
# Usage :  sudo bash test_vpn_trends.sh [config] [mot-clé]
#   ex.    sudo bash test_vpn_trends.sh wg-NL-FREE-79 "beach sandals"
#
# Filet de sécurité : le VPN est coupé automatiquement (trap + minuteur 90s) même
# si le script échoue ou si la session se ferme — la connectivité revient seule.
set -u
CONF="${1:-wg-NL-FREE-79}"
KW="${2:-beach sandals}"
ENGINE="/home/albator/scrappingstuff/scripts/organic_engine"
PY="$ENGINE/.venv/bin/python"

cleanup() { wg-quick down "$CONF" >/dev/null 2>&1; }
trap cleanup EXIT
( sleep 90; cleanup ) &   # garde-fou : coupe le VPN quoi qu'il arrive

ip()     { curl -s --max-time 10 https://api.ipify.org || echo "?"; }
trends() { (cd "$ENGINE" && "$PY" -m collectors.google_trends "$KW"); }

echo "── IP maison        : $(ip)"
echo "── Trends SANS VPN  :"; trends
echo
echo "── Montée VPN ($CONF) ..."
if ! wg-quick up "$CONF" >/dev/null 2>&1; then echo "échec wg-quick up $CONF"; exit 1; fi
sleep 3
echo "── IP via VPN       : $(ip)"
echo "── Trends AVEC VPN  :"; trends
echo
echo "(le VPN va être coupé automatiquement)"
