"""API backend du moteur organique (FastAPI).

Endpoints alignés sur les besoins du frontend : liste scorée, détail explicable,
historique des signaux, alertes. Chaque score est renvoyé AVEC son explication
(contributions par source) pour que l'utilisateur comprenne le « pourquoi ».

Lancement :
    uvicorn api.main:app --reload
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query
except ImportError:  # permet d'importer le module sans FastAPI installé
    FastAPI = None  # type: ignore

from scoring.engine import ScoreResult, score_population
from signals.features import ProductFeatures

# Dépôt injectable : en prod, implémentation SQLite/Postgres ; ici, en mémoire.
from .repository import Repository, InMemoryRepository

repo: Repository = InMemoryRepository()


def _serialize(result: ScoreResult) -> dict[str, Any]:
    """Sérialise un score AVEC son explication (contrat frontend)."""
    return {
        "product_id": result.product_id,
        "organic_score": round(result.organic_score, 1),
        "confidence": round(result.confidence, 3),
        "phase": result.phase.value,
        "monthly_growth": round(result.monthly_growth, 3),
        "corroboration": result.corroboration,
        "momentum": round(result.momentum, 3),
        "maturity": round(result.maturity, 3),
        "reasons": result.top_reasons(),
        "contributions": [
            {
                "source": c.source,
                "z_velocity": round(c.z_velocity, 2),
                "z_acceleration": round(c.z_acceleration, 2),
                "contribution": round(c.contribution, 3),
            }
            for c in result.contributions
        ],
    }


if FastAPI is not None:
    app = FastAPI(title="Organic Growth Engine", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/products")
    def list_products(
        min_score: float = Query(0, ge=0, le=100),
        phase: str | None = None,
        limit: int = Query(50, ge=1, le=500),
    ) -> dict[str, Any]:
        """Liste des produits scorés, triés par score décroissant."""
        population: list[ProductFeatures] = repo.load_population()
        results = score_population(population)
        results.sort(key=lambda r: r.organic_score, reverse=True)
        filtered = [
            r for r in results
            if r.organic_score >= min_score and (phase is None or r.phase.value == phase)
        ]
        return {"count": len(filtered), "products": [_serialize(r) for r in filtered[:limit]]}

    @app.get("/api/product/{product_id}")
    def product_detail(product_id: str) -> dict[str, Any]:
        """Détail d'un produit : score explicable + historique des signaux."""
        population = repo.load_population()
        results = {r.product_id: r for r in score_population(population)}
        if product_id not in results:
            raise HTTPException(status_code=404, detail="Produit inconnu")
        return {
            "score": _serialize(results[product_id]),
            "history": repo.load_history(product_id),
        }

    @app.get("/api/alerts")
    def list_alerts(undelivered_only: bool = True) -> dict[str, Any]:
        """Alertes en attente (produits émergents / franchissements de seuil)."""
        return {"alerts": repo.load_alerts(undelivered_only)}
