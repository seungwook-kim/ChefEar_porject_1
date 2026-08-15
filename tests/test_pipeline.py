"""pipeline.py 테스트 — 문서 7.4/7.1.1 AC-07~09, AC-12/13."""
from fake_supabase import FakeSupabaseClient

from orchestration.pipeline import (
    NOT_AVAILABLE_MESSAGE,
    advance_step,
    get_precomputed_steps,
    manual_fallback,
)


def _seed_recipe_with_steps(client, n=3):
    recipe = client.table("recipes").seed({"dish_name": "된장찌개", "ingredients": "두부", "source": "api_standard"})
    for i in range(1, n + 1):
        client.table("recipe_steps").seed(
            {"recipe_id": recipe["id"], "step_number": i, "step_text": f"{i}단계", "source": "api_standard"}
        )
    return recipe


def test_ac12_existing_recipe_steps_available():
    client = FakeSupabaseClient()
    recipe = _seed_recipe_with_steps(client)

    result = get_precomputed_steps(recipe["id"], client=client)

    assert result["available"] is True
    assert [s["step_number"] for s in result["steps"]] == [1, 2, 3]


def test_ac13_missing_recipe_id_is_honest_about_it():
    client = FakeSupabaseClient()
    result = get_precomputed_steps("no-such-id", client=client)
    assert result == {"available": False, "ingredients_only": False, "message": NOT_AVAILABLE_MESSAGE}


def test_ac07_previous_step_moves_back_one():
    client = FakeSupabaseClient()
    recipe = _seed_recipe_with_steps(client)
    session = {"current_recipe_id": recipe["id"], "step_number": 3}

    result = advance_step(session, "이전", client=client)

    assert result["step_number"] == 2
    assert session["step_number"] == 2
    assert result["step"]["text"] == "2단계"


def test_ac08_previous_at_step_one_stays_and_flags_no_previous():
    client = FakeSupabaseClient()
    recipe = _seed_recipe_with_steps(client)
    session = {"current_recipe_id": recipe["id"], "step_number": 1}

    result = advance_step(session, "이전", client=client)

    assert result["step_number"] == 1
    assert result["no_previous"] is True


def test_next_moves_forward_and_again_stays():
    client = FakeSupabaseClient()
    recipe = _seed_recipe_with_steps(client)
    session = {"current_recipe_id": recipe["id"], "step_number": 1}

    advance_step(session, "다음", client=client)
    assert session["step_number"] == 2

    advance_step(session, "다시", client=client)
    assert session["step_number"] == 2


def test_ac09_manual_button_bypasses_intent_classification():
    """FR-16/AC-09: 화면의 [다시] 버튼은 classify_intent 없이 바로 현재 단계를 다시 안내."""
    client = FakeSupabaseClient()
    recipe = _seed_recipe_with_steps(client)
    session = {"current_recipe_id": recipe["id"], "step_number": 2}

    result = manual_fallback(session, "다시", client=client)

    assert result["step_number"] == 2
    assert result["step"]["text"] == "2단계"
