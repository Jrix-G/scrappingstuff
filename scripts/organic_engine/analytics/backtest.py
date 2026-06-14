"""Évaluation rétrospective des prédictions (boucle de feedback).

On stocke chaque prédiction (score à l'instant t) ; après N semaines on observe
l'issue réelle (le produit a-t-il crû de plus de X % ?). Ce module mesure la
qualité prédictive du modèle sur ces couples (score, issue) :

* CALIBRATION : un score de 80-90 correspond-il vraiment à ~85 % de réussite ?
* DISCRIMINATION : AUC ROC + precision@k (les meilleurs scores sont-ils les bons ?).

Ces métriques pilotent la promotion (ou non) d'un nouveau jeu de poids.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class BacktestReport:
    """Synthèse de la performance prédictive."""

    n: int
    auc: float
    precision_at_k: float
    k: int
    brier: float                     # erreur quadratique de calibration [0,1], bas = mieux
    calibration_bins: list[tuple[float, float, int]]  # (score_moyen, taux_réel, effectif)

    def summary(self) -> str:
        return (
            f"n={self.n} | AUC={self.auc:.3f} | "
            f"precision@{self.k}={self.precision_at_k:.3f} | Brier={self.brier:.3f}"
        )


def roc_auc(scores: np.ndarray, outcomes: np.ndarray) -> float:
    """AUC ROC via la statistique de Mann-Whitney U (sans dépendance externe).

    AUC = P(score d'un positif > score d'un négatif). 0.5 = hasard, 1.0 = parfait.
    """
    scores = np.asarray(scores, dtype=float)
    outcomes = np.asarray(outcomes, dtype=int)
    pos = scores[outcomes == 1]
    neg = scores[outcomes == 0]
    if pos.size == 0 or neg.size == 0:
        return 0.5
    order = scores.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, scores.size + 1)
    # Moyenne des rangs pour les ex-aequo.
    _, inv, counts = np.unique(scores, return_inverse=True, return_counts=True)
    cum = np.cumsum(counts)
    avg_rank = cum - (counts - 1) / 2.0
    ranks = avg_rank[inv]
    sum_pos = ranks[outcomes == 1].sum()
    auc = (sum_pos - pos.size * (pos.size + 1) / 2.0) / (pos.size * neg.size)
    return float(auc)


def precision_at_k(scores: np.ndarray, outcomes: np.ndarray, k: int) -> float:
    """Proportion de vrais positifs parmi les k meilleurs scores."""
    scores = np.asarray(scores, dtype=float)
    outcomes = np.asarray(outcomes, dtype=int)
    k = min(k, scores.size)
    if k == 0:
        return 0.0
    top = scores.argsort()[::-1][:k]
    return float(outcomes[top].mean())


def calibration_curve(
    probs: np.ndarray, outcomes: np.ndarray, bins: int = 10
) -> list[tuple[float, float, int]]:
    """Courbe de calibration : (proba moyenne prédite, taux réel, effectif) par tranche."""
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=int)
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (probs >= lo) & (probs < hi if hi < 1.0 else probs <= hi)
        if mask.sum() > 0:
            out.append((float(probs[mask].mean()), float(outcomes[mask].mean()), int(mask.sum())))
    return out


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Score de Brier : moyenne (proba − issue)². Mesure directe de calibration."""
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)
    if probs.size == 0:
        return 1.0
    return float(np.mean((probs - outcomes) ** 2))


def run_backtest(
    scores_0_100: np.ndarray, outcomes: np.ndarray, k: int | None = None
) -> BacktestReport:
    """Évalue un lot de prédictions contre les issues observées.

    Args:
        scores_0_100: scores organiques (0-100) au moment de la prédiction.
        outcomes: 1 si le produit a effectivement explosé, 0 sinon.
        k: taille du top pour precision@k (défaut : 10 % de l'effectif).
    """
    scores = np.asarray(scores_0_100, dtype=float)
    outcomes = np.asarray(outcomes, dtype=int)
    n = scores.size
    if k is None:
        k = max(1, n // 10)
    probs = scores / 100.0
    return BacktestReport(
        n=n,
        auc=roc_auc(scores, outcomes),
        precision_at_k=precision_at_k(scores, outcomes, k),
        k=k,
        brier=brier_score(probs, outcomes),
        calibration_bins=calibration_curve(probs, outcomes),
    )
