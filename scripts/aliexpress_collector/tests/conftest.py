"""Configuration pytest : rend les modules du collecteur importables.

Ajoute la racine du paquet (``aliexpress_collector/``) au ``sys.path`` afin que
``import config.settings`` etc. fonctionnent sans installation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
