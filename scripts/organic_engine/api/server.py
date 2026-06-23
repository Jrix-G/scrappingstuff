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
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


def _catalogue_page(
    conn: sqlite3.Connection,
    exclude_ids: set[str],
    sql_offset: int,
    sql_limit: int,
) -> list[dict[str, Any]]:
    """Lit une page du catalogue cj.db et la met à la forme BASE du dashboard.

    Tri stable par listed_num desc puis pid (déterministe entre requêtes, donc pas
    de doublon/saut entre pages successives). Les pids déjà servis par le cache
    enrichi sont exclus DIRECTEMENT en SQL (substr(pid,-7) NOT IN exclude_ids) :
    ainsi l'OFFSET SQL == l'offset logique du catalogue, et chaque page contient
    exactement ``sql_limit`` lignes. Aucune ligne au-delà de la page n'est chargée.
    """
    from scoring.sellability import score_sellability
    from scoring.loss_risk import assess_loss_risk

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

    out: list[dict[str, Any]] = []
    for r in rows:
        pid = r["pid"]
        cost = float(r["price"]) if r["price"] else None
        listed = int(r["listed_num"]) if r["listed_num"] is not None else 0
        age = _age_days(r["create_time"])
        suggest = float(r["suggest_price"]) if r["suggest_price"] else None

        sr = score_sellability(pid, cost, listed, age, retail_override=suggest)
        loss = assess_loss_risk(
            pid,
            net_after_cpa_eur=sr.net_after_cpa_eur,
            gross_margin_eur=sr.gross_margin_eur,
            pct_low_rating=None,
            listed_num=listed,
            retail_eur=sr.retail_eur,
        )

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
            "aliExpressSold": None,
            "aliExpressMedianSold": None,
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
            # Pas d'historique réel pour le catalogue brut -> hasRealHistory=false côté UI.
            "history": {"sales": None, "amazon": None},
            "lastCollection": None,
            "detectedHrs": None,
            "image": r["image"],
            "enriched": False,
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
def meta() -> dict[str, Any]:
    """Fraîcheur des données : quand, combien, enrichi ou non."""
    return _load_cache().get("meta", {})


@app.get("/api/products")
def list_products(
    cat: str | None = Query(None, description="Bucket catégorie (HOME, TECH, ...)"),
    verdict: str | None = Query(None, description="BUY / WATCH / PASS"),
    min_score: float = Query(0, ge=0, le=100, description="Score Tandor minimum"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0, description="Décalage pour la pagination / infinite scroll"),
) -> dict[str, Any]:
    """Produits du dashboard, paginés sur L'UNIVERS COMPLET (cache enrichi + cj.db).

    Stratégie de pagination unifiée :
      * Les ~60 produits ENRICHIS (cache JSON, Trends/Reddit/vélocité) occupent les
        premiers offsets, triés par score Tandor décroissant.
      * Au-delà, on sert le reste du catalogue cj.db (~6100 produits) page par page
        en SQL (LIMIT/OFFSET), scoré à la volée par les fonctions pures (aucun
        réseau). Ces produits ont les champs CJ de base mais organic=0 / pas
        d'historique réel — le front les affiche en empty-state « History building ».

    Rétro-compat : un appel sans ``offset`` repart de 0 et fonctionne comme avant.
    Les filtres (cat/verdict/min_score) ne s'appliquent qu'à la partie enrichie
    (le catalogue brut est servi tel quel ; le front filtre côté client).

    La réponse expose ``meta.total`` (univers complet), ``meta.has_more`` et
    ``meta.next_offset`` pour piloter l'infinite scroll côté front.
    """
    data = _load_cache()
    enriched = data.get("products", [])

    def tandor(p: dict) -> float:
        return 0.55 * p.get("organic", 0) + 0.45 * p.get("sellability", 0)

    # Filtres appliqués sur la partie enrichie uniquement.
    filtered = [
        p for p in enriched
        if (cat is None or p.get("cat") == cat)
        and (verdict is None or p.get("verdict") == verdict)
        and tandor(p) >= min_score
    ]
    filtered.sort(key=tandor, reverse=True)
    n_enriched = len(filtered)

    # Le cache ne stocke que l'``id`` = 7 derniers chiffres du pid CJ. On exclut donc
    # du catalogue les pids dont le suffixe correspond à un produit déjà enrichi.
    enriched_ids = {str(p.get("id")) for p in enriched if p.get("id")}

    page: list[dict[str, Any]] = []

    # 1. Tranche dans la partie enrichie.
    if offset < n_enriched:
        page.extend(filtered[offset:offset + limit])

    # 2. Complément depuis le catalogue cj.db si la page n'est pas pleine.
    has_more = False
    cat_total = 0
    # Le catalogue brut n'est servi que sans filtre enrichi (sinon incohérent) :
    # avec un filtre actif, on reste sur la partie enrichie.
    serve_catalogue = cat is None and verdict is None and min_score <= 0
    if CJ_DB.exists() and serve_catalogue:
        try:
            conn = sqlite3.connect(CJ_DB, timeout=5)
            conn.row_factory = sqlite3.Row
            try:
                cat_total = _catalogue_total(conn, enriched_ids)
                remaining = limit - len(page)
                if remaining > 0:
                    # Offset dans le catalogue = ce qui dépasse la partie enrichie.
                    # L'exclusion étant faite en SQL, cet offset est exact.
                    cat_offset = max(0, offset - n_enriched)
                    raw = _catalogue_page(conn, enriched_ids, cat_offset, remaining)
                    page.extend(raw)
                next_offset = offset + len(page)
                has_more = next_offset < (n_enriched + cat_total)
            finally:
                conn.close()
        except sqlite3.Error:
            # DB indisponible : on dégrade proprement sur la seule partie enrichie.
            cat_total = 0
            has_more = offset + len(page) < n_enriched
    else:
        has_more = offset + len(page) < n_enriched

    total = n_enriched + cat_total
    next_offset = offset + len(page)

    meta = dict(data.get("meta", {}))
    meta.update({
        "total": total,
        "enriched_count": n_enriched,
        "catalogue_count": cat_total,
        "offset": offset,
        "limit": limit,
        "returned": len(page),
        "next_offset": next_offset if has_more else None,
        "has_more": has_more,
    })

    return {
        "meta": meta,
        "count": len(page),
        "total": total,
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
        "products": page,
    }


@app.get("/api/product/{product_id}")
def product_detail(product_id: str) -> dict[str, Any]:
    """Détail d'un produit par son id (les 7 derniers chiffres du pid CJ)."""
    for p in _load_cache().get("products", []):
        if p.get("id") == product_id:
            return p
    raise HTTPException(status_code=404, detail="Produit inconnu")


@app.post("/api/validate")
def validate_product(body: ValidateRequest) -> dict[str, Any]:
    """Analyse à la demande d'un produit (URL Amazon/AliExpress ou nom libre).

    Pipeline :
      1. Extraction du mot-clé depuis l'input.
      2. Recherche du produit correspondant dans la DB CJ locale (coût, saturation).
      3. Score de vendabilité financière (marge, prix, saturation, fraîcheur).
      4. Signaux de demande en parallèle : Google Trends + Reddit + Amazon (avec timeout).
      5. Score organique via le moteur d'accélération.
      6. Saisonnalité.
      7. Score Tandor combiné + verdict final.
    """
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
