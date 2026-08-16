"""③ 조리 진행 화면 (메인) - PRD 3.3 화면 구성, FR-02/FR-03/FR-04/FR-16을 실제로 동작시킨다.

전달받은 목업 이미지(된장찌개 3/5단계)를 기준으로 하되, [이전]/[다시]/[다음] 버튼은
docs/ChefEar_PRD_SDD_v0.8.md 7.1.1 상태 전이 규칙을 그대로 구현했다(정적 HTML 프로토타입과의
차이점 - 여기서는 st.session_state.step_number가 실제로 바뀐다).
"""
import streamlit as st

from mock_data import fresh_recipe
from nav import goto
from theme import render_badge, render_chat, render_chips, render_mic_bar, render_section_title, render_step_card


def _ensure_recipe() -> dict:
    if st.session_state.get("recipe") is None:
        st.session_state.recipe = fresh_recipe("doenjang")
        st.session_state.step_number = 1
    return st.session_state.recipe


def render() -> None:
    recipe = _ensure_recipe()
    steps = recipe["steps"]
    total = len(steps)
    step_number = min(st.session_state.step_number, total)
    current = steps[step_number - 1]

    render_badge(f'{recipe["dish_name"]} · {step_number} / {total} 단계')

    render_step_card(total, step_number, current["text"], current["minutes"])

    render_section_title("오늘의 재료")
    render_chips(recipe["ingredients"], substituted_name=st.session_state.get("substituted_ingredient"))

    if st.session_state.chat_log:
        render_chat(st.session_state.chat_log)

    render_mic_bar("듣는 중", '"다음" · "다시" · "재료 바꾸기"', listening=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("이전", use_container_width=True):
            if step_number == 1:
                st.info("1단계예요, 이전 단계가 없어요 (AC-08).")
            else:
                st.session_state.step_number = step_number - 1
                st.session_state.chat_log = []
                goto("cooking_step")
    with c2:
        if st.button("다시", use_container_width=True):
            st.session_state.chat_log = []
            goto("cooking_step")
    with c3:
        if st.button("다음", use_container_width=True):
            if step_number < total:
                st.session_state.step_number = step_number + 1
                st.session_state.chat_log = []
                goto("cooking_step")
            else:
                goto("complete")

    st.divider()
    st.caption("아래 버튼들은 재료 대체·예외 상황 화면으로 이어지는 데모용 예시 발화입니다.")

    if recipe["id"] == "doenjang" and st.session_state.get("substituted_ingredient") != "감자":
        if st.button("🎙️ “감자 대신 양파 넣어도 돼?” (같은 레시피 안에서 1:1 대체)", use_container_width=True):
            for ing in recipe["ingredients"]:
                if ing["name"] == "감자":
                    ing["name"], ing["qty"], ing["emoji"] = "양파", "1/2개", "🧅"
                    break
            st.session_state.substituted_ingredient = "양파"
            st.session_state.chat_log = [("user", "감자 대신 양파 넣어도 돼?"), ("ai", "네, 양파로 대체했어요.")]
            goto("cooking_step")

    if st.button("🎙️ “바지락 넣어도 돼?” (다른 레시피로 교체 제안 예시)", use_container_width=True):
        goto("substitution_confirm")

    if st.button("🎙️ “문어랑 성게 같이 넣어도 돼?” (매칭 실패 예시)", use_container_width=True):
        goto("no_match")

    if st.button("음성 인식 실패 Fallback 예시 보기", use_container_width=True):
        goto("unclassified")
