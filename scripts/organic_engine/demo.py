"""Démo end-to-end : génère des produits synthétiques et affiche le scoring.

Lancer :  python3 demo.py
Montre comment le moteur classe un produit émergent au-dessus d'un produit
mature ou en déclin, avec score, phase, confiance et explication.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from signals.features import RawSignal, build_product_features
from scoring.engine import score_population


def _grow(start: float, factor: float, accel: float = 1.0, n: int = 6) -> list[float]:
    """Série temporelle synthétique : factor par pas, accel>1 = accélère."""
    vals, cur, rate = [], float(start), factor
    for _ in range(n):
        vals.append(round(cur, 1))
        cur *= rate
        rate *= accel
    return vals


def _make(pid, spec, **meta):
    # Pas HEBDOMADAIRES (0,7,14,...) : la croissance mensuelle extrapolée reste réaliste.
    t = [7 * i for i in range(6)]
    raws = [RawSignal(name, t, _grow(*params)) for name, params in spec.items()]
    return build_product_features(pid, raws, **meta)


def main() -> None:
    universe = [
        _make("🚀 Mini-projecteur LED", {
            "sales": (40, 1.18, 1.05), "reddit": (4, 1.30, 1.08),
            "tiktok": (6, 1.35, 1.07), "google_trends": (8, 1.22, 1.05),
        }, age_days=18, seller_count=4, review_count=12),

        _make("📈 Bracelet magnétique", {
            "sales": (120, 1.10, 1.01), "google_trends": (30, 1.08, 1.0),
            "reddit": (10, 1.10, 1.0),
        }, age_days=60, seller_count=15, review_count=140),

        _make("🏔️ Coque iPhone (saturé)", {
            "sales": (8000, 1.0, 1.0), "google_trends": (1200, 1.0, 1.0),
            "reddit": (300, 1.0, 1.0),
        }, age_days=500, seller_count=200, review_count=15000),

        _make("📉 Spinner (déclin)", {
            "sales": (3000, 0.93, 1.0), "google_trends": (500, 0.92, 1.0),
        }, age_days=900, seller_count=90, review_count=8000),
    ]

    results = score_population(universe)
    results.sort(key=lambda r: r.organic_score, reverse=True)

    print("\n" + "=" * 70)
    print(" MOTEUR DE DÉTECTION DE CROISSANCE ORGANIQUE — démo")
    print("=" * 70)
    for r in results:
        print(f"\n  {r.product_id}")
        print(f"    Score organique : {r.organic_score:5.1f}/100   "
              f"Confiance : {r.confidence:.2f}   Phase : {r.phase.value}")
        print(f"    Croissance/mois : {r.monthly_growth:+.0%}   "
              f"Corroboration : {r.corroboration} sources   "
              f"Momentum : {r.momentum:+.2f}  Maturité : {r.maturity:+.2f}")
        for reason in r.top_reasons(3):
            print(f"      {reason}")
    print("\n" + "=" * 70)
    print(" → Le produit émergent (bas niveau + accélération multi-sources)")
    print("   domine, AVANT d'être saturé. C'est l'angle différenciant.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
