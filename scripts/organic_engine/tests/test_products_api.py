"""Validation de l'endpoint /api/products (tri Tandor global + filtres + pagination).

On appelle ``list_products()`` EN DIRECT (pas via HTTP) avec un cache JSON scratch
et une cj.db scratch — aucune écriture sur le cache/DB de prod (lecture seule). On
prouve : filtres appliqués AU-DELÀ des enrichis, page de 30, plafond 2000, page_count.
"""

from __future__ import annotations

import json
import sqlite3
import time

import pytest

from api import server


# --- Fixtures : cache enrichi + catalogue cj.db scratch --------------------

def _make_cj_db(path, n_buy: int, n_pass: int) -> None:
    """Crée une cj.db minimale avec n_buy produits BUY (TECH) + n_pass PASS (PETS).

    BUY : coût 18€, peu saturé, récent -> verdict BUY (cf. test_sellability).
    PASS: coût 2€  -> marge < CPA -> verdict PASS.
    Tables de demande créées mais VIDES (le catalogue n'a pas d'historique réel).
    """
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE cj_products(pid TEXT PRIMARY KEY, name TEXT, category TEXT,
                                 image TEXT, create_time TEXT);
        CREATE TABLE cj_snapshots(pid TEXT, observed_at TEXT, price REAL, listed_num INTEGER);
        CREATE TABLE cj_details(pid TEXT, suggest_price REAL);
        CREATE TABLE amazon_snapshots(keyword TEXT, observed_at TEXT,
                                      max_bought INTEGER, median_bought INTEGER);
        CREATE TABLE sales_snapshots(keyword TEXT, observed_at TEXT,
                                     max_sold INTEGER, median_sold INTEGER, listings INTEGER);
        """
    )
    # create_time récent (epoch ms ~ 20 jours).
    recent = str(int((time.time() - 20 * 86400) * 1000))
    rows = []
    snaps = []
    for i in range(n_buy):
        pid = f"BUY{i:07d}"
        rows.append((pid, f"Phone Charger Cable {i}", "Electronics", None, recent))
        snaps.append((pid, "2026-06-01T00:00:00", 18.0, 6))
    for i in range(n_pass):
        pid = f"PAS{i:07d}"
        rows.append((pid, f"Dog Chew Toy {i}", "Pet Supplies", None, recent))
        snaps.append((pid, "2026-06-01T00:00:00", 2.0, 5))
    conn.executemany("INSERT INTO cj_products VALUES(?,?,?,?,?)", rows)
    conn.executemany("INSERT INTO cj_snapshots VALUES(?,?,?,?)", snaps)
    conn.commit()
    conn.close()


def _make_cache(path, products: list[dict]) -> None:
    path.write_text(json.dumps({
        "meta": {"generated_at": "2026-06-29T00:00:00+00:00", "enriched": True},
        "products": products,
    }))


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """Branche server.CACHE/CJ_DB sur des fichiers scratch et neutralise le quota."""
    cache = tmp_path / "cache.json"
    db = tmp_path / "cj.db"
    monkeypatch.setattr(server, "CACHE", cache)
    monkeypatch.setattr(server, "CJ_DB", db)
    server._reset_catalogue_cache()              # repart à froid pour chaque test
    return {"cache": cache, "db": db}


# --- Tests -----------------------------------------------------------------

def test_filter_verdict_applies_beyond_enriched(wired):
    """verdict=BUY réduit le total et n'inclut AUCUN produit catalogue PASS."""
    _make_cache(wired["cache"], [])              # cache vide : tout vient du catalogue
    _make_cj_db(wired["db"], n_buy=50, n_pass=40)

    all_res = server.query_products()
    buy_res = server.query_products(verdict="BUY")

    assert all_res["total"] == 90
    assert buy_res["total"] == 50               # seuls les BUY du catalogue
    assert all(p["verdict"] == "BUY" for p in buy_res["products"])


def test_filter_cat_applies_beyond_enriched(wired):
    """cat=PETS ne renvoie que les produits catalogue mappés PETS."""
    _make_cache(wired["cache"], [])
    _make_cj_db(wired["db"], n_buy=50, n_pass=40)

    pets = server.query_products(cat="PETS", limit=100)
    assert pets["total"] == 40
    assert all(p["cat"] == "PETS" for p in pets["products"])


def test_pagination_30_per_page(wired):
    """Page par défaut = 30 ; page 2 (offset 30) enchaîne sans doublon."""
    _make_cache(wired["cache"], [])
    _make_cj_db(wired["db"], n_buy=50, n_pass=40)

    p1 = server.query_products()
    assert len(p1["products"]) == 30
    assert p1["meta"]["page_size"] == 30
    assert p1["meta"]["page"] == 1
    assert p1["has_more"] is True

    p2 = server.query_products(page=2)
    assert p2["meta"]["page"] == 2
    assert p2["meta"]["offset"] == 30
    ids1 = {p["id"] for p in p1["products"]}
    ids2 = {p["id"] for p in p2["products"]}
    assert ids1.isdisjoint(ids2)               # aucune répétition entre pages


def test_offset_and_page_equivalent(wired):
    """page=2 et offset=30 (limit 30) renvoient la même tranche."""
    _make_cache(wired["cache"], [])
    _make_cj_db(wired["db"], n_buy=50, n_pass=40)
    by_page = server.query_products(page=2)
    by_offset = server.query_products(offset=30)
    assert [p["id"] for p in by_page["products"]] == [p["id"] for p in by_offset["products"]]


def test_cap_2000(wired):
    """Plus de 2000 correspondants -> total plafonné à 2000, pagination bornée."""
    _make_cache(wired["cache"], [])
    _make_cj_db(wired["db"], n_buy=2100, n_pass=0)

    res = server.query_products(limit=100)
    assert res["total"] == server.PRODUCTS_CAP == 2000
    assert res["meta"]["page_count"] == 20      # 2000 / 100

    # La dernière page navigable s'arrête au plafond (pas de débordement).
    last = server.query_products(limit=100, offset=1950)
    assert len(last["products"]) == 50          # 1950..2000
    assert last["has_more"] is False
    assert last["next_offset"] is None


def test_page_count_meta(wired):
    """page_count = ceil(total / page_size)."""
    _make_cache(wired["cache"], [])
    _make_cj_db(wired["db"], n_buy=95, n_pass=0)
    res = server.query_products(limit=30)
    assert res["total"] == 95
    assert res["meta"]["page_count"] == 4       # ceil(95/30)
    assert res["meta"]["page_size"] == 30


def test_enriched_sorted_first_by_tandor(wired):
    """Un enrichi à fort organic se classe AVANT le catalogue (tri Tandor global)."""
    enriched = [{
        "id": "9999999", "name": "Hot Trend Gadget", "cat": "TECH",
        "verdict": "BUY", "sellability": 80, "organic": 95, "phase": "GROWTH",
    }]
    _make_cache(wired["cache"], enriched)
    _make_cj_db(wired["db"], n_buy=50, n_pass=0)

    res = server.query_products()
    assert res["products"][0]["id"] == "9999999"
    assert res["total"] == 51                   # 1 enrichi + 50 catalogue


def test_q_text_search(wired):
    """q filtre par sous-chaîne du nom sur tout l'univers."""
    _make_cache(wired["cache"], [])
    _make_cj_db(wired["db"], n_buy=50, n_pass=40)
    res = server.query_products(q="Dog Chew", limit=100)
    assert res["total"] == 40
    assert all("dog chew" in p["name"].lower() for p in res["products"])


def test_catalogue_products_carry_verdict_and_lossflags(wired):
    """Les fiches catalogue de la page portent verdict + lossFlags (hydratation)."""
    _make_cache(wired["cache"], [])
    _make_cj_db(wired["db"], n_buy=5, n_pass=0)
    res = server.query_products()
    p = res["products"][0]
    assert p["verdict"] in {"BUY", "WATCH", "PASS"}
    assert "lossFlags" in p and isinstance(p["lossFlags"], list)
    assert "trapVerdict" in p
    assert p["enriched"] is False


def test_degrades_without_db(wired):
    """cj.db absente -> on sert la seule partie enrichie, sans planter."""
    enriched = [{"id": "1", "name": "X", "cat": "HOME", "verdict": "BUY",
                 "sellability": 50, "organic": 10, "phase": "MATURE"}]
    _make_cache(wired["cache"], enriched)
    # NE PAS créer la db : wired["db"] n'existe pas.
    res = server.query_products()
    assert res["total"] == 1
    assert res["products"][0]["id"] == "1"


# --- Filtre par trapVerdict (le pivot anti-piège, dimension VIABLE/RISKY/TRAP) ---

def test_filter_trapverdict_applies_beyond_enriched(wired):
    """verdict=VIABLE (anti-piège) filtre sur trapVerdict pour TOUT le catalogue.

    BUY-ish (coût 18€) -> trapVerdict VIABLE ; PASS-ish (coût 2€) -> trapVerdict TRAP.
    """
    _make_cache(wired["cache"], [])
    _make_cj_db(wired["db"], n_buy=50, n_pass=40)

    viable = server.query_products(verdict="VIABLE", limit=100)
    trap = server.query_products(verdict="TRAP", limit=100)

    assert viable["total"] == 50
    assert all(p["trapVerdict"] == "VIABLE" for p in viable["products"])
    assert trap["total"] == 40
    assert all(p["trapVerdict"] == "TRAP" for p in trap["products"])
    # Réduction réelle vs l'univers complet (90).
    assert viable["total"] < 90


def test_filter_verdict_csv_multi_value(wired):
    """verdict=VIABLE,TRAP (CSV) -> match l'UNE des deux valeurs (union)."""
    _make_cache(wired["cache"], [])
    _make_cj_db(wired["db"], n_buy=50, n_pass=40)

    both = server.query_products(verdict="VIABLE,TRAP", limit=200)
    assert both["total"] == 90                  # 50 VIABLE + 40 TRAP

    # Une valeur absente du jeu (RISKY) n'ajoute rien.
    just_viable = server.query_products(verdict="VIABLE,RISKY", limit=200)
    assert just_viable["total"] == 50


def test_filter_verdict_case_insensitive(wired):
    """Les valeurs de verdict sont insensibles à la casse."""
    _make_cache(wired["cache"], [])
    _make_cj_db(wired["db"], n_buy=50, n_pass=40)
    lower = server.query_products(verdict="viable", limit=100)
    upper = server.query_products(verdict="VIABLE", limit=100)
    assert lower["total"] == upper["total"] == 50


def test_trapverdict_filter_targets_enriched_dimension(wired):
    """Sur la partie enrichie aussi, VIABLE/RISKY filtre sur le champ trapVerdict."""
    enriched = [{
        "id": "7777777", "name": "Risky Enriched", "cat": "TECH",
        "verdict": "BUY", "trapVerdict": "RISKY",
        "sellability": 70, "organic": 90, "phase": "GROWTH",
    }]
    _make_cache(wired["cache"], enriched)
    _make_cj_db(wired["db"], n_buy=20, n_pass=0)   # catalogue = VIABLE uniquement

    risky = server.query_products(verdict="RISKY", limit=100)
    assert risky["total"] == 1                  # seul l'enrichi est RISKY
    assert risky["products"][0]["id"] == "7777777"

    viable = server.query_products(verdict="VIABLE", limit=100)
    assert viable["total"] == 20                # tout le catalogue, pas l'enrichi
