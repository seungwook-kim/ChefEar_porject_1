"""⑨ 신규 등록 3/3 - 조리 순서 + 최종 확인 체크포인트 (FR-06, 2단계 확인 구조 중 2번째)."""
import streamlit as st

from nav import goto
from theme import render_dots


def render() -> None:
    data = st.session_state.get("register_data")
    if not data:
        goto("register_intro")

    st.markdown(f'<p class="ce-hint">{data["dish_name"]} · 3 / 3 · 조리 순서</p>', unsafe_allow_html=True)
    render_dots(3, 3)

    st.markdown("**조리 순서를 알려주세요**")
    st.caption("순서대로 한 단계씩 말씀해주세요.")

    for i, step_text in enumerate(data["steps"], start=1):
        st.markdown(f"**{i}.** {step_text}")

    new_step = st.text_input("순서 추가", key="reg_step_new", label_visibility="collapsed", placeholder="새 단계 추가")
    if st.button("단계 추가") and new_step.strip():
        data["steps"].append(new_step.strip())
        st.rerun()

    st.markdown(
        '<div class="ce-checkpoint"><p class="title">최종 확인 체크포인트</p>'
        "<p>이대로 저장할까요? 저장한 뒤에도 언제든 다시 수정할 수 있어요.</p></div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("네, 저장할게요", type="primary", use_container_width=True):
            goto("complete")
    with c2:
        if st.button("이전", use_container_width=True):
            goto("register_ingredients")
