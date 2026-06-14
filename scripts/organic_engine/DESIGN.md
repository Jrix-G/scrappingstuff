# Moteur de détection de croissance organique — Design

Concurrent technologique de Minea / SellTheTrend / Dropship.io, avec un angle
distinct : **détecter les produits AVANT leur saturation commerciale**, en
mesurant l'*accélération* de popularité plutôt que la popularité actuelle.

Ce document couvre les 10 livrables. Le code est implémenté et testé
(`python3 -m pytest tests/` → 18 tests verts ; `python3 demo.py` pour une démo).

---

## 1. Architecture

```
organic_engine/
├── collectors/   # interface de collecte (1 source = 1 implémentation)
│   └── base.py       Collector (Protocol) + SignalPoint
├── signals/      # transformation séries brutes -> features dérivées
│   ├── timeseries.py extract_trend (vélocité/accélération/volatilité), z robustes
│   └── features.py   catalogue SIGNALS, ProductFeatures
├── scoring/      # score composite + phase
│   ├── config.py     poids (PRIOR max-entropie, remplacé par apprentissage)
│   ├── phases.py     classification EMERGENT..DECLINING
│   └── engine.py     score_population (calculs transversaux + explicabilité)
├── analytics/    # boucle de feedback
│   ├── backtest.py   AUC, precision@k, Brier, calibration
│   └── learning.py   régression logistique L2 -> poids appris + valeur prédictive
├── database/
│   └── schema.sql    products, signals, signal_history, predictions,
│                     prediction_results, models, alerts (+ index)
├── api/
│   ├── main.py       FastAPI : /products, /product/{id}, /alerts
│   └── repository.py interface d'accès données (mémoire / SQL injectable)
└── tests/        # validation scientifique du cœur
```

Chaque composant est indépendant : le scoring ne connaît pas les collecteurs,
l'API ne connaît que l'interface `Repository`. **Tolérance aux pannes de
source** : un collecteur indisponible renvoie `[]` ; le scoring fonctionne avec
les sources présentes et baisse la *confiance* en conséquence.

---

## 2. Modèle mathématique

### 2.1 Pourquoi l'accélération, pas le niveau

Un produit populaire ≠ un produit qui va exploser. La grandeur prédictive d'une
explosion future est la **dérivée seconde** de la popularité (l'accélération),
quand le **niveau** est encore bas (pas saturé). Le moteur formalise « croissance
précoce » = *accélération élevée à bas niveau*.

### 2.2 Extraction des dérivées (par signal, par produit)

La croissance organique précoce est **multiplicative**. On travaille donc sur
`y = log(1 + valeur)` :

- **Vélocité** `v` = pente OLS de `y` vs temps (jours) = taux de croissance
  exponentiel instantané, **invariant d'échelle** (comparable entre produits de
  tailles différentes).
- **Accélération** `a` = `2·c` où `c` est le coefficient quadratique de
  l'ajustement `y = c·t² + b·t + d`. Distingue « croît régulièrement » (a≈0) de
  « EXPLOSE » (a>0).
- **Volatilité** `σ` = écart-type des résidus du trend (échelle log) → bruit du
  signal, utilisé pour pondérer la confiance.
- **R²** = qualité d'ajustement.

Ce sont des dérivées **mathématiquement définies**, pas des réglages.

### 2.3 Normalisation transversale robuste

Pour comparer des signaux d'unités différentes (ventes vs upvotes Reddit), on
standardise **à travers la population** via z-score robuste :

```
z(x) = (x − médiane) / (1.4826 · MAD)
```

Médiane/MAD plutôt que moyenne/écart-type : le e-commerce a une distribution à
queue lourde (best-sellers extrêmes) qui ferait exploser un écart-type classique.

### 2.4 Score composite

```
momentum_i      = Σ_s w_s · (0.5·z(v_{i,s}) + 0.5·z(a_{i,s}))  /  Σ_s w_s
   avec w_s     = fiabilité(R², σ, n_points) · boost_source_précoce

corroboration_i = # sources de i avec croissance mensuelle nette > 5 %
                  (propriété INTRA-produit, indépendante de la population)
momentum_adj_i  = momentum_i · (1 + 0.15·max(0, corroboration_i − 1))   [si >0]

maturity_i      = moyenne z(niveau ventes, âge, nb vendeurs, log avis)

organic_raw_i   = momentum_adj_i − λ · max(0, maturity_i)        (λ = 0.6)

SCORE_i (0-100) = 100 · rang_percentile(organic_raw)_i
```

- Le **boost source précoce** (Reddit, TikTok, YouTube, Pinterest, Trends ×1.3)
  encode l'hypothèse métier : l'organique précède la demande de masse.
- La **corroboration** est l'anti-faux-positif clé : un mouvement confirmé par
  plusieurs sources indépendantes est très improbable sous le seul bruit.
- Le score final est un **rang-percentile** → interprétable (« top 5 % du
  potentiel organique actuel »).

### 2.5 Confiance (séparée du score)

```
confidence_i = (couverture · adéquation_historique · stabilité · corroboration)^¼
```

Moyenne géométrique : une seule dimension faible plombe la confiance (prudence).
Le score est le point estimé ; la confiance dit *à quel point s'y fier*.

### 2.6 Détection d'anomalie

Pic = `|z(vélocité)| > 3.5`. Un pic isolé peut être un bug OU une viralité réelle.
La distinction se fait par **corroboration inter-sources** : seul un pic présent
sur ≥2 sources indépendantes est traité comme signal, pas comme bruit.

---

## 3. Schéma SQL

Voir `database/schema.sql`. Sept tables : `products`, `signal_sources`,
`signal_history` (séries brutes, socle factuel), `signals` (features dérivées en
cache), `predictions` (snapshots horodatés du score + explication JSON),
`prediction_results` (issues mesurées = vérité terrain), `models` (poids appris
versionnés), `alerts`. Index optimisés pour : lecture d'une série
`(product_id, source, observed_at)`, tri par score, requêtes par phase, alertes
non délivrées.

---

## 4. API backend

`api/main.py` (FastAPI) :

- `GET /api/products?min_score&phase&limit` — liste scorée triée.
- `GET /api/product/{id}` — score **explicable** + historique des signaux.
- `GET /api/alerts` — émergents / franchissements de seuil.

Chaque réponse inclut `reasons` (top contributions lisibles) et `contributions`
(décomposition par source) → **explicabilité native**.

---

## 5. Frontend (structure)

```
/dashboard      Top produits (score, phase, mini-graphe vélocité), filtres
/product/:id    Score + jauge confiance, graphes par signal (niveau/vélocité/
                accélération), encart « pourquoi ce score » (contributions),
                marge estimée, lien source
/alerts         Produits fraîchement EMERGENT, réglage des seuils
/backtest       Performance historique du modèle (calibration, AUC) = preuve sociale
```

Principe UX : **tout score est cliquable jusqu'à sa justification**. L'utilisateur
doit comprendre *pourquoi* un produit est recommandé, sinon il ne fait pas confiance.

---

## 6. Algorithme de scoring

Implémenté dans `scoring/engine.py::score_population` (transversal à la
population). Testé dans `tests/test_engine.py` : un produit émergent (bas niveau
+ accélération multi-sources) score au-dessus d'un mature et d'un déclinant ;
corroboration, confiance et explicabilité validées.

### Classification de phase (`scoring/phases.py`)

Fonction déterministe de (croissance mensuelle, accélération, percentile de niveau,
historique) :

| Phase | Condition |
|---|---|
| DECLINING | croissance < −5 %/mois |
| MATURE | croissance plate (|g| ≤ 5 %/mois) |
| PEAK | croissance >0, niveau ≥ p85, accélération ≤ 0 |
| EMERGENT | croissance >0, niveau ≤ p35, accélération >0, historique ≤ 45 j |
| EARLY_GROWTH | croissance ≥ 30 %/mois, niveau ≤ p50, accélération ≥ 0 |
| GROWTH | sinon (croît, niveau déjà significatif) |

Phases mises en avant : **EMERGENT, EARLY_GROWTH** (avant saturation).

---

## 7. Auto-amélioration (boucle de feedback)

1. À chaque run, on **enregistre** la prédiction (score + features) dans
   `predictions`.
2. Après `horizon_days` (ex. 28), on **mesure** l'issue réelle (`actual_growth`,
   `exploded`) dans `prediction_results`.
3. `analytics/backtest.py` calcule **AUC, precision@k, Brier, calibration** sur
   ces couples.
4. `analytics/learning.py` ajuste une **régression logistique L2** : ses
   coefficients **remplacent le prior** d'équipondération, et leur magnitude
   donne la **valeur prédictive de chaque signal** (testé : le signal vraiment
   prédictif domine le bruit).
5. **Promotion conditionnelle** : un nouveau modèle n'est activé (`models.is_active`)
   que s'il bat l'actuel en backtest hold-out. On ne déploie jamais des poids
   non validés.

---

## 8. Plan de développement & priorisation

| Phase | Livrable | Pourquoi en premier |
|---|---|---|
| **P0 (fait)** | Moteur scoring + phases + backtest + tests | Le cœur différenciant, vérifiable sans données réelles |
| **P1** | Collecteurs CJ + Google Trends + 1 source précoce (Reddit) | Sans ≥1 source organique, pas de proposition de valeur |
| **P1** | Repository SQL + ingestion `signal_history` | Persiste l'historique = condition de la vélocité |
| **P2** | API + frontend dashboard + explicabilité | Rendre le signal consommable et crédible |
| **P2** | Alertes EMERGENT (email/webhook) | Le moment « waouh » qui retient l'abonné |
| **P3** | Boucle feedback active + poids appris | Le moat : précision qui s'améliore avec le temps |
| **P3** | TikTok/YouTube/Pinterest | Élargir la corroboration |

**Priorité absolue** : 1 source organique précoce réelle + historique persistant.
Le reste du moteur est déjà prêt à la consommer.

---

## 9. Analyse des risques

| Risque | Impact | Mitigation |
|---|---|---|
| **Cold-start** (pas d'issues pour apprendre) | Poids = prior non validé | Prior max-entropie explicite + bascule auto vers appris dès assez de données |
| **Faux positifs viraux** (pic = bug data) | Mauvaises recommandations | Corroboration inter-sources obligatoire + détection d'anomalie |
| **Accès aux sources** (blocage AliExpress, quotas API) | Données manquantes | Sources interchangeables, scoring dégradé + confiance abaissée, jamais d'exception |
| **Survivorship bias** dans le backtest | Sur-optimisme | Évaluer TOUTES les prédictions, pas seulement les gagnantes |
| **Drift temporel** (les modes changent) | Modèle périmé | Ré-apprentissage périodique + fenêtre glissante |
| **Historique trop court** au lancement | Vélocité peu fiable | Confiance basse signalée ; ne pas survendre les scores précoces |
| **Sur-ajustement** sur peu d'issues | AUC backtest trompeur | Régularisation L2 forte + hold-out + promotion conditionnelle |
| **Gaming** (vendeurs gonflent les signaux) | Pollution du signal | Pondérer par fiabilité, privilégier sources difficiles à manipuler |

---

## 10. Améliorations futures

- **Modèle de survie** (Cox / hazard) pour estimer le *temps avant explosion*,
  pas seulement la probabilité.
- **Gradient boosting** (XGBoost) une fois assez d'issues, avec interactions
  non linéaires entre signaux.
- **Détection de changepoint bayésienne** (ruptures de tendance plus fines que
  l'accélération polynomiale).
- **Embeddings produit** (titre/image) pour transférer le signal entre produits
  similaires et atténuer le cold-start par produit.
- **Décomposition par catégorie** : normaliser au sein de la catégorie (un score
  relatif intra-niche, plus actionnable).
- **Corroboration pondérée par l'indépendance réelle** des sources (corrélations
  estimées au lieu d'un simple comptage).
- **Calibration isotonique** des scores en probabilités fiables pour l'utilisateur.
```
