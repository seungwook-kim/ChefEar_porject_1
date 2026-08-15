"""substitution.py 테스트 — 문서 EC-21/AC-11(재료대체 롤백)."""
from fake_supabase import FakeSupabaseClient

from orchestration.substitution import apply_substitution, cancel_substitution


def test_ac11_cancel_restores_previous_recipe():
    client = FakeSupabaseClient()
    original = client.table("recipes").seed({"dish_name": "된장찌개", "ingredients": "두부", "source": "api_standard"})
    variant = client.table("recipes").seed({"dish_name": "바지락된장찌개", "ingredients": "바지락", "source": "api_standard"})

    session = {"current_recipe_id": original["id"]}
    apply_substitution(session, {"match_type": "exact_name", "result_recipe_id": variant["id"]})
    assert session["current_recipe_id"] == variant["id"]
    assert session["previous_recipe_id"] == original["id"]

    result = cancel_substitution(session, client=client)

    assert result["rolled_back"] is True
    assert result["recipe_id"] == original["id"]
    assert session["current_recipe_id"] == original["id"]


def test_cancel_without_prior_substitution_is_noop():
    client = FakeSupabaseClient()
    session = {"current_recipe_id": "some-id"}

    result = cancel_substitution(session, client=client)

    assert result == {"rolled_back": False, "recipe_id": "some-id"}


def test_apply_substitution_ignores_failed_match():
    session = {"current_recipe_id": "original-id"}
    apply_substitution(session, {"match_type": "none", "message": "없음"})
    assert session["current_recipe_id"] == "original-id"
    assert "previous_recipe_id" not in session
