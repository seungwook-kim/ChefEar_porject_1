"""⑦ 신규 등록 1/3 - 요리명 (FR-06)."""
import streamlit as st

from mock_data import REGISTER_DEFAULTS
from nav import goto
from theme import render_dots, render_mic_bar


def render() -> None:
    st.markdown('<p class="ce-hint">새 레시피 등록 · 1 / 3 · 요리명</p>', unsafe_allow_html=True)
    render_dots(3, 1)

    st.markdown("**어떤 요리인가요?**")
    st.caption("요리 이름을 말씀해주시면 그대로 등록할게요. 마이크 대신 STT 결과를 텍스트로 흉내 냈어요.")

    data = st.session_state.setdefault(
        "register_data", {"dish_name": "", "ingredients": [], "steps": list(REGISTER_DEFAULTS["steps"])}
    )
    dish_name = st.text_input(
        "인식된 요리명", value=data["dish_name"] or REGISTER_DEFAULTS["dish_name"], key="reg_dish_name_input"
    )

    render_mic_bar("듣는 중", "요리 이름을 말씀해주세요", listening=True)

    if st.button("다음", type="primary", use_container_width=True):
        if not dish_name.strip():
            st.warning("요리 이름을 입력해주세요.")
        else:
            st.session_state.register_data["dish_name"] = dish_name.strip()
            goto("register_ingredients")

    if st.button("취소", use_container_width=True):
        goto("register_intro")
