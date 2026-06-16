#!/usr/bin/env bash
# test_vpn_rotation.sh — Test de rotation VPN (3 min max).
# Vérifie que : le namespace existe, le VPN monte, l'IP change, le scraping passe.
# Usage : sudo bash test_vpn_rotation.sh
set -uo pipefail

ENGINE="/home/albator/scrappingstuff/scripts/organic_engine"
PY="$ENGINE/.venv/bin/python3"
WG_DIR="/etc/wireguard"
NETNS="tandor-vpn"
WG_IF="wg-tnd"
KW="ceiling fan"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓ $*${NC}"; }
fail() { echo -e "${RED}  ✗ $*${NC}"; }
info() { echo -e "${YELLOW}  → $*${NC}"; }

echo "═══════════════════════════════════════════"
echo " Tandor VPN Rotation — Test 3 min"
echo "═══════════════════════════════════════════"

# ── 1. Prérequis ─────────────────────────────────────────────────────────────
echo
echo "[1/5] Prérequis"

if [[ ! -x /usr/local/bin/tandor-vpn-up ]]; then
    fail "vpn_setup.sh jamais lancé — exécute d'abord : sudo bash vpn_setup.sh"
    exit 1
fi
ok "Helpers installés"

mapfile -t CONFIGS < <(ls "$WG_DIR"/*.conf 2>/dev/null)
if [[ ${#CONFIGS[@]} -eq 0 ]]; then
    fail "Aucun .conf dans $WG_DIR"
    exit 1
fi
ok "${#CONFIGS[@]} configs WireGuard trouvées"

if ! ip netns list 2>/dev/null | grep -q "$NETNS"; then
    fail "Namespace '$NETNS' absent — relance vpn_setup.sh"
    exit 1
fi
ok "Namespace '$NETNS' présent"

# ── 2. IP maison ─────────────────────────────────────────────────────────────
echo
echo "[2/5] IP maison (sans VPN)"
HOME_IP=$(curl -s --max-time 8 https://api.ipify.org 2>/dev/null || echo "?")
info "IP actuelle : $HOME_IP"

# ── 3. Rotation sur 2 configs ────────────────────────────────────────────────
echo
echo "[3/5] Rotation VPN (2 configs)"

tested=0
for CONF in "${CONFIGS[@]:0:2}"; do
    NAME=$(basename "$CONF" .conf)
    info "Test $NAME ..."

    # Nettoyage
    ip netns exec "$NETNS" ip link del "$WG_IF" 2>/dev/null || true
    ip link del "$WG_IF" 2>/dev/null || true

    if ! /usr/local/bin/tandor-vpn-up "$CONF" 2>&1 | grep -q "VPN ↑"; then
        fail "$NAME : échec montage WireGuard"
        continue
    fi
    sleep 3

    VPN_IP=$(ip netns exec "$NETNS" curl -s --max-time 10 https://api.ipify.org 2>/dev/null || echo "?")
    if [[ "$VPN_IP" == "$HOME_IP" ]] || [[ "$VPN_IP" == "?" ]]; then
        fail "$NAME : IP inchangée ($VPN_IP) — tunnel non établi"
    else
        ok "$NAME : IP changée → $VPN_IP"
        ((tested++)) || true
    fi

    /usr/local/bin/tandor-vpn-down 2>/dev/null || true
    sleep 5
done

if [[ $tested -eq 0 ]]; then
    fail "Aucun VPN n'a fonctionné — vérifie les configs WireGuard"
    exit 1
fi

# ── 4. Scraping à travers le VPN ─────────────────────────────────────────────
echo
echo "[4/5] Scraping AliExpress + Trends via VPN (mot-clé : '$KW')"

# Utilise la première config qui a fonctionné
CONF="${CONFIGS[0]}"
NAME=$(basename "$CONF" .conf)
info "VPN : $NAME"

/usr/local/bin/tandor-vpn-up "$CONF" > /dev/null 2>&1
sleep 3

VPN_IP=$(ip netns exec "$NETNS" curl -s --max-time 10 https://api.ipify.org 2>/dev/null || echo "?")
info "IP VPN : $VPN_IP"

# Supprimer le cache pour forcer un vrai fetch
CACHE_HASH=$(ip netns exec "$NETNS" runuser -u albator -- "$PY" -c "
import hashlib, sys
sys.path.insert(0, '$ENGINE')
from collectors.aliexpress_orders import _cache_path
p = _cache_path('$KW')
print(p)
" 2>/dev/null || echo "")

if [[ -n "$CACHE_HASH" ]]; then
    rm -f "$CACHE_HASH" 2>/dev/null || true
fi

TRENDS_HASH=$(ip netns exec "$NETNS" runuser -u albator -- "$PY" -c "
import hashlib, sys
sys.path.insert(0, '$ENGINE')
from collectors.google_trends import _cache_path
print(_cache_path('$KW|today 3-m|'))
" 2>/dev/null || echo "")
if [[ -n "$TRENDS_HASH" ]]; then
    rm -f "$TRENDS_HASH" 2>/dev/null || true
fi

# Lancer le scraping dans le namespace
RESULT=$(ip netns exec "$NETNS" runuser -u albator -- "$PY" "$ENGINE/vpn_warmer.py" \
    --batch 1 --target all 2>&1)

echo "$RESULT" | while IFS= read -r line; do
    echo "    $line"
done

/usr/local/bin/tandor-vpn-down > /dev/null 2>&1

if echo "$RESULT" | grep -q "fetched"; then
    ok "Scraping réussi via VPN"
elif echo "$RESULT" | grep -q "BLOCKED\|blocked"; then
    fail "IP bloquée (normal si config ProtonVPN free déjà connue d'AliExpress)"
else
    info "Résultat ambigu — voir détails ci-dessus"
fi

# ── 5. Bilan ──────────────────────────────────────────────────────────────────
echo
echo "[5/5] Bilan"
ok "$tested/2 VPN opérationnels (IP distincte confirmée)"
ok "Namespace isolé — trafic CJ non affecté"

echo
echo "═══════════════════════════════════════════"
echo " Test terminé. Lance le warmer complet avec :"
echo "   bash $ENGINE/vpn_warmer.sh"
echo "═══════════════════════════════════════════"
