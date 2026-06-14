-- ===========================================================================
-- Schéma du moteur de détection de croissance organique.
-- Compatible SQLite (dev) et PostgreSQL (prod) au prix de types génériques.
-- Principe : séparer le RÉFÉRENTIEL produit (products), les SÉRIES temporelles
-- brutes (signal_history), l'état dérivé courant (signals), les PRÉDICTIONS
-- horodatées et leurs ISSUES mesurées (boucle de feedback), et les ALERTES.
-- ===========================================================================

-- --- Référentiel produit ---------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY,
    external_id   TEXT NOT NULL,          -- id source (AliExpress/CJ...)
    source        TEXT NOT NULL,          -- plateforme d'origine
    title         TEXT,
    category      TEXT,
    image_url     TEXT,
    product_url   TEXT,
    price         REAL,
    currency      TEXT,
    seller_count  INTEGER,
    review_count  INTEGER,
    first_seen    TEXT NOT NULL,          -- ISO-8601 UTC
    last_seen     TEXT NOT NULL,
    age_days      REAL,                   -- âge estimé
    UNIQUE (source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_last_seen ON products(last_seen);

-- --- Catalogue des sources de signal ---------------------------------------
CREATE TABLE IF NOT EXISTS signal_sources (
    name        TEXT PRIMARY KEY,         -- 'sales','google_trends','reddit'...
    direction   INTEGER NOT NULL DEFAULT 1, -- +1 hausse=bon, -1 inversé (BSR)
    is_early    INTEGER NOT NULL DEFAULT 0, -- source organique précoce ?
    description TEXT
);

-- --- Séries temporelles brutes (le socle factuel) --------------------------
CREATE TABLE IF NOT EXISTS signal_history (
    id           INTEGER PRIMARY KEY,
    product_id   INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    source       TEXT NOT NULL REFERENCES signal_sources(name),
    observed_at  TEXT NOT NULL,           -- ISO-8601 UTC
    value        REAL NOT NULL,
    UNIQUE (product_id, source, observed_at)
);
-- Index clé : lecture d'une série complète (product, source) par ordre temporel.
CREATE INDEX IF NOT EXISTS idx_sighist_pss ON signal_history(product_id, source, observed_at);
CREATE INDEX IF NOT EXISTS idx_sighist_source_time ON signal_history(source, observed_at);

-- --- État dérivé courant par (produit, source) -----------------------------
-- Cache des TrendFeatures recalculées, pour éviter de tout refitter à la volée.
CREATE TABLE IF NOT EXISTS signals (
    product_id    INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    source        TEXT NOT NULL REFERENCES signal_sources(name),
    level         REAL,
    velocity      REAL,                   -- pente log/jour
    acceleration  REAL,                   -- dérivée seconde log/jour²
    volatility    REAL,
    r2            REAL,
    n_points      INTEGER,
    computed_at   TEXT NOT NULL,
    PRIMARY KEY (product_id, source)
);

-- --- Prédictions horodatées (snapshot du score à un instant t) --------------
CREATE TABLE IF NOT EXISTS predictions (
    id             INTEGER PRIMARY KEY,
    product_id     INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    predicted_at   TEXT NOT NULL,
    organic_score  REAL NOT NULL,         -- 0-100
    confidence     REAL NOT NULL,         -- 0-1
    phase          TEXT NOT NULL,
    momentum       REAL,
    maturity       REAL,
    corroboration  INTEGER,
    monthly_growth REAL,
    model_version  TEXT NOT NULL,         -- 'prior:max-entropy' / 'learned:v3'
    explanation    TEXT                   -- JSON des contributions (explicabilité)
);
CREATE INDEX IF NOT EXISTS idx_pred_product_time ON predictions(product_id, predicted_at);
CREATE INDEX IF NOT EXISTS idx_pred_score ON predictions(organic_score DESC);
CREATE INDEX IF NOT EXISTS idx_pred_phase ON predictions(phase);

-- --- Issues mesurées (vérité terrain pour le feedback) ----------------------
CREATE TABLE IF NOT EXISTS prediction_results (
    id              INTEGER PRIMARY KEY,
    prediction_id   INTEGER NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    evaluated_at    TEXT NOT NULL,
    horizon_days    INTEGER NOT NULL,     -- fenêtre d'évaluation (ex. 28)
    actual_growth   REAL,                 -- croissance réelle observée
    exploded        INTEGER NOT NULL,     -- 1 si seuil de croissance atteint
    UNIQUE (prediction_id, horizon_days)
);
CREATE INDEX IF NOT EXISTS idx_predres_pred ON prediction_results(prediction_id);

-- --- Modèles appris (versionnés, promus seulement si meilleurs en backtest) -
CREATE TABLE IF NOT EXISTS models (
    version        TEXT PRIMARY KEY,
    created_at     TEXT NOT NULL,
    coefficients   TEXT NOT NULL,         -- JSON {feature: poids}
    bias           REAL NOT NULL,
    auc            REAL,                  -- score backtest hold-out
    precision_at_k REAL,
    brier          REAL,
    is_active      INTEGER NOT NULL DEFAULT 0
);

-- --- Alertes (franchissement de seuil de score/phase) -----------------------
CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY,
    product_id   INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL,
    type         TEXT NOT NULL,           -- 'emergent','score_threshold','acceleration'
    score        REAL,
    phase        TEXT,
    message      TEXT,
    delivered    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_alerts_undelivered ON alerts(delivered, created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_product ON alerts(product_id);
