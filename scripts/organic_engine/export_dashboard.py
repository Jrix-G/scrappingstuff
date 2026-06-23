"""Exporte les vraies données vers le dashboard React (forme `BASE` attendue par l'UI).

Lit `cj.db` (analyse vendabilité réelle), enrichit le top N avec Google Trends + Reddit
réels (vélocité, accélération, phase, confiance), mappe les catégories CJ libres vers les
buckets du dashboard, et écrit `frontend/src/dashboard/products.json`.

Usage :
    python3 export_dashboard.py --limit 12            # top 12, enrichi Trends+Reddit
    python3 export_dashboard.py --limit 12 --no-enrich  # rapide, sans appels réseau
    python3 export_dashboard.py --geo FR
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from analyze import analyze
from enrich import keyword_from_name
from collectors.google_trends import trends_raw_signal
from collectors.reddit_mentions import reddit_raw_signal
from signals.features import build_product_features
from scoring.engine import score_population
from scoring.loss_risk import assess_loss_risk

OUT = ROOT.parent.parent / "frontend" / "src" / "dashboard" / "products.json"
# Cache servi par l'API (forme {meta, products}) — source de vérité côté Pi.
CACHE = ROOT / "data" / "dashboard_export.json"

# Catégories CJ libres -> buckets du dashboard (hue + i18n gérés côté UI).
CAT_BUCKETS = {
    "WELLNESS": ["massage", "neck", "health", "care", "relief", "posture", "wellness"],
    "HOME": ["home", "storage", "light", "lamp", "decor", "kitchen storage", "cleaning",
             "organizer", "bedside"],
    "TECH": ["phone", "charger", "power", "usb", "electronic", "gadget", "cable", "led",
             "solar", "bluetooth", "printer"],
    "BEAUTY": ["beauty", "hair", "makeup", "skin", "nail", "gua sha", "curl", "cosmetic"],
    "PETS": ["pet", "dog", "cat", "animal"],
    "OUTDOOR": ["outdoor", "camp", "garden", "travel", "hiking", "bottle", "picnic",
                "backpack", "chair", "fishing"],
    "KITCHEN": ["kitchen", "cook", "drink", "cup", "mug", "bottle opener", "spice",
                "cutlery", "coffee"],
    "FITNESS": ["fitness", "gym", "yoga", "training", "sport", "workout", "muscle"],
    "APPAREL": ["shoe", "sock", "cloth", "wear", "dress", "pant", "shirt", "slipper",
                "bag", "lint", "vest", "gown"],
    "BABY": ["baby", "kid", "child", "infant", "bib"],
}


def map_category(name: str, category: str) -> str:
    """Choisit le bucket dashboard dont un mot-clé matche le nom/catégorie."""
    h = f"{name or ''} {category or ''}".lower()
    for bucket, kws in CAT_BUCKETS.items():
        if any(k in h for k in kws):
            return bucket
    return "HOME"  # repli neutre


def z_to_100(z: float) -> int:
    """Re-mappe un z-score (~[-2,2]) vers 0..100 pour l'affichage par source."""
    return int(max(0, min(100, round((z + 2.0) / 4.0 * 100))))


def _series_block(rows: list[tuple]) -> dict | None:
    """(observed_at, valeur) triés -> bloc série pour le front, ou ``None``.

    Règle dure (moat = transparence vérifiable) : moins de 2 snapshots réels
    => ``None``, JAMAIS de courbe fabriquée ni de remplissage neutre.
    """
    rows = [(t, v) for t, v in rows if v is not None]
    if len(rows) < 2:
        return None
    t0 = datetime.fromisoformat(rows[0][0])
    dates = [t for t, _ in rows]
    days = [round((datetime.fromisoformat(t) - t0).total_seconds() / 86400.0, 3)
            for t, _ in rows]
    vals = [float(v) for _, v in rows]
    return {"points": len(rows), "dates": dates, "days": days,
            "values": vals, "spanDays": days[-1]}


def _demand_history(conn, keyword: str) -> dict:
    """Historique RÉEL de demande pour un mot-clé : ventes AliExpress + « bought » Amazon.

    Lecture DB pure (aucun appel réseau). Chaque série vaut ``None`` tant qu'il
    n'y a pas ≥2 snapshots. Amazon (« bought in past month ») couvre bien plus de
    produits que les ventes AliExpress et est notre meilleur signal de demande.
    """
    sales = conn.execute(
        "SELECT observed_at, max_sold FROM sales_snapshots "
        "WHERE keyword=? AND max_sold IS NOT NULL ORDER BY observed_at",
        (keyword,),
    ).fetchall()
    amazon = conn.execute(
        "SELECT observed_at, max_bought FROM amazon_snapshots "
        "WHERE keyword=? AND max_bought IS NOT NULL ORDER BY observed_at",
        (keyword,),
    ).fetchall()
    return {"sales": _series_block(sales), "amazon": _series_block(amazon)}


def _db_last_collection(conn) -> str | None:
    """Horodatage RÉEL de la dernière collecte (max observed_at, sources de demande)."""
    row = conn.execute(
        "SELECT MAX(observed_at) FROM ("
        "  SELECT MAX(observed_at) AS observed_at FROM sales_snapshots"
        "  UNION ALL SELECT MAX(observed_at) FROM amazon_snapshots"
        ")"
    ).fetchone()
    return row[0] if row and row[0] else None


def _build_dossier(r: dict) -> dict:
    """Assemble la fiche produit qualitative (CJ product/query) pour le front.

    Parse les champs JSON stockés (galerie, variantes) et expose proprement le
    dossier. Tout est dégradable : si le produit n'a pas encore été re-photographié,
    les champs valent ``None`` et ``hasDetail`` vaut ``False``.
    """
    def _load(raw, default):
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError, TypeError):
            return default

    images = _load(r.get("images"), [])
    variants = _load(r.get("variants"), {})
    return {
        "hasDetail": bool(r.get("has_detail")),
        "priceFromCJ": r.get("suggest_price_eur") is not None,
        "suggestPrice": r.get("suggest_price_eur"),
        "description": r.get("description"),
        "video": r.get("video"),
        "images": images,
        "imageCount": len(images),
        "variantCount": variants.get("count") if isinstance(variants, dict) else None,
        "variantOptions": variants.get("options") if isinstance(variants, dict) else None,
        "material": r.get("material"),
        "weightG": r.get("weight_g"),
        "supplier": r.get("supplier"),
    }


def build_records(limit: int, geo: str, no_enrich: bool) -> tuple[list[dict], int]:
    """Construit la liste de produits à la forme BASE du dashboard.

    Renvoie (records, total_in_db). Réutilisable par l'export fichier ET par
    le job quotidien qui alimente le cache de l'API.
    """
    month = datetime.now(timezone.utc).month
    records = analyze(month)
    if not records:
        return [], 0
    total_in_db = len(records)
    top = records[:limit]

    # Enrichissement organique réel (Trends + Reddit live + demande marché snapshotée)
    # sur le top. C'EST le chemin de prod (run_daily) : il doit consommer les mêmes
    # sources que enrich.py, sinon les snapshots eBay/AliExpress ne compteraient jamais.
    organic_by_id: dict[str, dict] = {}
    if not no_enrich:
        from collect_demand import init_db as demand_db, demand_raw_signals
        conn = demand_db()
        try:
            population = []
            for i, r in enumerate(top):
                kw = keyword_from_name(r["name"])
                print(f"  [{i+1}/{len(top)}] « {kw} » → Trends + Reddit + marché ...", flush=True)
                trends_sig = trends_raw_signal(kw, geo=geo)
                reddit_sig = reddit_raw_signal(kw)
                raws = [s for s in (trends_sig, reddit_sig) if s.values]
                # Historique demande (eBay/AliExpress) si déjà snapshoté ≥2 fois.
                raws += demand_raw_signals(conn, kw)
                pf = build_product_features(
                    r["product_id"], raws,
                    age_days=r.get("age_days"), seller_count=r.get("listed_num"),
                )
                population.append(pf)
        finally:
            conn.close()
        results = {res.product_id: res for res in score_population(population)}
        pfs = {pf.product_id: pf for pf in population}
        for pid, res in results.items():
            pf = pfs[pid]
            tr = pf.signals.get("google_trends")
            rd = pf.signals.get("reddit")
            # score par source depuis les contributions (z -> 0..100)
            tscore = next((z_to_100(c.z_velocity) for c in res.contributions
                           if c.source == "google_trends"), 50)
            rscore = next((z_to_100(c.z_velocity) for c in res.contributions
                           if c.source == "reddit"), 50)
            # Ventes AliExpress : None tant qu'il n'y a pas ≥2 snapshots (≠ 50 neutre).
            sscore = next((z_to_100(c.z_velocity) for c in res.contributions
                           if c.source == "sales"), None)
            organic_by_id[pid] = {
                "organic": round(res.organic_score),
                "phase": res.phase.value,
                "growth": round(res.monthly_growth, 3),
                "confidence": round(res.confidence, 2),
                "volatility": round(tr.volatility if tr else 0.3, 2),
                "trendsScore": tscore,
                "redditScore": rscore,
                "salesScore": sscore,
            }

    # Niveau ABSOLU de ventes AliExpress par produit (validation demande dès le 1er
    # snapshot, indépendamment de la vélocité). Pure lecture DB, aucun appel réseau.
    sold_by_id: dict[str, dict] = {}
    # Tendance de la demande par produit (drapeau « déclin »). NOTRE horloge :
    # sales_snapshots accumulé jour après jour -> extract_trend -> pente log/jour.
    # Pure lecture DB. Le garde-fou « < 3 points = inconnu » vit dans loss_risk.
    decline_by_id: dict[str, dict] = {}
    # Courbes RÉELLES (séries de demande snapshotées) par produit + horodatage réel
    # de la dernière collecte. Remplace les courbes procédurales fabriquées côté front.
    history_by_id: dict[str, dict] = {}
    last_collection: str | None = None
    try:
        from collect_demand import init_db as demand_db, latest_sales_level, demand_raw_signals
        from signals.timeseries import extract_trend
        dconn = demand_db()
        try:
            last_collection = _db_last_collection(dconn)
            for r in top:
                kw = keyword_from_name(r["name"])
                history_by_id[r["product_id"]] = _demand_history(dconn, kw)
                lvl = latest_sales_level(dconn, kw)
                if lvl:
                    sold_by_id[r["product_id"]] = lvl
                for sig in demand_raw_signals(dconn, kw):
                    if sig.name == "sales":
                        tf = extract_trend(sig.timestamps_days, sig.values)
                        decline_by_id[r["product_id"]] = {
                            "velocity": tf.velocity,
                            "points": tf.n_points,
                            "volatility": tf.volatility,
                            "velocity_se": tf.velocity_se,
                            "span_days": tf.span_days,
                        }
        finally:
            dconn.close()
    except Exception:
        pass  # demande indisponible -> champs None, dégradation propre

    # Construction des enregistrements à la forme BASE du dashboard.
    out = []
    for i, r in enumerate(top):
        pid = r["product_id"]
        enr = organic_by_id.get(pid)
        sell = r["sellability"]
        if enr is None:  # repli (mode --no-enrich) : dérivations transparentes
            enr = {
                "organic": round(sell),
                "phase": "GROWTH" if r["verdict"] == "BUY" else "MATURE",
                "growth": round((r.get("season_factor", 1.0) - 1.0), 3),
                "confidence": 0.6,
                "volatility": 0.3,
                "trendsScore": round(min(100, sell)),
                "redditScore": round(min(100, sell * 0.8)),
                "salesScore": None,
            }
        season = r.get("seasonality", {})
        # Verdict anti-piège (le pivot Tandor : « ne perds pas d'argent », pas « voici un gagnant »).
        # Différenciateur vs Minea — exposé en première classe pour l'UI.
        dec = decline_by_id.get(pid) or {}
        loss = assess_loss_risk(
            product_id=pid,
            net_after_cpa_eur=r.get("net_after_cpa_eur"),
            gross_margin_eur=r.get("gross_margin_eur"),
            pct_low_rating=r.get("pct_low_rating"),
            listed_num=r.get("listed_num"),
            retail_eur=r.get("retail_eur"),
            demand_velocity=dec.get("velocity"),
            demand_points=dec.get("points", 0),
            demand_volatility=dec.get("volatility"),
            demand_velocity_se=dec.get("velocity_se"),
            demand_span_days=dec.get("span_days"),
        )
        out.append({
            "id": pid[-7:] if pid else f"P{i}",
            "name": r["name"],
            "cat": map_category(r["name"], r["category"]),
            "cost": round(r["cost_eur"], 2),
            "retail": round(r["retail_eur"], 2),
            "sellability": round(sell),
            "organic": enr["organic"],
            "phase": enr["phase"],
            "verdict": r["verdict"],
            "growth": enr["growth"],
            "confidence": enr["confidence"],
            "listed": r.get("listed_num") or 0,
            "age": round(r.get("age_days") or 60),
            "volatility": enr["volatility"],
            "net": round(r["net_after_cpa_eur"], 1),
            "redditScore": enr["redditScore"],
            "trendsScore": enr["trendsScore"],
            "salesScore": enr.get("salesScore"),
            # Ventes réelles AliExpress (niveau absolu, type de produit) — None tant
            # qu'aucun snapshot ; se remplit dès la 1re collecte (cron nocturne).
            "aliExpressSold": (sold_by_id.get(pid) or {}).get("maxSold"),
            "aliExpressMedianSold": (sold_by_id.get(pid) or {}).get("medianSold"),
            "seasonPeak": season.get("peak_month") or 6,
            "seasonMult": round(season.get("multiplier", 1.0), 2),
            "reason": {"en": r["reason"], "fr": r["reason"]},
            # ── Détecteur de pièges à fric (valeur organique, anti-perte) ──────
            "trapVerdict": loss.verdict,            # TRAP | RISKY | VIABLE
            "trapHeadline": loss.headline,
            "lossFlags": [{"name": f.name, "level": f.level, "reason": f.reason}
                          for f in loss.flags],
            "breakevenCpa": (round(loss.breakeven_cpa_eur, 1)
                             if loss.breakeven_cpa_eur is not None else None),
            # Courbes RÉELLES (séries snapshotées) : `null` par série tant qu'il n'y
            # a pas ≥2 points. Le front retombe sur « pas de données » au lieu de
            # fabriquer une tendance. `lastCollection` = vrai horodatage DB.
            "history": history_by_id.get(pid) or {"sales": None, "amazon": None},
            "lastCollection": last_collection,
            "detectedHrs": i + 1,  # ordre du flux (proxy : par score)
            # Dossier qualitatif (CJ product/query) : enrichit la fiche produit.
            # `null`/`priceFromCJ:false` tant que le produit n'a pas été re-photographié.
            "dossier": _build_dossier(r),
        })

    return out, total_in_db


def main() -> None:
    ap = argparse.ArgumentParser(description="Export dashboard data")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--geo", type=str, default="")
    ap.add_argument("--no-enrich", action="store_true", help="Sans Trends/Reddit (rapide)")
    args = ap.parse_args()

    out, total_in_db = build_records(args.limit, args.geo, args.no_enrich)
    if not out:
        print("Aucune donnée (cj.db vide ?).")
        return

    # 1) JSON bundlé dans le build du front (fallback hors-ligne).
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    # 2) Cache horodaté servi par l'API (forme {meta, products}).
    cache = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(out),
            "total_in_db": total_in_db,
            "enriched": not args.no_enrich,
            "geo": args.geo or "WW",
        },
        "products": out,
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    print(f"\n✓ {len(out)} produits réels exportés → {OUT}")
    print(f"✓ Cache API horodaté → {CACHE}  ({total_in_db} produits en base)")
    print(f"  Exemple : {out[0]['name']} | Tandor~{round(0.55*out[0]['organic']+0.45*out[0]['sellability'])} "
          f"| marge {out[0]['net']}€ | {out[0]['phase']}")


if __name__ == "__main__":
    main()
