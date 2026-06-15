"""Analyse de vendabilité du catalogue CJ — opérationnelle dès le 1er snapshot.

Combine, pour chaque produit en base :
  • vendabilité financière (marge nette après CPA, prix, saturation, fraîcheur)
  • saisonnalité (le mois courant est-il porteur pour ce produit ?)

Produit un **score composite final** = vendabilité × multiplicateur saisonnier (borné),
classe le catalogue, affiche le top + un exemple détaillé, et exporte un JSON consommable
par le frontend.

Usage :
    python3 analyze.py                 # top 20 + meilleur exemple détaillé
    python3 analyze.py --top 50
    python3 analyze.py --verdict BUY    # ne garde que les BUY
    python3 analyze.py --export out.json
    python3 analyze.py --month 7        # forcer un mois (test saisonnalité)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scoring.sellability import score_sellability, SellabilityResult
from signals.seasonality import seasonality_for

DB_PATH = Path(__file__).resolve().parent / "data" / "cj.db"
# Le multiplicateur saisonnier est borné pour ne pas écraser la vendabilité.
_SEASON_CLAMP = (0.6, 1.4)


def _age_days(create_time: str | None) -> float | None:
    """Âge en jours. CJ renvoie un epoch en MILLISECONDES (ex. 1781263470000)."""
    if not create_time:
        return None
    s = str(create_time).strip()
    now = datetime.now(timezone.utc)
    if s.isdigit():
        ts = int(s)
        if ts > 10_000_000_000:  # millisecondes
            ts /= 1000.0
        try:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return (now - dt).total_seconds() / 86400.0
        except (ValueError, OSError, OverflowError):
            return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:19], fmt).replace(tzinfo=timezone.utc)
            return (now - dt).total_seconds() / 86400.0
        except ValueError:
            continue
    return None


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def analyze(month: int) -> list[dict]:
    """Charge la base, calcule vendabilité × saisonnalité, renvoie une liste classée."""
    if not DB_PATH.exists():
        print(f"Base introuvable : {DB_PATH}")
        print("→ Lance d'abord `python3 collect_cj.py --pages 20` (CJ_EMAIL/CJ_API_KEY requis).")
        return []

    conn = sqlite3.connect(DB_PATH)
    # Dernier snapshot connu de chaque produit (prix + vendeurs les plus récents),
    # enrichi du dossier qualitatif (cj_details) quand il est disponible.
    rows = conn.execute(
        """
        SELECT p.pid, p.name, p.category, p.image, p.create_time,
               s.price, s.listed_num,
               d.suggest_price, d.description, d.video, d.images,
               d.variants, d.material, d.weight, d.supplier
        FROM cj_products p
        JOIN cj_snapshots s ON s.pid = p.pid
        JOIN (SELECT pid, MAX(observed_at) AS mx FROM cj_snapshots GROUP BY pid) last
             ON last.pid = s.pid AND last.mx = s.observed_at
        LEFT JOIN cj_details d ON d.pid = p.pid
        """
    ).fetchall()
    conn.close()

    out: list[dict] = []
    for (pid, name, category, image, create_time, price, listed_num,
         suggest_price, description, video, images,
         variants, material, weight, supplier) in rows:
        age = _age_days(create_time)
        sell: SellabilityResult = score_sellability(
            product_id=pid, cost_eur=price, listed_num=listed_num, age_days=age,
            retail_override=suggest_price,
        )
        season = seasonality_for(f"{name or ''} {category or ''}", month)
        season_factor = _clamp(season.multiplier, *_SEASON_CLAMP)
        # La vendabilité (0–100) reste le score honnête ; la saisonnalité est un
        # multiplicateur de tri (en saison la pousse, hors saison la rétrograde).
        final = sell.sellability * season_factor

        rec = sell.as_dict()
        rec.update({
            "name": name,
            "category": category,
            "image": image,
            "age_days": round(age, 1) if age is not None else None,
            "listed_num": listed_num,
            "seasonality": season.as_dict(),
            "season_factor": round(season_factor, 2),
            "rank_score": round(final, 1),
            # Dossier qualitatif (None tant que le produit n'a pas été re-photographié).
            "suggest_price_eur": round(suggest_price, 2) if suggest_price else None,
            "description": description,
            "video": video,
            "images": images,
            "variants": variants,
            "material": material,
            "weight_g": weight,
            "supplier": supplier,
            "has_detail": bool(suggest_price or description or supplier),
        })
        out.append(rec)

    out.sort(key=lambda r: r["rank_score"], reverse=True)
    return out


def print_top(records: list[dict], top: int, verdict: str | None) -> None:
    filtered = [r for r in records if verdict is None or r["verdict"] == verdict]
    n_buy = sum(1 for r in records if r["verdict"] == "BUY")
    n_watch = sum(1 for r in records if r["verdict"] == "WATCH")
    print(f"\n{'='*78}")
    print(f"  ANALYSE DE VENDABILITÉ — {len(records)} produits  "
          f"| BUY: {n_buy}  WATCH: {n_watch}  PASS: {len(records)-n_buy-n_watch}")
    print(f"{'='*78}")
    print(f"  {'VEND':>5} {'×SAIS':>5} {'VERDICT':<8} {'MARGE€':>7} {'PRIX':>6} {'#V':>4}  PRODUIT")
    print(f"  {'-'*74}")
    for r in filtered[:top]:
        print(f"  {r['sellability']:>5.0f} {r['season_factor']:>5.2f} {r['verdict']:<8} "
              f"{r['gross_margin_eur']:>7.1f} {r['retail_eur']:>6.1f} "
              f"{str(r['listed_num']):>4}  {(r['name'] or '')[:42]}")


def print_example(records: list[dict]) -> None:
    """Affiche en détail le meilleur produit BUY (ou le top si aucun BUY)."""
    buys = [r for r in records if r["verdict"] == "BUY"]
    target = buys[0] if buys else (records[0] if records else None)
    if not target:
        return
    s = target
    print(f"\n{'='*78}")
    print(f"  EXEMPLE DÉTAILLÉ — pourquoi ce produit ?")
    print(f"{'='*78}")
    print(f"  Produit    : {s['name']}")
    print(f"  Catégorie  : {s['category']}")
    print(f"  Verdict    : {s['verdict']}   (vendabilité {s['sellability']}/100 "
          f"× saison {s['season_factor']} → tri {s['rank_score']})")
    print(f"  ─ Économie")
    print(f"    Coût CJ           : {s['cost_eur']:.2f} €")
    print(f"    Retail estimé     : {s['retail_eur']:.2f} €")
    print(f"    Marge brute       : {s['gross_margin_eur']:.2f} €  ({s['margin_pct']*100:.0f}%)")
    print(f"    Net après ~CPA    : {s['net_after_cpa_eur']:.2f} € / vente")
    print(f"  ─ Marché")
    print(f"    Vendeurs (CJ)     : {s['listed_num']}  (saturation {s['scores']['saturation']:.2f})")
    print(f"    Âge produit       : {s['age_days']} j  (fraîcheur {s['scores']['freshness']:.2f})")
    print(f"    Saisonnalité      : {s['seasonality']['label']}")
    print(f"  ─ Verdict")
    print(f"    {s['reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse de vendabilité du catalogue CJ")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--verdict", type=str, default=None, choices=["BUY", "WATCH", "PASS"])
    parser.add_argument("--month", type=int, default=None, help="Mois 1–12 (défaut: mois courant)")
    parser.add_argument("--export", type=str, default=None, help="Chemin JSON de sortie")
    args = parser.parse_args()

    month = args.month or datetime.now(timezone.utc).month
    records = analyze(month)
    if not records:
        return

    print_top(records, args.top, args.verdict)
    print_example(records)

    if args.export:
        Path(args.export).write_text(json.dumps(records, ensure_ascii=False, indent=2))
        print(f"\n  ✓ Export JSON : {args.export} ({len(records)} produits)")


if __name__ == "__main__":
    main()
