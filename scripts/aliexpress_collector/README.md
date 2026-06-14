# Collecteur AliExpress

Collecteur de données AliExpress robuste, modulaire et tolérant aux changements
du site. Conçu pour remplacer les scrapers historiques (`alibibi.py`,
`aliexpress-pages-scrapper-main/`) qui reposaient sur des classes CSS fragiles.

## Idée directrice

Au lieu de parser le HTML (classes du type `recommend-card--card-wrap--2jjBf6S`
qui changent à chaque refonte), on **intercepte le JSON interne** déjà chargé par
AliExpress et on en extrait les produits par *forme* plutôt que par chemin figé.
Résultat : beaucoup plus stable, plus riche, et bien plus difficile à casser.

> Usage public, anonyme et à faible cadence. Respecte les serveurs : délais
> humains entre requêtes, pas de parallélisme agressif, dédup pour ne jamais
> re-télécharger ce qu'on a déjà.

## Arborescence

```
aliexpress_collector/
├── config/
│   ├── config.yaml        # URL cible + tous les réglages
│   └── settings.py        # chargement YAML + surcharge par variables d'env
├── core/
│   ├── models.py          # dataclass Product (schéma unique du pipeline)
│   ├── browser.py         # contexte Playwright furtif + capture JSON réseau
│   └── exceptions.py      # hiérarchie d'exceptions métier
├── collectors/
│   ├── listing.py         # produits d'une page de listing (JSON, repli DOM)
│   └── product.py         # enrichissement via la fiche produit
├── extractors/
│   ├── parser.py          # extraction tolérante à la structure
│   └── normalize.py       # prix/devise/entiers localisés -> types propres
├── storage/
│   ├── base.py            # interface Storage (Protocol)
│   ├── sqlite_store.py    # SQLite + historique time-series (vélocité)
│   ├── json_store.py      # JSON atomique (petits volumes / inspection)
│   └── factory.py         # choix du backend selon la config
├── utils/
│   ├── logging_conf.py    # logs colorés + fichier
│   ├── humanize.py        # délais d'apparence humaine (loi Beta)
│   └── rate_limiter.py    # limiteur de débit asynchrone partageable
├── tests/                 # pytest : normalize, parser, storage, models
├── run.py                 # point d'entrée / orchestrateur
└── requirements.txt
```

Chaque module a **une responsabilité unique** ; le pipeline ne communique que
via la dataclass `Product` et l'interface `Storage`.

## Installation

```bash
cd scripts/aliexpress_collector
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium     # télécharge le navigateur
```

## Exécution

```bash
# 1) Régler l'URL cible dans config/config.yaml (champ target_url)
# 2) Lancer
python run.py

# Variante : surcharge ponctuelle par variable d'environnement
AEC_TARGET_URL="https://fr.aliexpress.com/w/wholesale-montre-connectee.html" \
AEC_MAX_PRODUCTS=20 python run.py

# Autre fichier de config
python run.py --config /chemin/vers/ma_config.yaml
```

Les données atterrissent dans `data/aliexpress.db` (SQLite par défaut). Lancer
plusieurs fois enrichit l'historique des prix/ventes (table `price_history`)
sans recréer les doublons.

### Tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -q          # 18 tests, ~0.4 s
```

## Données collectées (si disponibles)

`product_id`, `title`, `price`, `currency`, `original_price`, `rating`,
`reviews_count`, `orders_count`, `seller`, `url`, `images`, `variants`,
`category`, `description`, `available`, `collected_at`.

Les champs absents restent `null` — l'absence est une information, on n'invente rien.

## Choix de stockage

**SQLite par défaut.** Le projet vise un signal d'émergence basé sur la
**vélocité** (évolution des ventes/prix dans le temps). Cela exige un historique
time-series : la table `price_history` enregistre un point à chaque passage.
SQLite donne aussi gratuitement la dédup (clé primaire) et la reprise (lecture
des ids connus). JSON reste sélectionnable (`storage_backend: json`) pour les
petits volumes ou l'inspection manuelle, mais ne gère pas l'historique.

## Améliorations vs. scrapers initiaux

| Sujet | Avant | Maintenant |
|---|---|---|
| Source des données | HTML + classes CSS volatiles | JSON interne + extraction par forme |
| Champs collectés | 5 (titre, prix, note, livraison, vendus) | 16 (id, devise, commandes, vendeur, images, variantes…) |
| Doublons | aucun contrôle | dédup par `product_id` |
| Reprise après arrêt | impossible (repart de zéro) | reprise sur ids connus |
| Historique temporel | absent | table `price_history` (vélocité) |
| Gestion d'erreurs | `try/except: pass` | exceptions typées, repli, logs |
| Configuration | constantes en dur | YAML centralisé + surcharge env |
| Anti-détection | délais uniformes | contexte furtif + délais loi Beta |
| Architecture | script monolithique | modules à responsabilité unique |
| Tests | aucun | 18 tests unitaires |
| Stockage | CSV écrasé à chaque run | SQLite/JSON persistant + dédup |

## Prochaines étapes naturelles

- Calcul de vélocité : `(moy_7j - moy_30j) / moy_30j` depuis `price_history`.
- Pagination multi-pages du listing.
- Brancher la sortie sur le scoring composite multi-sources (Reddit, TikTok…).
