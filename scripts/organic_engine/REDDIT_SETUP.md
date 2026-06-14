# Reddit — aucune clé nécessaire ✅

Reddit a verrouillé son API legacy (création d'app « script » réservée aux cas de
modération) **et** bloque ses endpoints `.json` depuis les clients non-navigateur
(HTTP 403). On contourne proprement : le collecteur (`collectors/reddit_mentions.py`)
utilise le **flux RSS public de recherche** (`search.rss`), qui reste servi sans
authentification.

## Ce que ça implique

- **Pas de clé, pas d'inscription, pas d'approbation.** Ça marche tout de suite.
- Le RSS donne les **titres + dates** des posts → on construit une série temporelle de
  mentions par semaine → vélocité réelle. Il ne donne pas les upvotes/commentaires
  (réservés au JSON bloqué) ; le signal est la **fréquence de mentions dans le temps**,
  qui est précisément l'indicateur d'émergence recherché.
- Reddit rate-limite agressivement le RSS (HTTP 429). Le collecteur gère ça par :
  requête **multi-subreddit unique**, **cache disque 6 h**, **backoff** et intervalle
  minimal entre appels.

## Tester

```bash
python3 -m collectors.reddit_mentions "robot vacuum"
```

Si tu vois « posts vus / gardés » non nuls, c'est opérationnel. Le signal Reddit
s'ajoute alors automatiquement à Google Trends dans `enrich.py` (deux sources
indépendantes → corroboration du moteur).

> Si jamais le RSS finit par être bloqué lui aussi (même classe de problème que le
> scraping AliExpress sur IP datacenter), le repli est un navigateur headless
> (Playwright, déjà présent dans le projet) ou un proxy résidentiel.
