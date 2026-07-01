"""Authentification serveur de l'API Tandor (vérification d'ID token Firebase).

POURQUOI : sans ce module, /api/products & co. exposaient TOUT le dataset payant
(~6100 produits + scores) en accès libre via le tunnel public — le gating React
n'était que cosmétique. Ici on vérifie côté serveur un ID token Firebase signé,
on résout le plan de l'utilisateur (source de vérité = custom claim posé par le
webhook Stripe, ou repli Firestore admin), et on applique un quota journalier.

CONFIGURATION REQUISE (à faire une fois sur le Pi, AVANT de redémarrer l'API) :
    1. Générer une clé de compte de service Firebase (console → Paramètres du
       projet → Comptes de service → Générer une nouvelle clé privée).
    2. La déposer HORS du repo, ex. /home/albator/secrets/tandor-sa.json (chmod 600).
    3. Ajouter dans ~/tandor.env :
           FIREBASE_CREDENTIALS=/home/albator/secrets/tandor-sa.json
    4. Installer la dépendance : .venv/bin/pip install "firebase-admin>=6.5"
    5. Redémarrer l'API.

Tant que FIREBASE_CREDENTIALS n'est pas configuré, les endpoints protégés
renvoient 503 (fail-closed) : on préfère un service indisponible à un dataset
payant ouvert. Pour un déploiement de transition, TANDOR_AUTH_REQUIRED=0 désactive
explicitement l'auth (À ÉVITER en prod — c'est exactement la faille corrigée).
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Header, HTTPException

_ROOT = Path(__file__).resolve().parent.parent
_USAGE_DB = _ROOT / "data" / "usage.db"

# Quota journalier de requêtes par plan (cf. landing : free 50/j, Pro 2000/j).
QUOTA = {"free": 50, "starter": 500, "pro": 2000}

# Coût (en unités de quota) d'une opération coûteuse type scraping live.
VALIDATE_COST = 10

_AUTH_REQUIRED = os.environ.get("TANDOR_AUTH_REQUIRED", "1") != "0"

_fb_app = None
_fb_lock = threading.Lock()


def _firebase():
    """Initialise (une fois) l'app firebase-admin depuis la clé de service."""
    global _fb_app
    if _fb_app is not None:
        return _fb_app
    with _fb_lock:
        if _fb_app is not None:
            return _fb_app
        cred_path = os.environ.get("FIREBASE_CREDENTIALS")
        if not cred_path or not Path(cred_path).exists():
            raise HTTPException(503, "Auth non configurée (FIREBASE_CREDENTIALS manquant).")
        try:
            import firebase_admin
            from firebase_admin import credentials
        except ImportError:
            raise HTTPException(503, "Dépendance firebase-admin absente côté serveur.")
        _fb_app = firebase_admin.initialize_app(credentials.Certificate(cred_path))
        return _fb_app


def _verify_token(token: str) -> dict:
    from firebase_admin import auth as fb_auth
    try:
        return fb_auth.verify_id_token(token, app=_firebase())
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Token Firebase invalide.")


def plan_for(decoded: dict) -> str:
    """Plan de l'utilisateur, NON falsifiable par le client.

    1) custom claim ``plan`` (posé par le webhook Stripe via l'Admin SDK) — rapide.
    2) repli : lecture Firestore admin de users/{uid} (ignore les security rules).
    Tout échec -> 'free' (moindre privilège).
    """
    plan = decoded.get("plan")
    if plan in QUOTA:
        return plan
    try:
        from firebase_admin import firestore as fb_fs
        snap = fb_fs.client(_firebase()).collection("users").document(decoded["uid"]).get()
        d = snap.to_dict() or {}
        return d.get("plan", "free") if d.get("subscription_active") else "free"
    except Exception:
        return "free"


def charge_quota(uid: str, plan: str, cost: int = 1) -> None:
    """Incrémente le compteur journalier de l'utilisateur ; 429 si dépassement."""
    limit = QUOTA.get(plan, QUOTA["free"])
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _USAGE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_USAGE_DB, timeout=5)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS usage("
                     "uid TEXT, day TEXT, n INTEGER, PRIMARY KEY(uid, day))")
        conn.execute("INSERT INTO usage(uid, day, n) VALUES(?,?,?) "
                     "ON CONFLICT(uid, day) DO UPDATE SET n = n + ?",
                     (uid, day, cost, cost))
        n = conn.execute("SELECT n FROM usage WHERE uid=? AND day=?", (uid, day)).fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    if n > limit:
        raise HTTPException(429, f"Quota journalier dépassé ({limit}/j, plan {plan}).")


def require_user(authorization: str = Header(None)) -> dict:
    """Dépendance FastAPI : exige un Bearer ID token Firebase valide.

    Renvoie le token décodé (contient ``uid``). Si l'auth est désactivée
    (TANDOR_AUTH_REQUIRED=0), renvoie un pseudo-utilisateur anonyme 'free'.
    """
    if not _AUTH_REQUIRED:
        return {"uid": "anonymous", "plan": "free"}
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token Firebase manquant (header Authorization).")
    return _verify_token(authorization.split(" ", 1)[1])
