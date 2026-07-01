"""Validation de la dérivation de mot-clé (``enrich.keyword_from_name``).

Cas connus issus du correctif : radicaux dupliqués consécutifs, fragments d'une
seule lettre, mots vides. Plus quelques titres réels tirés de cj.db.
"""

from __future__ import annotations

from enrich import keyword_from_name, _legacy_keyword_from_name, keyword_candidates


# --- Cas buggés explicitement visés par le correctif -----------------------

def test_consecutive_duplicate_collapsed():
    # « ... Beach Pants Casual Pants » → l'ancienne logique sortait « pants pants ».
    assert keyword_from_name("Omen's Cotton And Linen Wide-leg Beach Pants Casual Pants") == "beach pants"


def test_perfume_duplicate_collapsed():
    kw = keyword_from_name(
        "Women's 6 Piece Set Travel Perfume 35ml 1.18oz Perfume For Her PDQ"
    )
    assert "perfume perfume" not in kw
    assert kw.split() and kw.split()[-1] == "perfume"


def test_plural_singular_duplicate_collapsed():
    # « Visors Visor » : radicaux identiques au pluriel près -> un seul.
    assert keyword_from_name("Sport Sun Visors Visor") == "sun visors"


def test_single_letter_fragment_dropped():
    # « ... Floor Mount S Witch » : le « s » parasite disparaît.
    kw = keyword_from_name("Headlight Dimmer Floor Mount S Witch")
    assert " s " not in f" {kw} "
    assert kw.split()[0] != "s"
    assert kw.endswith("witch")


def test_anklet_duplicate_collapsed():
    assert keyword_from_name("Vintage Alloy Owl Pendant Anklet Anklet") == "pendant anklet"


# --- Propriétés générales --------------------------------------------------

def test_no_consecutive_duplicate_tokens_ever():
    for name in [
        "Bed Bed", "Daybed Daybed", "Dress Dress", "Hallway Hallway",
        "Soft Cotton T-shirt T-shirt",
    ]:
        toks = keyword_from_name(name).split()
        assert all(toks[i] != toks[i + 1] for i in range(len(toks) - 1)), name


def test_no_single_letter_tokens():
    for name in ["S Witch", "A B Phone Charger", "10p C Cable"]:
        assert all(len(t) > 1 for t in keyword_from_name(name).split()), name


def test_legit_three_letter_words_preserved():
    # Les vrais mots de 3 lettres ne doivent PAS être supprimés.
    assert keyword_from_name("Mid-length Faux Fur Coat") == "fur coat"
    assert keyword_from_name("Saint Bernard Dog Doll For Children") == "dog doll"
    assert keyword_from_name("Colorful Feather Cat Wand") == "cat wand"
    assert keyword_from_name("Water Gun") == "water gun"


def test_empty_and_none():
    assert keyword_from_name("") == ""
    assert keyword_from_name(None) == ""  # type: ignore[arg-type]


def test_signature_n_words():
    assert len(keyword_from_name("Mens Breathable Beach Sandals", n_words=1).split()) == 1
    assert len(keyword_from_name("Mens Breathable Beach Sandals", n_words=3).split()) <= 3


# --- Candidats de jointure (repli historique) ------------------------------

def test_candidates_include_clean_first():
    cands = keyword_candidates("Omen's Wide-leg Beach Pants Casual Pants")
    assert cands[0] == "beach pants"
    # Le repli legacy reproduit l'ancien bug -> doit être présent comme clé de secours.
    assert "pants pants" in cands


def test_candidates_dedup_when_identical():
    # Titre déjà propre : une seule candidate (pas de doublon clean==legacy).
    cands = keyword_candidates("Water Gun")
    assert cands == ["water gun"]


def test_legacy_keeps_bug():
    # Garde-fou : le repli legacy DOIT reproduire l'ancienne sortie (sinon il ne
    # ré-aligne pas les snapshots historiques).
    assert _legacy_keyword_from_name(
        "Omen's Wide-leg Beach Pants Casual Pants") == "pants pants"
