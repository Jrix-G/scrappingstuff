#!/usr/bin/env bash
# vpn_setup.sh — Configuration initiale du namespace VPN Tandor (run ONCE as root)
#
# Ce script installe 3 helpers dans /usr/local/bin/, crée le namespace réseau
# isolé 'tandor-vpn', configure le DNS, et ajoute les permissions sudo minimales
# pour que l'utilisateur albator puisse activer/désactiver le VPN SANS être root.
#
# Usage : sudo bash vpn_setup.sh
#
# Ce que ça fait :
#   1. Installe /usr/local/bin/tandor-vpn-{up,down,exec-warmer}
#   2. Crée le netns 'tandor-vpn' (idempotent)
#   3. Écrit /etc/netns/tandor-vpn/resolv.conf  (DNS Cloudflare par défaut)
#   4. Active le routage IP (ip_forward)
#   5. Ajoute /etc/sudoers.d/tandor-vpn (3 commandes précises, pas de sudo total)
#
# Ce que ça NE fait PAS :
#   - Ne modifie ni daily.sh ni hourly.sh
#   - Ne touche pas au namespace par défaut (trafic CJ non affecté)
#   - Ne démarre pas de VPN (géré à chaque run du warmer)
#
# Ré-exécutable : idempotent, écrase les helpers si besoin.

set -euo pipefail

NETNS="tandor-vpn"
USER_TANDOR="${SUDO_USER:-albator}"
ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_WARMER="$ENGINE_DIR/vpn_warmer.py"
VENV_PY="$ENGINE_DIR/.venv/bin/python3"

echo "=== Tandor VPN Setup ==="
echo "Namespace  : $NETNS"
echo "User       : $USER_TANDOR"
echo "Engine dir : $ENGINE_DIR"
echo

# ── 1. Helper : tandor-vpn-up ───────────────────────────────────────────────
# Crée l'interface WireGuard dans le root namespace, la configure, la déplace
# dans 'tandor-vpn'. Le trafic UDP du tunnel reste dans le root namespace
# (comportement kernel WireGuard) → le CJ dans le root namespace est non affecté.

cat > /usr/local/bin/tandor-vpn-up << 'HELPER_UP'
#!/usr/bin/env bash
# tandor-vpn-up <conf>  — Monte le VPN WireGuard dans le namespace 'tandor-vpn'.
# Doit être exécuté en root (via sudo).
set -euo pipefail

CONF="${1:?Usage: tandor-vpn-up /etc/wireguard/<name>.conf}"
NETNS="tandor-vpn"
WG_IF="wg-tnd"

# Validation : uniquement les configs WireGuard officielles
[[ -f "$CONF" ]] || { echo "Config introuvable : $CONF" >&2; exit 1; }
[[ "$CONF" == /etc/wireguard/*.conf ]] || { echo "Config hors /etc/wireguard/ refusée" >&2; exit 1; }

# Extraire l'adresse IP du client depuis [Interface]
ADDR=$(grep -i '^\s*Address\s*=' "$CONF" | head -1 | sed 's/.*=\s*//' | tr -d ' ' | cut -d',' -f1)
[[ -n "$ADDR" ]] || { echo "Impossible de lire 'Address' dans $CONF" >&2; exit 1; }

# Extraire le DNS (si présent)
DNS_IP=$(grep -i '^\s*DNS\s*=' "$CONF" | head -1 | sed 's/.*=\s*//' | tr -d ' ' | cut -d',' -f1 || true)

# Créer le namespace s'il n'existe pas encore
ip netns add "$NETNS" 2>/dev/null || true
ip netns exec "$NETNS" ip link set lo up 2>/dev/null || true

# Supprimer une interface wg-tnd résiduelle
ip netns exec "$NETNS" ip link del "$WG_IF" 2>/dev/null || true
ip link del "$WG_IF" 2>/dev/null || true

# Créer dans root ns, configurer avec wg-quick strip (= pas les directives spécifiques
# wg-quick comme PostUp/DNS), puis déplacer dans le namespace isolé.
ip link add "$WG_IF" type wireguard
wg setconf "$WG_IF" <(wg-quick strip "$CONF" 2>/dev/null || grep -v '^\s*\(DNS\|MTU\|PreUp\|PostUp\|PreDown\|PostDown\|Table\|Address\|SaveConfig\)' "$CONF")
ip link set "$WG_IF" netns "$NETNS"

# Configurer dans le namespace
ip netns exec "$NETNS" ip addr flush dev "$WG_IF" 2>/dev/null || true
ip netns exec "$NETNS" ip addr add "$ADDR" dev "$WG_IF"
ip netns exec "$NETNS" ip link set "$WG_IF" mtu 1420 up
ip netns exec "$NETNS" ip route replace default dev "$WG_IF"

# DNS dans le namespace
mkdir -p /etc/netns/"$NETNS"
if [[ -n "$DNS_IP" ]]; then
    echo "nameserver $DNS_IP" > /etc/netns/"$NETNS"/resolv.conf
else
    echo "nameserver 1.1.1.1" > /etc/netns/"$NETNS"/resolv.conf
fi

echo "VPN ↑  $(basename "$CONF" .conf)  addr=$ADDR  dns=${DNS_IP:-1.1.1.1}"
HELPER_UP

# ── 2. Helper : tandor-vpn-down ─────────────────────────────────────────────

cat > /usr/local/bin/tandor-vpn-down << 'HELPER_DOWN'
#!/usr/bin/env bash
# tandor-vpn-down — Coupe le VPN WireGuard dans le namespace 'tandor-vpn'.
NETNS="tandor-vpn"
WG_IF="wg-tnd"
ip netns exec "$NETNS" ip link del "$WG_IF" 2>/dev/null && echo "VPN ↓  (ns=$NETNS)" || echo "VPN déjà arrêté"
HELPER_DOWN

# ── 3. Helper : tandor-vpn-exec-warmer ──────────────────────────────────────
# Exécute le warmer Python DANS le namespace 'tandor-vpn', en tant qu'albator.
# Command fixe → sudoers ne laisse passer que ce binaire précis.

cat > /usr/local/bin/tandor-vpn-exec-warmer << HELPER_EXEC
#!/usr/bin/env bash
# tandor-vpn-exec-warmer [args] — Lance vpn_warmer.py dans le namespace VPN.
NETNS="tandor-vpn"
PY="$VENV_PY"
WARMER="$PYTHON_WARMER"
exec ip netns exec "\$NETNS" runuser -u $USER_TANDOR -- "\$PY" "\$WARMER" "\$@"
HELPER_EXEC

chmod 755 /usr/local/bin/tandor-vpn-up
chmod 755 /usr/local/bin/tandor-vpn-down
chmod 755 /usr/local/bin/tandor-vpn-exec-warmer
echo "✓ Helpers installés dans /usr/local/bin/"

# ── 4. Namespace réseau ──────────────────────────────────────────────────────

ip netns add "$NETNS" 2>/dev/null && echo "✓ Namespace '$NETNS' créé" || echo "ℹ  Namespace '$NETNS' existait déjà"
ip netns exec "$NETNS" ip link set lo up 2>/dev/null || true

# DNS par défaut (écrasé par tandor-vpn-up à chaque activation)
mkdir -p /etc/netns/"$NETNS"
echo "nameserver 1.1.1.1" > /etc/netns/"$NETNS"/resolv.conf
echo "✓ DNS namespace → 1.1.1.1"

# ── 5. Routage IP (pour que les paquets WireGuard partent du root namespace) ─

sysctl -w net.ipv4.ip_forward=1 > /dev/null
# Persister au reboot
grep -q 'net.ipv4.ip_forward=1' /etc/sysctl.conf 2>/dev/null || \
    echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
echo "✓ ip_forward activé"

# ── 6. Sudoers : permissions minimales ──────────────────────────────────────
# Seules ces 3 commandes précises peuvent être lancées sans mot de passe.
# Aucun sudo général, aucun accès shell root.

SUDOERS_FILE="/etc/sudoers.d/tandor-vpn"
cat > "$SUDOERS_FILE" << SUDOERS
# Tandor VPN cache-warmer — permissions minimales
# Généré par vpn_setup.sh — ne pas éditer à la main
$USER_TANDOR ALL=(root) NOPASSWD: /usr/local/bin/tandor-vpn-up
$USER_TANDOR ALL=(root) NOPASSWD: /usr/local/bin/tandor-vpn-down
$USER_TANDOR ALL=(root) NOPASSWD: /usr/local/bin/tandor-vpn-exec-warmer
SUDOERS

chmod 440 "$SUDOERS_FILE"
# Valider la syntaxe sudoers
visudo -c -f "$SUDOERS_FILE" && echo "✓ Sudoers validé : $SUDOERS_FILE" || {
    echo "✗ Erreur sudoers — suppression du fichier invalide"
    rm -f "$SUDOERS_FILE"
    exit 1
}

echo
echo "=== Setup terminé ==="
echo "Lance le warmer avec :"
echo "  bash $ENGINE_DIR/vpn_warmer.sh"
echo
echo "Test manuel :"
echo "  sudo /usr/local/bin/tandor-vpn-up /etc/wireguard/<config>.conf"
echo "  sudo ip netns exec tandor-vpn curl -s https://api.ipify.org"
echo "  sudo /usr/local/bin/tandor-vpn-down"
