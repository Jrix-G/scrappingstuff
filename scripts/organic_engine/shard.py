"""Partition déterministe de l'univers de mots-clés entre plusieurs nœuds de scraping.

Objectif : faire tourner le MÊME pipeline Tandor sur plusieurs machines (Pi + VPS)
sans jamais scraper deux fois le même mot-clé. Chaque mot-clé est assigné à UN seul
shard via ``crc32(kw) % count`` → ensembles strictement disjoints, sans coordination
entre les nœuds (pas de DB partagée nécessaire).

Configuration (par ordre de priorité) :
  1. variables d'env ``TANDOR_SHARD`` / ``TANDOR_SHARD_COUNT`` ;
  2. fichier ``~/.tandor_shard`` contenant « <shard> <count> » (ex. « 1 2 ») ;
  3. défaut (0, 1) = AUCUNE partition → comportement historique strictement inchangé.

Rétro-compatible : tant que ``count <= 1`` (ou aucune config), ``in_shard`` renvoie
toujours True et le nœud couvre tout l'univers comme avant.

``crc32`` est choisi plutôt que ``hash()`` car le hash natif de Python est randomisé
par processus (PYTHONHASHSEED) → instable. crc32 est déterministe et identique sur
toutes les machines/versions, condition indispensable pour que la partition soit
cohérente entre les nœuds.
"""
from __future__ import annotations

import os
import zlib
from pathlib import Path


def config() -> tuple[int, int]:
    """Renvoie (shard, count) effectifs. Tolérant : toute config invalide → (0, 1)."""
    shard = os.getenv("TANDOR_SHARD")
    count = os.getenv("TANDOR_SHARD_COUNT")
    if shard is None or count is None:
        try:
            parts = (Path.home() / ".tandor_shard").read_text().split()
            if len(parts) >= 2:
                shard = shard if shard is not None else parts[0]
                count = count if count is not None else parts[1]
        except Exception:
            pass
    try:
        s = int(shard) if shard is not None else 0
        c = int(count) if count is not None else 1
    except (TypeError, ValueError):
        return 0, 1
    if c < 1:
        c = 1
    return s % c, c


# Figé à l'import : poser la config (env / fichier) AVANT de lancer les process.
SHARD, SHARD_COUNT = config()


def in_shard(keyword: str) -> bool:
    """True si ce mot-clé appartient au shard de ce nœud (ou si pas de partition)."""
    if SHARD_COUNT <= 1:
        return True
    if not keyword:
        return True
    return (zlib.crc32(keyword.encode("utf-8")) % SHARD_COUNT) == SHARD


def describe() -> str:
    """Libellé court pour les logs / le démarrage."""
    if SHARD_COUNT <= 1:
        return "shard désactivé (couverture complète de l'univers)"
    return f"shard {SHARD}/{SHARD_COUNT} (≈1/{SHARD_COUNT} de l'univers, disjoint des autres nœuds)"


if __name__ == "__main__":  # python3 shard.py → montre la config + un test de répartition
    print("Config:", describe())
    import sys
    # Petit test de distribution sur des mots-clés synthétiques.
    n = 20000
    counts: dict[int, int] = {}
    cnt = SHARD_COUNT if SHARD_COUNT > 1 else 2
    for i in range(n):
        b = zlib.crc32(f"keyword-{i}".encode()) % cnt
        counts[b] = counts.get(b, 0) + 1
    print(f"Répartition crc32 sur {n} mots-clés en {cnt} shards: "
          + ", ".join(f"shard{k}={v} ({v*100//n}%)" for k, v in sorted(counts.items())))
