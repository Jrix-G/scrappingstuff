# Proposition — refonte collecte AliExpress (à relire avant déploiement)

Ce fichier est une PROPOSITION. Rien de live n'a été modifié :
`demand_runner.py`, `tandor-demand.service` et `tandor_scrape.sh` sont intacts.

## Nouveaux fichiers livrés (sûrs, n'altèrent aucun comportement live)
- `collectors/ali_page_parser.py` — parseur d'extraction-MAX (1 page → ~60 produits).
- `ali_burst_worker.py` — worker burst + persistance masse + contrat exit 0/1/2.

Validés hors-ligne sur les 103 HTML du cache : **6180 produits, 5610 signaux
ventes** extraits, 0 anomalie. Persistance prouvée sur DB jetable
(`sales_snapshots` + `ali_products`).

---

## CHANGEMENT 1 — retirer la boucle Ali débile de `demand_runner.py`

`demand_runner` ne doit PLUS faire d'AliExpress par mot-clé. Raison : l'IP maison
du runner sert déjà à Amazon en continu ; y intercaler 1 req Ali/5,5 min ne fait
que brûler le budget IP Ali (3-4 req) en pure perte et polluer le pacing Amazon.

### Diff proposé

```diff
@@ constantes
-# ── Cadence AliExpress (budget rare, top produits) ───────────────────────────
-ALI_INTERVAL_S = 330             # ~5,5 min → ~260/jour, sous le plafond x5sec
+# AliExpress n'est PLUS scrapé ici : délégué à ali_burst_worker.py (burst+rotation
+# d'IP, lancé par tandor_scrape.sh la nuit). Voir PROPOSAL_ali_refactor.md.

@@ supprimer la fonction _scrape_aliexpress (devient inutile)
-def _scrape_aliexpress(keyword: str):
-    ...tout le corps...

@@ dans main(), supprimer l'init
-    last_ali = 0.0

@@ dans la boucle while _RUN, supprimer le bloc cadence Ali
-        # ── Cadence AliExpress (top produits) ────────────────────────────────
-        if time.time() - last_ali >= ALI_INTERVAL_S:
-            ali_kw = q.next_aliexpress_keyword(c)
-            if ali_kw:
-                res, ali_d = _scrape_aliexpress(ali_kw)
-                q.record_aliexpress(c, ali_kw, ali_d)
-                print(f"[{_ts()}]   ▸ AliExpress « {ali_kw} » → {res}", flush=True)
-            last_ali = time.time()
```

`demand_runner` reste responsable de REMPLIR `aliexpress_queue` (via
`record_amazon` → seuil `ALI_THRESHOLD`). Le worker burst CONSOMME cette file.
Aucun changement de schéma : `record_aliexpress`/`sales_snapshots` restent le
chemin canonique, désormais alimenté par `ali_burst_worker._persist_page`.

---

## CHANGEMENT 2 — brancher le worker dans la rotation nocturne

`tandor_scrape.sh` a DÉJÀ tout : sudo NOPASSWD sur `tandor-vpn-up/-down`,
rotation des 14 configs WireGuard, contrat exit 0/1/2. Il suffit de lui faire
appeler le worker au lieu de (ou en plus de) `vpn_warmer --target aliexpress`.

### Option A (recommandée) — remplacer le warmer Ali par le worker burst

Dans `tandor_scrape.sh`, section `[1/3] AliExpress`, remplacer l'appel
`vpn_warmer.py --target aliexpress` par :

```bash
"$PY" "$ENGINE/ali_burst_worker.py" --budget 4 --batch 60 --max-keywords 4000
```

et, dans `run_with_vpn_rotation()`, faire pointer le fallback Ali vers le worker
plutôt que `tandor-vpn-exec-warmer --target aliexpress`. Comme le worker respecte
le MÊME contrat (0/1/2), la mécanique de rotation existante marche sans modif :
exit 2 → l'IP a épuisé son budget → la shell tourne d'IP et relance.

### Option B (zéro risque, additif) — un netns-runner dédié

Si tu préfères ne pas toucher `tandor_scrape.sh`, ajoute un wrapper sudo jumeau
de `tandor-vpn-exec-warmer` qui lance `ali_burst_worker.py` dans le netns (voir
section « action root »), et une petite boucle bash de rotation calquée sur
`run_with_vpn_rotation`.

---

## Cadence cible

- Par IP propre : burst de ~4 req → ~240 produits + ~4 agrégats ventes, en
  quelques secondes, puis rotation.
- 14 IP × 4 req ≈ 56 pages/passage ≈ **~3360 produits / passage**, sans pacing
  inutile. Plusieurs passages/nuit possibles (les IP « refroidissent »).
- À comparer aux ~260 résumés/jour de l'ancienne boucle : gain ~×100 en lignes
  produit, pour MOINS de requêtes.
```
