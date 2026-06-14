# Plan — Couche « Vendabilité » (analyse financière + saisonnalité + signal organique réel)

Objectif : transformer le moteur d'accélération existant en un **verdict d'investissement
produit** au sens d'un trader — « ce produit va-t-il se vendre, avec quelle marge, et
maintenant est-ce le bon moment ? ». On submerge l'utilisateur d'indicateurs *bons et
explicables*, pas de bruit.

## Constat de départ

| Brique | État |
|---|---|
| Moteur accélération (`scoring/engine.py`) | ✅ solide, 18 tests verts |
| Collecteur CJ + 1000 produits en base | ✅ |
| Vélocité CJ | ❌ 1 seul snapshot (besoin de ≥2 jours) |
| **Analyse financière / vendabilité** | ❌ absente — cœur de ce plan |
| **Saisonnalité** | ❌ absente |
| Signal organique (Reddit / Google Trends) | ❌ déclaré mais non collecté |

## Insight central : la vélocité est disponible *aujourd'hui*

On n'attend PAS plusieurs jours de snapshots CJ. Les sources organiques précoces
portent leur propre historique en un seul appel :
- **Google Trends** → série 90 j en 1 requête → vélocité + accélération réelles.
- **Reddit** → âge du post × upvotes → vélocité instantanée (upvotes/heure).

CJ devient la couche *financière* (coût, marge, saturation `listedNum`, âge `createTime`).

## Modèle de vendabilité (« le loup de Wall Street ») — `scoring/sellability.py`

Par produit, à partir du seul snapshot CJ (donc opérationnel sur les 1000 produits actuels) :

1. **Marge** — coût = prix CJ ; retail estimé via courbe de markup dropshipping (×4 sous
   5 €, ×3 jusqu'à 15 €, ×2,5 jusqu'à 40 €, ×2 jusqu'à 80 €, ×1,7 au-delà).
   `profit_après_CPA = marge_brute − CPA` (CPA pub ≈ 12 € par défaut). Un produit qui ne
   peut pas absorber le coût d'acquisition publicitaire est **éliminé** (gate dur).
2. **Bande de prix psychologique** — sweet spot achat d'impulsion : retail ~15–60 €
   (log-gaussienne centrée 30 €). Trop cher = pas d'impulsion ; trop bas = pas de marge.
3. **Saturation** (`listedNum`) — 1–15 vendeurs = validé sans être saturé (idéal) ;
   0 = non prouvé ; >100 = océan rouge.
4. **Fraîcheur** (`createTime`) — récent = on surfe tôt.

Score 0–100 = **moyenne géométrique pondérée** des 4 sous-scores (la moyenne géométrique
sanctionne tout défaut fatal). Verdict **BUY / WATCH / PASS** + raison en une phrase.

## Saisonnalité — `signals/seasonality.py`

Table catégorie/mot-clé → courbe de demande mensuelle (multiplicateur 0,5–1,5). Boost du
score quand le mois courant approche le pic. Répond directement à « pistolets à eau en été ».

## Assemblage

- `analyze.py` : lit `cj.db`, calcule vendabilité × saisonnalité sur tout le catalogue,
  classe, affiche le top + **un exemple détaillé**, exporte un JSON pour le frontend.
- Collecteurs `google_trends.py` / `reddit_mentions.py` : best-effort, enrichissent le top-N
  avec la vélocité réelle quand les dépendances/clés sont présentes.
- `SQLiteRepository` : branche l'API FastAPI sur `cj.db`.

## Vérification

Tests unitaires sellability + saisonnalité ; run réel sur les 1000 produits ; exemple
produit ; calcul de débit (1 h / 24 h) ; analyse de marché.
