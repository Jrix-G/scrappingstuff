# Organic Growth Engine

Moteur qui répond à : **« Quelle est la probabilité qu'un produit connaisse une
forte croissance organique dans les prochaines semaines ? »**

Angle différenciant vs Minea / SellTheTrend / Dropship.io : on mesure
l'**accélération** de popularité (dérivée seconde, à bas niveau) pour repérer les
produits *avant* leur saturation — pas la popularité déjà installée.

## Démarrage

```bash
pip install -r requirements.txt   # numpy suffit pour le cœur
python3 demo.py                    # démo end-to-end
python3 -m pytest tests/ -q        # 18 tests (validation scientifique)
```

`demo.py` classe 4 produits synthétiques : l'émergent (accélération multi-sources,
bas niveau) sort à 100/100 en phase EMERGENT ; le saturé et le déclinant en bas.

## Idée en une formule

```
score = percentile( momentum·corroboration − λ·maturité )
        momentum   = accélération + vélocité normalisées (z robustes), par source
        maturité   = niveau + âge + vendeurs + avis (ce qui indique la saturation)
        → haut quand ça accélère ET que ce n'est pas encore saturé
```

Score 0-100 + **confiance** séparée + **phase** (EMERGENT…DECLINING) +
**explication** décomposée par source. Tout est justifiable.

## Structure

Voir `DESIGN.md` pour l'architecture complète, le modèle mathématique, le schéma
SQL, l'API, le plan de dev, les risques et les évolutions. Modules clés :

- `signals/timeseries.py` — dérivées (vélocité/accélération) sur log, z robustes
- `scoring/engine.py` — score composite transversal + explicabilité
- `scoring/phases.py` — classification du cycle de vie
- `analytics/backtest.py` — AUC / precision@k / calibration
- `analytics/learning.py` — apprentissage des poids (remplace le prior)
- `database/schema.sql` — schéma complet avec index
- `api/main.py` — FastAPI (products / product / alerts)

## État

- ✅ Cœur scientifique (signaux, score, phases, backtest, apprentissage) — testé
- ✅ Schéma SQL, API, interfaces collecteurs
- ⏳ À brancher : collecteurs réels (CJ, Reddit, Trends) + repository SQL

La priorité (cf. DESIGN.md §8) : connecter **une source organique précoce réelle**
+ persister l'historique. Le moteur est déjà prêt à la consommer.
