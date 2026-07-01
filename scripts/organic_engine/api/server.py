"""API de production servie depuis le Raspberry Pi.

Sert le cache produit (`data/dashboard_export.json`) régénéré chaque jour par
`run_daily.py`. Aucun appel réseau par requête : tout le travail lourd
(Trends/Reddit) est fait une fois par jour côté cron. L'API ne fait que lire,
filtrer et renvoyer — donc instantanée, même sur un Pi.

Lancement :
    uvicorn api.server:app --host 0.0.0.0 --port 8000
    # depuis le dossier scripts/organic_engine/

CORS : autorise le front local (CRA, port 3000) par défaut ; surcharge possible
via la variable d'env TANDOR_CORS_ORIGINS (liste séparée par des virgules, ou *).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.auth import require_user, plan_for, charge_quota, VALIDATE_COST
from api import alerts as alerts_mod

# Rend les modules organic_engine importables depuis api/server.py
_ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "dashboard_export.json"
CJ_DB = ROOT / "data" / "cj.db"


# ---------------------------------------------------------------------------
# Endpoint /api/validate — helpers
# ---------------------------------------------------------------------------

def _keyword_from_query(query: str) -> str:
    """Extrait un mot-clé propre depuis une URL produit ou un nom libre."""
    q = query.strip()
    if q.startswith("http"):
        parsed = urllib.parse.urlparse(q)
        # Amazon : /Produit-Titre/dp/ASIN → prendre le slug avant /dp/
        path = parsed.path
        if "/dp/" in path:
            slug = path.split("/dp/")[0].strip("/").split("/")
            slug = [s for s in slug if s]
            if slug:
                return slug[-1].replace("-", " ").strip()
        # Fallback param k= (recherche Amazon)
        qs = urllib.parse.parse_qs(parsed.query)
        for param in ("k", "q", "SearchText", "search"):
            if param in qs:
                return qs[param][0]
        # Dernier recours : nettoyer le path
        return parsed.path.strip("/").replace("-", " ").replace("/", " ")[:80]
    return q


def _cj_search(keyword: str) -> dict | None:
    """Cherche la meilleure correspondance CJ en DB locale (dégradation si absente)."""
    if not CJ_DB.exists():
        return None
    words = [w for w in re.sub(r"[^\w\s]", " ", keyword.lower()).split() if len(w) > 2]
    if not words:
        return None
    # Essaie des patterns de plus en plus larges
    patterns = [
        "%" + "%".join(words[:3]) + "%",
        "%" + words[0] + "%" + (words[1] + "%" if len(words) > 1 else ""),
        "%" + words[0] + "%",
    ]
    try:
        conn = sqlite3.connect(CJ_DB, timeout=5)
        conn.row_factory = sqlite3.Row
        for pat in patterns:
            rows = conn.execute("""
                SELECT p.pid, p.name, p.category, p.image, p.create_time,
                       s.price, s.listed_num, d.suggest_price
                FROM cj_products p
                LEFT JOIN cj_snapshots s ON s.pid = p.pid
                    AND s.observed_at = (
                        SELECT MAX(observed_at) FROM cj_snapshots WHERE pid = p.pid
                    )
                LEFT JOIN cj_details d ON d.pid = p.pid
                WHERE lower(p.name) LIKE ?
                ORDER BY coalesce(s.listed_num, 0) DESC
                LIMIT 10
            """, (pat,)).fetchall()
            if rows:
                # Choisir la ligne avec le plus de mots-clés dans le nom
                best = max(rows, key=lambda r: sum(
                    1 for w in words if w in (r["name"] or "").lower()
                ))
                conn.close()
                return dict(best)
        conn.close()
    except Exception:
        pass
    return None


def _age_days(create_time: str | None) -> float | None:
    if not create_time:
        return None
    try:
        ts = int(create_time) / 1000          # epoch ms → s
        age = (time.time() - ts) / 86400
        return age if 0 < age < 36500 else None
    except (ValueError, TypeError):
        pass
    try:
        dt = datetime.fromisoformat(str(create_time).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - dt).days
        return float(age) if age >= 0 else None
    except Exception:
        return None


def _run_with_timeout(fn, timeout: float, *args, **kwargs):
    """Exécute fn(*args, **kwargs) dans un thread ; retourne None si timeout."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn, *args, **kwargs)
        try:
            return fut.result(timeout=timeout)
        except (FuturesTimeout, Exception):
            return None


class ValidateRequest(BaseModel):
    query: str                    # URL Amazon/AliExpress ou nom produit
    geo: str = ""                 # code pays Trends (ex. "FR"), vide = monde

_DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def _load_cache() -> dict[str, Any]:
    """Relit le cache à chaque appel (fichier petit) → export quotidien pris en compte à chaud."""
    if not CACHE.exists():
        raise HTTPException(
            status_code=503,
            detail="Cache produit absent. Lance `python3 run_daily.py` (ou export_dashboard.py).",
        )
    try:
        return json.loads(CACHE.read_text())
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - I/O
        raise HTTPException(status_code=500, detail=f"Cache illisible : {exc}")


# ---------------------------------------------------------------------------
# Catalogue complet (cj.db) — produits NON enrichis, paginés en SQL
# ---------------------------------------------------------------------------
#
# Le cache JSON ne contient que le top ~60 produits enrichis (Trends/Reddit/
# vélocité). Le reste du catalogue (~6100 lignes) vit dans cj.db. On le sert à la
# demande, page par page (LIMIT/OFFSET), en calculant un score « léger » par ligne
# via les fonctions PURES (aucun réseau) score_sellability + assess_loss_risk.
# Cela garde la même forme de produit que le cache, donc le front n'a rien de
# spécial à gérer pour ces produits — ils n'ont simplement pas d'historique réel
# ni de score organique (organic=0, hasRealHistory=false côté UI).

# Buckets catégorie : repris à l'identique d'export_dashboard.py pour la cohérence
# d'affichage (hue + i18n gérés côté UI).
_CAT_BUCKETS = {
    "WELLNESS": ["massage", "neck", "health", "care", "relief", "posture", "wellness"],
    "HOME": ["home", "storage", "light", "lamp", "decor", "kitchen storage", "cleaning",
             "organizer", "bedside"],
    "TECH": ["phone", "charger", "power", "usb", "electronic", "gadget", "cable", "led",
             "solar", "bluetooth", "printer"],
    "BEAUTY": ["beauty", "hair", "makeup", "skin", "nail", "gua sha", "curl", "cosmetic"],
    "PETS": ["pet", "dog", "cat", "animal"],
    "OUTDOOR": ["outdoor", "camp", "garden", "travel", "hiking", "bottle", "picnic",
                "backpack", "chair", "fishing"],
    "KITCHEN": ["kitchen", "cook", "drink", "cup", "mug", "bottle opener", "spice",
                "cutlery", "coffee"],
    "FITNESS": ["fitness", "gym", "yoga", "training", "sport", "workout", "muscle"],
    "APPAREL": ["shoe", "sock", "cloth", "wear", "dress", "pant", "shirt", "slipper",
                "bag", "lint", "vest", "gown"],
    "BABY": ["baby", "kid", "child", "infant", "bib"],
}


def _map_category(name: str | None, category: str | None) -> str:
    h = f"{name or ''} {category or ''}".lower()
    for bucket, kws in _CAT_BUCKETS.items():
        if any(k in h for k in kws):
            return bucket
    return "HOME"


def _demand_map(conn: sqlite3.Connection, table: str, value_col: str,
                keywords: set[str]) -> dict[str, list[tuple]]:
    """{keyword -> [(observed_at, value), …]} pour une table de snapshots.

    Une SEULE requête ``IN`` pour toute la page (pas de N+1). Lecture DB pure :
    c'est ce qui apporte la demande RÉELLE aux milliers de produits du catalogue
    servis à la volée, sans aucun appel réseau.
    """
    out: dict[str, list[tuple]] = {}
    kws = [k for k in keywords if k]
    if not kws:
        return out
    rows = conn.execute(
        f"SELECT keyword, observed_at, {value_col} FROM {table} "
        f"WHERE keyword IN ({','.join('?' * len(kws))}) AND {value_col} IS NOT NULL "
        f"ORDER BY keyword, observed_at",
        tuple(kws),
    ).fetchall()
    for k, ts, val in rows:
        out.setdefault(k, []).append((ts, val))
    return out


def _level_and_velocity(series: list[tuple]) -> tuple[Any, Any, Any]:
    """(niveau = dernière valeur, vélocité log/j si ≥2 points, série pour le front)."""
    if not series:
        return None, None, None
    level = series[-1][1]
    velocity = None
    if len(series) >= 2:
        try:
            from signals.timeseries import extract_trend
            t0 = datetime.fromisoformat(series[0][0])
            days = [(datetime.fromisoformat(t) - t0).total_seconds() / 86400.0
                    for t, _ in series]
            vals = [float(v) for _, v in series]
            velocity = round(extract_trend(days, vals).velocity, 5)
        except Exception:
            velocity = None
    return level, velocity, series


def _series_to_block(series: list[tuple] | None) -> dict | None:
    """Série [(observed_at, valeur)] -> bloc { points, dates, days, values } ou None."""
    if not series or len(series) < 2:
        return None
    t0 = datetime.fromisoformat(series[0][0])
    dates = [t for t, _ in series]
    days = [round((datetime.fromisoformat(t) - t0).total_seconds() / 86400.0, 3)
            for t, _ in series]
    vals = [float(v) for _, v in series]
    return {"points": len(series), "dates": dates, "days": days,
            "values": vals, "spanDays": days[-1]}


def _catalogue_total(conn: sqlite3.Connection, exclude_ids: set[str]) -> int:
    """Nombre EXACT de produits du catalogue NON déjà servis par le cache enrichi.

    ``exclude_ids`` = suffixes 7 chiffres des pids déjà enrichis. Plusieurs pids
    peuvent partager le même suffixe : on compte donc précisément, en DB, les
    lignes dont le suffixe est dans ``exclude_ids`` et on les retranche du total.
    """
    total = conn.execute("SELECT COUNT(*) FROM cj_products").fetchone()[0]
    if not exclude_ids:
        return total
    excluded = conn.execute(
        "SELECT COUNT(*) FROM cj_products WHERE substr(pid, -7) IN (%s)"
        % ",".join("?" * len(exclude_ids)),
        tuple(exclude_ids),
    ).fetchone()[0]
    return max(0, total - excluded)


def _catalogue_light(
    conn: sqlite3.Connection,
    exclude_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, sqlite3.Row]]:
    """Scan COMPLET du catalogue cj.db, scoré LÉGER (vendabilité pure, aucun réseau).

    Renvoie ``(descripteurs, rows_by_pid)``. Un descripteur ne porte QUE ce qu'il
    faut pour TRIER (score Tandor) et FILTRER (cat/verdict/trapVerdict/min_score/q/
    phase) sur tout l'univers : id, name, cat, verdict (vendabilité BUY/WATCH/PASS),
    trapVerdict (anti-piège VIABLE/RISKY/TRAP), sellability, organic(=0), phase,
    tandor. Le travail LOURD (demande/déclin RÉELS) est volontairement reporté à la
    seule page renvoyée (cf. :func:`_hydrate_rows`), à partir des lignes brutes
    conservées dans ``rows_by_pid`` — donc sans refaire de requête SQL.

    ``trapVerdict`` est calculé ICI à partir des seuls drapeaux financiers (marge,
    prix, saturation) — assez pour filtrer/trier tout le catalogue. Les drapeaux
    demande/déclin (DB, batchés) ne sont ajoutés qu'à l'hydratation de la page : sur
    la frange de produits qui ont un historique, le trapVerdict AFFICHÉ peut donc
    être plus sévère que celui du filtre. Le gros du catalogue (sans historique) est
    identique des deux côtés.

    Coût mesuré : ~0,32 s pour ~15 k lignes (fetch + sellability + loss_risk pur)
    sur le Pi ; seule la page (≈30) subit ensuite l'hydratation lourde.
    """
    from scoring.sellability import score_sellability
    from scoring.loss_risk import assess_loss_risk

    if exclude_ids:
        placeholders = ",".join("?" * len(exclude_ids))
        where = f"WHERE substr(p.pid, -7) NOT IN ({placeholders})"
        params: tuple = tuple(exclude_ids)
    else:
        where = ""
        params = ()

    rows = conn.execute(
        f"""
        SELECT p.pid, p.name, p.category, p.image, p.create_time,
               s.price, s.listed_num, d.suggest_price
        FROM cj_products p
        LEFT JOIN cj_snapshots s ON s.pid = p.pid
            AND s.observed_at = (
                SELECT MAX(observed_at) FROM cj_snapshots WHERE pid = p.pid
            )
        LEFT JOIN cj_details d ON d.pid = p.pid
        {where}
        """,
        params,
    ).fetchall()

    descriptors: list[dict[str, Any]] = []
    rows_by_pid: dict[str, sqlite3.Row] = {}
    for r in rows:
        pid = r["pid"]
        cost = float(r["price"]) if r["price"] else None
        listed = int(r["listed_num"]) if r["listed_num"] is not None else 0
        age = _age_days(r["create_time"])
        suggest = float(r["suggest_price"]) if r["suggest_price"] else None
        sr = score_sellability(pid, cost, listed, age, retail_override=suggest)
        sell = round(sr.sellability)
        # Verdict anti-piège LÉGER (drapeaux financiers seuls, pas de demande/déclin).
        loss = assess_loss_risk(
            pid,
            net_after_cpa_eur=sr.net_after_cpa_eur,
            gross_margin_eur=sr.gross_margin_eur,
            pct_low_rating=None,
            listed_num=listed,
            retail_eur=sr.retail_eur,
        )
        rows_by_pid[pid] = r
        descriptors.append({
            "id": pid,                              # pid COMPLET (cf. _hydrate_rows)
            "name": r["name"],
            "cat": _map_category(r["name"], r["category"]),
            "verdict": sr.verdict,
            "trapVerdict": loss.verdict,            # VIABLE / RISKY / TRAP
            "sellability": sell,
            "organic": 0,                           # pas de signal organique réel
            "phase": "EMERGENT",
            # Score Tandor LÉGER : organic=0 sur le catalogue brut -> 0.45*sellability.
            "tandor": 0.45 * sell,
        })
    return descriptors, rows_by_pid


# ---------------------------------------------------------------------------
# Cache mémoire du catalogue léger (scan COMPLET cj.db, scoré pur)
# ---------------------------------------------------------------------------
#
# `_catalogue_light()` coûte ~0,7 s (scan de ~15 k lignes + scoring pur) et son
# résultat est IDENTIQUE entre deux requêtes : seuls le filtrage, le tri et la
# pagination changent côté `query_products`. On mémorise donc le scan complet et
# on ne le recalcule que si (a) le TTL expire ou (b) le mtime de cj.db change.
#
# Le scan est mémorisé SANS exclusion (`exclude_ids` vide) : l'exclusion des pids
# déjà enrichis dépend du cache JSON et se fait à la volée, en Python, côté
# `query_products` (comparaison de suffixe). On garde ainsi UN seul scan partagé,
# indépendant du contenu du cache enrichi.

_CATALOGUE_TTL = float(os.environ.get("TANDOR_CATALOGUE_TTL", "300"))  # secondes
_catalogue_lock = threading.Lock()
_catalogue_cache: dict[str, Any] = {
    "key": None,            # (chemin cj.db, mtime) — invalide si le fichier change
    "expires": 0.0,         # horloge monotone d'expiration TTL
    "descriptors": None,    # list[dict] : descripteurs légers (univers complet)
    "rows_by_pid": None,    # dict[str, sqlite3.Row] : lignes brutes pour l'hydratation
}
# Compteur de scans RÉELS de la DB (cache MISS) — instrumenté pour les tests.
_catalogue_builds = 0


def _reset_catalogue_cache() -> None:
    """Vide le cache catalogue (utilisé par les tests pour repartir à froid)."""
    with _catalogue_lock:
        _catalogue_cache.update(key=None, expires=0.0,
                                descriptors=None, rows_by_pid=None)


def _load_catalogue_cached() -> tuple[list[dict[str, Any]], dict[str, sqlite3.Row]]:
    """Renvoie ``(descripteurs, rows_by_pid)`` du catalogue COMPLET, depuis le cache.

    Le scan léger n'est refait que si le cache est froid, expiré (TTL) ou si le
    ``mtime`` de cj.db a changé. Thread-safe (un seul scan à la fois ; les requêtes
    concurrentes attendent le scan en cours puis lisent le cache chaud). Renvoie
    ``([], {})`` proprement si cj.db est absente ou illisible.
    """
    global _catalogue_builds
    if not CJ_DB.exists():
        return [], {}
    try:
        mtime = os.path.getmtime(CJ_DB)
    except OSError:
        return [], {}
    key = (str(CJ_DB), mtime)
    now = time.monotonic()
    with _catalogue_lock:
        if (_catalogue_cache["key"] == key
                and _catalogue_cache["descriptors"] is not None
                and now < _catalogue_cache["expires"]):
            return _catalogue_cache["descriptors"], _catalogue_cache["rows_by_pid"]

        # Cache MISS : scan complet (lecture seule). Réalisé SOUS le verrou afin de
        # ne le faire qu'une fois même sous requêtes parallèles (coût ~0,7 s, et
        # seulement toutes les ~300 s grâce au TTL).
        try:
            conn = sqlite3.connect(f"file:{CJ_DB}?mode=ro", uri=True, timeout=5)
            conn.row_factory = sqlite3.Row
            try:
                descs, rows_by_pid = _catalogue_light(conn, set())
            finally:
                conn.close()
        except sqlite3.Error:
            return [], {}

        _catalogue_builds += 1
        _catalogue_cache.update(
            key=key, expires=time.monotonic() + _CATALOGUE_TTL,
            descriptors=descs, rows_by_pid=rows_by_pid,
        )
        return descs, rows_by_pid


def _catalogue_page(
    conn: sqlite3.Connection,
    exclude_ids: set[str],
    sql_offset: int,
    sql_limit: int,
) -> list[dict[str, Any]]:
    """Lit une page du catalogue cj.db et la met à la forme BASE du dashboard.

    Conservé pour rétro-compat (tri par listed_num desc puis pid). Délègue toute la
    mise en forme à :func:`_hydrate_rows`. ``list_products`` ne l'utilise plus : il
    trie désormais l'univers complet par score Tandor (cf. _catalogue_light).
    """
    if exclude_ids:
        placeholders = ",".join("?" * len(exclude_ids))
        where = f"WHERE substr(p.pid, -7) NOT IN ({placeholders})"
        params: tuple = tuple(exclude_ids) + (sql_limit, sql_offset)
    else:
        where = ""
        params = (sql_limit, sql_offset)

    rows = conn.execute(
        f"""
        SELECT p.pid, p.name, p.category, p.image, p.create_time,
               s.price, s.listed_num, d.suggest_price
        FROM cj_products p
        LEFT JOIN cj_snapshots s ON s.pid = p.pid
            AND s.observed_at = (
                SELECT MAX(observed_at) FROM cj_snapshots WHERE pid = p.pid
            )
        LEFT JOIN cj_details d ON d.pid = p.pid
        {where}
        ORDER BY COALESCE(s.listed_num, 0) DESC, p.pid
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    return _hydrate_rows(conn, rows)


def _hydrate_rows(
    conn: sqlite3.Connection,
    rows: list[sqlite3.Row],
) -> list[dict[str, Any]]:
    """Hydrate des lignes catalogue DÉJÀ lues à la forme BASE du dashboard.

    Travail LOURD par ligne : demande RÉELLE jointe par mot-clé (batchée pour tout
    le lot), détecteur de pièges + déclin (lecture DB pure, aucun réseau). Réservé
    à la SEULE page renvoyée — jamais à l'univers entier — pour rester rapide même
    sur le Pi. ``rows`` provient soit d'une page LIMIT/OFFSET (_catalogue_page),
    soit du scan léger (_catalogue_light), donc l'``id`` rendu = pid COMPLET.
    """
    from scoring.sellability import score_sellability
    from scoring.loss_risk import assess_loss_risk

    if not rows:
        return []

    # Demande RÉELLE par mot-clé (lecture DB pure, batchée pour toute la page).
    # Candidats = mot-clé nettoyé + repli historique (ré-aligne les snapshots
    # indexés avec l'ancienne clé). On joint Amazon (« bought ») et AliExpress.
    try:
        from enrich import keyword_candidates
    except Exception:
        keyword_candidates = lambda n: []  # noqa: E731 - dégradation propre
    row_cands: dict[str, list[str]] = {
        r["pid"]: keyword_candidates(r["name"]) for r in rows
    }
    all_kw: set[str] = {k for cands in row_cands.values() for k in cands}
    amazon_series = _demand_map(conn, "amazon_snapshots", "max_bought", all_kw)
    amazon_median = _demand_map(conn, "amazon_snapshots", "median_bought", all_kw)
    sales_series = _demand_map(conn, "sales_snapshots", "max_sold", all_kw)

    def _pick(series_map: dict[str, list[tuple]], cands: list[str]) -> list[tuple] | None:
        for k in cands:
            if series_map.get(k):
                return series_map[k]
        return None

    out: list[dict[str, Any]] = []
    for r in rows:
        pid = r["pid"]
        cost = float(r["price"]) if r["price"] else None
        listed = int(r["listed_num"]) if r["listed_num"] is not None else 0
        age = _age_days(r["create_time"])
        suggest = float(r["suggest_price"]) if r["suggest_price"] else None

        sr = score_sellability(pid, cost, listed, age, retail_override=suggest)

        # Demande RÉELLE jointe par mot-clé (lecture DB) : niveau + vélocité.
        cands = row_cands.get(pid, [])
        amz_s = _pick(amazon_series, cands)
        amz_m = _pick(amazon_median, cands)
        sales_s = _pick(sales_series, cands)
        amz_level, amz_vel, _ = _level_and_velocity(amz_s)
        amz_med_level = amz_m[-1][1] if amz_m else None
        sale_level, sale_vel, _ = _level_and_velocity(sales_s)

        # Tendance de demande (déclin) -> détecteur de pièges, comme dans l'export.
        # Le garde-fou « < 3 points = inconnu » vit dans assess_loss_risk : aucune
        # conclusion sur série trop courte, donc pas de changement de sémantique.
        dec_velocity = dec_points = dec_vol = dec_se = dec_span = None
        if sales_s and len(sales_s) >= 2:
            try:
                from signals.timeseries import extract_trend
                t0 = datetime.fromisoformat(sales_s[0][0])
                days = [(datetime.fromisoformat(t) - t0).total_seconds() / 86400.0
                        for t, _ in sales_s]
                vals = [float(v) for _, v in sales_s]
                tf = extract_trend(days, vals)
                dec_velocity, dec_points = tf.velocity, tf.n_points
                dec_vol, dec_se, dec_span = tf.volatility, tf.velocity_se, tf.span_days
            except Exception:
                pass

        loss = assess_loss_risk(
            pid,
            net_after_cpa_eur=sr.net_after_cpa_eur,
            gross_margin_eur=sr.gross_margin_eur,
            pct_low_rating=None,
            listed_num=listed,
            retail_eur=sr.retail_eur,
            demand_velocity=dec_velocity,
            demand_points=dec_points or 0,
            demand_volatility=dec_vol,
            demand_velocity_se=dec_se,
            demand_span_days=dec_span,
        )
        has_demand = amz_s is not None or sales_s is not None

        out.append({
            # Le cache enrichi expose un id = 7 derniers chiffres du pid. Pour le
            # catalogue brut on garde le pid COMPLET : il est globalement unique
            # (pas de collision de suffixe entre lignes, ni avec les ids enrichis).
            "id": pid,
            "name": r["name"],
            "cat": _map_category(r["name"], r["category"]),
            "cost": round(sr.cost_eur, 2),
            "retail": round(sr.retail_eur, 2),
            "sellability": round(sr.sellability),
            # Produits non enrichis : pas de signal organique réel (Trends/Reddit).
            "organic": 0,
            "phase": "EMERGENT",
            "verdict": sr.verdict,
            "growth": 0.0,
            "confidence": 0.0,
            "listed": listed,
            "age": round(age) if age is not None else 60,
            "volatility": 0.0,
            "net": round(sr.net_after_cpa_eur, 1),
            "redditScore": 0,
            "trendsScore": 0,
            "salesScore": None,
            "aliExpressSold": sale_level,
            "aliExpressMedianSold": None,
            # Demande Amazon RÉELLE (« bought in past month ») jointe par mot-clé en
            # lecture DB — couvre la majorité du catalogue servi à la volée.
            "amazonBought": amz_level,
            "amazonMedianBought": amz_med_level,
            "amazonVelocity": amz_vel,
            "demandLevel": amz_level if amz_level is not None else sale_level,
            "seasonPeak": 6,
            "seasonMult": 1.0,
            "reason": {"en": sr.reason, "fr": sr.reason},
            "trapVerdict": loss.verdict,
            "trapHeadline": loss.headline,
            "lossFlags": [
                {"name": f.name, "level": f.level, "reason": f.reason}
                for f in loss.flags
            ],
            "breakevenCpa": (round(loss.breakeven_cpa_eur, 1)
                             if loss.breakeven_cpa_eur is not None else None),
            # Courbes RÉELLES de demande (séries snapshotées) jointes par mot-clé.
            # `null` par série tant qu'il n'y a pas ≥2 points.
            "history": {"sales": _series_to_block(sales_s),
                        "amazon": _series_to_block(amz_s)},
            "lastCollection": None,
            "detectedHrs": None,
            "image": r["image"],
            # `enriched`=False (pas de Trends/Reddit live) mais demande DB réelle si dispo.
            "enriched": False,
            "hasRealHistory": has_demand,
            "dossier": {
                "hasDetail": suggest is not None,
                "priceFromCJ": suggest is not None,
                "suggestPrice": suggest,
            },
        })
    return out


app = FastAPI(title="Tandor — Organic Engine API", version="1.0.0")

_origins = os.environ.get("TANDOR_CORS_ORIGINS", _DEFAULT_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _origins.strip() == "*" else [o.strip() for o in _origins.split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/meta")
def meta(user: dict = Depends(require_user)) -> dict[str, Any]:
    """Fraîcheur des données : quand, combien, enrichi ou non."""
    return _load_cache().get("meta", {})


# Plafond navigable DUR : on ne pagine jamais au-delà du top 2000 par score Tandor.
PRODUCTS_CAP = 2000

# Deux dimensions de verdict coexistent et le param ``verdict`` accepte les deux :
#   * vendabilité financière  : BUY / WATCH / PASS         (champ ``verdict``)
#   * anti-piège (le pivot)    : VIABLE / RISKY / TRAP       (champ ``trapVerdict``)
# Le front du dashboard envoie en pratique les valeurs ANTI-PIÈGE (les pastilles).
_SELL_VERDICTS = {"BUY", "WATCH", "PASS"}
_TRAP_VERDICTS = {"VIABLE", "RISKY", "TRAP"}


def _parse_verdict_filter(raw: str | None) -> tuple[set[str], set[str]]:
    """``verdict`` (CSV, insensible à la casse) -> (set vendabilité, set anti-piège).

    La dimension est auto-détectée PAR LA VALEUR : VIABLE/RISKY/TRAP ciblent
    ``trapVerdict`` ; BUY/WATCH/PASS ciblent ``verdict``. On peut mélanger (le match
    est un OU), mais en pratique le front n'envoie qu'un seul jeu. Valeurs inconnues
    ignorées. Renvoie deux sets vides si ``raw`` est vide -> aucun filtre verdict.
    """
    if not raw:
        return set(), set()
    vals = {v.strip().upper() for v in raw.split(",") if v.strip()}
    return vals & _SELL_VERDICTS, vals & _TRAP_VERDICTS


def query_products(
    *,
    cat: str | None = None,
    verdict: str | None = None,
    min_score: float = 0.0,
    q: str | None = None,
    phase: str | None = None,
    sort: str = "tandor",
    limit: int = 30,
    offset: int = 0,
    page: int | None = None,
) -> dict[str, Any]:
    """Logique PURE de /api/products (sans auth/quota) — directement testable.

    TOP 2000 produits par score Tandor décroissant sur L'UNIVERS COMPLET.
    Univers = cache enrichi (~60, Trends/Reddit/vélocité réels) UNION catalogue
    cj.db (~15 k, scoré à la volée par les fonctions PURES, aucun réseau). Tous les
    filtres (cat/verdict/min_score/q/phase) et le tri Tandor s'appliquent à
    L'ENSEMBLE du set — plus seulement à la partie enrichie.

    ``verdict`` accepte une LISTE CSV et auto-détecte la dimension par la valeur :
    VIABLE/RISKY/TRAP filtrent sur ``trapVerdict`` (le pivot anti-piège, calculé
    aussi pour tout le catalogue) ; BUY/WATCH/PASS filtrent sur ``verdict``
    (vendabilité). Insensible à la casse ; match = OU sur les valeurs fournies.

    Stratégie performante :
      1. Scan LÉGER du catalogue (vendabilité pure) : assez pour trier + filtrer.
      2. Fusion avec le cache enrichi, filtres + tri Tandor, plafond dur à 2000.
      3. Hydratation LOURDE (demande RÉELLE, pièges, déclin) de la SEULE page
         renvoyée (≈30 lignes) — verdict + lossFlags portés aussi par le catalogue.

    Pagination : ``page`` (1-indexée) prime sur ``offset`` ; ``page=1`` -> offset 0.
    ``meta.total`` = min(nb correspondants, 2000) ; la pagination ne dépasse jamais
    2000. Rétro-compat : un appel sans ``page``/``offset`` repart de 0.

    Dégradation : si cj.db est absente/illisible, on sert la seule partie enrichie.
    Si le cache est petit (60 aujourd'hui), le catalogue complète jusqu'à 2000.
    """
    import math

    # ``page`` (1-indexée) prime sur ``offset`` ; page=1 -> offset 0.
    if page is not None:
        offset = (page - 1) * limit

    data = _load_cache()
    enriched = data.get("products", [])

    def tandor(p: dict) -> float:
        return 0.55 * p.get("organic", 0) + 0.45 * p.get("sellability", 0)

    ql = q.strip().lower() if q and q.strip() else None
    # Filtre verdict : CSV multi-valeurs + auto-détection de dimension par la valeur.
    sell_filter, trap_filter = _parse_verdict_filter(verdict)
    has_verdict_filter = bool(sell_filter or trap_filter)

    def keep(p_cat: Any, p_verdict: Any, p_trap: Any, p_tandor: float,
             p_name: Any, p_phase: Any) -> bool:
        """Prédicat de filtre commun — appliqué à TOUT l'univers."""
        if cat is not None and p_cat != cat:
            return False
        if has_verdict_filter and not (
            (p_verdict in sell_filter) or (p_trap in trap_filter)
        ):
            return False
        if p_tandor < min_score:
            return False
        if phase is not None and p_phase != phase:
            return False
        if ql is not None and ql not in (p_name or "").lower():
            return False
        return True

    # 1. Partie enrichie (cache) — filtres appliqués. (score, type, payload)
    combined: list[tuple[float, str, dict]] = []
    for p in enriched:
        t = tandor(p)
        if keep(p.get("cat"), p.get("verdict"), p.get("trapVerdict"),
                t, p.get("name"), p.get("phase")):
            combined.append((t, "enriched", p))

    # Le cache ne stocke que l'``id`` = 7 derniers chiffres du pid CJ. On exclut donc
    # du catalogue les pids dont le suffixe correspond à un produit déjà enrichi.
    enriched_ids = {str(p.get("id")) for p in enriched if p.get("id")}

    # 2. Catalogue cj.db — scan LÉGER depuis le CACHE mémoire (mutualisé entre
    #    requêtes ; refait seulement sur TTL/mtime). L'exclusion des pids déjà
    #    enrichis est faite ICI en Python (le scan caché est, lui, sans exclusion).
    descs, rows_by_pid = _load_catalogue_cached()
    for d in descs:
        if str(d["id"])[-7:] in enriched_ids:
            continue
        if keep(d["cat"], d["verdict"], d["trapVerdict"],
                d["tandor"], d["name"], d["phase"]):
            combined.append((d["tandor"], "light", d))

    # 3. Tri global par score Tandor décroissant (id en départage => déterministe).
    combined.sort(key=lambda x: (-x[0], str(x[2].get("id"))))

    # 4. Plafond navigable DUR à 2000, puis tranche de page.
    total = min(len(combined), PRODUCTS_CAP)
    window = combined[:PRODUCTS_CAP]
    page_items = window[offset:offset + limit]

    # 5. Hydratation LOURDE de la SEULE page (lignes catalogue) : demande/pièges/déclin.
    #    Reste PAR REQUÊTE (dépend de la page) : on ouvre une connexion ro éphémère
    #    uniquement s'il y a des lignes catalogue à hydrater. Les ``rows_by_pid`` du
    #    cache sont des lignes déjà fetchées (détachées) : valides hors connexion.
    hydrated: dict[str, dict] = {}
    light_pids = [pl["id"] for _, kind, pl in page_items if kind == "light"]
    if light_pids and CJ_DB.exists():
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(f"file:{CJ_DB}?mode=ro", uri=True, timeout=5)
            conn.row_factory = sqlite3.Row
            page_rows = [rows_by_pid[pid] for pid in light_pids if pid in rows_by_pid]
            hydrated = {rec["id"]: rec for rec in _hydrate_rows(conn, page_rows)}
        except sqlite3.Error:
            hydrated = {}
        finally:
            if conn is not None:
                conn.close()

    out: list[dict[str, Any]] = []
    for _, kind, pl in page_items:
        if kind == "enriched":
            out.append(pl)
        else:
            # Repli sur le descripteur léger si l'hydratation a échoué (DB partie).
            out.append(hydrated.get(pl["id"], pl))

    # 6. Méta de pagination.
    page_size = limit
    page_count = math.ceil(total / page_size) if page_size else 0
    current_page = (offset // page_size) + 1 if page_size else 1
    returned = len(out)
    next_offset = offset + page_size
    has_more = next_offset < total

    meta = dict(data.get("meta", {}))
    meta.update({
        "total": total,
        "page": current_page,
        "page_size": page_size,
        "page_count": page_count,
        "offset": offset,
        "limit": limit,
        "returned": returned,
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
    })

    return {
        "meta": meta,
        "count": returned,
        "total": total,
        "page": current_page,
        "page_count": page_count,
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
        "products": out,
    }


@app.get("/api/products")
def list_products(
    cat: str | None = Query(None, description="Bucket catégorie (HOME, TECH, ...)"),
    verdict: str | None = Query(
        None,
        description="CSV ; VIABLE/RISKY/TRAP -> trapVerdict, BUY/WATCH/PASS -> verdict "
                    "(ex. « VIABLE,RISKY »). Insensible à la casse.",
    ),
    min_score: float = Query(0, ge=0, le=100, description="Score Tandor minimum"),
    q: str | None = Query(None, description="Recherche plein texte (sous-chaîne du nom)"),
    phase: str | None = Query(None, description="Phase (EMERGENT/GROWTH/MATURE/...)"),
    sort: str = Query("tandor", description="Tri (seul « tandor » est implémenté)"),
    limit: int = Query(30, ge=1, le=1000, description="Taille de page (défaut 30)"),
    offset: int = Query(0, ge=0, description="Décalage (ignoré si ``page`` est fourni)"),
    page: int | None = Query(None, ge=1, description="Page 1-indexée (alternative à offset)"),
    user: dict = Depends(require_user),
) -> dict[str, Any]:
    """Route /api/products : auth + quota, puis délègue à :func:`query_products`."""
    charge_quota(user["uid"], plan_for(user))
    return query_products(
        cat=cat, verdict=verdict, min_score=min_score, q=q, phase=phase,
        sort=sort, limit=limit, offset=offset, page=page,
    )


@app.get("/api/product/{product_id}")
def product_detail(product_id: str, user: dict = Depends(require_user)) -> dict[str, Any]:
    """Détail d'un produit par son id (les 7 derniers chiffres du pid CJ)."""
    charge_quota(user["uid"], plan_for(user))
    for p in _load_cache().get("products", []):
        if p.get("id") == product_id:
            return p
    raise HTTPException(status_code=404, detail="Produit inconnu")


@app.get("/api/alerts")
def list_alerts_route(undelivered_only: bool = False,
                      user: dict = Depends(require_user)) -> dict[str, Any]:
    """Alertes courantes, dérivées des signaux RÉELS (déclin, saturation, nouveautés)
    — voir api/alerts.py. Jamais fabriquées : liste vide si aucun signal. Pas de
    quota facturé (lecture légère, pollée par le badge de la cloche)."""
    return {"alerts": alerts_mod.list_alerts(undelivered_only)}


@app.post("/api/checkout")
def create_checkout(body: dict, user: dict = Depends(require_user)) -> dict[str, Any]:
    """Crée une session Stripe Checkout pour un plan payant ('pro' ou 'scale').

    Variables d'env requises : STRIPE_SECRET_KEY, STRIPE_PRICE_PRO, STRIPE_PRICE_SCALE ;
    optionnel : TANDOR_SITE_URL (URL de retour, défaut http://localhost:3000).
    Tant que STRIPE_SECRET_KEY est absent -> 503 propre (aucun crash au démarrage,
    aucun faux paiement). Le front gère le 503 en « bientôt disponible »."""
    import os
    plan = (body or {}).get("plan", "")
    price_env = {"pro": "STRIPE_PRICE_PRO", "scale": "STRIPE_PRICE_SCALE"}.get(plan)
    if not price_env:
        raise HTTPException(400, "Plan inconnu (attendu : 'pro' ou 'scale').")
    secret = os.environ.get("STRIPE_SECRET_KEY")
    if not secret:
        raise HTTPException(503, "Stripe non configuré (STRIPE_SECRET_KEY manquant).")
    price_id = os.environ.get(price_env)
    if not price_id:
        raise HTTPException(503, f"Stripe non configuré ({price_env} manquant).")
    try:
        import stripe
    except ImportError:
        raise HTTPException(503, "Dépendance 'stripe' absente côté serveur.")
    stripe.api_key = secret
    site = os.environ.get("TANDOR_SITE_URL", "http://localhost:3000").rstrip("/")
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            client_reference_id=user.get("uid"),
            success_url=f"{site}/dashboard?checkout=success",
            cancel_url=f"{site}/dashboard?checkout=cancel",
        )
    except Exception as exc:  # noqa: BLE001 — on remonte une erreur propre au front
        raise HTTPException(502, f"Échec création session Stripe : {exc}")
    return {"url": session.url}


import threading as _threading

# Throttle GLOBAL des scrapes live (toutes IP/utilisateurs confondus) : protège
# l'unique IP du Pi d'un bannissement par abus de /api/validate.
_VALIDATE_LOCK = _threading.Lock()
_LAST_VALIDATE = [0.0]
_VALIDATE_MIN_INTERVAL = 8.0  # secondes minimum entre deux scrapes live


@app.post("/api/validate")
def validate_product(body: ValidateRequest,
                     user: dict = Depends(require_user)) -> dict[str, Any]:
    """Analyse à la demande d'un produit (URL Amazon/AliExpress ou nom libre).

    Réservé aux plans payants (déclenche du scraping live, ressource sensible) et
    throttlé globalement pour ne pas faire bannir l'IP du Pi.

    Pipeline :
      1. Extraction du mot-clé depuis l'input.
      2. Recherche du produit correspondant dans la DB CJ locale (coût, saturation).
      3. Score de vendabilité financière (marge, prix, saturation, fraîcheur).
      4. Signaux de demande en parallèle : Google Trends + Reddit + Amazon (avec timeout).
      5. Score organique via le moteur d'accélération.
      6. Saisonnalité.
      7. Score Tandor combiné + verdict final.
    """
    plan = plan_for(user)
    if plan == "free":
        raise HTTPException(403, "Validation live réservée aux plans payants.")
    charge_quota(user["uid"], plan, cost=VALIDATE_COST)
    with _VALIDATE_LOCK:
        if time.time() - _LAST_VALIDATE[0] < _VALIDATE_MIN_INTERVAL:
            raise HTTPException(429, "Trop de validations rapprochées, réessaie dans quelques secondes.")
        _LAST_VALIDATE[0] = time.time()

    t0 = time.time()

    # 1. Keyword
    keyword = _keyword_from_query(body.query)
    if not keyword:
        raise HTTPException(status_code=422, detail="Impossible d'extraire un mot-clé depuis l'input.")

    # 2. Matching CJ
    cj = _cj_search(keyword)
    cost_eur = float(cj["price"]) if cj and cj.get("price") else None
    listed_num = int(cj["listed_num"]) if cj and cj.get("listed_num") is not None else None
    suggest_price = float(cj["suggest_price"]) if cj and cj.get("suggest_price") else None
    age_days = _age_days(cj.get("create_time")) if cj else None

    cj_summary: dict[str, Any] | None = None
    if cj:
        cj_summary = {
            "name": cj.get("name"),
            "cost_eur": round(cost_eur, 2) if cost_eur else None,
            "listed_num": listed_num,
            "age_days": round(age_days, 0) if age_days else None,
            "image": cj.get("image"),
            "suggest_price": round(suggest_price, 2) if suggest_price else None,
        }

    # 3. Vendabilité
    sell_result: dict[str, Any] = {}
    try:
        from scoring.sellability import score_sellability
        pid = cj["pid"] if cj else keyword[:20]
        sr = score_sellability(
            pid, cost_eur, listed_num, age_days,
            retail_override=suggest_price,
        )
        sell_result = sr.as_dict()
    except Exception as exc:
        sell_result = {"error": str(exc), "verdict": "UNKNOWN", "sellability": 0.0}

    # 4. Signaux de demande (en parallèle, avec timeout individuel)
    def _trends():
        try:
            from collectors.google_trends import trends_raw_signal
            return trends_raw_signal(keyword, geo=body.geo or "")
        except Exception:
            return None

    def _reddit():
        try:
            from collectors.reddit_mentions import reddit_raw_signal
            return reddit_raw_signal(keyword)
        except Exception:
            return None

    def _amazon():
        try:
            from collectors.amazon_demand import fetch_demand
            return fetch_demand(keyword)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        ft = pool.submit(_trends)
        fr = pool.submit(_reddit)
        fa = pool.submit(_amazon)
        _SIGNAL_TIMEOUT = 20.0
        try:
            trends_sig = ft.result(timeout=_SIGNAL_TIMEOUT)
        except Exception:
            trends_sig = None
        try:
            reddit_sig = fr.result(timeout=_SIGNAL_TIMEOUT)
        except Exception:
            reddit_sig = None
        try:
            amazon_result = fa.result(timeout=_SIGNAL_TIMEOUT)
        except Exception:
            amazon_result = None

    # 5. Score organique
    organic_score = 0.0
    organic_phase = "unknown"
    organic_growth = 0.0
    organic_confidence = 0.0
    organic_reasons: list[str] = []
    try:
        from signals.features import build_product_features, RawSignal
        from scoring.engine import score_population
        raws: list[RawSignal] = [s for s in (trends_sig, reddit_sig) if s and s.values]
        if raws:
            pf = build_product_features(
                cj["pid"] if cj else keyword[:20], raws,
                age_days=age_days, seller_count=listed_num,
            )
            scored = score_population([pf])
            if scored:
                r = scored[0]
                organic_score = round(r.organic_score, 1)
                organic_phase = r.phase.value
                organic_growth = round(r.monthly_growth, 3)
                organic_confidence = round(r.confidence, 3)
                organic_reasons = r.top_reasons()
    except Exception:
        pass

    # 6. Saisonnalité
    season_result: dict[str, Any] = {}
    try:
        from signals.seasonality import seasonality_for
        month = datetime.now().month
        text = " ".join(filter(None, [
            keyword,
            cj.get("name", "") if cj else "",
            cj.get("category", "") if cj else "",
        ]))
        sr2 = seasonality_for(text, month)
        season_result = sr2.as_dict()
    except Exception as exc:
        season_result = {"multiplier": 1.0, "label": "indisponible", "error": str(exc)}

    # 7. Score Tandor combiné + verdict final
    sellability_score = sell_result.get("sellability", 0.0)
    tandor_score = round(0.55 * organic_score + 0.45 * sellability_score, 1)

    sell_verdict = sell_result.get("verdict", "UNKNOWN")
    if sell_verdict == "BUY" and organic_score < 20 and organic_confidence > 0.3:
        final_verdict = "WATCH"
    else:
        final_verdict = sell_verdict

    # Signaux formatés pour le front
    signals: dict[str, Any] = {
        "trends": {
            "available": bool(trends_sig and trends_sig.values),
            "points": len(trends_sig.values) if trends_sig else 0,
        },
        "reddit": {
            "available": bool(reddit_sig and reddit_sig.values),
            "points": len(reddit_sig.values) if reddit_sig else 0,
        },
        "amazon": (amazon_result.as_dict() if amazon_result else {"available": False}),
    }

    return {
        "keyword": keyword,
        "query": body.query,
        "cj_match": cj_summary,
        "sellability": sell_result,
        "organic": {
            "score": organic_score,
            "phase": organic_phase,
            "monthly_growth": organic_growth,
            "confidence": organic_confidence,
            "reasons": organic_reasons,
        },
        "seasonality": season_result,
        "signals": signals,
        "tandor_score": tandor_score,
        "verdict": final_verdict,
        "processing_time_s": round(time.time() - t0, 2),
    }
