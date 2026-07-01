#!/usr/bin/env python3
"""ali_pacer.py — régulateur de cadence AIMD par IP pour la collecte AliExpress.

Problème
--------
Le blocage x5sec d'AliExpress est un état **par IP** : ~quelques requêtes propres,
puis une page « punish » et un cooldown (~30-40 min). Reprober PENDANT le cooldown
**réarme** le timer. Les scripts historiques utilisaient des constantes figées
(``DRIP=360`` entre requêtes, ``HEAL=2100`` après un punish). Une constante ne peut
pas être juste : trop lente, on gâche le budget de l'IP ; trop rapide, on la brûle.

Solution : AIMD (comme le contrôle de congestion TCP)
----------------------------------------------------
On adapte deux grandeurs, séparément pour chaque IP :

* ``interval`` — l'attente entre deux requêtes RÉUSSIES (le « DRIP »).
    - succès  → **décroissance additive** : on accélère prudemment (interval - STEP).
    - punish  → **croissance multiplicative** : on ralentit fort (interval * BACKOFF).
  L'équilibre converge juste sous le seuil de blocage : la cadence maximale sûre,
  découverte empiriquement plutôt que devinée.

* ``cooldown`` — le silence après un punish (le « HEAL »), pendant lequel on ne
  reprobe SURTOUT PAS (discipline de guérison : reprober réarme le timer).
    - punish  → croissance multiplicative (l'IP est manifestement plus chaude).
    - succès  → décroissance douce vers un plancher (l'IP a re-guéri).

On mémorise aussi ``est_capacity`` : moyenne mobile du nombre de requêtes propres
obtenues avant un punish — une mesure directe du budget réel de l'IP, utile pour
dimensionner un burst (``--budget``) ailleurs.

État
----
Persisté en JSON atomique dans ``data/ali_pacer_state.json``, clé = identité d'IP
(``TANDOR_PACER_IP`` sinon ``"self"``). Aucune requête réseau ici → n'interfère pas
avec la discipline de guérison.

CLI (pour les scripts shell)
----------------------------
  python3 ali_pacer.py get interval      # -> entier secondes (pour `sleep`)
  python3 ali_pacer.py get cooldown      # -> entier secondes
  python3 ali_pacer.py observe self success
  python3 ali_pacer.py observe self punish
  python3 ali_pacer.py status            # -> résumé lisible
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
STATE_FILE = ENGINE / "data" / "ali_pacer_state.json"

# ─── Bornes AIMD (secondes) ──────────────────────────────────────────────────
# interval : cadence entre requêtes réussies sur une même IP.
INTERVAL_FLOOR = 180.0     # jamais plus vite que 3 min (le durable prouvé est 5-6 min)
INTERVAL_CEIL = 1200.0     # jamais plus lent que 20 min
INTERVAL_START = 360.0     # départ = ancien DRIP
INTERVAL_STEP = 20.0       # décroissance additive par succès (accélération douce)
INTERVAL_BACKOFF = 1.7     # croissance multiplicative par punish (recul brutal)

# cooldown : guérison après un punish.
COOLDOWN_FLOOR = 1800.0    # au moins 30 min de silence
COOLDOWN_CEIL = 3600.0     # au plus 60 min
COOLDOWN_START = 2100.0    # départ = ancien HEAL
COOLDOWN_BACKOFF = 1.5     # croissance multiplicative par punish
COOLDOWN_HEAL = 0.97       # décroissance douce par succès (vers le plancher)

# est_capacity : moyenne mobile exponentielle du run propre avant blocage.
CAPACITY_ALPHA = 0.3


def _ip_key(ip: str | None = None) -> str:
    if ip:
        return ip
    return os.getenv("TANDOR_PACER_IP") or "self"


def _default_state() -> dict:
    return {
        "interval": INTERVAL_START,
        "cooldown": COOLDOWN_START,
        "clean_run": 0,        # succès consécutifs depuis le dernier punish
        "est_capacity": 0.0,   # EWMA du run propre avant punish
        "successes": 0,
        "punishes": 0,
        "last_outcome": "",
        "updated": 0.0,
    }


def _load() -> dict:
    try:
        d = json.loads(STATE_FILE.read_text())
        if not isinstance(d, dict) or "ips" not in d:
            raise ValueError("shape")
        return d
    except Exception:
        return {"version": 1, "ips": {}}


def _save(d: dict) -> None:
    """Écriture atomique : temp + os.replace (jamais de fichier à moitié écrit)."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(STATE_FILE.parent), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(d, f)
        os.replace(tmp, str(STATE_FILE))
    except Exception:
        pass


def _get_ip_state(d: dict, ip: str) -> dict:
    st = d.setdefault("ips", {}).get(ip)
    base = _default_state()
    if isinstance(st, dict):
        base.update({k: st[k] for k in base if k in st})
    d["ips"][ip] = base
    return base


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ─── API ─────────────────────────────────────────────────────────────────────

def observe(ip: str | None, outcome: str) -> dict:
    """Enregistre le résultat d'une requête et fait évoluer interval/cooldown.

    outcome ∈ {"success", "punish"}. Retourne l'état IP mis à jour. Best-effort :
    toute erreur est avalée (le pacer ne doit jamais faire tomber le collecteur)."""
    ip = _ip_key(ip)
    d = _load()
    st = _get_ip_state(d, ip)
    if outcome == "success":
        st["successes"] += 1
        st["clean_run"] += 1
        # AIMD : décroissance additive de l'intervalle (on accélère prudemment).
        st["interval"] = _clamp(st["interval"] - INTERVAL_STEP,
                                INTERVAL_FLOOR, INTERVAL_CEIL)
        # L'IP prouve sa santé → on détend doucement le cooldown vers le plancher.
        st["cooldown"] = _clamp(st["cooldown"] * COOLDOWN_HEAL,
                                COOLDOWN_FLOOR, COOLDOWN_CEIL)
    elif outcome == "punish":
        st["punishes"] += 1
        # Le run propre qui vient de finir mesure la capacité réelle de l'IP.
        if st["clean_run"] > 0:
            if st["est_capacity"] <= 0:
                st["est_capacity"] = float(st["clean_run"])
            else:
                st["est_capacity"] = (
                    (1 - CAPACITY_ALPHA) * st["est_capacity"]
                    + CAPACITY_ALPHA * st["clean_run"]
                )
        st["clean_run"] = 0
        # AIMD : croissance multiplicative (recul brutal sur les deux grandeurs).
        st["interval"] = _clamp(st["interval"] * INTERVAL_BACKOFF,
                                INTERVAL_FLOOR, INTERVAL_CEIL)
        st["cooldown"] = _clamp(st["cooldown"] * COOLDOWN_BACKOFF,
                                COOLDOWN_FLOOR, COOLDOWN_CEIL)
    else:
        return st
    st["last_outcome"] = outcome
    st["updated"] = time.time()
    _save(d)
    return st


def recommended_interval(ip: str | None = None) -> int:
    st = _get_ip_state(_load(), _ip_key(ip))
    return int(_clamp(st["interval"], INTERVAL_FLOOR, INTERVAL_CEIL))


def recommended_cooldown(ip: str | None = None) -> int:
    st = _get_ip_state(_load(), _ip_key(ip))
    return int(_clamp(st["cooldown"], COOLDOWN_FLOOR, COOLDOWN_CEIL))


def recommended_budget(ip: str | None = None) -> int:
    """Budget de burst suggéré = capacité estimée moins une marge (min 1).
    Utile pour le chemin VPS (worker --budget N). Conservateur par défaut."""
    st = _get_ip_state(_load(), _ip_key(ip))
    cap = st.get("est_capacity", 0.0)
    if cap <= 0:
        return 1
    return max(1, int(cap) - 1)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _main(argv: list[str]) -> int:
    if not argv:
        print("usage: ali_pacer.py get {interval|cooldown|budget} | "
              "observe <ip> {success|punish} | status", file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd == "get" and len(argv) >= 2:
        ip = argv[2] if len(argv) >= 3 else None
        if argv[1] == "interval":
            print(recommended_interval(ip)); return 0
        if argv[1] == "cooldown":
            print(recommended_cooldown(ip)); return 0
        if argv[1] == "budget":
            print(recommended_budget(ip)); return 0
        print("unknown get target", file=sys.stderr); return 2
    if cmd == "observe" and len(argv) >= 3:
        st = observe(argv[1], argv[2])
        print("interval=%d cooldown=%d clean_run=%d est_capacity=%.1f" % (
            int(st["interval"]), int(st["cooldown"]),
            st["clean_run"], st["est_capacity"]))
        return 0
    if cmd == "status":
        d = _load()
        ips = d.get("ips", {})
        if not ips:
            print("(aucun état pacer encore)")
            return 0
        for ip, st in ips.items():
            print("IP %-16s interval=%4ds cooldown=%4ds clean_run=%d "
                  "capacity~%.1f succ=%d punish=%d last=%s" % (
                      ip, int(st["interval"]), int(st["cooldown"]),
                      st["clean_run"], st["est_capacity"],
                      st["successes"], st["punishes"], st["last_outcome"] or "-"))
        return 0
    print("commande inconnue", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
