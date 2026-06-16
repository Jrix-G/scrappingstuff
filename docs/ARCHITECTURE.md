# Tandor — Architecture & Roadmap (vue CTO fondateur)

> Objectif : passer d'un prototype (moteur Python sur Pi + JSON statique + React) à un
> SaaS multi-tenant capable de répondre, **avant le marché**, à : *« ce produit a-t-il
> assez de signaux pour devenir un gagnant organique ? »* — et de le **prouver**.
>
> Principe directeur : on ne devient indispensable qu'en montant l'échelle de valeur
> `Donnée → Insight → Décision → Action → Résultat`. Chaque système ci-dessous fait
> monter d'un cran ET accumule du contexte propriétaire (le moat).

---

## 0. Décisions de plateforme (transversales — à figer avant tout le reste)

Ces choix sont communs aux 8 systèmes. Les décider une fois évite la dette.

| Domaine | Choix MVP | Choix cible | Justification |
|---|---|---|---|
| **Langage backend** | **Python / FastAPI** | idem | Le moteur, le ML et l'orchestration LLM sont en Python. Un seul langage = moins de dette pour une petite équipe. FastAPI = async natif, Pydantic (validation/typage), OpenAPI auto. On retire le serveur Node (`backend/index.js`) ou on le garde en proxy mince. (NestJS rejeté : ajoute un 2e écosystème sans gain.) |
| **Base de données** | **PostgreSQL + TimescaleDB + pgvector** (1 seul Postgres, Docker) | **Timescale Cloud** managé | UNE base relationnelle qui fait time-series (hypertables, compression, continuous aggregates, rétention) ET vecteurs (pgvector pour le RAG). Tout est joignable → c'est le moat. Évite 3 datastores (InfluxDB + Pinecone + Postgres) à maintenir. |
| **Auth / users** | **Clerk** (managé) | idem ou self-host OSS | Ne jamais coder sa propre crypto/sessions. Clerk = email+OAuth+MFA+orgs en heures, pas en semaines (priorité : vitesse d'exécution). Users mirrorés en base via webhook. Multi-tenant = colonne `org_id` + **Row-Level Security** Postgres. |
| **File / queue** | **Redis + Arq** (worker async Python) | idem + **Dagster** pour l'ETL | Redis = broker + cache + rate-limit. Arq pour les jobs async (briefs, alerts). L'ETL quotidien reste en cron tant que le DAG < 5 étapes ; passer à **Dagster** (lineage, retries, backfills observables) quand il grandit. |
| **LLM** | **Claude** (Anthropic) | idem | Briefs profonds : **Opus 4.8** (`claude-opus-4-8`, $5/$25 par M tokens). Analyste conversationnel : **Sonnet 4.6** (`claude-sonnet-4-6`, $3/$15) en *tool-use*. Classification/tagging de masse : **Haiku 4.5** (`claude-haiku-4-5`, $1/$5). Tiering = qualité là où ça compte, coût maîtrisé ailleurs (choix explicite, voir §Coûts). |
| **Stockage objet** | Cloudflare **R2** | idem | Archives Parquet (ML) + assets créatifs (GTM kit). R2 = pas de frais d'egress (vs S3). |
| **Hébergement** | **1 VPS** (Hetzner CPX21 ~€8/mo) en Docker Compose ; le **Pi reste nœud collecteur** qui pousse vers la base VPS | Conteneurs Fly.io/Render + Timescale Cloud + Cloudflare CDN | Un VPS + DB managée tient des milliers d'users. Pas de k8s prématuré. |

**Pattern LLM transverse** (vaut pour briefs ET analyste) :
- **Tool-use / text-to-SQL** : l'analyste appelle des *outils* (`query_timeseries`, `search_products`, `get_product_history`) qui interrogent Timescale, plutôt qu'on lui déverse la donnée. Réponses fondées + citables.
- **Prompt caching** : system prompt + schéma + few-shots en préfixe caché (lecture ~0,1×). Indispensable pour le coût.
- **Batches API** (−50 %) : génération nocturne des briefs en batch.
- **Provenance** : chaque affirmation IA stocke les `signal_event` / snapshots utilisés (citations).

---

## 1. Historique Time-Series  ⭐ PRIORITÉ ABSOLUE

> Le seul moat inattaquable : un concurrent qui démarre demain ne peut **pas**
> reconstruire 6 mois de trajectoires. Chaque jour non capturé est perdu à jamais.
> → **À démarrer aujourd'hui, même sans aucun utilisateur.**

**Architecture.** Collecteurs Python existants → normalisation/dédup → upsert dimension
`products` + insert append-only dans l'hypertable `product_snapshots` → calcul des scores
(scoring existant) → features dérivées (deltas/dérivées) → refresh des continuous aggregates
→ émission de `signal_event` pour les alertes. Idempotent par `(product_id, jour)`.

**Schéma (cœur)**
```sql
-- Dimension : 1 ligne par produit (attributs lents)
CREATE TABLE products (
  product_id   TEXT PRIMARY KEY,          -- hash stable: source + external_id
  source       TEXT NOT NULL,             -- cj | aliexpress | ebay | ...
  external_id  TEXT NOT NULL,
  title        TEXT, category TEXT, image_url TEXT,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  attrs        JSONB DEFAULT '{}'         -- variantes, poids, etc.
);

-- Faits : 1 ligne par produit par jour (hypertable)
CREATE TABLE product_snapshots (
  ts            TIMESTAMPTZ NOT NULL,
  product_id    TEXT NOT NULL REFERENCES products,
  price NUMERIC, cost NUMERIC, net_margin NUMERIC,
  sellers_count INT, orders_volume INT, ad_count INT,
  reddit_mentions INT, reddit_sentiment NUMERIC,
  trends_index  NUMERIC,
  tandor_score  NUMERIC,
  s_growth NUMERIC, s_margin NUMERIC, s_saturation NUMERIC,
  s_organic NUMERIC, s_reddit NUMERIC, s_trends NUMERIC,
  phase TEXT, verdict TEXT
);
SELECT create_hypertable('product_snapshots','ts', chunk_time_interval => INTERVAL '7 days');
ALTER TABLE product_snapshots SET (timescaledb.compress,
  timescaledb.compress_segmentby = 'product_id');
SELECT add_compression_policy('product_snapshots', INTERVAL '7 days');   -- ~90-95% gain

-- Log générique de signaux bruts (base des features ML futures)
CREATE TABLE signal_events (
  ts TIMESTAMPTZ NOT NULL, product_id TEXT NOT NULL,
  source TEXT, signal_type TEXT, value NUMERIC, meta JSONB
);
SELECT create_hypertable('signal_events','ts', chunk_time_interval => INTERVAL '7 days');

-- Rollups pré-calculés pour le dashboard (continuous aggregate)
CREATE MATERIALIZED VIEW product_features_daily
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', ts) AS day, product_id,
       last(tandor_score, ts) AS score,
       last(tandor_score, ts) - first(tandor_score, ts) AS score_delta_1d,
       avg(reddit_sentiment) AS sentiment, max(sellers_count) AS sellers
FROM product_snapshots GROUP BY day, product_id;
```

**Stratégie de stockage / indexation.** Compression Timescale (colonnaire) sur snapshots
> 7 j. Index composite `(product_id, ts DESC)` ; partition d'espace par hash `product_id`
au passage à l'échelle. Continuous aggregates pour les dérivées (croissance 7/30 j,
vélocité, accélération) → requêtes dashboard quasi gratuites. **Historisation infinie** =
rollups compressés gardés *forever* en base + raw exporté en **Parquet/R2** (entraînement ML).

**Flux** : `cron Pi (existant) → collect_*.py → normalize → COPY/upsert Postgres VPS → scoring → refresh agrégats → signal_events`.

**Coût** : MVP quasi nul (VPS €8/mo, la base tient des années compressée). Cible Timescale Cloud ~$50–300/mo selon volume.

**Risques → mitigations** :
- *Identité produit instable entre sources* → clé canonique (hash source+id) + table de résolution d'entités (fuzzy match titres/images en phase 2).
- *Snapshot manqué (Pi down)* → monitoring de fraîcheur (`max(ts)` par source) + alerte ; backfill idempotent.
- *Dérive des scores dans le temps* → versionner la formule de score (`score_version`) pour comparer des pommes avec des pommes.

**Monitoring** : Grafana sur Timescale ; métriques `rows_ingested/run`, fraîcheur par source, anomalie de chute de volume.

**Déploiement progressif** : (a) base + hypertables sur VPS → (b) brancher le cron Pi → (c) backfill du `products.json` actuel comme J0 → (d) agrégats + Grafana.

**Priorité réelle : 1/10 (la plus haute).** **MVP** : snapshots quotidiens + compression. **Idéal** : Parquet/R2, entity-resolution, feature store pour ML.

---

## 2. Backend réel + Auth + Persistance

**Architecture.** FastAPI (REST + OpenAPI) ; couche service ; SQLAlchemy/SQLModel sur le
Postgres unique ; Clerk pour l'auth (JWT vérifié en middleware) ; **RLS Postgres** pour
l'isolation multi-tenant ; Redis pour cache + rate-limit par plan.

**Structure API** (extrait) : `/auth/*` (webhooks Clerk), `/products` (recherche/filtre
**côté serveur**, pas un JSON de 200 lignes), `/products/{id}/history`, `/products/{id}/brief`,
`/watchlists`, `/alerts`, `/portfolio`, `/chat` (analyste), `/trending` (public), `/billing/*` (Stripe).

**DB (entités SaaS)** : `users`, `orgs`, `memberships(role)`, `subscriptions(plan,status)`,
`watchlists`, `alerts`, `portfolio_items`, `briefs`, `chat_sessions`. Multi-tenant : chaque
table porte `org_id` + policy RLS `USING (org_id = current_setting('app.org_id'))`.

**Gestion des accès** : rôles `owner/admin/member` ; permissions par plan (quotas briefs/chat) ;
quotas appliqués en middleware via Redis.

**Coût** : compris dans le VPS. Stripe = % transactions. Clerk gratuit < 10k MAU.

**Risques → mitigations** : *fuite cross-tenant* → RLS + tests d'isolation automatisés ;
*lock-in auth* → Clerk encapsulé derrière une interface `AuthProvider` ; *secrets* → SOPS/Vault, jamais en repo.

**Déploiement** : Docker Compose (api, worker, postgres, redis, caddy) → CI GitHub Actions → un VPS, puis Fly.io multi-région.

**Priorité : 2/10 (fondation).** **MVP** : auth + RLS + API produits/history + Stripe. **Idéal** : SSO, audit log, conformité (RGPD : export/suppression).

---

## 3. Opportunity Brief IA  ⭐ AHA MOMENT

**Architecture.** Pipeline RAG+raisonnement : récupération (snapshots récents +
trajectoire historique + voisins de catégorie + extraits Reddit via pgvector) → prompt
structuré → **Opus 4.8** (`output_config.format` JSON schema → sortie structurée fiable) →
persistance `briefs` + provenance. Génération **on-demand** (clic) et **batch nocturne**
(top-N / produits ayant changé de phase) via Batches API.

**Sortie (schéma)** : `executive_summary`, `signals_positive[]`, `signals_negative[]`,
`risk_level`, `organic_potential`, `ad_potential`, `entry_timing`, `confidence_score`,
`justification`, `citations[]` (ids des signaux utilisés).

**Flux** : `trigger → retrieve(Timescale+pgvector) → Claude (cache préfixe) → valider schéma → stocker → afficher`.

**Coût** (estim.) : ~3–5k tokens in (cachés en grande partie) + ~1,5k out.
- Opus 4.8 ≈ **$0,05–0,07/brief** ; en **Batches −50 %** ≈ $0,03.
- Variante coût : Sonnet 4.6 ≈ **$0,02/brief** (≈3× moins). **Reco** : Opus pour le top
  opportunités / plan payant, Sonnet pour le volume — tu décides le tiering.
- 500 briefs/j en Opus batché ≈ ~$15/j ; en Sonnet batché ≈ ~$6/j.

**Risques → mitigations** : *briefs « confiants mais faux »* → **dépend du backtest §9** (ne pas générer de verdict tant que le score n'est pas validé) + `confidence_score` honnête + citations ; *coût qui dérape* → on-demand + batch top-N + caching + tiering ; *hallucination de chiffres* → tool-use/valeurs injectées, jamais inventées.

**Déploiement** : (a) brief on-demand Sonnet → (b) sortie structurée + provenance → (c) batch nocturne → (d) Opus sur le premium.

**Priorité : 3/10 (saut de valeur).** **MVP** : brief on-demand structuré + citations. **Idéal** : briefs personnalisés (marché/budget/niche de l'user), comparaison vs gagnants passés.

---

## 4. Analyste Conversationnel  ⭐ SENSATION « J'EN AI BESOIN »

**Architecture.** Agent **tool-use** (Claude **Sonnet 4.6**) avec outils :
`search_products(filters)`, `query_timeseries(product, metric, window)`,
`compare_products(ids)`, `semantic_search(text)` (pgvector), `get_brief(id)`. La boucle
agentique orchestre ; le modèle **cite** la donnée. Mémoire de conversation +
**mémoire long terme** des préférences user (table `chat_memory`) → personnalisation.

**Flux** : `question → Claude planifie → appels outils (SQL/pgvector) → synthèse citée → réponse`. Streaming (SSE) pour l'UX.

**Coût** : ~10–30k tokens/conversation avec caching ≈ **$0,05–0,15/conv** (Sonnet). Scale avec les users actifs ; quota par plan.

**Risques → mitigations** : *text-to-SQL dangereux* → outils paramétrés (pas de SQL libre) + DB read-replica en lecture seule ; *réponses non fondées* → réponses uniquement à partir des résultats d'outils + citations obligatoires ; *coût abusif* → quotas Redis + caching agressif.

**Déploiement** : (a) 3 outils read-only → (b) streaming + citations → (c) mémoire préférences → (d) agent proactif (cf. §6).

**Priorité : 4/10 (verrou émotionnel).** **MVP** : Q&A sur la base avec citations. **Idéal** : proactif (« 3 moves aujourd'hui »), multi-tour, mémoire qui personnalise.

---

## 5. Trending Now public — moteur d'acquisition

**Architecture.** Pages SSR/SSG (Next.js *ou* pré-rendu statique régénéré depuis l'API)
servies derrière Cloudflare CDN. Contenu généré depuis la donnée propriétaire (top
catégories/produits émergents, anonymisés/teasés). `sitemap.xml`, JSON-LD, OpenGraph →
SEO + partage. Régénération nocturne. CTA → inscription (capture email).

**Flux** : `agrégats Timescale → générateur de pages (+ résumé Haiku) → cache CDN → SEO`.

**Coût** : quasi nul (CDN + Haiku marginal). **Meilleur ROI acquisition.**

**Risques → mitigations** : *donner trop = se faire copier* → teaser (tendance oui, score/brief complet réservé au login) ; *SEO lent* → contenu unique + preuve (trajectoires réelles « flaggé en émergent le X »).

**Déploiement** : (a) page statique top-tendances → (b) SEO/JSON-LD → (c) régénération auto → (d) rapports/email gated.

**Priorité : 5/10 (acquisition n°1, effort faible).** **MVP** : 1 page top-tendances régénérée. **Idéal** : pages par niche/catégorie indexables, rapports téléchargeables contre email.

---

## 6. Alertes & Digests — la rétention par l'habitude

**Architecture.** Règles évaluées à chaque ingestion (`signal_events` → moteur de règles) :
score en hausse, croissance anormale, changement de phase, nouveau signal fort. Fan-out
multi-canal : email (Resend/Postmark), in-app (table `notifications`), push web. Digest
quotidien personnalisé (worker Arq) résumé par **Haiku/Sonnet**.

**Flux** : `ingestion → règles → file → canaux ; cron quotidien → digest par user → email`.

**Coût** : email ~$0,001/envoi ; résumé LLM marginal.

**Risques → mitigations** : *fatigue de notif* → seuils + regroupement + préférences ; *faux positifs* → règles calibrées sur le backtest §9.

**Déploiement** : (a) alertes watchlist in-app → (b) email → (c) digest quotidien → (d) règles « anomalies » ML.

**Priorité : 6/10 (rétention pas chère).** **MVP** : alerte changement de phase + digest quotidien. **Idéal** : détection d'anomalies apprise, multi-canal.

---

## 7. GTM Kit automatique — de la découverte à l'exécution

**Architecture.** À partir du produit + brief : génération (Claude Sonnet, sorties
structurées) de hooks TikTok/Meta, angles, personas, scripts UGC, copy de landing.
Assets stockés en R2, éditables, exportables. Contextualisé par les signaux réels.

**Flux** : `produit + brief → prompts spécialisés → assets structurés → R2 → UI éditable/export`.

**Coût** : ~$0,03–0,08/kit (Sonnet).

**Risques → mitigations** : *contenu générique* → ancrer sur données réelles (audience Reddit, angle = signal détecté) + few-shots de gagnants ; *droits images créatives* → texte d'abord, génération visuelle en option externe.

**Priorité : 7/10 (fort une fois §3 en place).** **MVP** : hooks + copy landing. **Idéal** : personas+UGC+ciblage, variantes A/B.

---

## 8. Attribution & ROI — le moat ultime

**Architecture en 2 temps.**
1. **MVP léger (jour 1, sans intégration)** : feedback auto-déclaré dans le **portfolio**
   (« je teste / lancé / tué » + CA/dépense saisis). Alimente le data flywheel ET la preuve sociale.
2. **Cible** : connecteurs Shopify / Meta / TikTok (OAuth) → ingestion CA & dépenses pub →
   corrélation avec les recommandations IA → **ROI généré attribué** (« les produits trouvés
   via Tandor t'ont généré €X »).

**DB** : `portfolio_items(status, found_via, revenue, ad_spend)`, `connections(provider, tokens)`, `attribution_events`.

**Coût** : dev élevé (OAuth + webhooks par plateforme) ; infra marginale.

**Risques → mitigations** : *complexité OAuth/tokens* → encapsuler par provider, refresh géré ; *confiance/sécurité données financières* → chiffrement, scopes minimaux, RLS ; *attribution contestable* → modèle transparent + auto-déclaré comme garde-fou.

**Priorité : 8/10 (pic de valeur, mais tard).** **MVP** : portfolio auto-déclaré. **Idéal** : attribution multi-plateforme automatique.

---

## 9. (MANQUANT au plan initial) Backtest / Eval Harness  ⭐ CRITIQUE

> **L'erreur stratégique n°1 serait de bâtir briefs + analyste sur un score non validé.**
> Sans preuve que le Tandor score *prédit* les gagnants, on construit une IA « qui sonne
> intelligent » — l'inverse de l'objectif. C'est aussi ce qui rend le marketing (#5) et la
> preuve sociale crédibles.

**Architecture.** Dès que le time-series s'accumule : pour chaque produit, mesurer si le
score/phase à T prédit la trajectoire à T+30/60/90 j (croissance ventes/volume/saturation).
Métriques : **precision@K**, lift vs aléatoire, courbe de calibration du `confidence_score`.
Boucle : résultats → ajustement du scoring (`score_version`) → comparaison versionnée.

**Priorité : intercalée en Phase 1** (dès qu'il y a ~30–60 j d'historique). C'est le
multiplicateur de confiance de #3, #4, #5, #6.

---

## Critique du plan initial & priorités réorganisées

**Ce qui est juste** : #1 en priorité absolue (le moat), l'ordre global 1→8 est raisonnable.

**Erreurs stratégiques à corriger** :
1. **Aucun système de validation du signal** → ajouter le **Backtest/Eval (#9)**. Sans lui, briefs/analyste = risque de confiance injustifiée.
2. **#5 (Trending Now) placé trop tard** : c'est l'acquisition la moins chère et un sous-produit gratuit de la donnée → le faire **en parallèle** de #3, pas après #4.
3. **#8 (attribution) traité comme un bloc tardif** : le **portfolio auto-déclaré** peut démarrer dès le jour 1 (capture l'outcome + preuve sociale) sans aucune intégration.
4. **Sur-ingénierie « milliers d'users » day one** : un VPS + DB managée suffit. Pas de k8s/microservices prématurés.
5. **Piège de coût LLM** : générer tous les briefs en Opus = brûler du cash. Tiering (Opus/Sonnet/Haiku) + Batches + caching + génération on-demand/top-N.
6. **#1 ne doit pas attendre #2** : la capture time-series démarre **sans utilisateurs**.

**Roadmap optimale (≈ 6 mois)**

| Phase | Fenêtre | Livrables | Pourquoi |
|---|---|---|---|
| **0** | Semaine 1 (maintenant) | **#1 MVP** : Postgres/Timescale, cron Pi qui pousse, J0 = `products.json`, compression | Démarrer le moat sans attendre — chaque jour compte |
| **1** | S2–6 | **#2** (auth, RLS, API produits/history, Stripe) + brancher le dashboard React sur l'API live + **#9** backtest dès ~30 j d'historique | Fondation + validation du signal |
| **2** | S6–10 | **#3** Opportunity Brief + **#5** Trending Now (parallèle) | Aha moment + acquisition |
| **3** | S10–14 | **#4** Analyste conversationnel + **#6** Alertes/digests | Rétention (besoin + habitude) |
| **4** | M4–6 | **#7** GTM Kit + **#8 MVP** portfolio auto-déclaré | Exécution + début du flywheel d'outcome |
| **5** | M6+ | **#8** intégrations Shopify/Meta/TikTok + **ML** (prédiction de phase sur le time-series accumulé) | Verrou final + intelligence prédictive |

**Métriques nord** : *time-to-first-winner* (activation), funnel *brief→save→launch*,
*precision@K* (backtest), WAU/DAU (habitude), *GMV attribué* (#8).

**Le fil rouge** : à chaque phase on monte l'échelle de valeur ET on accumule du contexte
(préférences, décisions, outcomes) — comme la mémoire d'un assistant, ça rend le départ
coûteux. Le moat = la donnée historique (#1) + la preuve d'outcome (#8/#9), tous deux
impossibles à répliquer rétroactivement.
