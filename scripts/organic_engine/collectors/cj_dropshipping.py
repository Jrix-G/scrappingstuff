"""Collecteur CJ Dropshipping (API 2.0 officielle, gratuite).

Endpoints vérifiés en live :
* POST /api2.0/v1/authentication/getAccessToken  {email, password=API key}
* GET  /api2.0/v1/product/list?pageNum&pageSize   header CJ-Access-Token
* GET  /api2.0/v1/product/query?pid               header CJ-Access-Token

Contraintes API gérées ici :
* le token est valide ~15 jours et getAccessToken est limité (≈1 / 300 s) :
  on met donc le token en CACHE fichier pour ne pas le redemander à chaque run ;
* les endpoints produit sont limités en débit : délai poli entre les pages.

Ce que CJ expose réellement par produit (liste) : pid, nom, prix fournisseur,
catégorie, image, ``listedNum`` (nb de vendeurs l'ayant listé = saturation/
adoption côté offre) et ``createTime`` (âge). La *vélocité* se construit en
re-snapshotant dans le temps (un run/jour) : c'est l'historique qui crée le signal.

Aucune dépendance externe : urllib (stdlib) uniquement.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_BASE = "https://developers.cjdropshipping.com/api2.0/v1"
_TOKEN_CACHE = Path(__file__).resolve().parent.parent / ".cj_token.json"
# Marge de sécurité : on rafraîchit le token bien avant ses 15 jours.
_TOKEN_TTL_SECONDS = 12 * 24 * 3600


@dataclass(slots=True)
class CJProduct:
    """Produit CJ normalisé (snapshot à un instant).

    Les champs « dossier » (préfixe libre ci-dessous) ne sont renvoyés que par
    ``product/query`` (re-photo d'un produit précis), PAS par ``product/list``
    (découverte) : ils valent donc ``None`` lors d'une collecte de découverte et
    ne sont remplis qu'au refresh. Voir :class:`CJClient.query_product`.
    """

    pid: str
    name: str | None
    price: float | None
    category: str | None
    image: str | None
    listed_num: int | None       # nb de vendeurs (saturation offre / adoption)
    create_time: str | None      # date de création (âge produit)
    observed_at: str             # ISO-8601 UTC du snapshot
    # --- Dossier qualitatif (product/query uniquement) ---------------------
    suggest_price: float | None = None   # prix retail conseillé par CJ (≫ heuristique)
    description: str | None = None        # copy marketing (HTML brut)
    video: str | None = None              # URL vidéo produit (réutilisable en pub)
    images: str | None = None             # galerie multi-images (JSON liste d'URLs)
    variants: str | None = None           # variantes distillées (JSON compact)
    material: str | None = None           # matériau principal
    weight: float | None = None           # poids d'expédition (g)
    supplier: str | None = None           # nom du fournisseur

    @property
    def has_detail(self) -> bool:
        """Vrai si ce snapshot porte le dossier riche (vient de product/query)."""
        return any((self.suggest_price, self.description, self.video,
                    self.images, self.variants, self.supplier))


class CJError(Exception):
    """Erreur renvoyée par l'API CJ (auth, quota, etc.)."""


class CJClient:
    """Client minimal de l'API CJ 2.0 avec cache de token et politesse réseau."""

    name = "cj"

    def __init__(self, email: str, api_key: str, page_delay: float = 1.2) -> None:
        if not email or not api_key:
            raise CJError("Email et API key requis (variables CJ_EMAIL / CJ_API_KEY).")
        self._email = email
        self._api_key = api_key
        self._page_delay = page_delay
        self._token: str | None = None

    # -- HTTP bas niveau ----------------------------------------------------
    @staticmethod
    def _request(method: str, url: str, headers: dict, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except Exception:
                raise CJError(f"HTTP {exc.code} sur {url}") from exc
        if not payload.get("success", payload.get("result", False)):
            raise CJError(payload.get("message", "Erreur CJ inconnue"))
        return payload.get("data") or {}

    # -- Authentification ---------------------------------------------------
    def _load_cached_token(self) -> str | None:
        if not _TOKEN_CACHE.exists():
            return None
        try:
            cached = json.loads(_TOKEN_CACHE.read_text())
            if time.time() - cached.get("ts", 0) < _TOKEN_TTL_SECONDS:
                return cached.get("token")
        except Exception:
            return None
        return None

    def authenticate(self, force: bool = False) -> str:
        """Récupère un access token (depuis le cache si valide)."""
        if not force:
            token = self._load_cached_token()
            if token:
                self._token = token
                return token
        data = self._request(
            "POST",
            f"{_BASE}/authentication/getAccessToken",
            headers={"Content-Type": "application/json"},
            body={"email": self._email, "password": self._api_key},
        )
        token = data.get("accessToken")
        if not token:
            raise CJError("Token absent de la réponse d'authentification.")
        self._token = token
        try:
            _TOKEN_CACHE.write_text(json.dumps({"token": token, "ts": time.time()}))
        except Exception:
            pass  # cache best-effort
        return token

    # -- Produits -----------------------------------------------------------
    def _headers(self) -> dict:
        if not self._token:
            self.authenticate()
        return {"CJ-Access-Token": self._token, "Content-Type": "application/json"}

    def fetch_page(self, page_num: int, page_size: int = 50, category_keyword: str | None = None) -> tuple[list[CJProduct], int]:
        """Récupère une page du catalogue. Renvoie (produits, total disponible)."""
        url = f"{_BASE}/product/list?pageNum={page_num}&pageSize={page_size}"
        if category_keyword:
            url += f"&productNameEn={urllib.parse.quote(category_keyword)}"
        data = self._request("GET", url, headers=self._headers())
        total = int(data.get("total", 0))
        now = datetime.now(timezone.utc).isoformat()
        products = [self._map(item, now) for item in data.get("list", [])]
        return products, total

    def query_product(self, pid: str) -> CJProduct | None:
        """Re-photographie UN produit déjà connu (prix + listedNum à jour).

        Sert au suivi quotidien : on re-snapshote l'univers persistant pour
        construire la vélocité réelle dans le temps. ``createTime`` n'est pas
        renvoyé ici — on conserve celui déjà stocké en base (l'upsert ne
        l'écrase pas). Renvoie ``None`` si le produit est introuvable/retiré.
        """
        url = f"{_BASE}/product/query?pid={urllib.parse.quote(str(pid))}"
        try:
            data = self._request("GET", url, headers=self._headers())
        except CJError:
            return None  # produit retiré ou momentanément indisponible
        if not data:
            return None
        now = datetime.now(timezone.utc).isoformat()
        return self._map(data, now)

    @staticmethod
    def _map(item: dict, observed_at: str) -> CJProduct:
        """Normalise un item brut CJ en :class:`CJProduct`.

        Gère indifféremment les payloads ``product/list`` (champs dossier absents)
        et ``product/query`` (dossier complet) : tout champ riche manquant reste
        à ``None``.
        """
        def _to_float(v):
            try:
                return float(str(v).split("--")[0].split("-")[0].strip())
            except (ValueError, AttributeError):
                return None

        def _to_int(v):
            try:
                return int(v)
            except (ValueError, TypeError):
                return None

        return CJProduct(
            pid=str(item.get("pid") or item.get("productId") or ""),
            name=item.get("productNameEn") or item.get("productName"),
            price=_to_float(item.get("sellPrice")),
            category=item.get("categoryName"),
            image=item.get("productImage"),
            listed_num=_to_int(item.get("listedNum")),
            create_time=item.get("createTime"),
            observed_at=observed_at,
            # --- Dossier riche (présent seulement via product/query) -----
            suggest_price=_to_float(item.get("suggestSellPrice")),
            description=CJClient._clean_text(item.get("description")),
            video=item.get("productVideo") or None,
            images=CJClient._images_json(item),
            variants=CJClient._variants_json(item.get("variants")),
            material=CJClient._first_of(item.get("materialNameEnSet")
                                        or item.get("materialNameEn")),
            weight=_to_float(item.get("productWeight")),
            supplier=item.get("supplierName") or None,
        )

    # -- Helpers d'extraction du dossier riche ------------------------------
    @staticmethod
    def _clean_text(html: str | None, limit: int = 600) -> str | None:
        """Dégrossit la description HTML CJ en texte court lisible."""
        if not html:
            return None
        text = re.sub(r"<[^>]+>", " ", str(html))          # retire les balises
        text = re.sub(r"&[a-z#0-9]+;", " ", text)          # entités HTML
        text = re.sub(r"\s+", " ", text).strip()
        return text[:limit] or None

    @staticmethod
    def _first_of(value) -> str | None:
        """Premier élément d'une liste CJ (ou la valeur scalaire), nettoyé."""
        if isinstance(value, list):
            return str(value[0]) if value else None
        return str(value) if value else None

    @staticmethod
    def _images_json(item: dict) -> str | None:
        """Sérialise la galerie d'images (productImageSet) en JSON liste d'URLs."""
        imgs = item.get("productImageSet")
        if isinstance(imgs, str):
            try:
                imgs = json.loads(imgs)
            except (json.JSONDecodeError, ValueError):
                imgs = [imgs]
        if not isinstance(imgs, list) or not imgs:
            return None
        urls = [str(u) for u in imgs if u][:8]             # plafonné (poids)
        return json.dumps(urls) if urls else None

    @staticmethod
    def _variants_json(variants) -> str | None:
        """Distille les variantes en JSON compact : nb, options, plage de prix.

        On ne stocke PAS le brut (volumineux, redondant) : seulement ce qui aide
        à décider — combien de déclinaisons, lesquelles, et l'amplitude de prix.
        """
        if not isinstance(variants, list) or not variants:
            return None
        options = [v.get("variantKey") for v in variants if v.get("variantKey")]
        prices = []
        for v in variants:
            try:
                prices.append(float(v.get("variantSellPrice")))
            except (TypeError, ValueError):
                continue
        distilled = {
            "count": len(variants),
            "options": [str(o) for o in options][:12],
            "price_min": round(min(prices), 2) if prices else None,
            "price_max": round(max(prices), 2) if prices else None,
        }
        return json.dumps(distilled, ensure_ascii=False)

    def iter_catalog(
        self,
        max_pages: int,
        page_size: int = 50,
        category_keyword: str | None = None,
        start_page: int = 1,
    ):
        """Itère sur le catalogue, page par page, avec délai poli entre les pages."""
        end_page = start_page + max_pages  # exclusif
        for page in range(start_page, end_page):
            products, total = self.fetch_page(page, page_size, category_keyword)
            if not products:
                break
            yield page, products, total
            if page < end_page - 1:
                time.sleep(self._page_delay)


# urllib.parse importé tardivement pour rester groupé.
import urllib.parse  # noqa: E402
