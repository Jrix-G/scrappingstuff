# Time-series — historisation quotidienne des produits (Phase 0)

Capture chaque jour l'état des produits dans une base **SQLite** locale
(`backend/data/timeseries.db`) pour constituer un historique exploitable
(analyse, scoring, backtesting, ML). Voir `docs/ARCHITECTURE.md §1`.

Aucun Docker, aucun serveur externe : SQLite est un simple fichier. N'impacte ni
`index.js`, ni le produit actuel — le service ne fait que **lire** les sources
(il n'écrit jamais `products.json` ni `cj.db`).

## Ce qui est historisé

**Tout l'univers** (~5000 produits), pas seulement le top-60 affiché. Chaque jour,
une ligne par produit consolidant deux sources :

| Source (lecture seule) | Apporte |
|---|---|
| `scripts/organic_engine/data/cj.db` (`cj_products` + `cj_snapshots`) | l'univers complet : prix, nb de vendeurs (`listed`), âge, catégorie |
| `frontend/src/dashboard/products.json` | les **scores** du sous-ensemble enrichi : sellability, organic, growth, phase, verdict, reddit/trends |

> Les scores ne couvrent aujourd'hui que ~50–60 produits (ceux que le moteur
> enrichit). L'overlay est **anti-collision** : `products.json` n'expose qu'un id
> court (`pid[-7:]`) ; on n'attache un score que si ce suffixe désigne UN seul
> produit de l'univers — jamais d'attribution au hasard.

## Installation

```bash
cd backend && npm install
```

## Utilisation

```bash
npm run snapshot:validate              # tests (DB in-memory) — à lancer en premier
npm run snapshot:backfill              # (une fois) amorce avec l'historique brut déjà dans cj_snapshots
npm run snapshot:once                  # snapshot du jour (univers complet, idempotent)
npm run snapshot:once -- --date 2026-06-10   # forcer une date précise
npm run snapshot:history -- <productId>      # historique d'un produit (pid complet)
npm run snapshot:history                     # derniers runs (observabilité)
npm run snapshot:cron                   # process long-vivant : snapshot quotidien
```

## Job quotidien : deux options (au choix)

1. **node-cron** (process long-vivant) : `npm run snapshot:cron`
   (config : `SNAPSHOT_CRON`, `SNAPSHOT_TZ`, `SNAPSHOT_RUN_ON_START=1`).
2. **cron système** (recommandé sur le Pi, déjà équipé de cron) :
   ```cron
   0 3 * * *  cd /home/albator/scrappingstuff/backend && npm run snapshot:once >> data/snapshot.log 2>&1
   ```
   Le job étant idempotent, les deux approches sont sûres.

## Configuration (env)

| Variable | Défaut | Rôle |
|---|---|---|
| `TIMESERIES_DB_PATH` | `backend/data/timeseries.db` | Emplacement de la base d'historique |
| `SNAPSHOT_SOURCE` | `auto` | `auto` (univers cj.db si présent) · `universe` · `json` (top-60 seul) |
| `CJ_DB_PATH` | `scripts/organic_engine/data/cj.db` | Univers complet (lecture seule) |
| `PRODUCTS_API_URL` | _(vide)_ | Mode `json` : lit `${URL}/api/products` ; sinon `products.json` |
| `PRODUCTS_JSON_PATH` | `frontend/src/dashboard/products.json` | Source des scores (overlay) |
| `SNAPSHOT_CRON` | `0 3 * * *` | Planning du scheduler node-cron |
| `SNAPSHOT_TZ` | `Europe/Paris` | Timezone |

## Schéma

`products` (dimension) · `product_snapshots` (time-series, PK `(product_id, snapshot_date)`)
· `signals` (préparé, ML futur) · `snapshot_runs` (observabilité).
