"""Streamlit UI 프로토타입용 mock 데이터.

STT/TTS/orchestration.pipeline 통합이 아직 끝나지 않아(src/ui/README.md 참고)
진짜 DB·모델을 연결할 수 없다. 그래서 이 화면 프로토타입은 orchestration/mock_client.py의
시드(된장찌개·바지락된장찌개·해물된장찌개)와 같은 요리를 재사용하되, 화면 시연에 필요한
분량·소요시간 등 표시용 정보를 더 채워넣었다. 실제 DB 스키마(recipes/recipe_steps)와는
별개이며, 나중에 orchestration.pipeline이 완성되면 이 파일 대신 실제 함수 호출로 교체하면 된다.
"""
from __future__ import annotations

import copy

RECIPES: dict[str, dict] = {
    "doenjang": {
        "id": "doenjang",
        "dish_name": "된장찌개",
        "view_count": 1403370,
        "intro": "표준 레시피 기준으로는 멸치육수에 감자, 두부가 들어가는 된장찌개예요.",
        "ingredients": [
            {"name": "감자", "qty": "1개", "emoji": "🥔"},
            {"name": "두부", "qty": "1/2모", "emoji": "🧈"},
            {"name": "애호박", "qty": "1/3개", "emoji": "🥒"},
            {"name": "된장", "qty": "1큰술", "emoji": "🫘"},
            {"name": "양파", "qty": "1/2개", "emoji": "🧅"},
        ],
        # recipe_confirm 화면의 "재료 미리보기"는 HTML 목업(02_recipe_confirm.html)처럼
        # 수량 없이 7개를 보여준다. cooking_step 화면의 "오늘의 재료"는 수량이 있는
        # 위 ingredients를 그대로 쓰므로 건드리지 않는다.
        "preview_ingredients": [
            {"name": "감자", "emoji": "🥔"},
            {"name": "두부", "emoji": "🧈"},
            {"name": "애호박", "emoji": "🥒"},
            {"name": "양파", "emoji": "🧅"},
            {"name": "대파", "emoji": "🌱"},
            {"name": "멸치육수", "emoji": "🐟"},
            {"name": "된장", "emoji": "🫘"},
        ],
        "steps": [
            {"text": "멸치와 다시마로 육수를 끓입니다.", "minutes": 5},
            {"text": "두부를 한입 크기로 썰어 준비합니다.", "minutes": 2},
            {"text": "감자를 한입 크기로 썰어 냄비에 넣어주세요.", "minutes": 2},
            {"text": "애호박을 썰어 넣고 된장을 풀어줍니다.", "minutes": 3},
            {"text": "한소끔 끓이면 완성입니다.", "minutes": 4},
        ],
    },
    "bajirak": {
        "id": "bajirak",
        "dish_name": "바지락된장찌개",
        "view_count": 52000,
        "intro": "바지락된장찌개로 등록된 레시피가 있어요.",
        "ingredients": [
            {"name": "바지락", "qty": "1봉지", "emoji": "🦪"},
            {"name": "두부", "qty": "1/2모", "emoji": "🧈"},
            {"name": "애호박", "qty": "1/3개", "emoji": "🥒"},
            {"name": "양파", "qty": "1/2개", "emoji": "🧅"},
            {"name": "된장", "qty": "1큰술", "emoji": "🫘"},
        ],
        "steps": [
            {"text": "바지락 해감한 것을 준비합니다.", "minutes": 3},
            {"text": "육수에 바지락을 먼저 넣고 끓입니다.", "minutes": 4},
            {"text": "된장을 풀고 두부를 넣어 마무리합니다.", "minutes": 3},
        ],
    },
    "haemul": {
        "id": "haemul",
        "dish_name": "해물된장찌개",
        "view_count": 31000,
        "intro": "새우와 바지락을 모두 포함하는 레시피는 이름이 아니라 재료 내용 기준으로 찾았어요.",
        "ingredients": [
            {"name": "새우", "qty": "5마리", "emoji": "🦐"},
            {"name": "바지락", "qty": "1봉지", "emoji": "🦪"},
            {"name": "오징어", "qty": "1/2마리", "emoji": "🦑"},
            {"name": "두부", "qty": "1/2모", "emoji": "🧈"},
            {"name": "된장", "qty": "1큰술", "emoji": "🫘"},
        ],
        "steps": [
            {"text": "해물을 손질해 준비합니다.", "minutes": 5},
            {"text": "육수에 해물을 넣고 끓입니다.", "minutes": 5},
            {"text": "된장을 풀고 채소를 넣어 마무리합니다.", "minutes": 3},
        ],
    },
}

# 시나리오 D(6.5) - 표준 데이터 밖 요리, 신규 등록 데모 기본값
REGISTER_DEFAULTS = {
    "dish_name": "문어초무침",
    "ingredients": [
        {"name": "문어", "qty": "1마리", "emoji": "🐙"},
        {"name": "오이", "qty": "1/2개", "emoji": "🥒"},
        {"name": "양파", "qty": "1/4개", "emoji": "🧅"},
        {"name": "초고추장", "qty": "2큰술", "emoji": "🌶️"},
    ],
    "steps": [
        "문어를 끓는 물에 살짝 데쳐 한입 크기로 썹니다.",
        "오이와 양파를 얇게 채썹니다.",
        "초고추장·식초·설탕을 섞어 양념을 만듭니다.",
        "모든 재료를 양념에 버무려 완성합니다.",
    ],
}


def fresh_recipe(recipe_key: str) -> dict:
    """세션에 넣을 레시피 사본. 대체/등록 중 원본 RECIPES를 건드리지 않기 위해 deepcopy."""
    return copy.deepcopy(RECIPES[recipe_key])
