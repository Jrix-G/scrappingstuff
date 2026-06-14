"""Hiérarchie d'exceptions propre au collecteur.

Permet d'attraper sélectivement les erreurs métier sans masquer les bugs
réels (qui restent des exceptions Python standard).
"""

from __future__ import annotations


class CollectorError(Exception):
    """Erreur de base du collecteur."""


class NavigationError(CollectorError):
    """Échec de chargement d'une page (timeout, réseau, blocage)."""


class ExtractionError(CollectorError):
    """Impossible d'extraire des données exploitables d'une réponse."""


class StorageError(CollectorError):
    """Échec de lecture/écriture côté stockage."""
