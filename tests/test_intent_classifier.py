"""classify_intent() 테스트 — 문서 7.2 AC-01/AC-02/AC-10, EC-01~05."""
from orchestration.intent_classifier import THRESHOLD, _pick_intent, classify_intent


def test_ac01_next_utterance_classified_as_progress():
    result = classify_intent("다음")
    assert result["intent"] == "진행"
    assert result["similarity_score"] >= THRESHOLD


def test_ac02_ambiguous_utterance_returns_unclassified_without_crash():
    result = classify_intent("어… 그거…")
    assert result["intent"] == "미분류"
    assert "fallback_message" in result


def test_ec04_empty_utterance_skips_classification():
    result = classify_intent("")
    assert result == {
        "intent": "미분류",
        "similarity_score": 0.0,
        "fallback_message": "다시 말씀해주세요.",
    }


def test_ec05_substitution_intent_without_context_asks_which_recipe():
    result = classify_intent("바지락 넣어도 돼?", context_recipe_id=None)
    assert result["intent"] == "미분류"
    assert result["fallback_message"] == "어떤 레시피에 대해 말씀하시는 건가요?"


def test_ec05_substitution_intent_with_context_is_classified():
    result = classify_intent("바지락 넣어도 돼?", context_recipe_id="recipe-123")
    assert result["intent"] == "재료대체"


def test_ec03_ambiguous_resume_phrase_prioritized_as_progress():
    result = classify_intent("다시 진행해")
    assert result["intent"] == "진행"


# --- 아래는 _pick_intent()에 합성 점수를 직접 넣어 threshold/margin 로직만 단위테스트 ---


def test_ac10_close_top1_top2_within_margin_returns_unclassified():
    ranked = [
        ("진행", (0.60, "다음")),
        ("재청취", (0.58, "다시")),  # 차이 0.02 < MARGIN(0.05)
    ]
    result = _pick_intent(ranked, context_recipe_id=None)
    assert result["intent"] == "미분류"


def test_pick_intent_below_threshold_returns_unclassified():
    ranked = [("진행", (THRESHOLD - 0.1, "다음"))]
    result = _pick_intent(ranked, context_recipe_id=None)
    assert result["intent"] == "미분류"


def test_pick_intent_clear_winner_above_margin_is_classified():
    ranked = [
        ("진행", (0.90, "다음")),
        ("재청취", (0.50, "다시")),  # 차이 0.4 >= MARGIN
    ]
    result = _pick_intent(ranked, context_recipe_id=None)
    assert result["intent"] == "진행"
    assert result["matched_example"] == "다음"
