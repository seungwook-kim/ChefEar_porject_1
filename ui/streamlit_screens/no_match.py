"""⑤ 매칭 실패 안내 - 시나리오 C, 6.4 ③: 요리명·재료 모두 실패 시 정직하게 안내."""
import streamlit as st

from nav import goto
from theme import ICON_X_CIRCLE, render_chat, render_spacer


def render() -> None:
    render_spacer()
    st.markdown(f'<div class="ce-lead-icon warn">{ICON_X_CIRCLE}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ce-center"><h1>이 조합의 레시피는 없어요</h1>'
        "<p>요리명과 재료 내용, 두 가지 기준으로 모두 찾아봤지만 없어서 정직하게 말씀드려요.</p></div>",
        unsafe_allow_html=True,
    )

    render_chat(
        [
            ("user", "문어랑 성게 같이 넣어도 돼?"),
            ("ai", "죄송해요, 이 조합의 레시피는 없어요."),
        ]
    )

    st.caption("실데이터 검색만으로 판단해요 — 없는 레시피를 지어내지 않아요 (1.5 원칙, LLM 생성 fallback 없음).")
    render_spacer()

    if st.button("원래 레시피로 계속하기", type="primary", use_container_width=True):
        goto("cooking_step")
