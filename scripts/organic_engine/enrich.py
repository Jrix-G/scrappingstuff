"""Enrichissement organique — croise vendabilité CJ + vélocité de demande réelle.

Prend les meilleurs produits vendables (``analyze.py``), en dérive un mot-clé de
recherche, récupère la série Google Trends (et Reddit si configuré), puis fait tourner
le MOTEUR D'ACCÉLÉRATION (``scoring/engine.py``) pour mesurer la vélocité/accélération
RÉELLE de la demande — sans attendre l'historique de snapshots CJ.

Le résultat fusionne deux questions :
  • « ça se vend ? »      → vendabilité (marge, prix, saturation)
  • « ça décolle ? »      → momentum organique (Google Trends / Reddit)

Usage :
    python3 enrich.py --top 6                 # enrichit les 6 meilleurs BUY
    python3 enrich.py --keyword "portable blender"   # un mot-clé précis
    python3 enrich.py --geo FR --top 5

Dépendances live : pytrends (Google Trends), praw (Reddit, optionnel).
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze import analyze
from collectors.google_trends import trends_raw_signal, TrendsError
from collectors.reddit_mentions import reddit_raw_signal
from signals.features import build_product_features, RawSignal
from signals.timeseries import extract_trend
from scoring.engine import score_population

# Mots vides fréquents dans les titres CJ -> bruit pour un mot-clé de recherche.
_STOP = {
    "for", "with", "the", "and", "use", "set", "pcs", "pc", "1pc", "mini", "new",
    "of", "to", "in", "a", "an", "portable", "multifunctional", "versatile",
    "professional", "high", "quick", "soft", "outdoor", "indoor", "home", "kids",
    "men", "women", "womens", "mens", "small", "large", "quiet", "rechargeable",
    "plus", "size", "style", "fashion", "fashionable", "casual", "premium",
}

# Séparateurs qui introduisent la partie DÉCORATIVE d'un titre CJ (couleur, motif,
# specs) : le cœur du produit est AVANT eux. Ex. « Swimsuit With Palm Tree Print ».
_SPLIT_TOKENS = {"with", "for"}

# Jeton d'unité/mesure (nombre + suffixe éventuel) : bruit pur. Ex. 7200mah, 50mm.
_UNIT_RE = re.compile(r"^\d+(\.\d+)?(mah|mm|cm|ml|kg|g|w|v|in|inch|ft|m|l|oz|pcs|pc|x)?$")


def _stem(t: str) -> str:
    """Radical grossier pour comparer singulier/pluriel (« visors » ≈ « visor »)."""
    return t[:-1] if len(t) > 4 and t.endswith("s") else t


def _significant_tokens(name: str, *, drop_short: bool) -> list[str]:
    """Groupe principal d'un titre CJ → tokens signifiants, dédupliqués.

    Étapes : coupe la queue décorative (1re virgule / séparateur ``with``/``for``),
    retire mots vides, nombres purs et unités, puis (option) les fragments d'une
    seule lettre (« s witch » → « witch »), et enfin DÉDUPLIQUE les radicaux
    consécutifs (« pants pants » → « pants », « visors visor » → « visors »).
    """
    raw = (name or "").strip()
    if not raw:
        return []
    head = raw.split(",")[0]
    tokens: list[str] = []
    for tok in head.lower().split():
        t = tok.strip(",.;:()/-")
        if t in _SPLIT_TOKENS:
            break  # tout ce qui suit décrit (couleur, motif…), pas le produit
        tokens.append(t)
    kept = [t for t in tokens
            if t and t not in _STOP and not t.isdigit() and not _UNIT_RE.match(t)
            and (len(t) > 1 if drop_short else True)]
    # Déduplique les radicaux consécutifs : un titre CJ répète souvent la tête
    # nominale (« Beach Pants Casual Pants ») ; sans ça le mot-clé devient
    # « pants pants », qui ne matche rien et gâche le scrape.
    out: list[str] = []
    for t in kept:
        if out and _stem(out[-1]) == _stem(t):
            continue
        out.append(t)
    return out


def keyword_from_name(name: str, n_words: int = 2) -> str:
    """Dérive un mot-clé de recherche PROPRE depuis un titre produit CJ.

    Les titres CJ suivent le schéma « [adjectifs] NOM-PRODUIT[, ou 'with'] décoration » :
    la tête nominale (ce qu'on veut réellement chercher sur Trends/Reddit) est à la
    FIN du groupe principal, pas au début. On isole donc le groupe principal (avant
    la 1re virgule ou un séparateur décoratif) puis on garde ses derniers mots
    signifiants. Ex. « Mens Fashionable Casual Breathable Beach Sandals » → « beach
    sandals » (et non « fashionable casual breathable », qui ne matche rien).

    Nettoyage anti-bruit (vs ancienne version buguée) : radicaux dupliqués
    consécutifs supprimés (« pants pants » → « pants »), fragments d'une seule
    lettre supprimés (« s witch » → « witch »).
    """
    raw = (name or "").strip()
    if not raw:
        return ""
    kept = _significant_tokens(raw, drop_short=True)
    if not kept:
        return raw[:30].lower()
    # Tête nominale = les derniers mots signifiants du groupe principal.
    return " ".join(kept[-n_words:])


def _legacy_keyword_from_name(name: str, n_words: int = 2) -> str:
    """Ancienne dérivation (sans nettoyage) — UNIQUEMENT pour ré-aligner la jointure.

    Les snapshots de demande déjà en base ont été indexés avec CETTE logique
    (``vpn_warmer._keyword``). On la garde comme clé de repli pour ne PERDRE aucun
    match historique quand on joint la demande (cf. ``keyword_candidates``).
    """
    raw = (name or "").strip()
    if not raw:
        return ""
    head = raw.split(",")[0]
    tokens: list[str] = []
    for tok in head.lower().split():
        t = tok.strip(",.;:()/-")
        if t in _SPLIT_TOKENS:
            break
        tokens.append(t)
    kept = [t for t in tokens
            if t and t not in _STOP and not t.isdigit() and not _UNIT_RE.match(t)]
    return " ".join(kept[-n_words:]) if kept else raw[:30].lower()


def keyword_candidates(name: str, n_words: int = 2) -> list[str]:
    """Clés de jointure demande pour un produit : mot-clé propre + repli historique.

    Lecture DB pure côté appelant : on essaie d'abord le mot-clé NETTOYÉ
    (``keyword_from_name``), puis l'ancienne clé (``_legacy_keyword_from_name``)
    pour récupérer les snapshots indexés avant le correctif. Garantit une
    couverture ≥ à chacune des deux logiques prise seule. Ordre = priorité.
    """
    out: list[str] = []
    for k in (keyword_from_name(name, n_words), _legacy_keyword_from_name(name, n_words)):
        if k and k not in out:
            out.append(k)
    return out


def enrich(keywords_and_meta: list[dict], geo: str, delay: float) -> list[dict]:
    """Pour chaque produit, croise demande live (Trends/Reddit) et demande marché.

    Les séries eBay (annonces actives) et AliExpress (ventes) sont relues depuis
    l'historique de snapshots (``collect_demand.py``) : plus il y a de jours de
    collecte, plus leur vélocité pèse dans le scoring.
    """
    from collect_demand import init_db as demand_db, demand_raw_signals
    conn = demand_db()
    try:
        population = []
        index = {}
        for i, rec in enumerate(keywords_and_meta):
            kw = rec["keyword"]
            print(f"  [{i+1}/{len(keywords_and_meta)}] « {kw} » → Trends + Reddit + marché ...", flush=True)
            # Sources INDÉPENDANTES : leur accord active la corroboration du moteur.
            trends_sig: RawSignal = trends_raw_signal(kw, geo=geo)
            reddit_sig: RawSignal = reddit_raw_signal(kw)
            raws = [s for s in (trends_sig, reddit_sig) if s.values]
            # Historique demande marché (eBay/AliExpress) si déjà snapshoté ≥2 fois.
            raws += demand_raw_signals(conn, kw)
            pf = build_product_features(
                rec["product_id"], raws,
                age_days=rec.get("age_days"),
                seller_count=rec.get("listed_num"),
            )
            population.append(pf)
            index[rec["product_id"]] = rec
            time.sleep(delay)  # politesse anti rate-limit Google
    finally:
        conn.close()

    results = score_population(population)
    merged = []
    for r in results:
        rec = index[r.product_id]
        tf = None
        merged.append({
            **rec,
            "organic_score": round(r.organic_score, 1),
            "phase": r.phase.value,
            "monthly_growth": round(r.monthly_growth, 3),
            "confidence": round(r.confidence, 3),
            "reasons": r.top_reasons(),
        })
    merged.sort(key=lambda x: x["organic_score"], reverse=True)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrichissement organique (Trends/Reddit)")
    parser.add_argument("--top", type=int, default=6)
    parser.add_argument("--keyword", type=str, default=None)
    parser.add_argument("--geo", type=str, default="", help="Code pays Trends (ex. FR), vide = monde")
    parser.add_argument("--delay", type=float, default=2.0, help="Délai anti rate-limit (s)")
    args = parser.parse_args()

    if args.keyword:
        # Mode mot-clé unique : démonstration directe des dynamiques réelles.
        print(f"\nGoogle Trends « {args.keyword} » (geo={args.geo or 'monde'}) ...")
        try:
            from collectors.google_trends import fetch_interest
            ts, vals, meta = fetch_interest(args.keyword, geo=args.geo)
        except TrendsError as exc:
            print(f"✗ {exc}")
            return
        if not vals:
            print("Aucune donnée Trends.")
            return
        tf = extract_trend(ts, vals)
        print(f"\n  ─ Google Trends")
        print(f"    Points          : {meta['points']} (sur {meta['timeframe']})")
        print(f"    Intérêt actuel  : {vals[-1]:.0f}/100  (pic {max(vals):.0f})")
        print(f"    Vélocité        : {tf.velocity:+.4f} log/j")
        print(f"    Croissance/mois : {tf.monthly_growth*100:+.1f}%")
        print(f"    Accélération    : {tf.acceleration:+.5f}  ({'EXPLOSE' if tf.acceleration>0 else 'ralentit'})")
        print(f"    Fiabilité (R²)  : {tf.r2:.2f}")

        from collectors.reddit_mentions import fetch_mentions, RedditError
        print(f"\n  ─ Reddit (mentions organiques)")
        try:
            rts, rvals, rmeta = fetch_mentions(args.keyword)
            if rvals:
                rtf = extract_trend(rts, rvals)
                print(f"    Mentions gardées : {rmeta['posts_kept']} sur {len(rvals)} semaines")
                print(f"    Croissance/mois  : {rtf.monthly_growth*100:+.1f}%")
            else:
                print(f"    Aucune mention pertinente.")
        except RedditError as exc:
            print(f"    indisponible : {exc}")
        return

    records = analyze(__import__("datetime").datetime.now().month)
    if not records:
        return
    buys = [r for r in records if r["verdict"] == "BUY"][: args.top]
    for r in buys:
        r["keyword"] = keyword_from_name(r["name"])

    print(f"\nEnrichissement de {len(buys)} produits BUY avec la demande réelle (Google Trends)\n")
    merged = enrich(buys, args.geo, args.delay)

    print(f"\n{'='*82}")
    print(f"  PRODUITS VENDABLES × DEMANDE QUI DÉCOLLE")
    print(f"{'='*82}")
    print(f"  {'ORG':>4} {'PHASE':<12} {'CROIS/M':>8} {'VEND':>5} {'MARGE€':>7}  MOT-CLÉ / PRODUIT")
    print(f"  {'-'*78}")
    for m in merged:
        print(f"  {m['organic_score']:>4.0f} {m['phase']:<12} "
              f"{m['monthly_growth']*100:>+7.0f}% {m['sellability']:>5.0f} "
              f"{m['gross_margin_eur']:>7.1f}  {m['keyword']}  ·  {(m['name'] or '')[:32]}")


if __name__ == "__main__":
    main()
