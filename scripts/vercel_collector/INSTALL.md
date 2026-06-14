# Installation — 4 étapes, 5 minutes

## Étape 1 — Installer Vercel CLI (une seule fois)

```bash
npm install -g vercel
```

## Étape 2 — Déployer la fonction sur Vercel

```bash
cd scripts/vercel_collector
vercel deploy --prod
```

Vercel te demande de te connecter (compte gratuit sur vercel.com).
Si Vercel demande un nom de projet, utilise uniquement des minuscules, chiffres,
`.` `_` ou `-`, par exemple : `vercel-trey`.
À la fin il affiche une URL du type : `https://mon-projet-xyz.vercel.app`
**Copie cette URL.**

## Étape 3 — Installer les dépendances locales

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Étape 4 — Lancer la collecte

```bash
python run.py
```

La première fois, il te demande l'URL Vercel → colle-la → il la sauvegarde.
Ensuite il collecte automatiquement tous les mots-clés de `keywords.txt`.

---

## Options utiles

```bash
# Tester avec un seul mot-clé avant de tout lancer
python run.py --keyword "ecouteurs bluetooth"

# Plus de pages = plus de produits (3 pages = ~180 produits par mot-clé)
python run.py --pages 10

# Plus de workers = plus rapide (attention : limite Vercel free = 100k/jour)
python run.py --workers 50
```

## Ajouter des mots-clés

Édite `keywords.txt` — un mot-clé par ligne. Les lignes commençant par `#` sont ignorées.

## Les données

Tout est dans `data/products.db` (SQLite).
Pour voir le contenu :
```bash
sqlite3 data/products.db "SELECT title, price, orders_count FROM products ORDER BY orders_count DESC LIMIT 20;"
```

---

## Estimation volume / temps

| Pages/clé | Produits/clé | Avec 33 mots-clés | Durée (~30 workers) |
|---|---|---|---|
| 3 (défaut) | ~180 | ~6 000 | ~2 min |
| 10 | ~600 | ~20 000 | ~5 min |
| 50 | ~3 000 | ~100 000 | ~20 min |
| 200 | ~12 000 | ~400 000 | ~1h30 |
