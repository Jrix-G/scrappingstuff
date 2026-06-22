"""Verdict « Loss Risk » — le détecteur de pièges à fric de Tandor.

On INVERSE l'angle du marché : au lieu de « ce produit va gagner » (upside
invérifiable), on répond « ne lance pas ça, tu vas perdre de l'argent » (downside,
tractable). Chaque drapeau dit clairement ce qui est DUR vs ESTIMÉ.

Drapeaux disponibles aujourd'hui (jour 1) :
  - marge   : marge nette après CPA pub (depuis scoring.sellability). DUR (coût) +
              ESTIMÉ (CPA pub ~12 € par défaut).
  - retour  : note médiane Amazon de la catégorie = proxy qualité → risque de retour.
              DUR (note scrapée) mais c'est un PROXY, pas le vrai sentiment NLP.
  - saturation : niveau de concurrence (listed_num CJ). NB : c'est un NIVEAU, pas
              encore la *vélocité* de saturation (qui exige l'historique — l'horloge).
  - déclin  : VÉLOCITÉ de la demande dans le temps. On l'obtient de NOTRE PROPRE
              horloge : la table ``sales_snapshots`` accumule un point/jour, et
              ``signals.timeseries.extract_trend`` en sort la pente log/jour.
              Négatif = la demande pour ce TYPE de produit s'éteint → on arrive
              trop tard. Garde-fou DUR : < 3 mesures => « inconnu », JAMAIS « déclin »
              (2 points peuvent être du bruit de scraping, pas une tendance).

Verdict : TRAP (au moins un drapeau rouge) / RISKY (au moins un orange) / VIABLE.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import exp

# Risque de retour = PART de produits mal notés (<4.0★) dans la catégorie Amazon.
# Discrimine bien mieux que la médiane (qui est ~toujours ≥4.0). Une catégorie où
# beaucoup de produits sont mal notés = problème qualité structurel => retours/litiges.
LOWRATE_RED = 0.20      # >20% des produits <4.0★ => rouge
LOWRATE_AMBER = 0.10    # >10% => orange
# Seuils marge nette après CPA (€/vente). Sous ~5 €, un seul retour fait basculer négatif.
NET_THIN = 5.0
# Niveau de saturation (listed_num CJ).
SAT_DENSE = 15
# Bande de prix d'impulsion (retail €). Hors zone = mauvais produit dropship :
# trop cher = pas d'achat impulsif + retours/shipping qui tuent ; trop bas = pas de marge.
PRICE_MIN, PRICE_MAX = 12.0, 70.0
PRICE_HIGH_TICKET = 120.0
# Déclin de la demande (vélocité = pente log/jour de sales_snapshots).
# Garde-fou DUR : sous ce nb de mesures, on ne CONCLUT pas (un creux de 2 points
# est du bruit, pas une tendance). Cohérent avec TrendFeatures.is_reliable.
DECLINE_MIN_POINTS = 3
DECLINE_MAX_VOLATILITY = 1.0     # série trop bruitée au-delà => « inconnu », pas « déclin »
# Seuils sur la croissance MENSUELLE implicite (exp(velocity*30) - 1), interprétable.
DECLINE_RED = -0.30      # <= -30 %/mois => la tendance meurt, on arrive trop tard
DECLINE_AMBER = -0.12    # <= -12 %/mois => momentum qui s'essouffle


@dataclass(slots=True)
class LossFlag:
    name: str
    level: str          # "red" | "amber" | "green" | "unknown"
    reason: str


@dataclass(slots=True)
class LossRiskResult:
    product_id: str
    verdict: str        # TRAP | RISKY | VIABLE
    headline: str
    flags: list[LossFlag]
    breakeven_cpa_eur: float | None   # CPA pub à partir duquel on perd de l'argent

    def as_dict(self) -> dict:
        return {
            "productId": self.product_id,
            "verdict": self.verdict,
            "headline": self.headline,
            "breakevenCpaEur": (round(self.breakeven_cpa_eur, 1)
                                if self.breakeven_cpa_eur is not None else None),
            "flags": [{"name": f.name, "level": f.level, "reason": f.reason}
                      for f in self.flags],
        }


def _margin_flag(net_after_cpa: float | None, gross_margin: float | None) -> LossFlag:
    if net_after_cpa is None:
        return LossFlag("marge", "unknown", "coût inconnu")
    if net_after_cpa <= 0:
        return LossFlag("marge", "red",
                        f"après pub (~CPA), tu PERDS {abs(net_after_cpa):.0f}€/vente")
    if net_after_cpa < NET_THIN:
        return LossFlag("marge", "amber",
                        f"marge nette mince (~{net_after_cpa:.0f}€/vente) : fragile au "
                        "moindre retour ou hausse de CPM")
    return LossFlag("marge", "green", f"marge nette ~{net_after_cpa:.0f}€/vente")


def _return_flag(pct_low_rating: float | None) -> LossFlag:
    if pct_low_rating is None:
        return LossFlag("retour", "unknown", "avis insuffisants")
    pct = pct_low_rating * 100
    if pct_low_rating >= LOWRATE_RED:
        return LossFlag("retour", "red",
                        f"{pct:.0f}% des produits <4.0★ — qualité problématique, "
                        "retours/litiges probables (proxy avis)")
    if pct_low_rating >= LOWRATE_AMBER:
        return LossFlag("retour", "amber",
                        f"{pct:.0f}% des produits <4.0★ — qualité inégale (proxy avis)")
    return LossFlag("retour", "green",
                    f"seulement {pct:.0f}% des produits <4.0★ (proxy avis)")


def _saturation_flag(listed_num: int | None) -> LossFlag:
    if listed_num is None:
        return LossFlag("saturation", "unknown", "concurrence inconnue")
    if listed_num > SAT_DENSE:
        return LossFlag("saturation", "red",
                        f"{listed_num} vendeurs — concurrence dense (niveau)")
    if listed_num == 0:
        return LossFlag("saturation", "amber", "aucun vendeur — demande non prouvée")
    return LossFlag("saturation", "green",
                    f"{listed_num} vendeur(s) — peu saturé (niveau)")


def _decline_flag(
    demand_velocity: float | None,
    demand_points: int,
    demand_volatility: float | None,
) -> LossFlag:
    """Demande en déclin ? Lue sur NOTRE horloge (sales_snapshots via extract_trend).

    ``demand_velocity`` est la pente log/jour ; on l'exprime en croissance mensuelle
    implicite pour le verdict. ABSENCE d'historique fiable = « inconnu », jamais
    « déclin » : c'est le garde-fou contre le faux négatif (cf. DECLINE_MIN_POINTS).
    """
    if demand_velocity is None or demand_points < DECLINE_MIN_POINTS:
        return LossFlag("déclin", "unknown",
                        "historique de demande insuffisant (< 3 mesures)")
    if demand_volatility is not None and demand_volatility > DECLINE_MAX_VOLATILITY:
        return LossFlag("déclin", "unknown",
                        "série de demande trop bruitée pour conclure")
    # exp() borné : une vélocité positive forte ne doit pas overflow l'affichage.
    monthly = exp(min(demand_velocity * 30.0, 20.0)) - 1.0
    pct = monthly * 100.0
    if monthly <= DECLINE_RED:
        return LossFlag("déclin", "red",
                        f"demande en chute (~{pct:.0f}%/mois) — tendance qui meurt, "
                        "tu arrives trop tard")
    if monthly <= DECLINE_AMBER:
        return LossFlag("déclin", "amber",
                        f"demande en repli (~{pct:.0f}%/mois) — momentum qui s'essouffle")
    if monthly > 1.0:    # >+100 %/mois : afficher proprement, sans nombre absurde
        return LossFlag("déclin", "green", "demande en forte hausse")
    return LossFlag("déclin", "green",
                    f"demande stable/en hausse (~{pct:+.0f}%/mois)")


def _price_flag(retail_eur: float | None) -> LossFlag:
    if not retail_eur or retail_eur <= 0:
        return LossFlag("prix", "unknown", "prix retail inconnu")
    if retail_eur >= PRICE_HIGH_TICKET:
        return LossFlag("prix", "red",
                        f"retail ~{retail_eur:.0f}€ — high-ticket : pas d'achat impulsif, "
                        "shipping/retours qui tuent en dropship")
    if retail_eur > PRICE_MAX or retail_eur < PRICE_MIN:
        return LossFlag("prix", "amber",
                        f"retail ~{retail_eur:.0f}€ — hors zone d'impulsion (~12-70€)")
    return LossFlag("prix", "green", f"retail ~{retail_eur:.0f}€ — zone d'impulsion")


def assess_loss_risk(
    product_id: str,
    net_after_cpa_eur: float | None,
    gross_margin_eur: float | None,
    pct_low_rating: float | None,
    listed_num: int | None,
    retail_eur: float | None = None,
    demand_velocity: float | None = None,
    demand_points: int = 0,
    demand_volatility: float | None = None,
) -> LossRiskResult:
    """Assemble les drapeaux disponibles en un verdict loss-framed.

    ``demand_velocity`` / ``demand_points`` / ``demand_volatility`` viennent de
    ``timeseries.extract_trend`` sur la série ``sales_snapshots`` du mot-clé. Tous
    optionnels (défaut = signal absent → drapeau « déclin » en « inconnu ») pour
    rester rétro-compatible avec les call sites qui ne les passent pas encore.
    """
    flags = [
        _margin_flag(net_after_cpa_eur, gross_margin_eur),
        _price_flag(retail_eur),
        _return_flag(pct_low_rating),
        _saturation_flag(listed_num),
        _decline_flag(demand_velocity, demand_points, demand_volatility),
    ]
    reds = [f for f in flags if f.level == "red"]
    ambers = [f for f in flags if f.level == "amber"]

    if reds:
        verdict = "TRAP"
        headline = "❌ Piège : " + " ; ".join(f.reason for f in reds)
    elif ambers:
        verdict = "RISKY"
        headline = "⚠️ Risqué : " + " ; ".join(f.reason for f in ambers)
    else:
        verdict = "VIABLE"
        if gross_margin_eur is not None:
            headline = (f"✅ Viable jusqu'à un CPA de ~{gross_margin_eur:.0f}€ "
                        "(au-delà, tu perds)")
        else:
            headline = "✅ Viable"

    return LossRiskResult(
        product_id=product_id,
        verdict=verdict,
        headline=headline,
        flags=flags,
        breakeven_cpa_eur=gross_margin_eur,
    )
