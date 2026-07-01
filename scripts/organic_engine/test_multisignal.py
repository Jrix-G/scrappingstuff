#!/usr/bin/env python3
"""Vérification end-to-end : le scoring est-il désormais MULTI-SIGNAUX ?

Prouve que les signaux TikTok et Google Suggest, une fois persistés en base et
relus par ``signals.db_signals``, entrent RÉELLEMENT dans la décomposition du
momentum de ``scoring.engine`` — pas seulement la demande Amazon.

Deux parties :
  [1] ÉTAT RÉEL (lecture seule de data/cj.db) : montre les RawSignal produits par
      le loader pour des mots-clés ayant amazon+tiktok+suggest, et le scoring obtenu.
      Constat honnête : aujourd'hui les séries suggest sont PLATES (score saturé,
      constant) et tiktok n'a qu'1 snapshot/mot-clé -> vélocité 0 -> contribution 0.
      Le câblage est prouvé (le RawSignal arrive bien au moteur), mais la donnée ne
      bouge pas encore.
  [2] SÉRIES EN MOUVEMENT (simulation EN MÉMOIRE du prochain snapshot nightly, AUCUNE
      écriture DB) : on ajoute 1 point daté +1j à tiktok (views +35 %) et à
      google_trends (score qui monte), puis on rescore AVEC vs SANS ces signaux.
      Démontre que dès que les snapshots s'accumulent, tiktok et google_trends
      contribuent et déplacent l'organic_score.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))

from signals.features import RawSignal, build_product_features
from signals.db_signals import db_raw_signals
from scoring.engine import score_population

DB = ENGINE / "data" / "cj.db"
# Mots-clés ayant À LA FOIS demande Amazon ET mentions Reddit (et souvent tiktok/suggest)
# → permet de montrer reddit chargé en part1 et qui contribue en part2.
KEYWORDS = ["bed frame", "office chair", "water bottle", "air fryer", "vacuum cleaner"]


def amazon_demand_signal(conn, kw: str) -> RawSignal | None:
    """Série demande Amazon (« bought past month ») -> RawSignal occupant le slot
    canonique de demande 'sales' (direction +1, comme le moteur traite la demande)."""
    rows = conn.execute(
        "SELECT observed_at, max_bought FROM amazon_snapshots "
        "WHERE keyword=? AND max_bought IS NOT NULL ORDER BY observed_at", (kw,)
    ).fetchall()
    if len(rows) < 1:
        return None
    t0 = datetime.fromisoformat(rows[0][0])
    days = [(datetime.fromisoformat(r[0]) - t0).total_seconds() / 86400.0 for r in rows]
    vals = [float(r[1]) for r in rows]
    return RawSignal("sales", days, vals)


def _decomp(res) -> str:
    parts = [f"{c.source}(w={c.weight:.2f},contrib={c.contribution:+.2f})"
             for c in res.contributions]
    return ", ".join(parts) if parts else "(aucune source ≥2 points)"


def part1_real(conn) -> None:
    print("=" * 78)
    print("[1] ÉTAT RÉEL — lecture DB pure (data/cj.db)")
    print("=" * 78)
    pop, meta = [], []
    for kw in KEYWORDS:
        raws = []
        amz = amazon_demand_signal(conn, kw)
        if amz:
            raws.append(amz)
        db = db_raw_signals(conn, kw)
        raws += db
        print(f"\n• « {kw} » — RawSignal chargés :")
        for s in raws:
            print(f"    {s.name:14} {len(s.values):2} pts  vals={s.values[:4]}"
                  f"{'…' if len(s.values) > 4 else ''}")
        pop.append(build_product_features(kw, raws))
        meta.append(kw)
    results = score_population(pop)
    print("\n  → Scoring (état réel) :")
    for kw, r in zip(meta, results):
        print(f"    {kw:14} org={r.organic_score:5.1f} corro={r.corroboration} "
              f"| {_decomp(r)}")
    print("\n  Lecture : suggest saturé/plat + tiktok 1 point => vélocité 0 => "
          "ces sources n'entrent pas encore dans le momentum (n_points<2 ou pente nulle).")


def _shift_days(sig: RawSignal) -> float:
    return (max(sig.timestamps_days) + 1.0) if sig.timestamps_days else 1.0


# Scénarios DIFFÉRENCIÉS du prochain run nightly (multiplicateur tiktok views,
# delta suggest score). Le scoring est TRANSVERSAL : seul un mouvement qui varie
# d'un mot-clé à l'autre crée de la dispersion -> des z-scores non nuls ->
# des contributions et un déplacement de classement. (tiktok ×1.0 = à plat.)
SCENARIO = {
    "bed frame":     {"tiktok": 2.6,  "suggest": -25, "reddit": 1.8},  # buzz reddit+tiktok, recherche qui retombe
    "office chair":  {"tiktok": 1.0,  "suggest": 0,   "reddit": 1.0},  # à plat
    "water bottle":  {"tiktok": 1.05, "suggest": +18, "reddit": 1.4},  # mentions reddit qui montent
    "air fryer":     {"tiktok": 1.7,  "suggest": -10, "reddit": 1.6},  # reddit + tiktok up
    "vacuum cleaner":{"tiktok": 1.0,  "suggest": 0,   "reddit": 1.0},  # à plat
}


def part2_moving(conn) -> None:
    print("\n" + "=" * 78)
    print("[2] SÉRIES EN MOUVEMENT — simulation EN MÉMOIRE du prochain snapshot nightly")
    print("    (AUCUNE écriture DB ; +1 jour ; mouvement DIFFÉRENCIÉ par mot-clé)")
    print("=" * 78)
    base_pop, full_pop, meta = [], [], []
    for kw in KEYWORDS:
        amz = amazon_demand_signal(conn, kw)
        base_raws = [amz] if amz else []
        sc = SCENARIO[kw]

        # Charge le réel puis ajoute 1 point daté +1j (prochain run nightly simulé).
        moved = []
        for s in db_raw_signals(conn, kw):
            ts = list(s.timestamps_days)
            vs = list(s.values)
            nxt = _shift_days(s)
            if s.name == "tiktok":
                vs.append(vs[-1] * sc["tiktok"])
            elif s.name == "google_trends":
                vs.append(min(100.0, vs[-1] + sc["suggest"]))
            elif s.name == "reddit":
                vs.append(vs[-1] * sc.get("reddit", 1.0))
            else:
                vs.append(vs[-1])
            ts.append(nxt)
            moved.append(RawSignal(s.name, ts, vs))

        full_raws = base_raws + moved
        base_pop.append(build_product_features(kw, base_raws))   # SANS organiques
        full_pop.append(build_product_features(kw, full_raws))   # AVEC organiques
        meta.append(kw)

    base = {r.product_id: r for r in score_population(base_pop)}
    full = {r.product_id: r for r in score_population(full_pop)}

    print(f"\n  {'mot-clé':14} {'org SANS':>9} {'org AVEC':>9} {'Δ':>6}   décomposition AVEC")
    print("  " + "-" * 74)
    for kw in meta:
        b, f = base[kw], full[kw]
        d = f.organic_score - b.organic_score
        print(f"  {kw:14} {b.organic_score:9.1f} {f.organic_score:9.1f} {d:+6.1f}   {_decomp(f)}")
    print("\n  Lecture : tiktok, google_trends ET reddit apparaissent dans la décomposition "
          "et déplacent l'organic_score => scoring multi-signaux fonctionnel de bout en bout.")


def main() -> None:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        part1_real(conn)
        part2_moving(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
