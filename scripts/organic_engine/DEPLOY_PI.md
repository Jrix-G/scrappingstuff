# Déploiement sur Raspberry Pi — collecte + API + tunnel

Le Pi fait trois choses : **collecter** CJ chaque jour (démarre l'historique de
vélocité), **servir** l'API à partir du cache, et **exposer** cette API via un
tunnel Cloudflare (URL HTTPS stable, sans ouvrir de port sur la box).

Architecture : `run_daily.py` (cron) → écrit `data/dashboard_export.json` →
`api/server.py` (service uvicorn) lit ce cache → `cloudflared` l'expose.

---

## 0. Pré-requis (une fois)

```bash
cd ~/scrappingstuff/scripts/organic_engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # numpy, pytrends, fastapi, uvicorn, pytest
```

Mets les identifiants CJ dans un fichier d'environnement **hors du repo** :

```bash
# ~/tandor.env   (chmod 600)
CJ_EMAIL=jewixyt@gmail.com
CJ_API_KEY=ta_cle_api_cj
```

---

## 1. Collecte quotidienne (cron)

Un script wrapper qui charge l'env, active le venv et lance le job :

```bash
# ~/scrappingstuff/scripts/organic_engine/daily.sh
#!/usr/bin/env bash
set -a; source ~/tandor.env; set +a
cd ~/scrappingstuff/scripts/organic_engine
source .venv/bin/activate
python3 run_daily.py --pages 40 --limit 60 >> ~/tandor-daily.log 2>&1
```

```bash
chmod +x ~/scrappingstuff/scripts/organic_engine/daily.sh
crontab -e
# → collecte chaque jour à 04h12 (heure creuse, évite le rate-limit Trends en journée)
12 4 * * * ~/scrappingstuff/scripts/organic_engine/daily.sh
```

> Le **2ᵉ** passage (J+1) active la vélocité CJ réelle : `cj_snapshots` a alors
> 2 points par produit → accélération de la saturation mesurable.

---

## 2. API en service permanent (systemd)

```ini
# /etc/systemd/system/tandor-api.service
[Unit]
Description=Tandor Organic Engine API
After=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/scrappingstuff/scripts/organic_engine
EnvironmentFile=/home/pi/tandor.env
# Front local en dev : autorise localhost. Ajoute ton domaine quand le front sera en ligne.
Environment=TANDOR_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ExecStart=/home/pi/scrappingstuff/scripts/organic_engine/.venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tandor-api
curl http://localhost:8000/api/health      # {"status":"ok"}
curl http://localhost:8000/api/meta         # fraîcheur des données
```

Sur ton réseau local, l'API répond déjà à `http://<ip-du-pi>:8000`.

---

## 3. Tunnel Cloudflare (URL HTTPS publique stable)

Pour quand le front sera déployé en ligne (le navigateur des visiteurs doit
joindre le Pi). Gratuit, pas de port-forwarding, pas d'IP fixe.

```bash
# install cloudflared (ARM)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -o cloudflared
sudo install cloudflared /usr/local/bin/

cloudflared tunnel login                    # ouvre un lien à autoriser
cloudflared tunnel create tandor
cloudflared tunnel route dns tandor api.tondomaine.com
```

```yaml
# ~/.cloudflared/config.yml
tunnel: tandor
credentials-file: /home/pi/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: api.tondomaine.com
    service: http://localhost:8000
  - service: http_status:404
```

```bash
sudo cloudflared service install            # tourne au boot
# → l'API est joignable sur https://api.tondomaine.com/api/products
```

N'oublie pas d'ajouter `https://ton-front.vercel.app` à `TANDOR_CORS_ORIGINS`
(section 2) le jour où le front passe en ligne.

---

## 4. Brancher le front local sur l'API du Pi

Dans `frontend/.env.local` :

```
REACT_APP_API_URL=http://<ip-du-pi>:8000
```

`npm start` → le dashboard fetch `/api/products` ; si l'API est injoignable, il
retombe automatiquement sur le JSON bundlé (aucune page blanche). Sans cette
variable, le front reste 100 % en local sur le JSON bundlé.

---

## Récap des commandes utiles

| But | Commande |
|---|---|
| Collecte + cache à la main | `python3 run_daily.py --pages 40 --limit 60` |
| Cache seul (sans collecte) | `python3 run_daily.py --no-collect` |
| Cache rapide (sans Trends) | `python3 run_daily.py --no-collect --no-enrich` |
| Voir la fraîcheur | `curl localhost:8000/api/meta` |
| Logs du cron | `tail -f ~/tandor-daily.log` |
| Logs de l'API | `journalctl -u tandor-api -f` |
