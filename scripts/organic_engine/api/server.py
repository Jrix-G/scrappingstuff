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
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "dashboard_export.json"

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


app = FastAPI(title="Tandor — Organic Engine API", version="1.0.0")

_origins = os.environ.get("TANDOR_CORS_ORIGINS", _DEFAULT_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _origins.strip() == "*" else [o.strip() for o in _origins.split(",")],
    allow_methods=["GET"],
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
) -> dict[str, Any]:
    """Produits scorés (forme BASE du dashboard), filtrés et triés par score Tandor."""
    data = _load_cache()
    products = data.get("products", [])

    def tandor(p: dict) -> float:
        return 0.55 * p.get("organic", 0) + 0.45 * p.get("sellability", 0)

    filtered = [
        p for p in products
        if (cat is None or p.get("cat") == cat)
        and (verdict is None or p.get("verdict") == verdict)
        and tandor(p) >= min_score
    ]
    filtered.sort(key=tandor, reverse=True)
    return {
        "meta": data.get("meta", {}),
        "count": len(filtered),
        "products": filtered[:limit],
    }


@app.get("/api/product/{product_id}")
def product_detail(product_id: str) -> dict[str, Any]:
    """Détail d'un produit par son id (les 7 derniers chiffres du pid CJ)."""
    for p in _load_cache().get("products", []):
        if p.get("id") == product_id:
            return p
    raise HTTPException(status_code=404, detail="Produit inconnu")
