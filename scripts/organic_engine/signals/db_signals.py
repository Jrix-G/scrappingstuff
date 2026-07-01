"""Loader générique DB → RawSignal — point d'intégration partagé du scoring.

Les collecteurs organiques (TikTok, Google Suggest, et plus tard Reddit/YouTube)
empilent leurs photos datées dans des tables ``*_snapshots`` (cf.
``demand_queue.init_schema``). Ce module relit ces tables pour un mot-clé donné et
reconstruit les :class:`~signals.features.RawSignal` (séries temporelles) prêtes à
passer à ``scoring.engine.score_population`` — exactement comme
``collect_demand.demand_raw_signals`` le fait pour les ventes.

EXTENSIBILITÉ (vague 2) — ajouter un signal = AJOUTER UNE ENTRÉE, pas réécrire :

    register_source(SnapshotSource(
        signal="reddit",            # doit exister dans signals.features.SIGNALS
        table="reddit_snapshots",   # table CREATE IF NOT EXISTS déjà migrée
        value_col="mentions",       # colonne dont la série alimente la vélocité
        time_col="observed_at",     # (défaut) colonne horodatage ISO
        where="mentions IS NOT NULL",  # (défaut value_col IS NOT NULL) filtre anti-trou
    ))

Puis ``db_raw_signals(conn, kw)`` produira automatiquement un
``RawSignal("reddit", ...)`` dès que la table contient ≥1 ligne pour ``kw``.

API :
    db_raw_signals(conn, keyword)            -> list[RawSignal]   (toutes sources)
    db_raw_signal(conn, keyword, signal)     -> RawSignal | None  (une source)
    register_source(source)                  -> None
    REGISTRY: dict[str, SnapshotSource]      (signal -> config, modifiable)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from .features import RawSignal


@dataclass(slots=True)
class SnapshotSource:
    """Mapping déclaratif d'une table de snapshots vers un signal de scoring.

    Attributes:
        signal:    nom du signal (clé de ``signals.features.SIGNALS``), p.ex. "tiktok".
        table:     table SQLite ``*_snapshots`` à relire.
        value_col: colonne numérique dont la série temporelle porte la dynamique
                   (vélocité/accélération). On la passe BRUTE à ``extract_trend``,
                   qui la met en ``log1p`` (cohérent avec sales/amazon).
        time_col:  colonne horodatage ISO (croissante), défaut ``observed_at``.
        where:     filtre SQL anti-valeur-manquante, défaut ``<value_col> IS NOT NULL``.
    """

    signal: str
    table: str
    value_col: str
    time_col: str = "observed_at"
    where: str | None = None

    def filter_sql(self) -> str:
        return self.where if self.where is not None else f"{self.value_col} IS NOT NULL"


# ── Registre des sources câblées (vague 1) ───────────────────────────────────
# Vague 2 (reddit, youtube) : décommenter/register_source une fois alimentées.
REGISTRY: dict[str, SnapshotSource] = {
    "tiktok": SnapshotSource(
        signal="tiktok", table="tiktok_snapshots", value_col="view_count"
    ),
    "google_trends": SnapshotSource(
        signal="google_trends", table="suggest_snapshots", value_col="score"
    ),
    # Vague 2 — Reddit alimenté (flush du cache + reddit_worker). value_col="mentions" :
    # le RSS public ne fournit aucun upvote/score, le signal EST la fréquence de mentions
    # pertinentes dans le temps (la colonne `score` n'est qu'un proxy d'activité grossier).
    "reddit": SnapshotSource("reddit", "reddit_snapshots", "mentions"),
    # "youtube": SnapshotSource("youtube", "youtube_snapshots", "view_count"),
}


def register_source(source: SnapshotSource) -> None:
    """Enregistre (ou remplace) une source de snapshots dans le registre."""
    REGISTRY[source.signal] = source


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _series(rows: list[tuple]) -> tuple[list[float], list[float]]:
    """[(observed_at, value), ...] trié -> (jours depuis t0, valeurs)."""
    t0 = datetime.fromisoformat(rows[0][0])
    days = [(datetime.fromisoformat(r[0]) - t0).total_seconds() / 86400.0 for r in rows]
    vals = [float(r[1]) for r in rows]
    return days, vals


def db_raw_signal(
    conn: sqlite3.Connection, keyword: str, signal: str
) -> RawSignal | None:
    """RawSignal d'UNE source pour un mot-clé, ou ``None`` si table absente/vide.

    Renvoie la série complète disponible (≥1 point). La vélocité exige ≥2 points :
    en deçà, ``extract_trend`` la calcule à 0 et le scoring ignore la source — le
    filtrage fin est laissé au moteur, pas au loader.
    """
    src = REGISTRY.get(signal)
    if src is None or not _table_exists(conn, src.table):
        return None
    rows = conn.execute(
        f"SELECT {src.time_col}, {src.value_col} FROM {src.table} "
        f"WHERE keyword=? AND {src.filter_sql()} ORDER BY {src.time_col}",
        (keyword,),
    ).fetchall()
    if not rows:
        return None
    days, vals = _series(rows)
    return RawSignal(src.signal, days, vals)


def db_raw_signals(conn: sqlite3.Connection, keyword: str) -> list[RawSignal]:
    """Toutes les séries de snapshots disponibles en base pour un mot-clé.

    Itère le :data:`REGISTRY`. Tolérant : ignore silencieusement les sources dont
    la table n'existe pas encore ou n'a aucune ligne pour ce mot-clé.
    """
    out: list[RawSignal] = []
    for signal in REGISTRY:
        sig = db_raw_signal(conn, keyword, signal)
        if sig is not None and sig.values:
            out.append(sig)
    return out


if __name__ == "__main__":  # python3 -m signals.db_signals "ceiling fan"
    import sys
    from pathlib import Path

    db = Path(__file__).resolve().parent.parent / "data" / "cj.db"
    kw = " ".join(sys.argv[1:]) or "ceiling fan"
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    for s in db_raw_signals(c, kw):
        print(f"{s.name:14} {len(s.values)} pts  vals={s.values[:6]}")
    c.close()
