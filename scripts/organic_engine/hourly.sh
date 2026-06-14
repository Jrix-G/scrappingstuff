#!/usr/bin/env bash
# Job horaire Tandor : refresh étalé de l'univers persistant.
#
# Grâce au garde-fou --refresh-min-age-hours, chaque produit n'est re-photographié
# qu'une fois par ~jour : lancé toutes les heures, ce job répartit le travail sur
# 24h (et ne fait rien quand tout est déjà frais). flock garantit une seule
# instance à la fois — si un run déborde, l'heure suivante est sautée.
set -a; source "$HOME/tandor.env"; set +a
cd "$HOME/scrappingstuff/scripts/organic_engine" || exit 1
source .venv/bin/activate

# -n : ne pas attendre si le verrou est tenu (un refresh tourne déjà) → on saute.
exec flock -n "$HOME/.tandor-refresh.lock" \
    python3 collect_cj.py --refresh --max-refresh 2500 --refresh-min-age-hours 20 \
    >> "$HOME/tandor-hourly.log" 2>&1
