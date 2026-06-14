#!/usr/bin/env bash
# Job quotidien Tandor (cron). Charge les creds CJ, active le venv, collecte + rebuild cache.
set -a; source "$HOME/tandor.env"; set +a
cd "$HOME/scrappingstuff/scripts/organic_engine" || exit 1
source .venv/bin/activate
# Nocturne = découverte des nouveautés + enrichissement + rebuild du cache.
# Le refresh de l'univers est désormais étalé sur 24h par hourly.sh (--no-refresh ici).
# --pages 100 : ~5000 nouveaux produits découverts/jour
# --limit 60  : top 60 enrichi Trends/Reddit (heure creuse → anti-429)
python3 run_daily.py --pages 100 --no-refresh --limit 60 >> "$HOME/tandor-daily.log" 2>&1
