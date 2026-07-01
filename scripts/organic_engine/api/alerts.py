"""Dérivation des alertes Tandor — UNIQUEMENT à partir de signaux RÉELS.

Aucune alerte n'est fabriquée. Chaque alerte est la projection d'un signal déjà
calculé ailleurs dans le moteur :

  * **Cache enrichi** (``data/dashboard_export.json``, régénéré par ``run_daily``) :
    chaque produit du top porte une ``phase`` (EMERGENT/.../DECLINING), un
    ``trapVerdict`` (VIABLE/RISKY/TRAP) et des ``lossFlags`` — tous issus du scoring
    réel. On en tire les alertes « passé en phase DECLINING », « verdict TRAP/RISKY »
    et « demande en déclin » (drapeau ``déclin`` rouge/orange).

  * **Snapshots de demande** (``sales_snapshots`` / ``amazon_snapshots`` dans
    ``cj.db``) : pour les produits du catalogue NON enrichis, on relit la série
    réelle d'achats/ventes par mot-clé, on en sort la vélocité
    (``signals.timeseries.extract_trend``) et on réutilise EXACTEMENT le détecteur
    de déclin de ``scoring.loss_risk`` (``_decline_flag``). Un produit n'apparaît
    que si l'on sait le rattacher à une ligne réelle du catalogue (sinon on
    n'invente pas de nom).

Si aucun signal réel n'est disponible -> liste vide (empty-state honnête).

NOTE « delivered » : il n'existe pas encore de table de persistance des alertes
(pas de table ``alerts`` en base, cf. archi). Faute de journal de livraison, toutes
les alertes sont renvoyées avec ``delivered=false`` (rien n'a encore été marqué
comme livré/acquitté). ``undelivered_only=true`` renvoie donc l'ensemble courant.
Quand un store de livraison existera, c'est le SEUL endroit à modifier.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CJ_DB = _ROOT / "data" / "cj.db"

# Poids de tri par sévérité (décroissant) : high > warn > info.
_SEVERITY_RANK = {"high": 0, "warn": 1, "info": 2}

# Cache mémoire du résultat (calcul = lecture cache + scan snapshots). TTL court :
# les données ne changent qu'au rythme du cron quotidien.
_ALERTS_TTL = float(os.environ.get("TANDOR_ALERTS_TTL", "120"))
_alerts_lock = threading.Lock()
_alerts_cache: dict[str, Any] = {"expires": 0.0, "value": None}


def _mk_alert(*, atype: str, product_id: str, product_name: str | None,
              message: str, severity: str, created_at: str | None) -> dict[str, Any]:
    """Construit une alerte au contrat figé (id déterministe = type:product_id)."""
    return {
        "id": f"{atype}:{product_id}",
        "type": atype,
        "product_id": str(product_id),
        "product_name": product_name or str(product_id),
        "message": message,
        "severity": severity if severity in _SEVERITY_RANK else "info",
        "created_at": created_at,
        # Pas de journal de livraison persistant -> jamais livrée pour l'instant.
        "delivered": False,
    }


def _alerts_from_enriched(meta_generated: str | None) -> list[dict[str, Any]]:
    """Alertes issues du cache enrichi (phase / trapVerdict / drapeau déclin RÉELS)."""
    # Import local pour éviter tout cycle au chargement du module.
    from api.server import _load_cache

    try:
        data = _load_cache()
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for p in data.get("products", []):
        pid = p.get("id")
        if pid is None:
            continue
        name = p.get("name")
        # Horodatage RÉEL : dernière collecte du produit, sinon génération du cache.
        created = p.get("lastCollection") or meta_generated
        flags = {f.get("name"): f for f in (p.get("lossFlags") or [])}
        decline = flags.get("déclin") or {}
        decline_level = decline.get("level")

        emitted_decline = False
        if p.get("phase") == "DECLINING":
            out.append(_mk_alert(
                atype="phase_decline", product_id=pid, product_name=name,
                message="Passé en phase DECLINING — la dynamique organique du produit "
                        "se retourne.",
                severity="high", created_at=created,
            ))
            emitted_decline = True
        elif decline_level == "red":
            out.append(_mk_alert(
                atype="demand_decline", product_id=pid, product_name=name,
                message=decline.get("reason") or "Demande en chute (vélocité négative).",
                severity="high", created_at=created,
            ))
            emitted_decline = True
        elif decline_level == "amber":
            out.append(_mk_alert(
                atype="demand_decline", product_id=pid, product_name=name,
                message=decline.get("reason") or "Demande en repli (momentum qui s'essouffle).",
                severity="warn", created_at=created,
            ))
            emitted_decline = True

        tv = p.get("trapVerdict")
        if tv == "TRAP":
            out.append(_mk_alert(
                atype="trap", product_id=pid, product_name=name,
                message=p.get("trapHeadline") or "Verdict TRAP — piège à fric probable.",
                severity="high", created_at=created,
            ))
        elif tv == "RISKY" and not emitted_decline:
            # Évite le doublon quand le RISKY est précisément dû au déclin déjà signalé.
            out.append(_mk_alert(
                atype="trap_risky", product_id=pid, product_name=name,
                message=p.get("trapHeadline") or "Verdict RISKY — marge/saturation fragiles.",
                severity="warn", created_at=created,
            ))
    return out


def _reverse_keyword_index() -> dict[str, tuple[str, str]]:
    """{mot-clé -> (pid, name)} pour rattacher un snapshot de demande à un produit.

    Construit depuis le scan léger du catalogue déjà mémorisé par ``server.py`` (donc
    sans requête SQL supplémentaire). Premier produit gagnant par mot-clé (suffit à
    afficher un nom réel ; on ne fabrique jamais de libellé).
    """
    from api.server import _load_catalogue_cached
    try:
        from enrich import keyword_candidates
    except Exception:
        return {}

    descs, rows_by_pid = _load_catalogue_cached()
    index: dict[str, tuple[str, str]] = {}
    for d in descs:
        pid = d.get("id")
        name = d.get("name")
        if not pid or not name:
            continue
        for kw in keyword_candidates(name):
            index.setdefault(kw, (pid, name))
    return index


def _alerts_from_snapshots(exclude_pids: set[str]) -> list[dict[str, Any]]:
    """Alertes de déclin pour le catalogue, depuis la demande RÉELLE snapshotée.

    On relit ``sales_snapshots`` (ventes) et ``amazon_snapshots`` (achats/mois) par
    mot-clé, on calcule la vélocité et on réutilise le détecteur de déclin de
    ``scoring.loss_risk``. Un produit n'est émis que si on sait le rattacher au
    catalogue (index inverse de mots-clés) et qu'il n'est pas déjà couvert par le
    cache enrichi.
    """
    if not _CJ_DB.exists():
        return []
    try:
        from signals.timeseries import extract_trend
        from scoring.loss_risk import _decline_flag
    except Exception:
        return []

    index = _reverse_keyword_index()
    if not index:
        return []

    # (table, colonne de valeur) — on prend le « niveau max » observé chaque jour.
    sources = (("sales_snapshots", "max_sold"), ("amazon_snapshots", "max_bought"))

    # Agrège les séries par mot-clé (uniquement les mots-clés rattachables).
    series: dict[str, list[tuple[str, float]]] = {}
    last_seen: dict[str, str] = {}
    try:
        conn = sqlite3.connect(f"file:{_CJ_DB}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return []
    try:
        wanted = set(index.keys())
        for table, col in sources:
            try:
                rows = conn.execute(
                    f"SELECT keyword, observed_at, {col} FROM {table} "
                    f"WHERE {col} IS NOT NULL ORDER BY keyword, observed_at"
                ).fetchall()
            except sqlite3.Error:
                continue
            for kw, ts, val in rows:
                if kw not in wanted:
                    continue
                series.setdefault(kw, []).append((ts, float(val)))
                if ts and (kw not in last_seen or ts > last_seen[kw]):
                    last_seen[kw] = ts
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    seen_pids: set[str] = set()
    for kw, pts in series.items():
        if len(pts) < 2:
            continue
        pid, name = index[kw]
        if pid in exclude_pids or pid in seen_pids:
            continue
        try:
            t0 = datetime.fromisoformat(pts[0][0])
            days = [(datetime.fromisoformat(t) - t0).total_seconds() / 86400.0
                    for t, _ in pts]
            vals = [v for _, v in pts]
            tf = extract_trend(days, vals)
            flag = _decline_flag(tf.velocity, tf.n_points, tf.volatility,
                                 tf.velocity_se, tf.span_days)
        except Exception:
            continue
        if flag.level not in ("red", "amber"):
            continue
        seen_pids.add(pid)
        out.append(_mk_alert(
            atype="demand_decline", product_id=pid, product_name=name,
            message=flag.reason,
            severity="high" if flag.level == "red" else "warn",
            created_at=last_seen.get(kw),
        ))
    return out


def _build() -> list[dict[str, Any]]:
    """Calcule l'ensemble courant des alertes (toutes sources), trié et dédupliqué."""
    # Horodatage de génération du cache (repli quand un produit n'a pas de collecte).
    meta_generated = None
    try:
        from api.server import _load_cache
        meta_generated = (_load_cache().get("meta") or {}).get("generated_at")
    except Exception:
        meta_generated = None

    enriched_alerts = _alerts_from_enriched(meta_generated)
    enriched_pids = {a["product_id"] for a in enriched_alerts}
    snapshot_alerts = _alerts_from_snapshots(enriched_pids)

    alerts = enriched_alerts + snapshot_alerts
    # Dédoublonnage par id déterministe (sécurité ; chaque source est déjà disjointe).
    by_id: dict[str, dict[str, Any]] = {}
    for a in alerts:
        by_id.setdefault(a["id"], a)
    alerts = list(by_id.values())

    # Tri : sévérité décroissante, puis date décroissante (récent d'abord).
    alerts.sort(key=lambda a: (
        _SEVERITY_RANK.get(a["severity"], 99),
        # created_at peut être None -> renvoyé en dernier dans son groupe.
        _neg_iso(a.get("created_at")),
    ))
    return alerts


def _neg_iso(ts: str | None) -> str:
    """Clé de tri décroissant sur une date ISO (None en dernier)."""
    # On veut les plus récentes d'abord : on inverse l'ordre lexicographique en
    # plaçant None après tout (préfixe '0'), et les dates par préfixe '1' inversé.
    if not ts:
        return "0"
    # Inverse chaque caractère pour obtenir un tri décroissant via tri croissant.
    return "1" + "".join(chr(0x10FFFF - ord(c)) if ord(c) < 0x10FFFF else c for c in ts)


def list_alerts(undelivered_only: bool = False) -> list[dict[str, Any]]:
    """Liste les alertes courantes (cache mémoire TTL). ``undelivered_only`` filtre
    sur ``delivered=false`` (aujourd'hui : toutes, faute de journal de livraison)."""
    now = time.monotonic()
    with _alerts_lock:
        if _alerts_cache["value"] is not None and now < _alerts_cache["expires"]:
            alerts = _alerts_cache["value"]
        else:
            alerts = _build()
            _alerts_cache.update(value=alerts, expires=now + _ALERTS_TTL)
    if undelivered_only:
        return [a for a in alerts if not a.get("delivered")]
    return list(alerts)


def _reset_cache() -> None:
    """Vide le cache (tests)."""
    with _alerts_lock:
        _alerts_cache.update(expires=0.0, value=None)
