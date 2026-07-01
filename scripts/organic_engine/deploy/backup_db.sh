#!/usr/bin/env bash
# Backup SQLite cohérent (API Connection.backup), compressé, tournant, + off-site.
#
# POURQUOI : tout le produit vit sur un seul Pi (cron + SQLite mono-fichier +
# uvicorn) sans aucune sauvegarde. Pi mort = produit mort, données irrécupérables.
# Ce script prend un snapshot ATOMIQUE (sûr même pendant que le runner écrit),
# vérifie son intégrité, le compresse et fait tourner les anciennes copies.
# Gratuit, robuste, restaurable. N'exige PAS le binaire `sqlite3` (absent du Pi) :
# tout passe par le module sqlite3 de Python, comme le reste du pipeline.
#
# INSTALLATION (cron utilisateur) :
#   17 3 * * * /home/albator/scrappingstuff/scripts/organic_engine/deploy/backup_db.sh >> $HOME/tandor-backup.log 2>&1
#
# OFF-SITE (recommandé, gratuit) : configurer un remote rclone chiffré (Backblaze
# B2 a 10 Go gratuits ; cj.db.gz fait quelques Mo) puis décommenter le bloc rclone.
set -euo pipefail

ENGINE="$HOME/scrappingstuff/scripts/organic_engine"
DEST="$HOME/tandor-backups"
mkdir -p "$DEST"
STAMP=$(date +%Y%m%d-%H%M%S)

# Interpréteur : venv du moteur si présent, sinon python3 système.
PY="$ENGINE/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

backup_one() {  # $1 = chemin db ; $2 = label
  local db="$1"
  local label="$2"
  local out="$DEST/${label}-${STAMP}.db"
  [ -f "$db" ] || { echo "skip $db (absent)"; return 0; }
  # Snapshot atomique + integrity_check via l'API sqlite3 de Python.
  "$PY" - "$db" "$out" <<'PYEOF'
import sqlite3, sys
src_path, dst_path = sys.argv[1], sys.argv[2]
src = sqlite3.connect(src_path)
dst = sqlite3.connect(dst_path)
with dst:
    src.backup(dst)              # snapshot cohérent, n'empêche pas les écritures
ok = dst.execute("PRAGMA integrity_check;").fetchone()[0]
src.close(); dst.close()
if ok != "ok":
    sys.exit("integrity_check a échoué: %s" % ok)
PYEOF
  gzip -f "$out"
  echo "OK $label -> ${out}.gz"
}

backup_one "$ENGINE/data/cj.db" cj
backup_one "$HOME/scrappingstuff/backend/data/timeseries.db" timeseries

# Rotation : garde 7 jours de quotidiens + les snapshots du dimanche (hebdo).
find "$DEST" -name 'cj-*.db.gz'         -mtime +7 ! -newermt 'last sunday' -delete 2>/dev/null || true
find "$DEST" -name 'timeseries-*.db.gz' -mtime +7 -delete 2>/dev/null || true

# --- OFF-SITE (décommenter après `rclone config` d'un remote chiffré) ---------
# rclone copy "$DEST" remote-crypt:tandor-db --max-age 25h --transfers 2

echo "Backup terminé ($STAMP)"
