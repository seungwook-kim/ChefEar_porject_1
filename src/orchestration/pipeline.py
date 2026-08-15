"""7.1.1/7.4 — 조리순서 조회 및 진행 단계 상태 전이.

이 파일은 "레시피 하나를 골랐다"는 전제 아래, 그 레시피를 실제로 1단계씩
안내하는 흐름을 담당한다. 세션 상태(지금 몇 단계인지 등)는 호출하는 쪽이
넘겨주는 dict-like 객체(실제 앱에서는 st.session_state)에 저장한다 —
substitution.py 맨 위 설명에 있는 "세션이 뭔지" 부분과 같은 개념이다.
"""
from __future__ import annotations

from orchestration.db import get_client

NOT_AVAILABLE_MESSAGE = "죄송해요, 이 레시피는 아직 등록되어 있지 않아요."


def get_precomputed_steps(recipe_id: str, client=None) -> dict:
    """레시피 하나의 조리순서 "전체 목록"을 한 번에 가져온다(7.4). AC-12/AC-13.

    "precomputed"(미리 계산된)라는 이름이 붙은 이유: 이 프로젝트는 조리순서를
    그때그때 AI가 만들어내지 않고, 작업1에서 미리 DB에 다 넣어둔 실데이터를
    그냥 읽기만 한다(1.5 원칙 — LLM 실시간 생성 금지). 그래서 함수가 하는 일은
    사실 단순한 SELECT 하나뿐이다.
    """
    client = client or get_client()
    res = (
        client.table("recipe_steps")
        .select("*")
        .eq("recipe_id", recipe_id)
        .order("step_number")  # 1단계, 2단계, 3단계 순서로 정렬해서 받는다
        .execute()
    )
    if not res.data:
        # recipe_steps에 이 recipe_id로 된 행이 하나도 없음 = 등록 안 된 레시피.
        # AC-13: 없으면 그냥 정직하게 "없다"고 말한다(1.5 원칙, 지어내지 않음).
        return {"available": False, "ingredients_only": False, "message": NOT_AVAILABLE_MESSAGE}

    return {
        "available": True,
        "steps": [{"step_number": r["step_number"], "text": r["step_text"]} for r in res.data],
        "source": res.data[0]["source"],  # 모든 단계가 같은 레시피 소속이라 source도 동일함
    }


def get_current_step(recipe_id: str, step_number: int, client=None) -> dict | None:
    """레시피의 "딱 한 단계"만 콕 집어서 가져온다. get_precomputed_steps()가
    "전체 목록"을 가져오는 것과 달리, 이건 "지금 몇 단계인지"가 이미 정해진
    상태에서 그 단계 텍스트만 필요할 때 쓴다(advance_step()이 이 함수를 부른다).
    """
    client = client or get_client()
    res = (
        client.table("recipe_steps")
        .select("*")
        .eq("recipe_id", recipe_id)
        .eq("step_number", step_number)
        .execute()
    )
    if not res.data:
        return None
    row = res.data[0]
    return {"step_number": row["step_number"], "text": row["step_text"], "source": row["source"]}


def advance_step(session: dict, direction: str, client=None) -> dict:
    """"다음"/"다시"/"이전" 발화 하나를 받아서 진행 단계를 옮긴다(7.1.1 상태 전이표).

    규칙은 딱 세 가지뿐이라 간단하다.
      다음 -> step_number를 1 늘림 (다음 단계로)
      다시 -> step_number 그대로 (같은 단계를 한 번 더 안내)
      이전 -> step_number를 1 줄임, 단 1단계에서 "이전"을 누르면 더 줄일 데가
              없으니 1단계를 유지하고 "이전 단계 없음"이라고 알려줌(AC-08)

    재료 대체로 레시피 자체가 바뀐 뒤에도(substitution.py의 apply_substitution()이
    session["current_recipe_id"]를 바꿔놓음) 이 함수는 그냥 session에 있는
    "현재" recipe_id/step_number를 기준으로 그대로 동작한다 — 그래서 재료를
    바꾼 뒤 "다음"이라고 말해도 자연스럽게 이어진다(문서 7.1.1 마지막 항목).
    """
    recipe_id = session["current_recipe_id"]
    step_number = session.get("step_number", 1)  # 아직 한 번도 안 정해졌으면 1단계부터
    no_previous = False

    if direction == "다음":
        step_number += 1
    elif direction == "다시":
        pass  # step_number를 안 바꾸는 것 자체가 "그대로 다시 안내"를 의미함
    elif direction == "이전":
        if step_number <= 1:
            no_previous = True  # AC-08: 1단계 유지 + 이전 단계 없음 안내
        else:
            step_number -= 1
    else:
        raise ValueError(f"알 수 없는 방향: {direction}")

    session["step_number"] = step_number  # 다음 호출을 위해 세션에 반영
    step = get_current_step(recipe_id, step_number, client=client)
    return {"step_number": step_number, "step": step, "no_previous": no_previous}


def manual_fallback(session: dict, button: str, client=None) -> dict:
    """화면의 [이전][다시][다음] 수동 버튼 처리(FR-16/AC-09).

    음성 인식이 실패했을 때(혹은 그냥 손으로 누르고 싶을 때)를 위한 대체
    경로다. classify_intent()의 임베딩 유사도 판정을 완전히 건너뛰고
    advance_step()을 바로 호출한다 — 버튼은 이미 사용자의 의도가 100% 명확하니
    "얼마나 비슷한 문장인가"를 판단할 필요 자체가 없기 때문이다.
    """
    if button not in ("이전", "다시", "다음"):
        raise ValueError(f"알 수 없는 버튼: {button}")
    return advance_step(session, button, client=client)
