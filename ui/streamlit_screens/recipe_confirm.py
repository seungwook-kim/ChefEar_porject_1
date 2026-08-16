"""② 레시피 확인 화면 - FR-05: 조회수 1위 표준 레시피 자동 채택, 되묻지 않음."""
import streamlit as st

from mock_data import fresh_recipe
from nav import goto
from theme import render_badge, render_chat, render_chips, render_section_title


def render() -> None:
    recipe_key = st.session_state.get("pending_recipe_key") or "doenjang"
    recipe = fresh_recipe(recipe_key)

    render_badge("조회수 1위 표준 레시피 자동 선택 · 되묻지 않음 (FR-05)")

    chat = list(st.session_state.chat_log) + [("ai", f'{recipe["intro"]} 이걸로 시작할까요?')]
    render_chat(chat)

    render_section_title("재료 미리보기")
    render_chips(recipe["ingredients"])

    c1, c2 = st.columns(2)
    with c1:
        if st.button("응, 시작할게요", type="primary", use_container_width=True):
            st.session_state.recipe = recipe
            st.session_state.step_number = 1
            st.session_state.substituted_ingredient = None
            st.session_state.chat_log = []
            goto("cooking_step")
    with c2:
        if st.button("다른 레시피 찾을래요", use_container_width=True):
            goto("start")
