"""ChefEar 화면 프로토타입 - Streamlit 진입점.

실행: streamlit run ui/app.py

src/app.py(진짜 배포 엔트리포인트)는 orchestration.pipeline·stt/infer.py·tts/infer.py가
갖춰져야 실제로 동작한다(아직 미완성, src/ui/README.md 참고). 이 파일은 그 세 조각을
기다리지 않고 화면 흐름과 상태 전이(FR-03 다음/다시/이전, FR-04 재료 대체, FR-06 신규 등록)를
mock_data.py의 가짜 데이터로 먼저 보여주기 위한 별도의 화면 프로토타입이다.
"""
import streamlit as st

from streamlit_screens import (
    complete,
    cooking_step,
    no_match,
    recipe_confirm,
    register_dish_name,
    register_ingredients,
    register_intro,
    register_steps,
    start,
    substitution_confirm,
    unclassified,
)
from theme import inject_css, render_brand

SCREENS = {
    "start": start.render,
    "recipe_confirm": recipe_confirm.render,
    "cooking_step": cooking_step.render,
    "substitution_confirm": substitution_confirm.render,
    "no_match": no_match.render,
    "register_intro": register_intro.render,
    "register_dish_name": register_dish_name.render,
    "register_ingredients": register_ingredients.render,
    "register_steps": register_steps.render,
    "complete": complete.render,
    "unclassified": unclassified.render,
}

DEFAULT_STATE = {
    "screen": "start",
    "recipe": None,
    "step_number": 1,
    "chat_log": [],
    "substituted_ingredient": None,
    "pending_recipe_key": None,
    "register_data": None,
}


def init_state() -> None:
    for key, value in DEFAULT_STATE.items():
        st.session_state.setdefault(key, value)


def main() -> None:
    st.set_page_config(
        page_title="ChefEar", page_icon="🍲", layout="centered", initial_sidebar_state="collapsed"
    )
    init_state()
    inject_css()
    render_brand()

    screen_name = st.session_state.screen
    SCREENS[screen_name]()

    with st.sidebar:
        st.markdown("**화면 바로가기 (개발용)**")
        for name in SCREENS:
            if st.button(name, key=f"jump_{name}", use_container_width=True):
                st.session_state.screen = name
                st.rerun()


if __name__ == "__main__":
    main()
