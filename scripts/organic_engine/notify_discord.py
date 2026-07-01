"""Notifications Discord du runner de demande — best-effort, non bloquant.

Poste dans un salon via l'API REST Discord en réutilisant le TOKEN du bot existant
(``/home/albator/discord/.env``). On ne lance PAS le bot : un simple POST authentifié
``Bot <token>`` suffit, donc c'est totalement découplé du process bot (il peut être éteint).

Conçu pour ne JAMAIS casser le runner :
* envoi dans un thread daemon (fire-and-forget) → la boucle de scraping ne bloque pas ;
* toute erreur (réseau, token absent, rate-limit) est avalée silencieusement + logguée ;
* si le token ou l'ID de salon manque, les appels deviennent des no-op.

Config (lue à l'import) :
* ``DISCORD_TOKEN``        — token du bot (par défaut depuis /home/albator/discord/.env) ;
* ``DISCORD_CHANNEL_ID``   — ID du salon cible (env var, ou ligne dans le même .env).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import urllib.request
from pathlib import Path

logger = logging.getLogger("tandor.discord")

# Chemin du .env du bot : configurable (TANDOR_DISCORD_ENV) avec repli sur
# ~/discord/.env. Sur le Pi (home=albator) cela vaut /home/albator/discord/.env →
# identique à avant ; sur un autre nœud (ex. VPS opc) cela suit son propre HOME.
_BOT_ENV = Path(os.getenv("TANDOR_DISCORD_ENV") or (Path.home() / "discord" / ".env"))
_API = "https://discord.com/api/v10/channels/{channel}/messages"


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse minimal d'un .env (KEY=VALUE), sans dépendance externe."""
    out: dict[str, str] = {}
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


_file_env = _load_env_file(_BOT_ENV)
_TOKEN = os.getenv("DISCORD_TOKEN") or _file_env.get("DISCORD_TOKEN")
_CHANNEL = os.getenv("DISCORD_CHANNEL_ID") or _file_env.get("DISCORD_CHANNEL_ID")
# Préfixe de nœud (ex. « [2] ») pour distinguer la source quand plusieurs machines
# postent dans le MÊME salon. Vide sur le Pi → messages inchangés.
_PREFIX = os.getenv("TANDOR_NOTIFY_PREFIX") or _file_env.get("TANDOR_NOTIFY_PREFIX") or ""

_enabled = bool(_TOKEN and _CHANNEL)
if not _enabled:
    logger.info("Discord désactivé (token ou DISCORD_CHANNEL_ID manquant) — no-op.")


def _post(content: str, ping: bool = False) -> None:
    url = _API.format(channel=_CHANNEL)
    if _PREFIX:
        content = f"{_PREFIX.rstrip()} {content}"
    payload: dict = {"content": content[:1900]}
    if ping:
        # @here réellement notifiant : il FAUT allowed_mentions pour que Discord ping.
        payload["content"] = "@here\n" + content[:1880]
        payload["allowed_mentions"] = {"parse": ["everyone"]}
    else:
        payload["allowed_mentions"] = {"parse": []}  # jamais de ping parasite
    data = json.dumps(payload).encode()  # marge sous la limite 2000
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Authorization": f"Bot {_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "TandorDemandRunner (https://tandor, 1.0)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as e:  # réseau / 401 / 429 → on log, on ne propage jamais
        logger.warning("Échec notif Discord: %s", e)


def send(content: str, ping: bool = False) -> None:
    """Envoie un message dans le salon (asynchrone, best-effort). No-op si non configuré.
    ping=True ajoute un @here notifiant (à réserver aux events importants)."""
    if not _enabled:
        return
    threading.Thread(target=_post, args=(content, ping), daemon=True).start()


# ── Helpers de mise en forme (cohérents avec les logs du runner) ─────────────

def ali_scraped(keyword: str, max_sold, median_sold, listings: int) -> None:
    send(f"🟢 **AliExpress** · `{keyword}` — maxSold **{max_sold:,}** · "
         f"médiane {median_sold:,} · {listings} annonces")


def ali_no_sales(keyword: str) -> None:
    send(f"⚪ **AliExpress** · `{keyword}` — page OK, aucun compteur de ventes")


def blocked(keyword: str, source: str = "AliExpress") -> None:
    send(f"🔴 **BAN / blocage {source}** sur `{keyword}` — IP en cooldown x5sec")


def amazon_hot(keyword: str, max_bought, median_bought, n_velocity: int, n_results: int) -> None:
    """Breakout Amazon : nouveau record de demande atteignant le palier massif
    (≥ q.BREAKOUT_THRESHOLD). Rare par design (~3/jour) — pas une notif par produit."""
    send(f"🚀 **Amazon breakout** · `{keyword}` — nouveau record **{max_bought:,}**/mois · "
         f"médiane {median_bought:,} · {n_velocity}/{n_results} produits")


def _fmt_bought(v) -> str:
    """Entier badge Amazon → libellé compact (« 100000 »→« 100k+ », « 50 »→« 50+ »).
    Les badges Amazon sont tous des planchers (« X+ ») → le « + » est toujours exact."""
    if v is None:
        return "?"
    if v >= 1000:
        return f"{v // 1000}k+"
    return f"{v}+"


def digest(scraped_last_h: int, top, queue_total: int, blocks: int = 0) -> None:
    """Digest horaire (remplace le 💓 heartbeat) : volume scrapé + top demande réel."""
    lines = [f"📦 **Dernière heure — {scraped_last_h} produits scrapés**"]
    if top:
        lines.append("Top demande :")
        for kw, mb in top:
            lines.append(f"• {kw} — {_fmt_bought(mb)}/mois")
    block_txt = f"{blocks} blocage{'s' if blocks != 1 else ''}"
    lines.append(f"(file : {queue_total:,} mots-clés · {block_txt})")
    send("\n".join(lines))


def sales_hot(keyword: str, source: str, max_sold, median_sold, listings: int) -> None:
    """Vente secondaire chaude (eBay/DHgate). source ex. 'eBay', 'DHgate'."""
    send(f"🟢 **{source} HOT** · `{keyword}` — sold **{max_sold:,}** · "
         f"médiane {median_sold:,} · {listings} annonces")


if __name__ == "__main__":  # test manuel : python3 notify_discord.py
    logging.basicConfig(level=logging.INFO)
    if not _enabled:
        print("Non configuré : exporte DISCORD_CHANNEL_ID (token déjà dans le .env du bot).")
    else:
        _post("✅ Test notif Tandor — le runner peut écrire dans ce salon.")
        print("Message de test envoyé (vérifie le salon).")
