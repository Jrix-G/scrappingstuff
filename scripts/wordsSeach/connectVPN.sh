#!/bin/bash

WG_DIR="/etc/wireguard"
TAILSCALE_IP="100.87.86.58"
GATEWAY=$(ip route | grep default | awk '{print $3}')
IFACE=$(ip route | grep default | awk '{print $5}')

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

add_tailscale_route() {
    ip route add $TAILSCALE_IP/32 via $GATEWAY dev $IFACE 2>/dev/null
}

remove_tailscale_route() {
    ip route del $TAILSCALE_IP/32 via $GATEWAY dev $IFACE 2>/dev/null
}

if [ -n "$current_iface" ]; then
    echo "VPN actif sur interface: $current_iface"
    current_config_file="$WG_DIR/$current_iface.conf"

    new_config=$(choose_random_config "$current_config_file")

    echo "Suppression de la route Tailscale..."
    remove_tailscale_route

    echo "Déconnexion de l'interface actuelle..."
    sudo wg-quick down "$current_iface"

    echo "Connexion avec la config : $new_config"
    sudo wg-quick up "$new_config"

    echo "Ajout de la route Tailscale..."
    add_tailscale_route
else
    echo "Pas de VPN actif, connexion aléatoire."
    new_config=${configs[RANDOM % ${#configs[@]}]}

    sudo wg-quick up "$new_config"
    add_tailscale_route
fi
