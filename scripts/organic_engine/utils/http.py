"""utils/http.py — transport HTTP partagé (curl_cffi chrome131 → urllib de repli).

Pourquoi
--------
Les collecteurs « faibles » (suggest_trends, aliexpress_orders, dhgate_sold,
tiktok_trending, ebay_*) tapaient chacun le web avec `urllib.request` nu et un
User-Agent souvent **malformé** (`Chrome/124.0` — 2 segments, une empreinte de
bot évidente) sans TLS/JA3 crédible ni client-hints. Résultat : soft-blocs et
pages vides silencieuses.

Ce module centralise UN transport correct :
* **curl_cffi** avec `impersonate="chrome131"` quand il est présent → empreinte
  TLS/JA3 + headers d'un vrai Chrome (le même que le worker AliExpress qui, lui,
  passe). C'est le chemin par défaut.
* **urllib de repli** si curl_cffi manque : au moins un UA Chrome 131 CANONIQUE
  (4 segments) + client-hints + gestion gzip, pour ne pas régresser.

API minimale, pensée pour remplacer un `urlopen` sans réécrire la logique métier
(chaque collecteur garde SA détection de blocage et SES exceptions) ::

    from utils import http
    res = http.get_text(url, headers={"Accept": "application/json"})
    if res.status != 200 or not res.text:
        ...
    data = res.text

Un `http.Session()` réutilisable est offert pour les collecteurs qui « chauffent »
une home avant la vraie requête (ex. eBay) — la session garde cookies + connexion.
"""

from __future__ import annotations

import gzip
import urllib.error
import urllib.request
from typing import NamedTuple, Optional

# UA Chrome 131 canonique (4 segments) — cohérent avec impersonate="chrome131".
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Client-hints d'un vrai Chrome 131 (utiles surtout sur le chemin urllib de repli ;
# sur le chemin curl_cffi, impersonate pose déjà les siens, cohérents avec le JA3).
CLIENT_HINTS = {
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

DEFAULT_ACCEPT_LANGUAGE = "en-US,en;q=0.9"

# Détection unique : curl_cffi est-il utilisable ?
try:
    from curl_cffi import requests as _creq  # type: ignore
    _HAS_CURL = True
except Exception:  # pragma: no cover
    _creq = None
    _HAS_CURL = False


class HttpResult(NamedTuple):
    status: int          # code HTTP (0 si échec transport avant réponse)
    text: str            # corps décodé (str, jamais None)
    transport: str       # "curl_cffi" | "urllib" — pour le diagnostic/log


def _merge_headers(headers: Optional[dict], *, with_hints: bool) -> dict:
    h = {"accept-language": DEFAULT_ACCEPT_LANGUAGE}
    if with_hints:
        h.update(CLIENT_HINTS)
    if headers:
        # Les headers de l'appelant priment (casse d'origine conservée).
        h.update(headers)
    return h


class Session:
    """Session réutilisable (cookies + keep-alive). curl_cffi si dispo, sinon
    un shim urllib sans état partagé de cookies (suffisant pour un repli)."""

    def __init__(self, impersonate: str = "chrome131") -> None:
        self.transport = "urllib"
        self._sess = None
        if _HAS_CURL:
            try:
                self._sess = _creq.Session(impersonate=impersonate)
                self._sess.headers.update({"accept-language": DEFAULT_ACCEPT_LANGUAGE})
                self.transport = "curl_cffi"
            except Exception:
                self._sess = None
                self.transport = "urllib"

    def get_text(self, url: str, *, headers: Optional[dict] = None,
                 timeout: int = 25) -> HttpResult:
        if self._sess is not None:
            try:
                # impersonate fournit déjà UA + sec-ch-ua cohérents avec le JA3 ;
                # on n'ajoute donc PAS les client-hints ici (éviter les doublons).
                r = self._sess.get(url, headers=_merge_headers(headers, with_hints=False),
                                   timeout=timeout)
                return HttpResult(int(r.status_code), r.text, "curl_cffi")
            except Exception:
                return HttpResult(0, "", "curl_cffi")
        return _urllib_get(url, headers=headers, timeout=timeout)

    def close(self) -> None:
        if self._sess is not None:
            try:
                self._sess.close()
            except Exception:
                pass


def _urllib_get(url: str, *, headers: Optional[dict], timeout: int) -> HttpResult:
    """Repli urllib : UA Chrome 131 canonique + client-hints + gzip."""
    h = _merge_headers(headers, with_hints=True)
    h.setdefault("User-Agent", UA)
    h.setdefault("Accept-Encoding", "gzip")
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if "gzip" in (resp.headers.get("Content-Encoding") or ""):
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            text = raw.decode("utf-8", "replace")
            return HttpResult(int(getattr(resp, "status", 200) or 200), text, "urllib")
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return HttpResult(int(e.code), body, "urllib")
    except Exception:
        return HttpResult(0, "", "urllib")


# Session partagée paresseuse (pour les appels one-shot sans warm-up).
_shared: Optional[Session] = None


def _shared_session() -> Session:
    global _shared
    if _shared is None:
        _shared = Session()
    return _shared


def get_text(url: str, *, headers: Optional[dict] = None,
             timeout: int = 25) -> HttpResult:
    """GET one-shot via la session partagée. Renvoie toujours un HttpResult
    (status=0 en cas d'échec transport). Ne lève jamais : c'est l'appelant qui
    décide de sa politique de blocage à partir de (status, text)."""
    return _shared_session().get_text(url, headers=headers, timeout=timeout)
