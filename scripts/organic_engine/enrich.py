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
}


def keyword_from_name(name: str, n_words: int = 3) -> str:
    """Dérive un mot-clé de recherche court et signifiant depuis un titre produit."""
    tokens = [t.strip(",.;:()").lower() for t in (name or "").split()]
    kept = [t for t in tokens if t and t not in _STOP and not t.isdigit()]
    return " ".join(kept[:n_words]) if kept else (name or "")[:30]


def enrich(keywords_and_meta: list[dict], geo: str, delay: float) -> list[dict]:
    """Pour chaque produit, récupère Trends, calcule les dynamiques réelles."""
    population = []
    index = {}
    for i, rec in enumerate(keywords_and_meta):
        kw = rec["keyword"]
        print(f"  [{i+1}/{len(keywords_and_meta)}] « {kw} » → Google Trends + Reddit ...", flush=True)
        # Deux sources INDÉPENDANTES : leur accord active la corroboration du moteur.
        trends_sig: RawSignal = trends_raw_signal(kw, geo=geo)
        reddit_sig: RawSignal = reddit_raw_signal(kw)
        raws = [s for s in (trends_sig, reddit_sig) if s.values]
        pf = build_product_features(
            rec["product_id"], raws,
            age_days=rec.get("age_days"),
            seller_count=rec.get("listed_num"),
        )
        population.append(pf)
        index[rec["product_id"]] = rec
        time.sleep(delay)  # politesse anti rate-limit Google

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
