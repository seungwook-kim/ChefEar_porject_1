"""entity_extract_llm.py 테스트 — generate_json()을 모킹해서 extract_dish_name_llm()의
파싱/방어 로직만 검증한다(Spec AC-01/AC-02, `docs/specs/llm_dish_name_extract.md`).
`generate_json()` 자체의 JSON 파싱 방어 로직은 `tests/test_llm_infer.py`가 따로 검증한다.
"""
from orchestration import entity_extract_llm


def test_extracts_dish_name(monkeypatch):
    monkeypatch.setattr(entity_extract_llm, "generate_json", lambda prompt: {"dish_name": "된장찌개"})

    assert entity_extract_llm.extract_dish_name_llm("된장찌개 어떻게 만들어?") == "된장찌개"


def test_no_dish_name_returns_none(monkeypatch):
    monkeypatch.setattr(entity_extract_llm, "generate_json", lambda prompt: {"dish_name": None})

    assert entity_extract_llm.extract_dish_name_llm("다음 단계로 넘어가줘") is None


def test_server_failure_returns_none(monkeypatch):
    monkeypatch.setattr(entity_extract_llm, "generate_json", lambda prompt: None)

    assert entity_extract_llm.extract_dish_name_llm("된장찌개 어떻게 만들어?") is None


def test_malformed_dish_name_type_returns_none(monkeypatch):
    monkeypatch.setattr(entity_extract_llm, "generate_json", lambda prompt: {"dish_name": 123})

    assert entity_extract_llm.extract_dish_name_llm("아무 발화") is None


def test_blank_dish_name_returns_none(monkeypatch):
    monkeypatch.setattr(entity_extract_llm, "generate_json", lambda prompt: {"dish_name": "   "})

    assert entity_extract_llm.extract_dish_name_llm("아무 발화") is None


def test_empty_utterance_short_circuits_without_calling_llm(monkeypatch):
    called = []
    monkeypatch.setattr(entity_extract_llm, "generate_json", lambda prompt: called.append(prompt))

    assert entity_extract_llm.extract_dish_name_llm("   ") is None
    assert called == []
