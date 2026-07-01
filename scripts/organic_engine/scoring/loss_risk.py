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
from math import exp, inf

# Risque de retour = PART de produits mal notés (<4.0★) dans la catégorie Amazon.
# Discrimine bien mieux que la médiane (qui est ~toujours ≥4.0). Une catégorie où
# beaucoup de produits sont mal notés = problème qualité structurel => retours/litiges.
LOWRATE_RED = 0.20      # >20% des produits <4.0★ => rouge
LOWRATE_AMBER = 0.10    # >10% => orange
# Seuils marge nette après CPA (€/vente). Sous ~5 €, un seul retour fait basculer négatif.
NET_THIN = 5.0
# Niveau de saturation (listed_num CJ).
SAT_DENSE = 15
# Demande prouvée : achats Amazon (« bought in past month ») au-dessus desquels la
# demande est considérée RÉELLE (signal positif). En dessous (mais mesuré) = faible.
# JAMAIS de rouge : l'absence de demande prouvée est un risque, pas une perte certaine.
DEMAND_PROVEN = 100
# Bande de prix d'impulsion (retail €). Hors zone = mauvais produit dropship :
# trop cher = pas d'achat impulsif + retours/shipping qui tuent ; trop bas = pas de marge.
PRICE_MIN, PRICE_MAX = 12.0, 70.0
PRICE_HIGH_TICKET = 120.0
# Déclin de la demande (vélocité = pente log/jour de sales_snapshots).
# Garde-fou DUR : sous ce nb de mesures, on ne CONCLUT pas (un creux de 2 points
# est du bruit, pas une tendance). Cohérent avec TrendFeatures.is_reliable.
DECLINE_MIN_POINTS = 3
DECLINE_MAX_VOLATILITY = 1.0     # série trop bruitée au-delà => « inconnu », pas « déclin »
# Fenêtre minimale couverte par la série pour OSER un rouge. Une pente -30 %/mois
# lue sur 3 j est du bruit ; il faut une durée réelle d'observation.
DECLINE_MIN_SPAN_DAYS = 10.0
# Seuils sur la croissance MENSUELLE implicite (exp(velocity*30) - 1), interprétable.
DECLINE_RED = -0.30      # <= -30 %/mois => la tendance meurt, on arrive trop tard
DECLINE_AMBER = -0.12    # <= -12 %/mois => momentum qui s'essouffle

# Valeurs critiques de Student (bilatéral, α=0.05) par degré de liberté (= n-2).
# Au-delà de la table, on tend vers la loi normale (1.96). Sert au test de
# significativité de la pente : un -30 %/mois sur une pente non distinguable de 0
# n'est PAS un déclin, juste du bruit -> on ne crie pas « piège ».
_T_CRIT_05 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36,
              8: 2.31, 9: 2.26, 10: 2.23, 11: 2.20, 12: 2.18, 13: 2.16, 14: 2.14}


def _slope_is_significant(velocity: float, velocity_se: float | None,
                          n_points: int) -> bool:
    """La pente est-elle distinguable de 0 à α=0.05 ? (test t = pente / SE)."""
    if velocity_se is None or velocity_se == inf or velocity_se <= 0.0:
        return False
    df = n_points - 2
    if df < 1:
        return False
    t_crit = _T_CRIT_05.get(df, 1.96)
    return abs(velocity / velocity_se) >= t_crit


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
    # Couverture : combien des signaux de risque ont été RÉELLEMENT mesurés (level
    # != unknown) sur le total. Un VIABLE à 2/5 signaux mesurés ne « vaut » pas un
    # VIABLE à 5/5 : l'UI affiche ce ratio pour qualifier l'absence de preuve.
    coverage_measured: int = 0
    coverage_total: int = 0

    def as_dict(self) -> dict:
        return {
            "productId": self.product_id,
            "verdict": self.verdict,
            "headline": self.headline,
            "breakevenCpaEur": (round(self.breakeven_cpa_eur, 1)
                                if self.breakeven_cpa_eur is not None else None),
            "coverageMeasured": self.coverage_measured,
            "coverageTotal": self.coverage_total,
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
    demand_velocity_se: float | None = None,
    demand_span_days: float | None = None,
) -> LossFlag:
    """Demande en déclin ? Lue sur NOTRE horloge (sales_snapshots via extract_trend).

    ``demand_velocity`` est la pente log/jour ; on l'exprime en croissance mensuelle
    implicite pour le verdict. ABSENCE d'historique fiable = « inconnu », jamais
    « déclin » : c'est le garde-fou contre le faux négatif (cf. DECLINE_MIN_POINTS).

    Un rouge « déclin » n'est émis que si la chute est PROUVÉE : pente significative
    à α=0.05 (``demand_velocity_se``) ET fenêtre d'observation suffisante
    (``demand_span_days`` ≥ DECLINE_MIN_SPAN_DAYS). Sinon on rétrograde en amber
    (« déclin soupçonné ») : pour un outil qui dit « non », un faux rouge coûte
    plus cher qu'un amber prudent.
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
        proven = (_slope_is_significant(demand_velocity, demand_velocity_se, demand_points)
                  and demand_span_days is not None
                  and demand_span_days >= DECLINE_MIN_SPAN_DAYS)
        if proven:
            return LossFlag("déclin", "red",
                            f"demande en chute (~{pct:.0f}%/mois) — tendance qui meurt, "
                            "tu arrives trop tard")
        return LossFlag("déclin", "amber",
                        f"déclin soupçonné (~{pct:.0f}%/mois) mais non confirmé "
                        "(série trop courte ou pente non significative)")
    if monthly <= DECLINE_AMBER:
        return LossFlag("déclin", "amber",
                        f"demande en repli (~{pct:.0f}%/mois) — momentum qui s'essouffle")
    if monthly > 1.0:    # >+100 %/mois : afficher proprement, sans nombre absurde
        return LossFlag("déclin", "green", "demande en forte hausse")
    return LossFlag("déclin", "green",
                    f"demande stable/en hausse (~{pct:+.0f}%/mois)")


def _demand_flag(demand_level: float | None) -> LossFlag:
    """Demande RÉELLE via Amazon « bought in past month » (achats/mois mesurés).

    C'est le signal POSITIF du verdict : un « viable » + demande prouvée est un vrai
    feu vert, pas une simple absence de drapeau rouge. Couverture large (~4900
    mots-clés) — bien meilleure que les avis ou les ventes AliExpress.

    Loss-framed : JAMAIS rouge (ne pas avoir de demande prouvée n'est pas une perte
    certaine). None = non mesuré (« inconnu », n'altère pas le verdict mais baisse
    la couverture) ; 0/faible = amber ; au-dessus du seuil = green.
    """
    if demand_level is None:
        return LossFlag("demande", "unknown", "demande Amazon non mesurée")
    lvl = int(demand_level)
    if lvl <= 0:
        return LossFlag("demande", "amber",
                        "aucun achat Amazon mesuré — demande non prouvée")
    if lvl < DEMAND_PROVEN:
        return LossFlag("demande", "amber",
                        f"demande faible (~{lvl} achats/mois sur Amazon)")
    return LossFlag("demande", "green",
                    f"demande prouvée (~{lvl} achats/mois sur Amazon)")


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
    demand_level: float | None = None,
    demand_velocity: float | None = None,
    demand_points: int = 0,
    demand_volatility: float | None = None,
    demand_velocity_se: float | None = None,
    demand_span_days: float | None = None,
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
        _demand_flag(demand_level),
        _return_flag(pct_low_rating),
        _saturation_flag(listed_num),
        _decline_flag(demand_velocity, demand_points, demand_volatility,
                      demand_velocity_se, demand_span_days),
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

    measured = sum(1 for f in flags if f.level != "unknown")
    return LossRiskResult(
        product_id=product_id,
        verdict=verdict,
        headline=headline,
        flags=flags,
        breakeven_cpa_eur=gross_margin_eur,
        coverage_measured=measured,
        coverage_total=len(flags),
    )
