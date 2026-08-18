"""② 레시피 확인 화면 - FR-05: 조회수 1위 표준 레시피 자동 채택, 되묻지 않음."""
import streamlit as st

from mock_data import fresh_recipe
from nav import goto
from theme import render_back_link, render_badge, render_chat, render_chips, render_section_title


def render() -> None:
    if render_back_link("처음으로"):
        goto("start")

    recipe_key = st.session_state.get("pending_recipe_key") or "doenjang"
    recipe = fresh_recipe(recipe_key)

    render_badge("조회수 1위 표준 레시피 자동 선택 · 되묻지 않음 (FR-05)")

    chat = list(st.session_state.chat_log) + [("ai", f'{recipe["intro"]} 이걸로 시작할까요?')]
    render_chat(chat)

    render_section_title("재료 미리보기")
    render_chips(recipe.get("preview_ingredients", recipe["ingredients"]), show_qty=False)

    # 아래 rc_footer_buttons가 하단에 고정(position:fixed)되면서 흐름에서 빠지는 만큼,
    # 마지막 콘텐츠(재료 칩)가 그 밑에 가려지지 않도록 같은 높이의 여백을 미리 남겨둔다.
    st.markdown('<div style="height:130px;"></div>', unsafe_allow_html=True)

    with st.container(key="rc_footer_buttons"):
        if st.button("응, 시작할게요", type="primary", use_container_width=True):
            st.session_state.recipe = recipe
            st.session_state.step_number = 1
            st.session_state.substituted_ingredient = None
            st.session_state.chat_log = []
            goto("cooking_step")

        if st.button("다른 레시피 찾을래요", use_container_width=True):
            goto("start")
