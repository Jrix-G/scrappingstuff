# Plan — Tandor (scrappingstuff)

Rapport d'analyse généré le 2026-06-10.

---

## PARTIE 1 — Architecture actuelle

### Stack technique

**Backend scraping (Python) :**
- `pytrends` (unofficial Google Trends API) + Playwright (navigateur headless)
- `Groq` API avec `llama-3.1-8b-instant` pour normaliser les noms de produits
- WireGuard/ProtonVPN avec rotation via `pyautogui` (clicks GUI automatiques)
- `fake-useragent` + fingerprints navigateur manuels

**Backend API (Node.js) :**
- Express.js sur le port 3001 — rôle unique : copier les `trends_*.json` vers `public/graphs/` et exposer `/api/graphs`

**Frontend (React/TypeScript) :**
- React 19 + Recharts + Bootstrap/MUI
- Deux pages : `Home.tsx` (landing statique) et `Home_by.tsx` (affichage des courbes de tendances)
- Nom du produit : **Tandor**

### Structure des dossiers et flux de données

```
scrappingstuff/
├── main.py                  # Scraper Wikipedia (hors sujet)
├── proxy_rotatifs.py        # Proxy HTTP basique (hors sujet)
├── videoge.py               # Génération vidéo OpenCV (hors sujet)
├── backend/                 # Express.js - sert les JSON de trends
├── scrapa/                  # React frontend (Tandor)
└── scripts/
    ├── jsmain.py / sjsmain.py  # Collecte Google Trends par liste de mots
    └── wordsSeach/
        ├── main.py             # Orchestrateur principal
        ├── Vapora/Vapora.py    # Scraper Amazon (Playwright sync)
        ├── Ilaw/Ilaw.py        # Scraper AliExpress (Playwright sync)
        ├── Ilat/Ilat.py        # Collecte Google Trends + scoring
        ├── Ilat/Greg.py        # Normalisation produit via Groq/LLaMA
        ├── generateUrl.py      # Générateur URLs Amazon bestsellers
        ├── VPN.py              # Rotation VPN (GUI Windows)
        └── products/           # 50 fichiers JSON produits Amazon scrapés
```

### Flux de données réel

1. `generateURL()` pioche aléatoirement dans 10 URLs hardcodées Amazon bestsellers FR
2. Vapora crawle les pages produit Amazon (nom, catégorie, BSR, prix, date)
3. Fichier JSON sauvegardé dans `products/`
4. Ilaw prend chaque produit Amazon, cherche sur AliExpress, extrait (prix, notes, nb vendus)
5. Greg appelle Groq/LLaMA pour normaliser le nom en mot-clé court, puis Google Trends 7 jours FR — `score = sum(valeurs)`
6. Les JSON de trends sont servis par Express et affichés dans React

**Sources intégrées :** Amazon.fr, AliExpress FR, Google Trends
**Absentes :** Reddit (totalement), TikTok Creative Center (totalement)

**Stockage :** Zéro base de données. Fichiers JSON plats dans `products/`. Sur 50 fichiers produits présents, aucun n'a traversé les 3 étapes du pipeline.

---

## PARTIE 2 — Évaluation de viabilité

**Légalité :** Zone grise risquée. Amazon et AliExpress interdisent explicitement le scraping automatisé dans leurs CGU. Les techniques utilisées (Playwright headless, rotation VPN, simulation comportement humain via `pyautogui`) montrent une conscience de cette limite.

> **Alerte critique :** Le fichier `.env` est committé dans Git avec des credentials ProtonVPN en clair et une clé Groq active. Changer ces credentials immédiatement et ajouter `.env` au `.gitignore`.

**Détection précoce :** Non. Google Trends sur 7 jours mesure un intérêt déjà présent. La logique est réactive, pas prédictive. Il n'y a pas de calcul de vélocité ou d'accélération.

**Déployabilité :** Non déployable. Pas d'auth utilisateur, pas de DB, pas de logique freemium, pas de paiement. Le VPN tourne via `pyautogui.moveTo(1181, 1057)` — des coordonnées écran hardcodées qui ne fonctionnent que sur le poste de développement.

**Pertinence dropshipping :** Partiellement. BSR Amazon + prix AliExpress permettent de calculer une marge brute, mais il manque la vélocité BSR dans le temps, la comparaison historique, et les sources organiques réelles.

---

## PARTIE 3 — Gaps critiques

| Priorité | Gap | Pourquoi critique | Complexité |
|---|---|---|---|
| 1 | Credentials `.env` dans Git | Clé Groq et MDP ProtonVPN exposés publiquement | Faible |
| 2 | Aucun signal organique (Reddit/TikTok) | C'est toute la valeur différentielle promise | Moyenne |
| 3 | Scoring = `sum(values)`, pas de vélocité | Sans vélocité, pas de signal "avant les autres" | Faible |
| 4 | Pipeline bloqué (50 fichiers à l'étape 1) | VPN `pyautogui` provoque des erreurs en cascade | Faible |
| 5 | Pas de base de données persistante | Impossible de comparer sur 4 semaines | Faible |
| 6 | VPN via `pyautogui` = incompatible cloud | Déploiement impossible sur serveur | Faible→Moyenne |
| 7 | Pas d'auth utilisateur ni de multi-tenancy | Boutons Login/SignUp pointent vers routes inexistantes | Élevée |
| 8 | Frontend déconnecté de la valeur dropshipping | Courbes brutes sans marge, liens, ni contexte | Faible |
| 9 | Sélecteurs CSS AliExpress fragiles | Classes comme `div.lh_jy` changent régulièrement | Moyenne |

---

## PARTIE 4 — Qualité du signal organique

**Capture de signaux organiques :** Non au sens strict. Amazon BSR et Google Trends France mesurent une demande existante. Un produit viral sur Reddit avant de toucher Amazon BSR ne serait pas détecté par ce pipeline.

**Scoring prédit-il ou décrit-il ?** Il décrit seulement l'existant. Un produit stable à 50/100 depuis 6 mois aura un meilleur score qu'un produit passé de 5 à 30 en deux semaines — alors que c'est le second qui est la vraie tendance émergente.

### Améliorations concrètes pour un signal 4-6 semaines en avance

1. **Reddit API (gratuite)** — surveiller `/r/Entrepreneur`, `/r/ecommerce`, `/r/deals`, `/r/taobao`, `/r/frugal`. Un produit mentionné pour la première fois avec un ratio votes/commentaires élevé précède systématiquement de 3-8 semaines son apparition publicitaire. Limite : 100 req/minute gratuitement.

2. **Vélocité au lieu du score absolu** : `(moy_7j - moy_30j_précédents) / moy_30j_précédents`. Un ratio > 2.0 = signal d'émergence. 10 lignes de code une fois SQLite en place.

3. **Fenêtre glissante Google Trends** : comparer 3 fenêtres successives de 4 semaines et calculer l'accélération sur la dernière période.

4. **TikTok Creative Center (sans auth)** : `ads.tiktok.com/business/creativecenter/trends/` expose des hashtags trending sans authentification — un scraper Playwright ciblé suffit.

---

## PARTIE 5 — Roadmap de progression

### Phase 1 — MVP déployable (0–4 semaines)

- [ ] **J1-2** — Supprimer `.env` de l'historique Git (BFG Repo Cleaner), changer la clé Groq et le MDP ProtonVPN, ajouter `.env` au `.gitignore`
- [ ] **J2-5** — Remplacer `pyautogui` + VPN local par un proxy réseau (ScraperAPI ou Oxylabs ~$30/mois), injecter dans Playwright
- [ ] **J5-10** — Migrer vers SQLite : tables `products` (id, name, amazon_bsr, amazon_price, ali_price, ali_sold, created_at) et `trends` (product_id, date, value)
- [ ] **J10-15** — Implémenter la vélocité : `velocity_score = (moy_7j - moy_30j) / moy_30j`, flag `is_emerging = True` si > 1.5
- [ ] **J15-20** — Ajouter Reddit avec `praw` : 5 subreddits ciblés, stocker (titre, score, nb commentaires, subreddit, date), croiser avec vélocité Trends → score composite
- [ ] **J20-28** — Refaire le frontend Tandor : liste de 10 produits avec score, marge estimée, lien AliExpress direct, courbe de vélocité sur 30 jours — déployer sur Railway ou Fly.io

### Phase 2 — Justifier €9/mois (1–3 mois)

- [ ] Alertes email/webhook quand un produit dépasse le seuil de vélocité
- [ ] Filtre par catégorie et marge minimum
- [ ] TikTok Creative Center scraper pour les hashtags en croissance liés aux produits détectés
- [ ] Supabase Auth (gratuit jusqu'à 50k MAU) + logique freemium (3 tendances/semaine, délai 2 semaines) vs payant (temps réel)
- [ ] Historique 90 jours pour valider les prédictions passées (preuve sociale)

### Phase 3 — Justifier €29/mois et résister à la copie (3–6 mois)

- [ ] Modèle ML prédictif (XGBoost, ~6 features) : `BSR_J+30 ~ f(velocity_trends, reddit_score, ali_sold_growth)`
- [ ] Multi-marchés : US, UK, DE
- [ ] Intégration Shopify directe (webhook ou app Shopify)
- [ ] Communauté Discord/Slack avec signaux en temps réel — rétention forte non copiable
- [ ] **Moat data** : plus l'historique organique s'accumule, plus les prédictions s'améliorent — Minea ne peut pas copier rétroactivement cet historique

---

## PARTIE 6 — Verdict final

**1. Ce projet a-t-il une chance réelle de concurrencer Minea sur le signal organique précoce ?**

Pas dans son état actuel. La base technique est valide, mais l'avantage différentiel annoncé — "signal organique avant les pubs" — repose entièrement sur Reddit et TikTok organique, qui sont tous les deux absents. Sans ces sources, Tandor est un agrégateur Amazon BSR + Google Trends FR que des outils gratuits (Exploding Topics, Glimpse) font déjà mieux. La thèse business est bonne ; l'exécution ne correspond pas encore à la promesse.

**2. Quel est le risque technique le plus dangereux ?**

Le couplage entre la collecte de données et une machine locale avec VPN GUI. Toute la logique anti-blocage repose sur `pyautogui.moveTo(1181, 1057)` — des coordonnées écran hardcodées qui cliquent sur ProtonVPN ouvert. Le scraping ne peut tourner que sur le poste de développement, en mode interactif, avec ProtonVPN ouvert. Impossible à planifier, impossible à déployer sur serveur, impossible à faire tourner la nuit. C'est une fragilité architecturale fondamentale.

**3. La priorité absolue pour les 30 prochains jours**

**Ajouter Reddit comme source de signal + calculer la vélocité au lieu d'un score brut.**

Reddit est gratuit, l'API est stable, `praw` existe depuis 10 ans. Un post Reddit sur un produit de niche avec 500+ upvotes précède systématiquement de 3 à 8 semaines son apparition dans les pubs Facebook — c'est exactement la promesse du produit, et c'est faisable en une semaine de code.

Plan d'action concret :
- Semaine 1 : SQLite + calcul de vélocité Google Trends
- Semaine 2 : Reddit scraper avec `praw` (5 subreddits ciblés)
- Semaine 3 : Score composite Reddit + Trends, affichage dans Tandor

À ce stade, Tandor est démontrable avec une vraie valeur mesurable.
