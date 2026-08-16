"""⑪ 음성 인식/의도분류 실패 Fallback - FR-16, AC-02/AC-09."""
import streamlit as st

from nav import goto
from theme import ICON_QUESTION_CIRCLE, render_mic_bar, render_spacer


def render() -> None:
    render_spacer()
    st.markdown(f'<div class="ce-lead-icon warn">{ICON_QUESTION_CIRCLE}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ce-center"><h1>잘 이해하지 못했어요</h1>'
        "<p>죄송해요, 다시 한번 말씀해주시겠어요? 안 될 때는 아래 버튼으로도 진행할 수 있어요.</p></div>",
        unsafe_allow_html=True,
    )
    render_spacer()
    render_mic_bar("다시 말씀해주세요", "또는 아래 버튼을 눌러주세요", listening=False)

    st.caption("음성 인식·의도 파악이 안 될 때를 위한 수동 Fallback UI (FR-16 · AC-09)")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("이전", use_container_width=True):
            goto("cooking_step")
    with c2:
        if st.button("다시", use_container_width=True):
            goto("cooking_step")
    with c3:
        if st.button("다음", use_container_width=True):
            goto("cooking_step")
