"""7.1 신규 — cancel_substitution(). EC-21, AC-11(재료대체 롤백).

## "세션"이 뭔지 먼저 이해하기

이 프로젝트는 요리 한 번 진행하는 동안 "지금 어떤 레시피를 보고 있는지",
"몇 단계째인지", "직전엔 어떤 레시피였는지" 같은 정보를 계속 기억해야 한다.
이런 "한 사용자가 서비스를 쓰는 동안 유지되는 임시 정보"를 세션(session)이라고
부른다. 작업2에서 "이 세션 정보를 어디에 저장할까?"를 정했는데, DB에 별도
테이블을 만드는 대신 Streamlit의 st.session_state(브라우저 탭 하나가 떠 있는
동안 서버 메모리에 유지되는 딕셔너리)를 그대로 쓰기로 했다. 그래서 이 파일의
함수들은 session이라는 dict를 인자로 받아서 그 안의 값을 읽고 쓴다 — 이
session은 실제 앱에서는 st.session_state가 되고, 테스트에서는 그냥 평범한
파이썬 dict를 넣어서 검증한다.

## 이 파일이 하는 일

사용자가 "바지락 넣어도 돼?"라고 물어서 레시피가 "된장찌개"에서
"바지락된장찌개"로 바뀌었다고 하자. 그런데 바로 다음에 "아니다, 원래대로
해줘"라고 말하면 어떻게 될까? 이 "직전 상태로 되돌리기" 기능이
cancel_substitution()이다. 이걸 가능하게 하려면 애초에 레시피가 바뀔 때
"바뀌기 직전엔 뭐였는지"를 어딘가에 기록해둬야 하는데, 그 기록을 남기는
쪽이 apply_substitution()이다.
"""
from __future__ import annotations

from orchestration.db import get_client


def apply_substitution(session: dict, match: dict) -> None:
    """재료 대체 검색이 성공했을 때, 세션에 "직전 레시피"를 기록하고 현재 레시피를 바꾼다.

    recipe_search.py의 search_variant_recipe()/search_by_ingredient_content()는
    DB에서 찾기만 할 뿐 세션을 직접 건드리지 않는다(검색 함수는 "조회"에만
    집중하게 하고, "세션 상태를 바꾸는 일"은 이 함수가 따로 맡는 것 —
    책임을 분리해두면 각각을 따로 테스트하기 쉽다). 그래서 파이프라인 쪽
    코드가 검색 결과를 받은 뒤 이 함수를 호출해서 실제로 반영해야 한다.

    match["match_type"]이 "none"(못 찾음)이면 아무것도 하지 않는다 — 없는
    레시피로 바꿔치기할 수는 없으니까.
    """
    if match.get("match_type") not in ("exact_name", "ingredient_content"):
        return
    # 지금 보고 있던 레시피를 "직전 레시피"로 기록해두고,
    session["previous_recipe_id"] = session.get("current_recipe_id")
    # 새로 찾은 레시피로 "현재 레시피"를 바꾼다.
    session["current_recipe_id"] = match["result_recipe_id"]
    # 참고: step_number(몇 단계째인지)는 여기서 건드리지 않는다. 문서 7.1.1의
    # 마지막 항목("재료대체 후에도 변경된 recipe_id와 현재 step_number를
    # 기준으로 동일 규칙 적용")대로, 레시피만 바뀌고 진행 단계는 그대로 유지된다.


def cancel_substitution(session: dict, client=None) -> dict:
    """"취소해줘"/"원래대로" 요청을 처리한다. EC-21/AC-11.

    previous_recipe_id가 세션에 기록돼 있으면(=방금 전에 apply_substitution()이
    호출된 적이 있으면) 그걸로 되돌리고, 없으면(대체한 적이 아예 없으면)
    되돌릴 게 없다는 뜻이므로 아무것도 안 하고 그 사실을 알려준다.

    한 단계만 되돌릴 수 있다(previous_recipe_id 하나만 기억함, 여러 번 취소를
    거슬러 올라가는 "실행 취소 스택" 같은 건 아니다) — 문서에도 딱 "직전
    상태로 롤백"이라고만 돼 있어서 그 범위만 구현했다.
    """
    previous_recipe_id = session.get("previous_recipe_id")
    if not previous_recipe_id:
        return {"rolled_back": False, "recipe_id": session.get("current_recipe_id")}

    session["current_recipe_id"] = previous_recipe_id
    session["previous_recipe_id"] = None  # 한 번 취소하면 그걸로 끝 -> 다시 취소해도 더 되돌아갈 곳 없음

    # 사용자에게 "된장찌개로 돌아갔어요"처럼 이름을 말해주려고 dish_name을 조회한다.
    client = client or get_client()
    row = client.table("recipes").select("dish_name").eq("id", previous_recipe_id).single().execute().data
    return {"rolled_back": True, "recipe_id": previous_recipe_id, "dish_name": row["dish_name"] if row else None}
