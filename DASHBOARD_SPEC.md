# Tandor — Cahier des charges UX/UI du Dashboard

Document de référence destiné à **Claude Design**. Objectif : permettre de construire
l'intégralité du dashboard SaaS premium **sans information complémentaire**. Niveau de
détail : suffisant pour une équipe de designers seniors + développeurs front-end.

Produit : **Tandor** — plateforme de détection de produits gagnants en dropshipping
*avant* leur saturation. Positionnement émotionnel : **un hedge fund spécialisé dans la
découverte de produits**. L'utilisateur doit ressentir confiance, intelligence,
technologie, précision, puissance.

Référentiel de qualité visé (à dépasser) : Linear (rigueur, vitesse), Mercury/Ramp
(densité financière maîtrisée), Stripe (clarté des data-viz), Vercel/Framer (matière et
profondeur), Similarweb/Ahrefs/Semrush (densité analytique sans lourdeur).

---

## 0. CONTRAT DE DONNÉES (source de vérité — ne rien inventer au-delà)

Le backend produit un JSON par produit. **Toute visualisation doit se mapper sur ces
champs réels.** Aucun graphique ne doit exiger une donnée absente de cette liste.

### 0.1 Champs « produit » (export `analyze.py`)
| Champ | Type | Sens | Usage UI |
|---|---|---|---|
| `product_id` | string | identifiant CJ | clé, deep-link |
| `name` | string | titre produit (EN) | titre carte/hero |
| `category` | string | catégorie CJ | tag, filtre |
| `image` | url | visuel produit | média carte/hero |
| `cost_eur` | float | coût fournisseur CJ | bloc économie |
| `retail_eur` | float | prix de vente estimé | bloc économie |
| `gross_margin_eur` | float | marge brute € | **« marge estimée »** |
| `margin_pct` | float 0–1 | marge brute / prix | jauge marge |
| `net_after_cpa_eur` | float | profit net après pub | bloc économie, KPI |
| `sellability` | float 0–100 | score de vendabilité financière | **score potentiel** |
| `verdict` | enum `BUY`/`WATCH`/`PASS` | décision | badge cardinal |
| `scores.margin` | float 0–1 | sous-score marge | radar, barres |
| `scores.price` | float 0–1 | sous-score prix d'impulsion | radar, barres |
| `scores.saturation` | float 0–1 | sous-score saturation offre | radar, barres |
| `scores.freshness` | float 0–1 | sous-score fraîcheur | radar, barres |
| `listed_num` | int | nb de vendeurs CJ | **« saturation »** |
| `age_days` | float | âge produit (jours) | **« date de détection »** |
| `seasonality.multiplier` | float | demande du mois courant | badge saison |
| `seasonality.profile` | string\|null | profil saisonnier | tag saison |
| `seasonality.peak_month` | int 1–12 | mois de pic | courbe saison |
| `seasonality.label` | string | phrase saison | tooltip |
| `season_factor` | float 0.6–1.4 | multiplicateur de tri | indicateur |
| `rank_score` | float | score de classement | tri par défaut |
| `reason` | string | justification lisible | encart « pourquoi » |

### 0.2 Champs « enrichissement organique » (export `enrich.py`)
| Champ | Type | Sens | Usage UI |
|---|---|---|---|
| `organic_score` | float 0–100 | momentum organique (rang-percentile) | **score global / potentiel** |
| `phase` | enum | `EMERGENT`/`EARLY_GROWTH`/`GROWTH`/`MATURE`/`PEAK`/`DECLINING` | badge phase, timeline |
| `monthly_growth` | float | croissance mensuelle (ex. 0.61 = +61 %) | **« vitesse de croissance »** |
| `confidence` | float 0–1 | fiabilité du score | **« confiance de prédiction »** |
| `reasons` | string[] | top raisons (par source) | liste « signaux détectés » |

### 0.3 Séries temporelles (par produit, par source) — pour les graphiques
Chaque source expose une série `(timestamps_days, values)` et des features dérivées :
`velocity` (pente log/jour), `acceleration` (dérivée 2nde), `volatility`, `r2`,
`n_points`, `level`, `monthly_growth`.

Sources disponibles : `google_trends` (intérêt 0–100, ~90 pts), `reddit` (mentions
hebdo), `cj_listings` (nb vendeurs dans le temps), et à terme `sales`, `amazon_bsr`,
`tiktok`, `youtube`, `pinterest`.

Décomposition explicable par source : `contributions[]` = `{source, z_velocity,
z_acceleration, contribution}`. **C'est la matière des graphiques de corrélation/radar.**

### 0.4 Scores dérivés à composer côté produit (définis ici pour cohérence)
- **Tandor Score** (score global affiché partout, 0–100) =
  `0.55·organic_score + 0.45·sellability`, arrondi entier. C'est LE chiffre héros.
- **Score Croissance** = normalisation de `monthly_growth` sur \[−50 %, +150 %] → 0–100.
- **Score Trends** = contribution `google_trends` re-mappée 0–100 (z → percentile).
- **Score Reddit** = contribution `reddit` re-mappée 0–100.
- **Score Potentiel** = `organic_score`.
- **Niveau de risque** = fonction de `confidence` + `volatility` + `listed_num`
  (faible confiance OU forte volatilité OU 0 vendeur ⇒ risque ↑). 3 niveaux :
  `Faible` / `Modéré` / `Élevé`.

---

## 1. DESIGN SYSTEM

Identité : **« terminal de trading, mais habité »**. Sombre, dense, précis, avec une
seule couleur-signal qui guide l'œil vers l'opportunité. Cohérent avec la landing Tandor
existante (fond sombre, accent teal→vert, typographies Hanken Grotesk / JetBrains Mono /
Instrument Serif).

### 1.1 Palette (dark-first, le dark est le mode principal)

**Canvas & surfaces (échelle de profondeur, du plus bas au plus haut) :**
- `--bg-base` : `#0A0B0D` (presque noir, légèrement bleuté) — fond d'app
- `--bg-sunken` : `#070809` — zones en creux (graphiques, code)
- `--surface-1` : `#101216` — cartes
- `--surface-2` : `#15181E` — cartes survolées / modales
- `--surface-3` : `#1C2027` — popovers, menus
- `--border-subtle` : `#1E222A` (≈ rgba blanc 6 %) — séparateurs
- `--border-strong` : `#2A2F3A` — bordures de focus/actives

**Texte :**
- `--text-primary` : `#F2F4F7`
- `--text-secondary` : `#A4ACB9`
- `--text-tertiary` : `#6B7280`
- `--text-disabled` : `#3F4651`

**Couleur-signal (accent unique, teal→émeraude) :**
- `--signal-500` : `#16E0B4` (teal-vert lumineux) — accent primaire, données « live »
- `--signal-400` : `#3BEDC6` (hover)
- `--signal-600` : `#0FB694` (pressed)
- `--signal-glow` : `rgba(22,224,180,0.35)` — halo/lueur

**Sémantique (verdicts & santé) :**
- BUY / positif : `--emerald` `#19C37D`
- WATCH / neutre-attention : `--amber` `#F5B544`
- PASS / négatif : `--slate` `#5B6573` (volontairement éteint, pas rouge agressif)
- Danger réel (suppression, churn) : `--red` `#F0616D`
- Info / Trends : `--azure` `#5B8DEF`
- Reddit : `--reddit` `#FF6A3D` (orange Reddit assumé, pour la lisibilité de source)

**Phases produit (couleurs dédiées, réutilisées partout) :**
- `EMERGENT` `#16E0B4` · `EARLY_GROWTH` `#19C37D` · `GROWTH` `#5B8DEF` ·
  `MATURE` `#A4ACB9` · `PEAK` `#F5B544` · `DECLINING` `#5B6573`

**Light mode** (secondaire, requis pour parité) : inverser — canvas `#FBFCFD`,
surfaces `#FFFFFF`/`#F5F7FA`, texte `#0A0B0D`, bordures `#E6E9EE`, mêmes signal/sémantique
avec saturation légèrement réduite (−6 %).

### 1.2 Gradients & matière
- **Signal gradient** : `linear-gradient(135deg, #16E0B4 0%, #19C37D 100%)` — CTA, jauges.
- **Aurora héro** (fond de sections clés, très subtil) : radial teal `#16E0B4` 0 % →
  transparent, opacité 8 %, blur 120px, animé en respiration lente (12 s).
- **Mesh data** : dégradé maillé sombre bleu-vert pour l'arrière-plan des grands graphes.
- **Glass** : surfaces de modales/topbar = `backdrop-filter: blur(20px)` + surface à
  72 % d'opacité + bordure 1px `rgba(255,255,255,0.06)`.
- **Glow sélectif** : uniquement sur l'élément « opportunité forte » (Tandor Score ≥ 80)
  → fine ombre portée teintée signal. Jamais de glow décoratif gratuit.

### 1.3 Typographie
- **UI / texte** : `Hanken Grotesk` (400, 500, 600, 700). Lisible, neutre-chaleureux.
- **Données / chiffres / mono** : `JetBrains Mono` (400, 500) — TOUS les nombres, scores,
  prix, %, axes de graphiques, timestamps. Donne le côté « terminal/précision ».
- **Display éditorial** : `Instrument Serif` (regular + italic) — uniquement pour les
  très grands titres de page et les chiffres-héros (Tandor Score géant), en accent rare.

**Échelle typographique (rem, base 16px) :**
`Display 56/1.05 · H1 36/1.1 · H2 28/1.15 · H3 22/1.2 · H4 18/1.3 · Body-L 16/1.5 ·
Body 14/1.5 · Caption 13/1.4 · Micro 11/1.3 (uppercase, tracking +0.08em pour les labels)`.
Chiffres tabulaires (`font-variant-numeric: tabular-nums`) partout où des nombres
s'alignent en colonne.

### 1.4 Espacement & grille
- Échelle 4px : `4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48 · 64 · 80`.
- Grille app : 12 colonnes, gouttière 24px, marge de contenu 32px (desktop).
- Largeur de contenu max : 1440px centrée ; les tableaux denses peuvent aller plein cadre.
- Rythme vertical des sections : 48px (desktop), 32px (tablet), 24px (mobile).

### 1.5 Rayons, ombres, profondeur
- **Rayons** : `--r-sm 8px` (badges, inputs), `--r-md 12px` (cartes), `--r-lg 16px`
  (panneaux/modales), `--r-xl 24px` (héro), `--r-full` (pills, avatars).
- **Ombres (dark, subtiles, jamais grises sales) :**
  - `--elev-1` : `0 1px 2px rgba(0,0,0,0.4)`
  - `--elev-2` : `0 4px 16px rgba(0,0,0,0.45)`
  - `--elev-3` : `0 12px 40px rgba(0,0,0,0.55)` (modales)
  - `--elev-signal` : `0 8px 32px rgba(22,224,180,0.18)` (élément champion)
- Profondeur = combinaison surface plus claire + bordure + ombre, jamais l'un seul.

### 1.6 Iconographie
- Set unique : **Lucide** (trait 1.5px, grille 24), cohérent partout. Jamais de mix.
- Icônes de source toujours colorées de leur couleur sémantique (Trends azure, Reddit
  orange, CJ signal). Icônes UI en `--text-secondary`, passent en `--text-primary` au hover.
- Icônes « live » (données fraîches) : petit point pulsé `--signal-500`.

### 1.7 Principes de mouvement (transversaux)
- **Durées** : micro 120ms · standard 200ms · entrée panneau 280ms · page 320ms.
- **Easing** : `cubic-bezier(0.22, 1, 0.36, 1)` (sortie douce « Linear-like ») par défaut ;
  `cubic-bezier(0.4, 0, 0.2, 1)` pour les transformations symétriques.
- **Règle d'or** : rapide, jamais lourd. Aucune animation > 400ms sauf reveals de
  graphiques (≤ 900ms). Tout respecte `prefers-reduced-motion` (fondu simple en repli).
- **Spring** (Framer Motion) pour les éléments « vivants » : compteurs, jauges, drag.
  `stiffness 260, damping 30`.

---

## 2. APP SHELL (cadre global, présent sur toutes les pages)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  TOPBAR (h 56px, glass, sticky)                                            │
│  [logo Tandor] [⌘K recherche globale]      [marché ▾][⏱ live][🔔][avatar]  │
├───────────┬────────────────────────────────────────────────────────────────┤
│ SIDEBAR   │                                                                  │
│ (240px,   │   ZONE DE CONTENU (scrollable)                                   │
│ collap-   │                                                                  │
│ sible 72) │                                                                  │
│           │                                                                  │
└───────────┴──────────────────────────────────────────────────────────────────┘
```

### 2.1 Sidebar (navigation primaire)
- Largeur 240px, repliable à 72px (icônes seules + tooltip au hover). État mémorisé.
- Groupes :
  1. **DÉCOUVERTE** : Home · Product Discovery · Opportunity Radar
  2. **ANALYSE** : Trend Analysis · Reddit Intelligence · Market Signals · Analytics
  3. **MON ESPACE** : Saved · Watchlists · Alerts
  4. **bas de sidebar** : Settings · Billing · Account · sélecteur thème
- Item actif : barre signal 2px à gauche + fond `--surface-2` + texte primaire + icône
  teintée signal. Hover : fond `--surface-1`, transition 120ms.
- En bas : carte « plan » compacte (ex. *Scale · 1 240 produits suivis*) avec mini-jauge
  d'usage et bouton *Upgrade* discret.
- Repli : transition largeur 200ms, les labels fondent (opacity + translateX −8px).

### 2.2 Topbar
- **Logo** Tandor (mot-symbole) à gauche, cliquable → Home.
- **Recherche globale ⌘K** : champ central (ou bouton compact qui ouvre la *Command
  Palette*, cf. §6.9). Placeholder *« Rechercher un produit, une catégorie, un signal… »*.
- **Sélecteur de marché** : FR · EU · US · UK · DE · World (drapeau + code). Change le
  `geo` des Trends et le contexte. Pill avec chevron.
- **Indicateur Live** : point pulsé + *« Données à jour · il y a 2 h »* ; au clic, popover
  d'état du pipeline (dernier run CJ, Trends, Reddit, prochaine collecte).
- **Cloche notifications** : badge compteur ; ouvre un panneau latéral d'alertes.
- **Avatar** : menu compte (profil, settings, thème, déconnexion).

### 2.3 Comportement responsive du shell
- **Desktop ≥1280** : sidebar ouverte 240px.
- **Tablet 768–1279** : sidebar repliée 72px par défaut, extensible en overlay.
- **Mobile <768** : sidebar masquée → **bottom tab bar** (5 entrées : Home, Discovery,
  Radar, Saved, Alerts) + bouton ⌘K dans la topbar ; le reste dans un menu « Plus ».

---

## 3. ARCHITECTURE — LES 14 PAGES (vue d'ensemble)

| # | Page | Rôle en une phrase | Densité |
|---|---|---|---|
| 1 | **Dashboard Home** | Le « poste de marché » : ce qui bouge maintenant | haute |
| 2 | **Product Discovery** | Explorer/filtrer le catalogue scoré (cœur quotidien) | très haute |
| 3 | **Product Detail** | Le dossier d'investissement d'un produit | très haute |
| 4 | **Trend Analysis** | Demande Google Trends, vélocité, saisonnalité | haute |
| 5 | **Reddit Intelligence** | Signal social précoce, mentions, contexte | moyenne |
| 6 | **Market Signals** | Corrélation multi-sources, anomalies, corroboration | haute |
| 7 | **Opportunity Radar** | Matrice momentum × maturité (le « radar ») | moyenne |
| 8 | **Saved Products** | Bibliothèque personnelle | moyenne |
| 9 | **Watchlists** | Listes thématiques suivies dans le temps | moyenne |
| 10 | **Alerts** | Règles + journal des déclenchements | moyenne |
| 11 | **Analytics** | Performance du moteur, backtest, preuve | haute |
| 12 | **Settings** | Préférences, marchés, sources, équipe | faible |
| 13 | **Billing** | Plan, usage, factures | faible |
| 14 | **Account** | Profil, sécurité, API keys | faible |

---

## 4. PAGES EN DÉTAIL

### 4.1 DASHBOARD HOME — « le poste de marché »

**Intention** : en 5 secondes, l'utilisateur sait *ce qui bouge maintenant* et *où agir*.

**Disposition (desktop, top → bottom) :**
1. **Bandeau d'en-tête éditorial** : titre `Instrument Serif` *« Bonjour {prénom} »* +
   sous-titre dynamique *« 7 nouvelles opportunités détectées depuis hier »*. À droite :
   sélecteur de période (24h / 7j / 30j) en segmented control.
2. **Rangée de 4 KPI héros** (cartes `--surface-1`, hauteur 120px) :
   - *Opportunités actives* (count BUY) — compteur animé + delta vs période précédente.
   - *Score moyen du marché* (moyenne Tandor Score) — sparkline 14j.
   - *Marge nette médiane* (€) — sparkline.
   - *Produits émergents* (phase EMERGENT) — micro-barre de répartition par phase.
   Chaque KPI : grand chiffre `JetBrains Mono`, label micro uppercase, delta coloré
   (▲ emerald / ▼ slate), sparkline au survol qui s'étend.
3. **« Opportunity Feed »** (2/3 largeur) : flux chronologique des détections récentes.
   Chaque ligne = mini-carte (image 48px, nom, badge phase, Tandor Score en ring 36px,
   delta croissance, heure). Hover → preview latérale ; clic → Product Detail.
   En tête de flux, l'item le plus fort porte un léger `--elev-signal` (le « champion du
   jour »).
4. **Panneau droit (1/3) — « Radar express »** : version compacte de l'Opportunity Matrix
   (bubble chart momentum×maturité, §5.4) avec les 20 derniers produits. Clic sur bulle →
   detail. Sous le radar : *« Signaux du jour »* — 3 cartes (top Trends, top Reddit, top
   corroboration).
5. **Rangée basse** : *Répartition par catégorie* (treemap, §5.7) + *Carte de saisonnalité*
   (heatmap mois×catégorie, §5.5) côte à côte.

**États** : voir §8 (vide = onboarding ; chargement = skeleton ; live = pulse).

---

### 4.2 PRODUCT DISCOVERY — le cœur quotidien

**Intention** : explorer, filtrer, trier, comparer le catalogue scoré. C'est la page la
plus utilisée. Densité maximale **maîtrisée**.

**Layout (desktop) :**
```
┌───────────────┬───────────────────────────────────────────────────────────┐
│ FILTRES       │  Barre d'outils : [recherche] [tri ▾] [densité] [vue ▭/≣]   │
│ (rail 280px,  │  Chips de filtres actifs  ·  N résultats  ·  [Comparer (2)] │
│ sticky,       │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐             │
│ collapsible)  │ │ carte   │ │ carte   │ │ carte   │ │ carte   │   …grille    │
│               │ └─────────┘ └─────────┘ └─────────┘ └─────────┘             │
└───────────────┴───────────────────────────────────────────────────────────┘
```

#### 4.2.1 Rail de filtres (gauche, 280px, repliable)
Sections en accordéon, chaque filtre avec compteur de résultats en direct :
- **Verdict** : segmented `BUY / WATCH / PASS / Tous` (multi-select pills).
- **Phase** : checkboxes colorées (EMERGENT … DECLINING) avec pastille couleur.
- **Tandor Score** : range slider double poignée 0–100 (track signal).
- **Marge € / Marge %** : deux range sliders.
- **Prix de vente (retail)** : range slider + presets (< 25 € impulsion / 25–60 / 60+).
- **Saturation (vendeurs)** : range slider 0–100+ avec libellés (Vierge / Validé / Dense).
- **Vitesse de croissance** : slider −50 %…+200 % (mensuel).
- **Confiance** : slider 0–100 %.
- **Catégorie** : recherche + liste à cocher (virtualisée si longue).
- **Saisonnalité** : toggle *« en saison ce mois-ci »* + sélecteur de profil.
- **Âge / date de détection** : presets (24h, 7j, 30j) + date range.
Bas du rail : boutons *Réinitialiser* (ghost) et *Enregistrer ce filtre* (devient une
Watchlist/segment). Les filtres se reflètent dans l'URL (partage/deep-link).

#### 4.2.2 Barre d'outils
- **Recherche locale** : filtre instantané sur nom/catégorie (debounce 150ms), surlignage
  des correspondances.
- **Tri ▾** : Tandor Score · Croissance · Marge · Potentiel · Reddit · Trends · Récence ·
  Saturation (asc/desc). Le tri par défaut = `rank_score`.
- **Densité** : Confort / Compact (hauteur des cartes).
- **Vue** : grille de cartes ▭ ou tableau dense ≣ (data-grid triable, colonnes
  configurables — pour le power-user façon Ahrefs).
- **Comparer** : actif dès 2 produits cochés → ouvre le **Comparateur** (§4.2.5).

#### 4.2.3 CARTE PRODUIT (composant central) — anatomie exacte
Dimensions : 280×360px (confort) / 280×280 (compact). `--surface-1`, `--r-md`, bordure
subtile.
```
┌────────────────────────────────────┐
│ [image 16:10, lazy, ratio fixe]     │  ← coin haut-G : badge PHASE (pastille+label)
│                              ◔ 82   │  ← coin haut-D : Tandor Score (ring animé)
├────────────────────────────────────┤
│ Nom du produit (2 lignes max)       │
│ #Catégorie · détecté il y a 2 j     │
│                                     │
│ ▸ 5 micro-jauges horizontales :     │
│   Croissance ▰▰▰▰▱  Reddit ▰▰▱▱▱     │
│   Trends ▰▰▰▱▱  Potentiel ▰▰▰▰▱      │
│   Saturation ▰▱▱▱▱ (inversé)         │
│                                     │
│ Marge +24€ (60%)   ↗ +61%/mois      │  ← ligne KPI mono
│ [BUY] ●Faible risque  [♥][⊕ compare]│  ← footer actions
└────────────────────────────────────┘
```
- **Tandor Score** : anneau circulaire (SVG) 44px, remplissage = score, couleur = phase ;
  le chiffre au centre compte de 0→valeur au reveal.
- **5 micro-jauges** : barres segmentées (5 crans) ou mini-barres continues, couleur de
  source. Tooltip au hover = valeur exacte + z-score.
- **Ligne KPI** : marge € (et %), flèche + croissance/mois en mono coloré.
- **Footer** : badge Verdict (pill colorée), point de risque, ♥ Save (toggle), ⊕ Comparer.

**Micro-interactions de la carte :**
- *Hover* : élévation `--elev-2`, légère montée `translateY(-2px)` (200ms), l'image
  zoome 1.04 en `scale` (overflow hidden), le ring « brille » très légèrement.
- *Hover prolongé (400ms)* : un **mini-sparkline Trends 30j** apparaît en fondu sous les
  jauges (révèle la tendance sans clic).
- *Save (♥)* : burst de particules signal + remplissage du cœur (spring), toast discret.
- *Comparer (⊕)* : la carte reçoit une bordure signal + apparaît dans la barre Comparer.
- *Clic carte* : transition partagée (shared layout) image+nom+ring vers la Product Detail.
- *Long-press / clic droit* : menu contextuel (Save, Ajouter à watchlist, Comparer,
  Créer une alerte, Copier le lien, Masquer).

#### 4.2.4 Système de tags
- Tags = catégorie + phase + saison + tags personnalisés de l'utilisateur. Pills
  colorées, cliquables (= applique le filtre). Tags perso éditables (couleur au choix
  dans une palette restreinte cohérente).

#### 4.2.5 Comparateur (jusqu'à 4 produits)
- Ouvre un panneau plein écran ou un drawer large : tableau côte à côte (lignes = tous les
  scores/KPI, colonnes = produits), + **radar superposé** des 4 produits (§5.3) + courbes
  Trends superposées. Cellule gagnante par ligne légèrement surlignée signal. Export PNG/CSV.

#### 4.2.6 Pagination / volume
- **Scroll infini** virtualisé (windowing) par paquets de 24, avec skeleton en bas.
  Bouton « Remonter » flottant après 2 écrans. Compteur total fixe en barre d'outils.

---

### 4.3 PRODUCT DETAIL — le dossier d'investissement (la page la plus impressionnante)

**Intention** : tout score est cliquable jusqu'à sa justification. L'utilisateur doit
comprendre *pourquoi* et décider. Mise en page en deux colonnes (contenu 2/3 + rail
décisionnel sticky 1/3).

#### 4.3.1 Section HERO (pleine largeur, fond aurora subtil)
```
┌──────────────────────────────────────────────────────────────────────────┐
│ [image produit       ]   NOM DU PRODUIT (Instrument Serif, H1)            │
│ [grande, 4:3, zoom-  ]   #Catégorie · CJ · détecté il y a 2 j · marché FR │
│  able, galerie si +  ]                                                     │
│                          ┌───────────┐  Opportunité : ÉLEVÉE ▲            │
│                          │  ◔  82    │  Risque : ● Faible                  │
│                          │ TANDOR    │  Confiance : 78%  ▰▰▰▰▱             │
│                          │ SCORE     │  Phase : EARLY_GROWTH               │
│                          └───────────┘  Verdict : [ BUY ]                  │
│                          [♥ Sauvegarder][+ Watchlist][🔔 Alerte][↗ CJ]     │
└──────────────────────────────────────────────────────────────────────────┘
```
- **Tandor Score géant** : anneau 120px, chiffre `Instrument Serif` 56px qui compte au
  chargement ; sous-anneau = confiance (arc secondaire plus fin).
- **Indicateur d'opportunité** : jauge segmentée Faible/Moyenne/Élevée (flèche animée).
- **Niveau de risque** : pastille + libellé + tooltip (facteurs : confiance, volatilité,
  0 vendeur…).
- **Confiance de prédiction** : barre + %, tooltip expliquant la moyenne géométrique.
- **CTA** : Save, Watchlist, Créer une alerte, *Voir sur CJ* (lien sourcing direct).

#### 4.3.2 Bandeau « Économie du produit » (sous le hero, 4 tuiles mono)
Coût · Retail estimé · **Marge brute (€ / %)** · **Net après pub (€/vente)**. Chaque tuile
avec micro-explication au hover. La tuile « Net après pub » porte l'accent signal si > 15 €.

#### 4.3.3 GRAPHIQUES (zone principale, onglets ou empilés)
Tous les graphiques : axe X temps en `JetBrains Mono`, tooltip riche, hover crosshair,
reveal animé au scroll. Détails par type en §5.

1. **Croissance Google Trends** — *Area chart* (intérêt 0–100, ~90 j). Ligne signal,
   remplissage dégradé signal→transparent. Bande de saisonnalité en arrière-plan (mois de
   pic surligné). Marqueurs sur les pics. Toggle *« vélocité »* superpose la pente OLS.
2. **Évolution Reddit** — *Bar chart* hebdomadaire des mentions (couleur Reddit) + ligne
   de tendance. Chaque barre cliquable → liste des posts de la semaine (drawer).
3. **Croissance CJ (offre)** — *Line/step chart* du `listed_num` dans le temps (adoption
   vendeurs = saturation). Annotation quand la pente s'accélère (alerte saturation).
4. **Accélération de croissance** — *Diverging area* de l'accélération (dérivée 2nde) :
   au-dessus de 0 (vert, « EXPLOSE »), en dessous (slate, « ralentit »). Ligne 0 marquée.
5. **Corrélation des signaux** — *Radar/spider chart* (axes : Trends, Reddit, CJ, Marge,
   Saturation inv., Fraîcheur). Polygone signal semi-transparent. Compare au « profil
   gagnant moyen » (polygone fantôme). + *Mini-matrice de corrélation* (heatmap) entre les
   z-scores des sources pour matérialiser la **corroboration**.
6. **Signaux composés** — *Multi-line normalisé* (toutes les sources sur 0–100, même axe)
   pour voir l'alignement temporel des montées (le « moment de corroboration »).

#### 4.3.4 TIMELINE DU PRODUIT (composant signature)
Frise horizontale (desktop) / verticale (mobile) des **moments clés** :
- Détection initiale · 1ère mention Reddit · franchissement de seuil de vélocité ·
  changement de phase (EMERGENT→EARLY_GROWTH) · pic Trends · alerte saturation.
- Chaque événement = nœud coloré (couleur de source) sur la ligne de temps, avec date mono,
  label, et icône. Hover = carte de détail. La timeline « se dessine » de gauche à droite
  au reveal (path drawing 800ms).

#### 4.3.5 Encart « Pourquoi ce score » (explicabilité)
Liste ordonnée des `reasons` + décomposition `contributions[]` en **barres divergentes**
(chaque source pousse + ou −, largeur = contribution). C'est le « pitch du trader ». Texte
naturel issu de `reason`.

#### 4.3.6 Rail décisionnel droit (sticky)
- Carte verdict (grand badge + 1 phrase), niveau de risque, confiance.
- Bloc *Sourcing* : prix CJ, lien, nb vendeurs, délai estimé.
- Bloc *Saisonnalité* : mini-courbe annuelle 12 mois avec le mois courant marqué + label.
- Bloc *Produits similaires* (par catégorie/profil) : 3 mini-cartes.
- Actions : Save, Watchlist, Alerte, Exporter le dossier (PDF/PNG).

---

### 4.4 TREND ANALYSIS

**Intention** : explorer la demande Google Trends par mot-clé/catégorie, la vélocité et la
saisonnalité, indépendamment d'un produit.
- **Barre de recherche de mots-clés** (multi-keywords, jusqu'à 5 comparés).
- **Grand area/line multi-séries** (0–100) avec sélecteur de période (3m / 12m / 5y) et
  `geo`. Crosshair synchronisé entre séries.
- **Panneau vélocité** : pour chaque mot-clé, vélocité (log/j), croissance/mois,
  accélération, R² — en cartes mono + flèche de direction.
- **Heatmap de saisonnalité** (mois × mot-clé) : couleur = multiplicateur (§5.5).
- **Tableau** des mots-clés liés aux produits du catalogue (jointure → ouvre Discovery
  filtré).
- États : 429/indispo Trends → bandeau *« Source Trends momentanément limitée, réessai
  auto »* + dernières données en cache grisées.

---

### 4.5 REDDIT INTELLIGENCE

**Intention** : le signal social précoce, lisible.
- **KPIs** : mentions totales (période), vélocité moyenne, subreddits actifs.
- **Bar chart temporel** des mentions (global ou par mot-clé) + **stream/area empilé par
  subreddit** (qui parle de quoi).
- **Liste de posts** (drawer/colonne) : titre, subreddit (pastille), date, lien externe ↗.
  Filtrable par subreddit, triable par date. (Engagement non dispo via RSS → l'UI affiche
  *fréquence de mentions*, pas d'upvotes ; ne pas inventer de compteurs de votes.)
- **Nuage de subreddits** (bubble pack) : taille = volume de mentions.
- **Word/keyword chips** émergents (les termes qui montent).
- État vide : *« Pas encore de signal Reddit sur ce segment — le silence social est
  normal pour les produits très récents. »*

---

### 4.6 MARKET SIGNALS

**Intention** : la vue « salle des marchés » multi-sources — corrélation, anomalies,
corroboration.
- **Matrice de corrélation** (heatmap) entre sources sur l'ensemble du catalogue.
- **Scatter plot** vélocité × niveau (chaque point = produit ; couleur = phase ; taille =
  marge) → repérer les « bas niveau / forte vélocité » (le Graal). (§5.6)
- **Détecteur d'anomalies** : liste des pics (`|z_velocity| > 3.5`) avec statut
  *corroboré / isolé* (un pic confirmé par ≥2 sources est promu « signal »).
- **Flux de corroboration** : produits où Trends ET Reddit montent ensemble (badge
  « corroboré ×N »).

---

### 4.7 OPPORTUNITY RADAR (page signature marketing)

**Intention** : LE visuel « hedge fund ». Une **matrice d'opportunité** plein écran.
- **Bubble chart** : X = maturité (faible→saturé), Y = momentum (vélocité+accélération),
  taille = marge €, couleur = phase, halo = confiance. (§5.4)
- **4 quadrants nommés** : *« Émergent à fort potentiel »* (haut-gauche, mis en avant),
  *« En croissance »*, *« Saturé »*, *« À éviter »*. Le quadrant cible a un fond signal très
  léger.
- Lasso/brush de sélection → envoie la sélection vers Discovery/Comparateur/Watchlist.
- Animation : les bulles « entrent » en cascade depuis le centre (stagger), flottement
  micro continu (parallaxe lente, désactivé en reduced-motion).
- Contrôles : axes configurables, filtre par catégorie/marché, lecture temporelle (slider
  de date qui rejoue le déplacement des bulles dans le temps — « replay du marché »).

---

### 4.8 SAVED PRODUCTS
- Grille/tableau identique à Discovery mais limité aux sauvegardés. Regroupement par
  dossier/tag. Tri, recherche, export. Glisser-déposer vers une Watchlist. État vide =
  illustration + CTA *« Explore Discovery »*.

### 4.9 WATCHLISTS
- Liste de listes (cartes) : nom, nb produits, **score moyen + tendance** (sparkline),
  dernière activité. Création via modal (nom, couleur, filtre auto optionnel = « watchlist
  dynamique » qui se remplit selon des critères).
- Détail d'une watchlist : header avec évolution agrégée + tableau produits + graphe
  d'évolution du score moyen dans le temps. Notifications par watchlist.

### 4.10 ALERTS
- **Constructeur de règles** (no-code) : *Quand* [métrique: Tandor Score / croissance /
  phase / nouveau produit en catégorie X] [opérateur] [valeur] *alors* [notifier:
  in-app / email / webhook]. Aperçu en langage naturel de la règle.
- **Liste des règles** : toggle actif/inactif, fréquence de déclenchement, dernière fois.
- **Journal** : timeline des alertes déclenchées (produit, règle, valeur, heure), filtrable.
- Panneau latéral notifications (depuis la cloche topbar) : non-lues en tête, marquables.

### 4.11 ANALYTICS (preuve & confiance — vend l'abonnement)
- **Performance du moteur** (backtest) : AUC, precision@k, Brier, **courbe de
  calibration** (prévu vs réalisé), nb de prédictions évaluées. (§5 — line + calibration.)
- **« Nos paris passés »** : produits flaggés EMERGENT il y a N semaines et ce qu'ils sont
  devenus (preuve sociale) — table avec mini-courbes avant/après.
- **Couverture des sources** : disponibilité Trends/Reddit/CJ dans le temps (uptime).
- **Distribution des scores** (histogramme), répartition des phases (donut).

### 4.12 SETTINGS
- Sections : Général (langue FR/EN, thème, fuseau), Marchés par défaut (geo), Sources
  (activer/désactiver Trends/Reddit, paramètres CPA & markup pour personnaliser la
  vendabilité), Affichage (densité par défaut, vue par défaut), Équipe (membres, rôles),
  Notifications.
- Le réglage **CPA / markup** est clé : un slider qui recalcule en direct la marge nette et
  donc les verdicts (montrer l'impact en live sur un produit témoin).

### 4.13 BILLING
- Plan actuel (carte), **jauge d'usage** (produits suivis, alertes, exports vs quota),
  comparatif de plans (Starter / Growth / Scale — positionnés plusieurs centaines €/mois
  sur Scale), historique de factures (table + PDF), moyen de paiement, upgrade/downgrade.

### 4.14 ACCOUNT
- Profil (nom, email, avatar), Sécurité (mot de passe, 2FA, sessions actives), **API & clés**
  (génération de tokens pour l'export JSON / webhooks), Données (export RGPD, suppression).

---

## 5. CATALOGUE DES VISUALISATIONS (spéc par graphique)

Lib recommandée : **Recharts** (déjà au projet) pour le standard, **visx/D3** pour le radar,
la matrice et la heatmap, **Framer Motion** pour les reveals. Règles communes : axes mono,
grille très discrète (`--border-subtle`), pas de bordure de graphe, tooltip glass, légende
cliquable (toggle série), crosshair vertical au hover, animation d'entrée au scroll
(IntersectionObserver), respect reduced-motion (apparition instantanée).

### 5.1 Line / Area chart (Trends, signaux composés)
- **Objectif** : tendance temporelle d'un signal continu (intérêt 0–100, score normalisé).
- **Contenu** : 1–5 séries ; remplissage dégradé pour l'aire (signal→transparent).
- **Animation** : tracé progressif (stroke-dashoffset 0→100 %, 700ms) puis remplissage en
  fondu ; au changement de période, morph des points (200ms).
- **Interaction** : hover crosshair + tooltip multi-séries valeurs mono ; clic-glissé =
  zoom sur plage ; double-clic = reset ; légende toggle.
- **Mobile** : largeur pleine, hauteur 220px, tooltip déclenché au tap, pas de crosshair
  fin → marqueur + carte de valeur en bas.

### 5.2 Bar chart (Reddit mentions, distributions)
- **Objectif** : volumes discrets dans le temps / par catégorie.
- **Contenu** : barres hebdo (Reddit) ou catégories.
- **Animation** : barres montent depuis 0 en stagger (40ms d'écart), easing sortie.
- **Interaction** : hover = surbrillance barre + tooltip ; clic = drill (drawer posts).
- **Mobile** : scroll horizontal si > 12 barres, snap par barre.

### 5.3 Radar / Spider (profil multi-scores d'un produit, comparateur)
- **Objectif** : équilibre des dimensions (Trends, Reddit, CJ, Marge, Saturation inv.,
  Fraîcheur) d'un ou plusieurs produits.
- **Contenu** : polygone(s) 6 axes, 0–100. Polygone « gagnant moyen » en fantôme.
- **Animation** : déploiement du polygone depuis le centre (scale 0→1, spring) ; sommets
  qui « s'épinglent » avec un léger overshoot.
- **Interaction** : hover sommet = valeur + définition ; toggle des produits comparés.
- **Mobile** : taille réduite, labels d'axes abrégés, légende dessous.

### 5.4 Bubble chart / Opportunity Matrix (radar d'opportunité)
- **Objectif** : positionner chaque produit sur momentum × maturité ; repérer le quadrant
  émergent.
- **Contenu** : X maturité, Y momentum, r = marge €, couleur = phase, halo = confiance.
- **Animation** : entrée en cascade depuis le centre, flottement micro continu ; « replay »
  temporel (les bulles glissent selon le slider de date).
- **Interaction** : hover bulle = carte produit ; clic = detail ; lasso/brush = sélection
  multiple ; zoom/pan.
- **Mobile** : zoom pincé, bulles plus grosses, lasso remplacé par tap multiple.

### 5.5 Heatmap (saisonnalité mois×catégorie, corrélation sources)
- **Objectif** : motifs saisonniers / corrélations.
- **Contenu** : grille colorée (échelle signal→neutre→amber selon valeur), valeur au centre.
- **Animation** : cellules s'allument en vague diagonale (stagger).
- **Interaction** : hover = valeur exacte + libellé ; clic ligne/colonne = filtre.
- **Mobile** : scroll horizontal, en-têtes collants.

### 5.6 Scatter plot (vélocité × niveau, Market Signals)
- **Objectif** : repérer « bas niveau / forte vélocité ».
- **Contenu** : points = produits, couleur phase, taille marge ; lignes de quadrant.
- **Animation** : points fondent en place avec léger jitter d'arrivée.
- **Interaction** : hover, brush de sélection, zoom.

### 5.7 Treemap (répartition catégories)
- **Objectif** : poids des catégories dans les opportunités.
- **Contenu** : rectangles imbriqués, aire = nb de BUY, couleur = score moyen.
- **Animation** : tuiles s'agrandissent depuis 0 (stagger).
- **Interaction** : clic = filtre Discovery ; hover = détail.

### 5.8 Velocity map (mini, dans cartes & feed)
- **Objectif** : tendance ultra-compacte (sparkline) sans axes.
- **Contenu** : ligne 30–90j, couleur = direction (vert/slate).
- **Animation** : tracé 400ms au reveal ; sur hover de carte, dernier point pulse.

### 5.9 Diverging area (accélération)
- **Objectif** : montrer EXPLOSE vs ralentit.
- **Contenu** : aire au-dessus/dessous de 0, deux couleurs.
- **Animation** : remplissage depuis la ligne 0 vers l'extérieur.

### 5.10 Gauges & rings (scores)
- **Objectif** : score 0–100 / confiance.
- **Contenu** : anneau (score) + arc secondaire (confiance) ; chiffre central mono/serif.
- **Animation** : remplissage de l'arc + compteur numérique synchronisés (spring 600ms).

### 5.11 Calibration curve (Analytics)
- **Objectif** : prouver la fiabilité (prévu vs observé).
- **Contenu** : points calibrés + diagonale idéale + bande de confiance.
- **Animation** : diagonale en pointillés se trace, puis points fondent.

---

## 6. SYSTÈME D'ANIMATIONS (premium, rapide, jamais lourd)

### 6.1 Transitions de page
- **Cross-fade + slide léger** (12px) 320ms, easing sortie douce. Le contenu entre par
  paliers (header → KPIs → contenu) en stagger 40ms.
- **Shared element** : image + nom + ring d'une carte se « déplacent » physiquement vers le
  hero de la Product Detail (Framer Motion `layoutId`), 360ms.

### 6.2 Hover de cartes
- Élévation + `translateY(-2px)` + zoom image 1.04 + révélation sparkline (cf. §4.2.3),
  200ms. Curseur `pointer`. Aucune ombre « sale ».

### 6.3 Compteurs de métriques
- Tous les grands chiffres comptent de 0→valeur (ou ancienne→nouvelle) en 600–900ms,
  easing sortie, `tabular-nums` pour éviter le jitter de largeur. Delta colore l'apparition.

### 6.4 Reveals de graphiques
- Au scroll (IntersectionObserver, seuil 0.3) : tracé/montée des barres/déploiement radar
  selon §5. Une seule fois par session de vue. ≤ 900ms.

### 6.5 Loading states & skeletons
- **Skeletons** structurels (forme exacte du composant final) avec **shimmer** diagonal
  (gradient qui traverse, 1.4s en boucle, opacité faible). Jamais de spinner plein écran.
- **KPIs** : bloc chiffre + sparkline en skeleton.
- **Cartes** : image + lignes + jauges en skeleton ; la grille garde sa mise en page (pas
  de saut de layout — réserver l'espace).
- **Graphes** : silhouette d'axes + ligne ondulée fantôme.
- **Live refresh** : quand de nouvelles données arrivent, les éléments concernés « pulsent »
  une fois (halo signal 1.2s) sans recharger la page.

### 6.6 Boutons & inputs
- Press : `scale 0.98` 120ms. CTA primaire : léger déplacement du gradient au hover.
- Focus visible : anneau 2px `--signal-500` à 40 % + offset 2px (accessibilité clavier).
- Toggle/switch : pouce qui glisse avec spring + changement de couleur de piste.
- Champs : bordure qui s'illumine signal au focus (200ms), label flottant.

### 6.7 Modales & drawers
- **Modale** : overlay fondu (backdrop blur 8px) + carte qui monte de 16px + scale
  0.98→1, 280ms. Sortie symétrique 200ms.
- **Drawer latéral** (posts Reddit, détails événement) : glisse depuis la droite 280ms,
  overlay cliquable pour fermer, `Esc` pour fermer.

### 6.8 Toasts & feedback
- Toasts bas-droite, glass, icône colorée, auto-dismiss 4s, empilables, action « Annuler »
  quand pertinent (save, suppression). Entrée slide+fade 200ms.

### 6.9 Command Palette (⌘K)
- Overlay centré, glass, recherche floue (produits, pages, catégories, actions).
- Résultats groupés (Produits / Pages / Actions / Filtres récents). Navigation clavier
  complète (↑↓, Enter, Esc), aperçu à droite du produit survolé. Ouverture 180ms (scale +
  fade). C'est un marqueur fort de produit « pro ».

### 6.10 Micro-détails « signature »
- Point « live » qui pulse (2s) dans la topbar et sur les données fraîches.
- Le ring du champion du jour émet un très léger balayage lumineux (1 passage à
  l'apparition).
- Hover sur un badge de phase → tooltip avec définition courte de la phase.

---

## 7. ÉTATS (vides, chargement, erreur, succès)

Pour **chaque** liste/graphe/page, définir les 4 états :

### 7.1 États vides (jamais une page blanche)
- **Discovery sans résultat de filtre** : illustration line-art minimaliste + *« Aucun
  produit ne correspond. »* + bouton *Assouplir les filtres* (retire le filtre le plus
  restrictif) + suggestions de presets.
- **Saved/Watchlists vides** : onboarding visuel + CTA vers Discovery.
- **Reddit/Trends sans signal** : message contextuel rassurant (cf. §4.5) — l'absence de
  signal social est *normale* pour un produit très récent ; ne pas dramatiser.
- **Première connexion (cold start)** : écran d'accueil guidé (3 étapes : choisir un
  marché, lancer une découverte, créer une watchlist) + données de démonstration marquées
  *« exemple »*.

### 7.2 Chargement
- Skeletons partout (cf. §6.5). Temps perçu minimisé : afficher d'abord la structure +
  données en cache grisées, puis « durcir » à l'arrivée des données fraîches.

### 7.3 Erreur
- **Source indisponible** (Trends 429, Reddit bloqué) : bandeau non bloquant en haut du
  module concerné, ton factuel + *« réessai automatique »* + horodatage des dernières
  données. Le reste du dashboard reste pleinement utilisable (dégradation gracieuse,
  jamais d'écran d'erreur global).
- **Erreur réseau** : carte d'erreur locale avec bouton *Réessayer*.
- **404 produit** : page dédiée avec retour Discovery + suggestions similaires.

### 7.4 Succès / confirmation
- Toasts discrets ; états optimistes (le ♥ se remplit immédiatement, rollback si échec).

---

## 8. RESPONSIVE (par breakpoint, pour chaque type de page)

**Breakpoints** : `mobile <640 · sm 640 · tablet 768 · lg 1024 · desktop 1280 · xl 1536`.
Approche **mobile-first**, pensée dès le départ.

### 8.1 Desktop (≥1280)
- Sidebar 240px ouverte, contenu 12 colonnes, graphes pleine richesse, hover actif,
  Discovery en grille 3–4 colonnes + rail filtres visible, Product Detail en 2 colonnes.

### 8.2 Tablet (768–1279)
- Sidebar repliée 72px (overlay au besoin). Discovery 2 colonnes ; rail filtres devient un
  **bouton « Filtres »** ouvrant un drawer. Product Detail : rail décisionnel passe sous le
  contenu (sticky bottom CTA bar). Graphes hauteur réduite, légendes repliables.

### 8.3 Mobile (<768)
- **Bottom tab bar** (Home, Discovery, Radar, Saved, Alerts) ; topbar minimale (logo + ⌘K +
  cloche). Sidebar masquée (menu « Plus »).
- **Discovery** : 1 colonne, cartes pleine largeur compactes ; filtres + tri en
  **bottom-sheet** déclenché par boutons flottants ; comparaison limitée à 2.
- **Product Detail** : hero empilé (image → score ring → opportunité/risque → CTA en barre
  fixe bas) ; graphes en plein largeur, tap pour tooltip ; timeline verticale ; sections en
  accordéon pour limiter le scroll.
- **Graphes** : hauteur 200–240px, interactions au tap, pas de crosshair fin, légende sous
  le graphe, swipe horizontal pour changer de période.
- **Opportunity Radar** : zoom pincé, sélection par tap, contrôles en bottom-sheet.
- Cibles tactiles ≥ 44px, espacements augmentés, pas de hover-only (toute info au hover a un
  équivalent au tap/long-press).

---

## 9. COMPOSANTS — bibliothèque (récapitulatif pour build)

Boutons (primary signal-gradient, secondary surface, ghost, danger, icon) · Inputs (text,
search, number, range slider double, date range, select, multi-select, combobox) ·
Toggles/switch/checkbox/radio · Segmented control · Pills/Tags (colorables) · Badges
(verdict, phase, risque, live) · **Score Ring** (3 tailles) · **Micro-jauge** (5-crans &
continue) · **Sparkline** · KPI Card · **Product Card** · Data-grid (tri, colonnes
config, virtualisé, sélection) · Tableau standard · Accordion · Tabs · Tooltip (glass) ·
Popover · Modal · Drawer · Bottom-sheet · Toast · Command Palette · Empty-state ·
Skeleton (par composant) · Pagination/scroll-infini · Breadcrumb · Avatar/menu · Filter
rail · Filter chips · Stepper (onboarding) · Range/date presets · Notification item ·
Plan/usage card · Chart wrappers (§5). Tous déclinés en dark (primaire) + light, avec états
hover/focus/active/disabled/loading.

---

## 10. ACCESSIBILITÉ & PERFORMANCE (exigences de build)
- Contraste AA minimum (texte secondaire vérifié sur surfaces). Le signal teal sur fond
  sombre passe AA pour les éléments non-texte ; pour le texte sur signal, utiliser
  `--bg-base` foncé.
- Navigation clavier complète (focus visible partout, ordre logique, ⌘K, Esc, flèches dans
  les listes/grilles). ARIA sur graphes (résumé textuel + table de données accessible).
- `prefers-reduced-motion` : toutes les animations dégradent en fondu/instantané.
- Performance : virtualisation des grandes listes, lazy-load images (ratio réservé,
  pas de CLS), code-split par route, graphes rendus à la demande, cibler 60fps, LCP < 2.5s.
- i18n FR/EN dès le départ (chaînes externalisées), formats nombres/€/dates localisés.

---

## 11. RÉSUMÉ DIRECTEUR (à garder en tête)
Un **terminal de hedge fund habité** : sombre, dense, mono pour les chiffres, une seule
couleur-signal qui pointe l'opportunité, des graphiques qui se révèlent avec précision, des
micro-interactions rapides et satisfaisantes, zéro lourdeur, zéro aspect template. Chaque
score est cliquable jusqu'à sa preuve. Le produit doit donner envie de payer plusieurs
centaines d'euros par mois parce qu'il *donne l'impression de voir avant tout le monde*.
```
