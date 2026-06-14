"""Configuration de la journalisation (console colorée + fichier).

Reprend le style du logger historique du projet (colorlog) mais centralisé et
paramétrable. ``colorlog`` est optionnel : si absent, on retombe proprement
sur le logging standard.
"""

from __future__ import annotations

import logging
from pathlib import Path

try:  # dépendance optionnelle, dégrade gracieusement
    import colorlog

    _HAS_COLORLOG = True
except ImportError:  # pragma: no cover
    _HAS_COLORLOG = False

_CONSOLE_FMT = "%(asctime)s | %(levelname)-8s | %(message)s"
_FILE_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATEFMT = "%H:%M:%S"


def setup_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Initialise et renvoie le logger applicatif ``aec``.

    Idempotent : un second appel ne duplique pas les handlers.

    Args:
        level: niveau (``DEBUG``, ``INFO``, ...).
        log_file: chemin du fichier de log ; les dossiers sont créés au besoin.
    """
    logger = logging.getLogger("aec")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:  # déjà configuré
        return logger

    if _HAS_COLORLOG:
        console = colorlog.StreamHandler()
        console.setFormatter(
            colorlog.ColoredFormatter(
                "%(log_color)s" + _CONSOLE_FMT,
                datefmt=_DATEFMT,
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            )
        )
    else:  # pragma: no cover
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(_CONSOLE_FMT, datefmt=_DATEFMT))
    logger.addHandler(console)

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_FILE_FMT))
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger
