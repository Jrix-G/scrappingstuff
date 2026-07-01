#!/usr/bin/env python3
"""Worker AliExpress « burst + extraction-max », pensé pour la rotation d'IP.

Pourquoi ce worker
------------------
L'ancien chemin (``demand_runner`` → ``aliexpress_orders.fetch_demand``) faisait
1 mot-clé = 1 requête = 1 résumé, espacé de 5,5 min. C'est doublement absurde :
* le blocage AliExpress est un état **par IP** (~3-4 requêtes propres puis page
  « punish » ~30 min), PAS un débit — espacer les requêtes n'évite rien ;
* chaque page rend ~60 produits structurés (titre, ventes, prix, note) : on en
  jetait 59.

Ce worker fait l'inverse, comme un bon ingénieur le ferait :
1. **Burst** : il tire le budget de l'IP courante le plus vite possible (pas de
   pacing lent intra-IP — inutile).
2. **Extraction-max** : chaque réponse passe par ``ali_page_parser`` → 60 lignes
   produit + un agrégat ventes attribué au mot-clé de la page.
3. **Persistance en masse** : tout est écrit dans ``sales_snapshots`` (+ une table
   produits fine optionnelle) via le même chemin que le runner.
4. **Rotation d'IP** : à la 1re page « punish », il rend la main avec le code de
   sortie 2 — le harnais ``tandor_scrape.sh`` (qui a DÉJÀ le sudo NOPASSWD sur
   ``tandor-vpn-up/-down``) bascule alors d'IP et le relance. Aucun root requis
   DANS ce process : il dégrade proprement sur l'IP maison sans Playwright.

Contrat de sortie (identique à vpn_warmer.py, donc compatible tandor_scrape.sh) :
  0  — plus rien à faire (tous les mots-clés du scope sont frais)
  1  — batch traité, il reste du travail (la shell relancera un batch)
  2  — IP bloquée (page punish) : rotation d'IP demandée

Chemins de récupération, par ordre de préférence :
  A. AliCookiePool (Playwright→x5sec + curl_cffi)  — si playwright installé
  B. curl_cffi nu (impersonate chrome131)          — marche tant que l'IP est propre
  C. urllib (collectors.aliexpress_orders)          — dernier recours

Usage :
  python3 ali_burst_worker.py --budget 4 --batch 40 --max-keywords 4000
  (dans le netns VPN : sudo /usr/local/bin/tandor-vpn-exec-... — voir plan)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

import notify_discord as notify  # noqa: E402
from collectors.ali_page_parser import parse_page, page_to_demand, is_blocked  # noqa: E402

# Régulateur de cadence AIMD par IP (best-effort : jamais bloquant pour le worker).
try:
    import ali_pacer  # noqa: E402
except Exception:  # pragma: no cover — le collecteur doit tourner sans le pacer
    ali_pacer = None

EXIT_ALL_DONE = 0
EXIT_MORE_WORK = 1
EXIT_BLOCKED = 2

# Chaque mot-clé Ali traité ici est DÉJÀ un top-vélocité Amazon (file aliexpress_queue) :
# la notif sert de CONFIRMATION par produit. Volume faible (IP maison, ~3-4 req/IP),
# donc pas de digest nécessaire — seuil modeste pour taire les pages sans vraie traction.
ALI_HOT_THRESHOLD = 1000  # max_sold AliExpress min pour notifier une confirmation

DB = ENGINE / "data" / "cj.db"
CACHE_DIR = ENGINE / ".aliexpress_cache"

# ─── Détection d'anomalie de blocage (anti-spam Discord) ─────────────────────
# Un PUNISH AliExpress est NOMINAL : le blocage est par IP (~1-4 req propres puis
# cooldown ~35 min). Notifier à chaque PUNISH = ~35 notifs/jour de bruit. On ne
# veut alerter QUE sur une anomalie = scraping probablement HS. Comme chaque
# invocation du worker est éphémère (relancée par ali_single_ip_loop.sh), un
# compteur en mémoire ne survit pas : on persiste un petit état JSON entre runs.
BLOCK_STATE_FILE = ENGINE / ".ali_block_state.json"
# Seuil : N PUNISH consécutifs SANS aucun succès intercalé → anomalie probable.
# 10 d'affilée est bien au-delà du rate-limit normal (1-4/IP, succès fréquents).
ALI_BLOCK_STREAK_ALERT = 10
# Anti-flood : au plus 1 alerte d'anomalie par cette fenêtre (secondes).
ALI_BLOCK_ALERT_COOLDOWN = 3600  # 1 h

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _search_url(keyword: str) -> str:
    return "https://www.aliexpress.com/af/" + urllib.parse.quote(keyword) + ".html"


# ─── Sélection des mots-clés à tirer ────────────────────────────────────────

def _select_keywords(c: sqlite3.Connection, limit: int) -> list[str]:
    """Mots-clés AliExpress à confirmer en priorité.

    1. La file ``aliexpress_queue`` (top vélocité Amazon, jamais confirmés ou
       confirmation due > 24 h) — c'est le signal le plus précieux.
    2. Complétée, si la file est courte, par les mots-clés Amazon les plus
       couvrants encore sans snapshot ventes.
    """
    out: list[str] = []
    seen: set[str] = set()
    try:
        rows = c.execute(
            "SELECT keyword, last_scraped FROM aliexpress_queue ORDER BY priority DESC"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    from datetime import datetime, timezone
    from shard import in_shard  # partition multi-nœuds : ne confirmer que SON shard
    now = datetime.now(timezone.utc)
    for kw, last in rows:
        if kw in seen or not in_shard(kw):
            continue
        if last is None:
            out.append(kw); seen.add(kw)
        else:
            try:
                age_h = (now - datetime.fromisoformat(last)).total_seconds() / 3600
            except Exception:
                age_h = 1e9
            if age_h >= 24:
                out.append(kw); seen.add(kw)
        if len(out) >= limit:
            return out
    # Complément : mots-clés Amazon couvrants sans confirmation Ali.
    try:
        extra = c.execute(
            "SELECT keyword FROM amazon_queue ORDER BY n_products DESC LIMIT ?",
            (limit * 3,),
        ).fetchall()
    except sqlite3.OperationalError:
        extra = []
    for (kw,) in extra:
        if kw not in seen and in_shard(kw):
            out.append(kw); seen.add(kw)
        if len(out) >= limit:
            break
    return out[:limit]


# ─── Récupérateur (3 chemins, dégradation propre) ───────────────────────────

class Fetcher:
    """Encapsule le meilleur chemin disponible. fetch(url) -> (blocked, html)."""

    def __init__(self) -> None:
        self.kind = "none"
        self._pool = None
        self._sess = None
        self._loop = None
        # A. Cookie pool (Playwright + curl_cffi)
        try:
            from collectors.ali_cookie_pool import AliCookiePool, _HAS_PLAYWRIGHT, _HAS_CURL
            if _HAS_PLAYWRIGHT and _HAS_CURL:
                self._pool = AliCookiePool(n_sessions=1)
                import asyncio
                self._loop = asyncio.new_event_loop()
                self.kind = "cookiepool"
                return
        except Exception:
            pass
        # B. curl_cffi nu
        try:
            from curl_cffi import requests as creq
            self._sess = creq.Session(impersonate="chrome131")
            self._sess.headers.update({
                "accept-language": "en-US,en;q=0.9",
                "referer": "https://www.aliexpress.com/",
                "user-agent": _UA,
            })
            self.kind = "curl"
            return
        except Exception:
            pass
        # C. urllib (collecteur legacy)
        self.kind = "urllib"

    def fetch(self, url: str) -> tuple[bool, str]:
        if self.kind == "cookiepool":
            return self._loop.run_until_complete(self._pool.fetch(url))
        if self.kind == "curl":
            try:
                r = self._sess.get(url, timeout=25)
                return is_blocked(r.text), r.text
            except Exception:
                return True, ""
        # urllib
        try:
            from collectors.aliexpress_orders import _fetch_html, AliExpressBlocked
            try:
                return False, _fetch_html(url.split("/af/")[-1].rsplit(".html", 1)[0])
            except AliExpressBlocked:
                return True, ""
        except Exception:
            return True, ""

    def close(self) -> None:
        if self._loop is not None:
            try:
                self._loop.close()
            except Exception:
                pass


# ─── Persistance en masse ───────────────────────────────────────────────────

def _ensure_tables(c: sqlite3.Connection) -> None:
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS sales_snapshots (
            keyword TEXT, observed_at TEXT, max_sold INTEGER,
            median_sold INTEGER, listings INTEGER,
            PRIMARY KEY (keyword, observed_at)
        );
        CREATE TABLE IF NOT EXISTS ali_products (
            product_id TEXT, observed_at TEXT, keyword TEXT,
            title TEXT, sold INTEGER, price_cents INTEGER, star_rating REAL,
            PRIMARY KEY (product_id, observed_at)
        );
        CREATE INDEX IF NOT EXISTS idx_aliprod_kw ON ali_products(keyword);
        """
    )
    c.commit()


def _persist_page(c: sqlite3.Connection, keyword: str, page, observed_at: str) -> int:
    """Écrit l'agrégat ventes (sales_snapshots) + tous les produits (ali_products).
    Retourne le nombre de produits écrits."""
    d = page_to_demand(page, keyword=keyword)
    if not d.blocked and (d.max_sold or 0) > 0:
        c.execute(
            "INSERT OR IGNORE INTO sales_snapshots(keyword, observed_at, max_sold, "
            "median_sold, listings) VALUES(?,?,?,?,?)",
            (keyword, observed_at, d.max_sold or 0, d.median_sold or 0,
             d.n_results or d.listings_with_sales),
        )
    # Met à jour la file Ali si la ligne existe (last_scraped + compteur).
    c.execute(
        "UPDATE aliexpress_queue SET last_scraped=?, scrape_count=scrape_count+1 "
        "WHERE keyword=?",
        (observed_at, keyword),
    )
    n = 0
    for p in page.products:
        c.execute(
            "INSERT OR IGNORE INTO ali_products(product_id, observed_at, keyword, "
            "title, sold, price_cents, star_rating) VALUES(?,?,?,?,?,?,?)",
            (p.product_id, observed_at, keyword, p.title, p.sold,
             p.price_cents, p.star_rating),
        )
        n += 1
    return n


def _cache_write(keyword: str, html: str) -> None:
    """Alimente aussi .aliexpress_cache (clé compatible aliexpress_orders)."""
    try:
        import hashlib
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = CACHE_DIR / f"{hashlib.sha256(keyword.encode()).hexdigest()[:20]}.html"
        path.write_text(html)
    except Exception:
        pass


# ─── État de blocage persistant (anti-spam Discord) ──────────────────────────

def _load_block_state() -> dict:
    """Lit l'état persistant : {streak: int, last_alert_ts: float}.
    Tolérant : tout problème → état neutre (pas de crash du worker)."""
    try:
        d = json.loads(BLOCK_STATE_FILE.read_text())
        return {
            "streak": int(d.get("streak", 0)),
            "last_alert_ts": float(d.get("last_alert_ts", 0.0)),
        }
    except Exception:
        return {"streak": 0, "last_alert_ts": 0.0}


def _save_block_state(state: dict) -> None:
    """Persiste l'état (best-effort, jamais bloquant)."""
    try:
        BLOCK_STATE_FILE.write_text(json.dumps(state))
    except Exception:
        pass


def _on_punish(dry_run: bool) -> None:
    """À chaque PUNISH : incrémente le streak consécutif et n'alerte Discord QUE
    si l'anomalie est franchie (≥ ALI_BLOCK_STREAK_ALERT d'affilée) et que le
    cooldown anti-flood est respecté. Le PUNISH isolé reste silencieux (nominal)."""
    if dry_run:
        return
    state = _load_block_state()
    state["streak"] += 1
    now = time.time()
    if (state["streak"] >= ALI_BLOCK_STREAK_ALERT
            and now - state["last_alert_ts"] >= ALI_BLOCK_ALERT_COOLDOWN):
        notify.send(
            f"⚠️ **AliExpress scraping possiblement HS** — "
            f"{state['streak']} blocages (PUNISH) consécutifs sans aucun succès. "
            f"Le rate-limit normal n'excède jamais quelques req/IP : "
            f"vérifier le worker / la rotation d'IP."
        )
        state["last_alert_ts"] = now
    _save_block_state(state)


def _on_success(dry_run: bool) -> None:
    """Un succès prouve que le scraping fonctionne → reset du streak consécutif."""
    if dry_run:
        return
    state = _load_block_state()
    if state["streak"] != 0:
        state["streak"] = 0
        _save_block_state(state)


def _pace(dry_run: bool, outcome: str) -> None:
    """Nourrit le régulateur AIMD (ali_pacer) avec le résultat de chaque requête.
    Best-effort : toute erreur est avalée (le pacer ne doit jamais casser la
    collecte). En dry_run on n'écrit pas l'état de cadence."""
    if dry_run or ali_pacer is None:
        return
    try:
        ali_pacer.observe(None, outcome)  # ip = TANDOR_PACER_IP ou "self"
    except Exception:
        pass


# ─── Boucle burst ───────────────────────────────────────────────────────────

def run(budget: int, batch: int, max_keywords: int, dry_run: bool) -> int:
    if not DB.exists():
        print(f"[burst] cj.db introuvable : {DB}", flush=True)
        return EXIT_ALL_DONE
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    _ensure_tables(c)

    keywords = _select_keywords(c, max(batch, budget))
    if not keywords:
        print("[burst] Aucun mot-clé Ali à confirmer — terminé.", flush=True)
        return EXIT_ALL_DONE
    targets = keywords[:budget]
    print(f"[burst] Budget IP={budget} · {len(targets)} mots-clés en rafale : "
          f"{targets}", flush=True)

    fetcher = Fetcher()
    print(f"[burst] Récupérateur : {fetcher.kind}", flush=True)

    fired = total_products = total_signals = 0
    blocked_hit = False
    for kw in targets:
        url = _search_url(kw)
        t0 = time.time()
        blocked, html = fetcher.fetch(url)
        dt = time.time() - t0
        fired += 1
        if blocked or is_blocked(html):
            print(f"[burst] ✗ « {kw} » → PUNISH ({len(html)}o, {dt:.1f}s) "
                  f"— IP épuisée après {fired} req", flush=True)
            # PUNISH nominal : on NE notifie PAS à chaque fois (rate-limit attendu).
            # _on_punish n'alerte Discord que sur une vraie anomalie (streak élevé).
            _on_punish(dry_run)
            _pace(dry_run, "punish")   # AIMD : recul multiplicatif (interval↑, cooldown↑)
            blocked_hit = True
            break
        # Succès : le scraping fonctionne → on remet à zéro le streak de blocage.
        _on_success(dry_run)
        _pace(dry_run, "success")      # AIMD : accélération additive (interval↓)
        page = parse_page(html, keyword=kw)
        d = page_to_demand(page, keyword=kw)
        observed = _now()
        if dry_run:
            n = len(page.products)
        else:
            n = _persist_page(c, kw, page, observed)
            _cache_write(kw, html)
        total_products += n
        total_signals += len(page.sold_values)
        flag = " 🟢" if (d.max_sold or 0) >= ALI_HOT_THRESHOLD else ""
        print(f"[burst] ✓ « {kw} » → {n} produits, max={d.max_sold} "
              f"med={d.median_sold} total={d.n_results} ({dt:.1f}s){flag}", flush=True)
        if not dry_run and (d.max_sold or 0) >= ALI_HOT_THRESHOLD:
            notify.ali_scraped(kw, d.max_sold, d.median_sold or 0,
                               d.n_results or d.listings_with_sales)
    if not dry_run:
        c.commit()
    fetcher.close()
    c.close()

    print(f"[burst] Rafale terminée : {fired} req · {total_products} produits · "
          f"{total_signals} signaux ventes persistés", flush=True)
    if blocked_hit:
        return EXIT_BLOCKED          # → tandor_scrape.sh tourne d'IP
    remaining = len(keywords) - len(targets)
    return EXIT_MORE_WORK if remaining > 0 else EXIT_ALL_DONE


def main() -> int:
    ap = argparse.ArgumentParser(description="AliExpress burst+extraction-max worker")
    ap.add_argument("--budget", type=int, default=4,
                    help="Requêtes en rafale avant rotation d'IP (~3-4 propres/IP)")
    ap.add_argument("--batch", type=int, default=40,
                    help="Taille du scope considéré par run")
    ap.add_argument("--max-keywords", type=int, default=4000)
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse et compte sans écrire en base ni cache")
    args = ap.parse_args()
    return run(args.budget, args.batch, args.max_keywords, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
