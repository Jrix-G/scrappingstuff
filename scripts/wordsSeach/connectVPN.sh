#!/bin/bash
WG_DIR="/etc/wireguard"

# 🔍 IP fixes des sites à scraper
AMAZON_IPS="52.95.120.39,52.95.116.113,54.239.33.91"
ALIEXPRESS_IPS="23.54.143.80"
TRENDS_IPS="142.251.220.238"

ALLOWED="$AMAZON_IPS,$ALIEXPRESS_IPS,$TRENDS_IPS"

echo "✅ AllowedIPs = $ALLOWED"

# 🔧 Mise à jour de tous les .conf WireGuard
for conf in $WG_DIR/*.conf; do
    sudo sed -i "s|^AllowedIPs =.*|AllowedIPs = $ALLOWED|" "$conf"
done

# 🔀 Choix de la config VPN aléatoire
configs=($(ls $WG_DIR/*.conf 2>/dev/null))
if [ ${#configs[@]} -eq 0 ]; then
    echo "Aucun fichier .conf trouvé dans $WG_DIR"
    exit 1
fi

current_iface=$(wg show interfaces 2>/dev/null)

choose_random_config() {
    local current_config=$1
    local choices=()
    for c in "${configs[@]}"; do
        if [ "$c" != "$current_config" ]; then
            choices+=("$c")
        fi
    done
    if [ ${#choices[@]} -eq 0 ]; then
         echo "$current_config"
    else
        echo "${choices[RANDOM % ${#choices[@]}]}"
    fi
}

if [ -n "$current_iface" ]; then
    echo "VPN actif sur interface: $current_iface"
    sudo wg-quick down "$current_iface"
fi

new_config=$(choose_random_config "")
echo "Connexion avec la config : $new_config"
sudo wg-quick up "$new_config"

# 🚀 Fix DNS après connexion
echo -e "nameserver 1.1.1.1\nnameserver 8.8.8.8" | sudo tee /etc/resolv.conf > /dev/null
