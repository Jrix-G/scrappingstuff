"""Rapport Loss Risk sur tout le catalogue + analyse de vendabilité.

Joint : produit CJ -> coût/saturation/âge (cj_snapshots) -> verdict de marge
(scoring.sellability) -> note médiane Amazon par mot-clé (amazon_snapshots, proxy
risque de retour) -> verdict TRAP/RISKY/VIABLE (scoring.loss_risk).

Sortie : distribution des verdicts + drapeaux dominants + exemples. Lecture seule.
"""
from __future__ import annotations
import sqlite3
from collections import Counter
from enrich import keyword_from_name
from analyze import _age_days
from scoring.sellability import score_sellability
from scoring.loss_risk import assess_loss_risk
import demand_queue as dq


def build():
    c = dq.connect()
    # part de produits mal notés par mot-clé (dernier snapshot non nul)
    rating = {}
    for kw, plr, ts in c.execute(
        "SELECT keyword, pct_low_rating, observed_at FROM amazon_snapshots "
        "WHERE pct_low_rating IS NOT NULL"):
        if kw not in rating or ts > rating[kw][1]:
            rating[kw] = (plr, ts)

    rows = c.execute(
        """SELECT p.pid, p.name, p.create_time, s.price, s.listed_num, d.suggest_price
             FROM cj_products p
             JOIN cj_snapshots s ON s.pid = p.pid
             JOIN (SELECT pid, MAX(observed_at) mx FROM cj_snapshots GROUP BY pid) last
               ON last.pid = p.pid AND last.mx = s.observed_at
             LEFT JOIN cj_details d ON d.pid = p.pid""").fetchall()

    out = []
    for pid, name, ctime, price, listed_num, suggest in rows:
        sell = score_sellability(pid, cost_eur=price, listed_num=listed_num,
                                 age_days=_age_days(ctime), retail_override=suggest)
        kw = keyword_from_name(name or "")
        pct_low = rating.get(kw, (None,))[0]
        lr = assess_loss_risk(
            product_id=pid,
            net_after_cpa_eur=sell.net_after_cpa_eur,
            gross_margin_eur=sell.gross_margin_eur,
            pct_low_rating=pct_low,
            listed_num=listed_num,
            retail_eur=sell.retail_eur,
        )
        out.append({"name": name, "kw": kw, "rating": pct_low,
                    "net": sell.net_after_cpa_eur, "listed": listed_num,
                    "verdict": lr.verdict, "headline": lr.headline,
                    "flags": lr.flags})
    return out


def main():
    rec = build()
    n = len(rec)
    vc = Counter(r["verdict"] for r in rec)
    print(f"=== CATALOGUE : {n} produits ===")
    for v in ("TRAP", "RISKY", "VIABLE"):
        print(f"  {v:7} {vc.get(v,0):5d}  ({100*vc.get(v,0)//n}%)")

    # couverture du proxy retour
    with_rating = sum(1 for r in rec if r["rating"] is not None)
    print(f"\nproduits avec note (proxy retour): {with_rating} ({100*with_rating//n}%)")

    # drapeaux rouges dominants parmi les TRAP
    red_by = Counter()
    for r in rec:
        for f in r["flags"]:
            if f.level == "red":
                red_by[f.name] += 1
    print("drapeaux ROUGES (toutes causes de piège):", dict(red_by))

    def show(title, verdict, key=None, rev=True, k=6):
        sub = [r for r in rec if r["verdict"] == verdict]
        if key:
            sub = sorted(sub, key=key, reverse=rev)
        print(f"\n--- {title} ({len(sub)}) ---")
        for r in sub[:k]:
            rt = f"{r['rating']*100:.0f}%" if r["rating"] is not None else "—"
            print(f"  net={str(round(r['net']) if r['net'] is not None else '?'):>4}€ "
                  f"bad<4★={rt:>4} vend={r['listed']:>2}  {(r['name'] or '')[:36]:36} | {r['headline'][:58]}")

    show("Exemples PIÈGES (pire marge)", "TRAP", key=lambda r: r["net"] or 0, rev=False)
    show("Exemples VIABLES (meilleure marge)", "VIABLE", key=lambda r: r["net"] or 0, rev=True)


if __name__ == "__main__":
    main()
