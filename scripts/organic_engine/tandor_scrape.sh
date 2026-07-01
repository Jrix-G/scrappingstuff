#!/usr/bin/env bash
# tandor_scrape.sh — collecte nocturne Tandor (sources gratuites, SANS VPN)
#
# Lancé chaque soir à 20h via cron. VPN abandonné (IPs blacklistées) → tout passe
# par l'IP maison, sur des sources qui la tolèrent en cadence disciplinée.
#
# Pipeline :
#   [1] AliExpress → délégué à ali_single_ip_loop.sh (boucle dédiée, ne rien faire ici)
#   [2] TikTok     → IP maison (m.tiktok.com challenge endpoint) + flush -> tiktok_snapshots
#   [3] Trends     → Google Suggest (autocomplete, suggest_trends) + flush -> suggest_snapshots
#   [4] Ventes     → eBay sold + DHgate sold via sales_loop.sh (single-IP, budget borné)

set -uo pipefail

# ── ANTI-OVERLAP : un seul run à la fois ─────────────────────────────────────
# Deux déclencheurs cron (08h + 20h) pour un script de ~3h → risque de chevauchement.
# Un double scrape simultané = double trafic sortant = risque de ban IP.
# On prend un verrou non bloquant ; si un run tourne déjà, on sort proprement.
LOCKFILE="${TANDOR_SCRAPE_LOCK:-$HOME/.tandor_scrape.lock}"
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] run déjà en cours (verrou $LOCKFILE détenu), abandon" \
        | tee -a "$HOME/tandor-scrape.log"
    exit 0
fi

ENGINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ENGINE/.venv/bin/python3"
LOG="$HOME/tandor-scrape.log"
BATCH_SIZE=400        # mots-clés TikTok/nuit — couvre la croissance de l'univers

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# Notif Discord best-effort : ne casse JAMAIS le scrape (erreurs avalées).
notify() { "$PY" -c "import sys,notify_discord as n; n.send(sys.argv[1]); import time; time.sleep(2)" "$1" 2>/dev/null || true; }

# Compteur de lignes ventes (eBay/DHgate) pour mesurer le delta d'un run.
sales_count() { "$PY" -c "import sqlite3;print(sqlite3.connect('$ENGINE/data/cj.db').execute('SELECT COUNT(*) FROM sales_snapshots').fetchone()[0])" 2>/dev/null || echo 0; }

cd "$ENGINE" || exit 1

# ── [1] ALIEXPRESS — délégué ─────────────────────────────────────────────────
log "=== [1/3] AliExpress → délégué à ali_single_ip_loop.sh (rien ici) ==="

# ── [2] TIKTOK — IP maison ───────────────────────────────────────────────────
# vpn_warmer rend EXIT_MORE_WORK(1) tant qu'il reste des mots-clés non cachés :
# ce n'est PAS une erreur mais le signal « relance-moi ». L'ancien appel unique ne
# traitait qu'1 batch (400/4000) puis sortait en 1 → 90 % de l'univers restait
# périmé (TTL 24 h). On draine donc l'univers par batches jusqu'à EXIT_ALL_DONE(0),
# avec garde-fou (nb de passes) et back-off sur blocage(2). Endpoint
# m.tiktok.com/api/challenge/detail prouvé vivant (HTTP 200, statsV2.viewCount).
log "=== [2/4] TikTok (IP maison) ==="
tk_pass=0
while :; do
    "$PY" "$ENGINE/vpn_warmer.py" \
        --target tiktok \
        --batch "$BATCH_SIZE" \
        --max-keywords 4000 \
        >> "$LOG" 2>&1
    rc=$?
    tk_pass=$((tk_pass + 1))
    case "$rc" in
        0) log "  TikTok terminé : univers à jour (exit 0, $tk_pass passes)"
           notify "🟢 **TikTok OK** — univers à jour ($tk_pass passes, 0 blocage)"; break ;;
        2) log "  TikTok : blocage détecté (exit 2) → back-off 30 min"; sleep 1800 ;;
        *) log "  TikTok : batch $tk_pass fait, reste du travail (exit $rc) → suite"; sleep 5 ;;
    esac
    if [ "$tk_pass" -ge 12 ]; then
        log "  TikTok : garde-fou ${tk_pass} passes atteint — arrêt"; break
    fi
done

# Persistance : déverse le cache .tiktok_cache/ -> tiktok_snapshots (lu par le
# scoring via signals/db_signals). Idempotent (dédupe keyword+observed_at).
tk_flush=$("$PY" "$ENGINE/flush_signals.py" --target tiktok 2>>"$LOG" | grep tiktok_snapshots || true)
log "  flush DB : $tk_flush"

# ── [3] TRENDS — Google Suggest (autocomplete, IP maison, sans VPN) ──────────
# Le collecteur autocomplete (collectors/suggest_trends.py) remplace l'ancien
# google_trends dépendant du VPN. Même drainage par batches que TikTok :
# vpn_warmer --target trends rend 1 (encore du travail) / 0 (fini) / 2 (bloqué).
log "=== [3/4] Trends (Google Suggest, IP maison) ==="
tr_pass=0
while :; do
    "$PY" "$ENGINE/vpn_warmer.py" \
        --target trends \
        --batch "$BATCH_SIZE" \
        --max-keywords 4000 \
        >> "$LOG" 2>&1
    rc=$?
    tr_pass=$((tr_pass + 1))
    case "$rc" in
        0) log "  Trends terminé : univers à jour (exit 0, $tr_pass passes)"
           notify "🟢 **Trends OK** — Suggest à jour ($tr_pass passes, 0 blocage)"; break ;;
        2) log "  Trends : blocage détecté (exit 2) → back-off 30 min"; sleep 1800 ;;
        *) log "  Trends : batch $tr_pass fait, reste du travail (exit $rc) → suite"; sleep 5 ;;
    esac
    if [ "$tr_pass" -ge 12 ]; then
        log "  Trends : garde-fou ${tr_pass} passes atteint — arrêt"; break
    fi
done

# Persistance : déverse .trends_cache/suggest_*.json -> suggest_snapshots.
tr_flush=$("$PY" "$ENGINE/flush_signals.py" --target suggest 2>>"$LOG" | grep suggest_snapshots || true)
log "  flush DB : $tr_flush"

# ── [4] VENTES — eBay + DHgate (single-IP, sans VPN) ─────────────────────────
log "=== [4/4] Ventes secondaires (eBay sold + DHgate sold) ==="
sales_before=$(sales_count)
bash "$ENGINE/sales_loop.sh" >> "$LOG" 2>&1
sales_rc=$?
sales_after=$(sales_count)
sales_delta=$((sales_after - sales_before))
log "  sales_loop terminé (exit $sales_rc) — +$sales_delta lignes ventes (eBay/DHgate)"
if [ "$sales_delta" -gt 0 ]; then
    notify "🟢 **Ventes OK** (eBay sold + DHgate) — **+$sales_delta** mots-clés confirmés ce run"
else
    notify "🔴 **Ventes : 0 ligne** ce run (eBay/DHgate) — à vérifier"
fi

# ── [5] REDDIT — mentions RSS (IP maison, débit borné, reprenable) ───────────
# Couvre progressivement tout l'univers (~8000 mots-clés / 2 shards ≈ 4000/nœud) en
# empilant des snapshots datés dans reddit_snapshots (lu par le scoring). Source RSS
# publique (cache TTL 6 h + intervalle mini + backoff dans reddit_mentions). Budget
# borné par run → ~10 jours pour couvrir le shard. reddit_loop.sh fait sa propre
# sauvegarde DB et écrit dans reddit_snapshots directement (pas de flush séparé).
log "=== [5/5] Reddit (mentions RSS, IP maison) ==="
reddit_before=$("$PY" -c "import sqlite3;print(sqlite3.connect('$ENGINE/data/cj.db').execute('SELECT COUNT(*) FROM reddit_snapshots').fetchone()[0])" 2>/dev/null || echo 0)
bash "$ENGINE/reddit_loop.sh" >> "$LOG" 2>&1
reddit_after=$("$PY" -c "import sqlite3;print(sqlite3.connect('$ENGINE/data/cj.db').execute('SELECT COUNT(*) FROM reddit_snapshots').fetchone()[0])" 2>/dev/null || echo 0)
reddit_delta=$((reddit_after - reddit_before))
log "  reddit_loop terminé — +$reddit_delta snapshots reddit ce run"
notify "🟢 **Reddit OK** — **+$reddit_delta** snapshots de mentions ce run"

log "=== Scraping nuit terminé ==="
notify "✅ **Scraping nuit Tandor terminé** — TikTok + ventes + Reddit à jour"
