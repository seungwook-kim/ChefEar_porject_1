"""① 시작 화면 - FR-01: 숫자 메뉴 없이 자유발화 유도.

ui/html/01_start.html과 문구·구성 순서를 그대로 맞췄다(브랜드 → 여백 → 인사말+예시 문장
→ 큰 마이크 버튼 → "눌러서 말씀해주세요" → 힌트 카드 2개 → 여백). 힌트 카드의 "된장찌개
어떻게 만들어?" 부분처럼 글자색 일부만 다르게 주는 건 st.button 라벨(순수 텍스트만 지원)로는
불가능해서, 서식 있는 st.markdown으로 글씨를 그리고 그 위에 투명한 st.button을 정확히
겹쳐 클릭만 받는 방식을 쓴다(자세한 이유는 theme.py의 [class*="st-key-hint_chip"] 주석 참고).
"""
import streamlit as st

from nav import goto
from theme import render_big_mic, render_spacer

HINT_CHIPS = [
    (
        "hint_chip_doenjang",
        '이렇게 말해보세요 — <span class="quote">“된장찌개 어떻게 만들어?”</span>',
        "이렇게 말해보세요 — 된장찌개 어떻게 만들어?",
        "doenjang",
        "된장찌개 어떻게 만들어?",
    ),
    (
        "hint_chip_register",
        '등록된 레시피가 없는 경우 예시 — <span class="quote">“문어초무침 어떻게 만들어?”</span>',
        "등록된 레시피가 없는 경우 예시 — 문어초무침 어떻게 만들어?",
        None,
        "문어초무침 어떻게 만들어?",
    ),
]


def render() -> None:
    render_spacer()

    st.markdown(
        '<div class="ce-center">'
        "<h1>무엇을 만들고 싶으세요?</h1>"
        "<p>숫자 메뉴 없이, 하고 싶은 말을 편하게 그대로 말씀해주세요.</p>"
        '<p style="color:var(--text-faint); font-size:13.5px;">예: “된장찌개 어떻게 만들어?”</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    audio = render_big_mic()
    if audio is not None:
        st.info("녹음을 받았어요. STT 연결은 아직 준비 중이라 실제 음성 인식은 안 돼요 (src/ui/README.md 참고).")

    for key, styled_html, accessible_label, recipe_key, utterance in HINT_CHIPS:
        with st.container(key=key):
            st.markdown(f'<div class="ce-hint-chip">{styled_html}</div>', unsafe_allow_html=True)
            if st.button(accessible_label, use_container_width=True):
                st.session_state.chat_log = [("user", utterance)]
                if recipe_key:
                    st.session_state.pending_recipe_key = recipe_key
                    goto("recipe_confirm")
                else:
                    goto("register_intro")

    render_spacer()
