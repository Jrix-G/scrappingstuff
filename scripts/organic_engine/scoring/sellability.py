"""Analyse de vendabilité financière — le « verdict de trader » par produit.

Le moteur d'accélération (``scoring/engine.py``) répond à « ça monte ? ». Ce module
répond à la question complémentaire et tout aussi décisive : **« ça se VEND, avec
quelle marge, et faut-il l'acheter maintenant ? »** — au sens d'un acheteur qui
arbitre un portefeuille de produits.

Il fonctionne sur un SEUL snapshot CJ (coût, nombre de vendeurs, âge), donc il est
opérationnel immédiatement, sans attendre l'historique nécessaire à la vélocité.

Quatre dimensions, chacune un sous-score [0,1] explicable :

1. **Marge** — peut-on gagner de l'argent APRÈS le coût d'acquisition publicitaire ?
   C'est le filtre du trader : un produit sans marge nette n'existe pas, peu importe
   sa hype. Gate dur : ``profit_après_CPA <= 0`` => PASS.
2. **Bande de prix** — psychologie de l'achat d'impulsion (sweet spot retail ~15–60 €).
3. **Saturation** — ``listedNum`` (vendeurs CJ) : validé mais pas encore saturé = idéal.
4. **Fraîcheur** — ``createTime`` : surfer tôt vaut mieux qu'arriver après la vague.

Score global = moyenne géométrique pondérée des sous-scores. La moyenne géométrique
(et non arithmétique) est délibérée : elle **sanctionne tout défaut fatal** — un
produit excellent partout sauf sur la marge reste non vendable.

Les constantes sont des heuristiques métier documentées, destinées à être remplacées
par des coefficients appris une fois l'historique d'issues disponible (même
philosophie que ``scoring/config.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log

_EPS = 1e-9


@dataclass(slots=True)
class SellabilityConfig:
    """Hyperparamètres économiques de la vendabilité (heuristiques calibrées)."""

    # Coût d'acquisition client via pub payante (€). Un produit doit dégager
    # une marge brute > CPA pour être diffusable de façon rentable.
    cpa_eur: float = 12.0
    # Profit net visé au-delà du CPA pour un score marge « plein » (€).
    target_net_profit_eur: float = 25.0

    # Bande de prix retail d'impulsion : log-gaussienne (centre, largeur en log).
    price_sweet_spot_eur: float = 30.0
    price_log_sigma: float = 0.6

    # Pondérations du mélange géométrique (n'ont pas besoin de sommer à 1).
    w_margin: float = 0.40
    w_price: float = 0.20
    w_saturation: float = 0.25
    w_freshness: float = 0.15

    # Seuils de verdict sur le score 0–100.
    buy_threshold: float = 65.0
    watch_threshold: float = 40.0


DEFAULT_SELLABILITY = SellabilityConfig()


@dataclass(slots=True)
class SellabilityResult:
    """Verdict financier explicable d'un produit."""

    product_id: str
    sellability: float        # 0–100
    verdict: str              # BUY / WATCH / PASS
    cost_eur: float
    retail_eur: float
    gross_margin_eur: float
    margin_pct: float         # marge brute / prix de vente
    net_after_cpa_eur: float  # marge brute − CPA
    margin_score: float
    price_score: float
    saturation_score: float
    freshness_score: float
    reason: str

    def as_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "sellability": round(self.sellability, 1),
            "verdict": self.verdict,
            "cost_eur": round(self.cost_eur, 2),
            "retail_eur": round(self.retail_eur, 2),
            "gross_margin_eur": round(self.gross_margin_eur, 2),
            "margin_pct": round(self.margin_pct, 3),
            "net_after_cpa_eur": round(self.net_after_cpa_eur, 2),
            "scores": {
                "margin": round(self.margin_score, 3),
                "price": round(self.price_score, 3),
                "saturation": round(self.saturation_score, 3),
                "freshness": round(self.freshness_score, 3),
            },
            "reason": self.reason,
        }


def estimated_retail(cost_eur: float) -> float:
    """Prix retail estimé selon la courbe de markup dropshipping par bande de coût.

    Les petits articles supportent des multiples plus élevés (l'acheteur n'a pas
    d'ancrage de prix) ; les articles chers, des multiples plus faibles.
    """
    if cost_eur < 5:
        markup = 4.0
    elif cost_eur < 15:
        markup = 3.0
    elif cost_eur < 40:
        markup = 2.5
    elif cost_eur < 80:
        markup = 2.0
    else:
        markup = 1.7
    return cost_eur * markup


def _margin_score(net_after_cpa: float, cfg: SellabilityConfig) -> float:
    """Sous-score marge : 0 si on ne peut pas couvrir le CPA, sature au profit visé."""
    if net_after_cpa <= 0:
        return 0.0
    return min(1.0, net_after_cpa / cfg.target_net_profit_eur)


def _price_score(retail: float, cfg: SellabilityConfig) -> float:
    """Sous-score psychologie de prix : log-gaussienne autour du sweet spot."""
    if retail <= 0:
        return 0.0
    z = (log(retail) - log(cfg.price_sweet_spot_eur)) / cfg.price_log_sigma
    return float(exp(-0.5 * z * z))


def _saturation_score(listed_num: int | None) -> float:
    """Sous-score saturation offre : un produit validé mais pas saturé est idéal.

    0 vendeur = non prouvé (demande inconnue) ; 1–15 = validé + marge de manœuvre ;
    au-delà, l'océan rougit.
    """
    if listed_num is None:
        return 0.5
    n = max(0, listed_num)
    if n == 0:
        return 0.45
    if n <= 15:
        return 1.0
    if n <= 40:
        return 0.7
    if n <= 100:
        return 0.4
    return 0.2


def _freshness_score(age_days: float | None) -> float:
    """Sous-score fraîcheur : surfer tôt > arriver après la vague."""
    if age_days is None:
        return 0.6
    if age_days < 60:
        return 1.0
    if age_days < 180:
        return 0.85
    if age_days < 365:
        return 0.6
    return 0.4


def _weighted_geomean(scores: list[float], weights: list[float]) -> float:
    """Moyenne géométrique pondérée : tout sous-score nul annule l'ensemble."""
    total_w = sum(weights) + _EPS
    acc = 0.0
    for s, w in zip(scores, weights):
        acc += w * log(max(s, _EPS))
    return float(exp(acc / total_w))


def _reason(res_scores: dict[str, float], net_after_cpa: float, margin_pct: float,
            listed_num: int | None, verdict: str) -> str:
    """Phrase de justification orientée décision."""
    if net_after_cpa <= 0:
        return ("Marge trop fine : après ~CPA publicitaire, le produit ne dégage aucun "
                "profit. Invendable de façon rentable.")
    bits: list[str] = []
    bits.append(f"marge nette ~{net_after_cpa:.0f}€/vente ({margin_pct*100:.0f}% brut)")
    if listed_num is not None:
        vendeur = "vendeur" if listed_num == 1 else "vendeurs"
        if listed_num == 0:
            bits.append("aucun vendeur (non prouvé)")
        elif listed_num <= 15:
            bits.append(f"{listed_num} {vendeur} (validé, peu saturé)")
        else:
            bits.append(f"{listed_num} {vendeur} (concurrence dense)")
    if res_scores["price"] >= 0.7:
        bits.append("prix dans la zone d'impulsion")
    elif res_scores["price"] < 0.4:
        bits.append("prix hors zone d'impulsion")
    if res_scores["freshness"] >= 0.85:
        bits.append("produit récent")
    head = {"BUY": "ACHETER", "WATCH": "SURVEILLER", "PASS": "PASSER"}[verdict]
    return f"{head} — " + ", ".join(bits) + "."


def score_sellability(
    product_id: str,
    cost_eur: float | None,
    listed_num: int | None,
    age_days: float | None,
    cfg: SellabilityConfig = DEFAULT_SELLABILITY,
    retail_override: float | None = None,
) -> SellabilityResult:
    """Calcule le verdict de vendabilité d'un produit depuis un snapshot CJ.

    ``retail_override`` : prix retail conseillé par CJ (``suggestSellPrice``).
    Quand il est disponible et crédible (> coût), on l'utilise À LA PLACE de
    l'heuristique de markup — c'est une vraie donnée fournisseur, pas une estimation.
    """
    cost = float(cost_eur) if cost_eur and cost_eur > 0 else 0.0
    if retail_override and retail_override > cost > 0:
        retail = float(retail_override)
    else:
        retail = estimated_retail(cost) if cost > 0 else 0.0
    gross = retail - cost
    margin_pct = (gross / retail) if retail > 0 else 0.0
    net_after_cpa = gross - cfg.cpa_eur

    s_margin = _margin_score(net_after_cpa, cfg)
    s_price = _price_score(retail, cfg)
    s_sat = _saturation_score(listed_num)
    s_fresh = _freshness_score(age_days)

    raw = _weighted_geomean(
        [s_margin, s_price, s_sat, s_fresh],
        [cfg.w_margin, cfg.w_price, cfg.w_saturation, cfg.w_freshness],
    )
    sellability = 100.0 * raw

    # Gate dur : pas de profit après CPA => PASS quel que soit le reste.
    if net_after_cpa <= 0:
        verdict = "PASS"
    elif sellability >= cfg.buy_threshold:
        verdict = "BUY"
    elif sellability >= cfg.watch_threshold:
        verdict = "WATCH"
    else:
        verdict = "PASS"

    scores = {"margin": s_margin, "price": s_price,
              "saturation": s_sat, "freshness": s_fresh}
    return SellabilityResult(
        product_id=product_id,
        sellability=sellability,
        verdict=verdict,
        cost_eur=cost,
        retail_eur=retail,
        gross_margin_eur=gross,
        margin_pct=margin_pct,
        net_after_cpa_eur=net_after_cpa,
        margin_score=s_margin,
        price_score=s_price,
        saturation_score=s_sat,
        freshness_score=s_fresh,
        reason=_reason(scores, net_after_cpa, margin_pct, listed_num, verdict),
    )
