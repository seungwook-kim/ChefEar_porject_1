"""7.3/7.6 — 표준 레시피 선정, 재료 대체 검색(6.4).

이 파일의 세 함수는 전부 "DB에서 조건에 맞는 레시피를 찾는다"는 공통점이
있는데, 못 찾았을 때 절대로 답을 지어내지 않는다(1.5 원칙: 서비스 실행 중
LLM 생성 fallback 없음). 못 찾으면 그냥 "없다"고 정직하게 답한다 — 이게 이
프로젝트 재료 대체 기능의 핵심 설계다.
"""
from __future__ import annotations

from orchestration.db import get_client

NOT_FOUND_MESSAGE = "죄송해요, 이 조합의 레시피는 없어요."


def _max_view_count(rows: list[dict]) -> dict:
    """여러 후보 중 "표준"으로 뽑을 하나를 고른다. 6.1/EC-09/EC-19 규칙.

    key=lambda r: (view_count, created_at) 는 파이썬 max()에게 "먼저
    view_count(조회수)로 비교하고, 조회수가 같으면 created_at(등록일)으로
    비교해라"라고 알려주는 것이다. 튜플은 앞자리부터 비교되기 때문에
    (10, "2026-01-01") > (10, "2025-01-01")처럼 자연스럽게 2단계 정렬이 된다.
    조회수가 전부 0인 신규 등록 레시피끼리는 결국 created_at만으로 비교되므로
    EC-19("조회수 0이면 최신 등록일 우선")도 이 한 줄로 같이 처리된다.
    """
    return max(rows, key=lambda r: (r.get("view_count", 0), r.get("created_at", "")))


def select_standard_recipe(dish_name: str, owner_id: str | None = None, client=None) -> dict | None:
    """요리명 하나를 받아서, 이 사용자에게 보여줄 "그 요리의 대표 레시피" 하나를 고른다.

    같은 요리명이 여러 개 있을 수 있는 이유는 두 가지다.
      1) api_standard 레시피가 조회수 기준으로 이미 여러 후보 중 1등만 골라
         DB에 들어가 있으므로(작업1의 load_data.py) 보통 1개뿐이다.
      2) 사용자가 직접 등록/수정한 user_custom 버전이 추가로 있을 수 있다.
         심지어 서로 다른 사용자가 각자 자기 버전을 등록했을 수도 있다.

    owner_id(작업3, 쿠키 UUID)가 주어지면 "이 사용자 소유의" user_custom만
    후보로 본다 — 다른 사용자가 저장한 user_custom은 절대로 대신 보여주지
    않는다(그 사람의 개인 레시피를 남에게 노출하면 안 되므로). 내 것이 없으면
    api_standard로 폴백하고, 그마저 없으면(이색 요리를 남이 등록했는데 나는
    등록한 적 없는 경우) None을 반환한다.

    owner_id가 아직 없으면(예: UI가 아직 로그인 로직을 안 붙였거나, 이 함수를
    owner 구분 없이 그냥 써보는 테스트) 예전 방식대로 아무 user_custom이나
    우선한다 — 하위 호환을 위한 기본 동작이다.
    """
    client = client or get_client()
    # .eq("dish_name", ...) : dish_name이 정확히 일치하는 행만
    # .in_("source", [...]) : source가 두 값 중 하나인 행만 (SQL의 WHERE ... IN (...) 과 같음)
    res = (
        client.table("recipes")
        .select("*")
        .eq("dish_name", dish_name)
        .in_("source", ["api_standard", "user_custom"])
        .execute()
    )
    rows = res.data
    if not rows:
        return None  # 이 요리명 자체가 DB에 아예 없음 (6.5: 표준 데이터 밖 요리)

    if owner_id:
        my_custom_rows = [r for r in rows if r["source"] == "user_custom" and r.get("owner_id") == owner_id]
        api_rows = [r for r in rows if r["source"] == "api_standard"]
        candidates = my_custom_rows or api_rows  # 파이썬에서 "or"는 앞이 빈 리스트면 뒤를 씀
        if not candidates:
            return None  # 있는 건 남의 user_custom뿐 -> 노출하지 않음
    else:
        user_custom_rows = [r for r in rows if r["source"] == "user_custom"]
        candidates = user_custom_rows if user_custom_rows else rows  # EC-20/FR-08

    winner = _max_view_count(candidates)

    # representativeness(대표성)는 "1등이 후보들 전체 조회수 중 몇 %를 차지하는가"다.
    # `or 1`은 0으로 나누기(ZeroDivisionError)를 막기 위한 안전장치 —
    # 모든 후보의 view_count가 0이면 total_view도 0이 되니, 그 대신 1로 나눠서
    # representativeness를 그냥 0.0으로 만든다.
    total_view = sum(r.get("view_count", 0) for r in candidates) or 1
    return {
        "recipe_id": winner["id"],
        "dish_name": winner["dish_name"],
        "view_count": winner.get("view_count", 0),
        "total_candidates": len(candidates),
        "representativeness": winner.get("view_count", 0) / total_view,
    }


def _build_variant_name(base_dish_name: str, requested_ingredient: list[str]) -> str | None:
    """"바지락" + "된장찌개" -> "바지락된장찌개"처럼, 요청 재료를 붙인 요리명을 만든다.

    이 규칙은 6.4 문서에 나온 실제 테스트 사례("새우"+"바지락"+"된장찌개" ->
    "새우바지락된장찌개")를 그대로 따른 것이다. 재료가 하나도 없으면(빼기만
    요청한 EC-08 케이스) 만들 이름 자체가 없으니 None을 돌려주고, 호출하는 쪽은
    그러면 이름 매칭 단계를 건너뛰고 바로 재료 내용 검색으로 넘어간다.
    """
    if not requested_ingredient:
        return None
    return "".join(requested_ingredient) + base_dish_name


def search_variant_recipe(
    base_recipe_id: str,
    requested_ingredient: list[str],
    excluded_ingredient: str | None = None,
    client=None,
) -> dict:
    """재료 대체 검색의 1단계: 요리명이 정확히 일치하는 레시피가 있는지 먼저 본다(6.4①).

    예: "된장찌개"를 진행 중에 "바지락 넣어도 돼?"라고 물으면, 먼저
    "바지락된장찌개"라는 이름의 레시피가 DB에 그대로 있는지 찾아본다. 있으면
    그게 제일 확실한 매칭이라 바로 반환하고, 없으면(match_type=none이 아니라
    함수 자체가) 2단계인 search_by_ingredient_content()로 넘어간다 — 이름은
    달라도 재료 구성이 맞는 레시피가 있을 수 있어서다(6.4 문서의 "새우바지락된장찌개"
    이름으로는 0건이었지만 "해물된장찌개" 재료 내용으로는 매칭됐던 실측 사례 참고).
    """
    client = client or get_client()
    # .single() : 결과가 정확히 1건이라고 가정하고, res.data를 리스트가 아니라
    # 딕셔너리 하나로 바로 돌려준다(id로 조회하니 1건 아니면 이상한 상황).
    base = client.table("recipes").select("dish_name").eq("id", base_recipe_id).single().execute().data
    variant_name = _build_variant_name(base["dish_name"], requested_ingredient)

    if variant_name:
        res = client.table("recipes").select("*").eq("dish_name", variant_name).execute()
        if res.data:
            winner = _max_view_count(res.data)  # 같은 이름이 여러 건이면 EC-09 규칙대로 1등 선택
            return {
                "match_type": "exact_name",
                "result_recipe_id": winner["id"],
                "result_dish_name": winner["dish_name"],
                "source": winner["source"],
            }

    # 이름 매칭 실패 -> 2단계(재료 내용 검색)로 넘긴다. AND/제외 필터는
    # search_by_ingredient_content() 안에서 처리된다.
    return search_by_ingredient_content(base_recipe_id, requested_ingredient, excluded_ingredient, client=client)


def search_by_ingredient_content(
    base_recipe_id: str,
    requested_ingredient: list[str],
    excluded_ingredient: str | None = None,
    client=None,
) -> dict:
    """재료 대체 검색의 2단계: 이름이 아니라 "재료 목록에 이게 들어있는가"로 찾는다(6.4②).

    EC-06(부분 문자열 매칭)/EC-07(여러 재료 AND 조건)/EC-08(재료 제외) 전부
    여기서 처리한다.
    """
    client = client or get_client()
    query = client.table("recipes").select("*").eq("source", "api_standard")

    # .ilike(컬럼, "%문자열%") 은 SQL의 LIKE '%문자열%' 와 같다 — 대소문자 구분
    # 없이 부분 문자열이 포함돼 있으면 매칭된다. 그래서 사용자가 "바지락"이라고만
    # 말해도 재료란에 "바지락조개"라고 적힌 레시피가 걸린다(EC-06).
    #
    # requested_ingredient가 ["새우", "바지락"] 처럼 여러 개면 .ilike()를 그만큼
    # 여러 번 체이닝(연쇄 호출)한다. supabase-py는 필터를 여러 개 걸면 전부
    # AND로 합쳐지므로(SQL의 WHERE a AND b AND c와 동일), 결과적으로 "새우도
    # 있고 바지락도 있는" 레시피만 남는다(EC-07의 AND 조건).
    for ing in requested_ingredient:
        query = query.ilike("ingredients", f"%{ing}%")

    if excluded_ingredient:
        # .not_.ilike(...) 는 위와 반대로 "이 문자열이 없는" 행만 남긴다(EC-08).
        # 예: "애호박 빼고 새우 넣어도 돼?" -> 새우는 있고 애호박은 없는 레시피만.
        query = query.not_.ilike("ingredients", f"%{excluded_ingredient}%")

    res = query.execute()
    if res.data:
        winner = _max_view_count(res.data)  # 여러 건 매칭되면 EC-09 규칙대로 1등 선택
        return {
            "match_type": "ingredient_content",
            "result_recipe_id": winner["id"],
            "result_dish_name": winner["dish_name"],
            "source": winner["source"],
        }

    # 이름 매칭도, 재료 내용 매칭도 다 실패 -> AC-05. LLM으로 그럴싸한 답을
    # 지어내지 않고 정직하게 "없다"고만 답한다(1.5 원칙).
    return {"match_type": "none", "message": NOT_FOUND_MESSAGE}
