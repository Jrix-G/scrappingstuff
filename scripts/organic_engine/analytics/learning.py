"""Apprentissage des poids : remplace le prior par des coefficients validés.

Quand un volume suffisant de couples (features, issue) est accumulé, on ajuste
une **régression logistique régularisée (L2)** par descente de gradient (numpy
seul, aucune dépendance lourde). Les coefficients appris :

* remplacent l'équipondération du prior (cf. scoring.config) ;
* fournissent, via leur magnitude standardisée, la **valeur prédictive** de
  chaque signal — répondant à « quels signaux comptent le plus ? ».

La promotion d'un nouveau modèle est conditionnée à une amélioration mesurée en
backtest hold-out (cf. backtest.py) : on ne déploie jamais des poids non validés.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class LogisticModel:
    """Modèle logistique appris : poids + biais + nom des features."""

    feature_names: list[str]
    weights: np.ndarray
    bias: float
    version: str = "learned:v1"

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Probabilité d'explosion organique pour chaque ligne de X."""
        z = X @ self.weights + self.bias
        return 1.0 / (1.0 + np.exp(-z))

    def predictive_value(self) -> dict[str, float]:
        """Importance relative |poids| normalisée (somme = 1)."""
        mag = np.abs(self.weights)
        total = mag.sum()
        if total < 1e-9:
            return {name: 0.0 for name in self.feature_names}
        return {name: float(m / total) for name, m in zip(self.feature_names, mag)}


def _standardize(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Centre-réduit les colonnes (nécessaire pour comparer les coefficients)."""
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    return (X - mu) / sd, mu, sd


def fit_logistic(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    l2: float = 1.0,
    lr: float = 0.1,
    epochs: int = 2000,
    version: str = "learned:v1",
) -> LogisticModel:
    """Ajuste une régression logistique L2 par descente de gradient batch.

    Args:
        X: matrice (n_échantillons, n_features) des features au moment de la prédiction.
        y: issues binaires (1 = a explosé).
        feature_names: noms des colonnes de X (pour l'explicabilité).
        l2: force de régularisation (évite le surapprentissage sur peu de données).
        lr: pas d'apprentissage.
        epochs: itérations de descente de gradient.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    Xs, mu, sd = _standardize(X)
    n, d = Xs.shape
    w = np.zeros(d)
    b = 0.0
    for _ in range(epochs):
        z = Xs @ w + b
        p = 1.0 / (1.0 + np.exp(-z))
        grad_w = Xs.T @ (p - y) / n + l2 * w / n
        grad_b = float(np.mean(p - y))
        w -= lr * grad_w
        b -= lr * grad_b
    # Re-projection des poids vers l'espace des features d'origine.
    w_orig = w / sd
    b_orig = b - float(np.sum(w * mu / sd))
    return LogisticModel(feature_names, w_orig, b_orig, version)


# Features standard exposées au modèle (ordre = colonnes de X).
FEATURE_ORDER = [
    "momentum",
    "maturity",
    "corroboration",
    "monthly_growth",
    "confidence",
]


def features_from_result(result) -> list[float]:
    """Extrait le vecteur de features d'un ScoreResult pour l'apprentissage."""
    return [
        result.momentum,
        result.maturity,
        float(result.corroboration),
        result.monthly_growth,
        result.confidence,
    ]
