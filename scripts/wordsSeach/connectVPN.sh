#!/bin/bash
WG_DIR="/etc/wireguard"

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
        echo "${choices[RANDOM % ${#choices[@]}]}"`
    fi
}

if [ -n "$current_iface" ]; then
    echo "VPN actif sur interface: $current_iface"
    sudo wg-quick down "$current_iface"
fi

new_config=${configs[RANDOM % ${#configs[@]}]}
echo "Connexion avec la config : $new_config"
sudo wg-quick up "$new_config"

# 🚀 Fix DNS après connexion
echo -e "nameserver 1.1.1.1\nnameserver 8.8.8.8" | sudo tee /etc/resolv.conf > /dev/null
