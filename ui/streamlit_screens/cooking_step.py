"""③ 조리 진행 화면 (메인) - PRD 3.3 화면 구성, FR-02/FR-03/FR-04/FR-16을 실제로 동작시킨다.

전달받은 목업 이미지(된장찌개 3/5단계)를 기준으로 하되, [이전]/[다시]/[다음] 버튼은
docs/ChefEar_PRD_SDD_v0.8.md 7.1.1 상태 전이 규칙을 그대로 구현했다(정적 HTML 프로토타입과의
차이점 - 여기서는 st.session_state.step_number가 실제로 바뀐다).
"""
from pathlib import Path

import streamlit as st

from mock_data import fresh_recipe
from nav import goto
from theme import (
    render_badge,
    render_chat,
    render_chips,
    render_mic_bar_interactive,
    render_section_title,
    render_step_card,
)

# 실제 음성이 있는 레시피(부대찌개, ui/assets/audio/budaejjigae/)는 render_step_card()에
# audio_path를 넘겨서 카드 안에 진짜 재생바(theme.render_audio_player(), .ce-player와
# 같은 모양의 커스텀 위젯)를 넣는다 — st.audio()는 브라우저 기본 재생바가 그대로 노출돼
# 앱 디자인과 안 맞아서 안 쓴다. 오디오가 없는 레시피는 장식용 정지 파형만 보여준다.
_AUDIO_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"


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

    audio_file = current.get("audio")
    audio_path = _AUDIO_DIR / recipe["id"] / audio_file if audio_file else None
    has_real_audio = audio_path is not None and audio_path.exists()

    # 진짜 오디오가 있으면 그 wav로 카드 안에 진짜 재생바를 넣고(audio_path), 없으면
    # 장식용 정지 파형만 보여준다(theme.render_step_card() 참고).
    render_step_card(total, step_number, current["text"], audio_path=audio_path if has_real_audio else None)

    if audio_file and not has_real_audio:
        st.caption(f"⚠️ 음성 파일 없음: {audio_path.relative_to(_AUDIO_DIR.parent.parent)}")

    render_section_title("오늘의 재료")
    render_chips(recipe["ingredients"], substituted_name=st.session_state.get("substituted_ingredient"))

    # 아직 대체 등 상호작용이 없었을 때도(예: 1단계 진입 직후) 오늘의 재료↔듣는 중 사이에
    # 대화 구역이 항상 보이도록, 비어있으면 기본 예시 대화로 대체한다.
    chat = st.session_state.chat_log or [
        ("user", "감자 대신 양파 넣어도 돼?"),
        ("ai", "네, 양파로 대체했어요."),
    ]
    render_chat(chat)

    audio_input = render_mic_bar_interactive('"다음" · "다시" · "재료 바꾸기"')
    if audio_input is not None:
        st.info("녹음을 받았어요. STT 연결은 아직 준비 중이라 실제 음성 인식은 안 돼요 (src/ui/README.md 참고).")

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

    with st.container(key="cs_demo_buttons"):
        if recipe["id"] == "doenjang" and st.session_state.get("substituted_ingredient") != "양파":
            if st.button('🎙️ "감자 대신 양파 넣어도 돼?" (같은 레시피 안에서 1:1 대체)'):
                st.session_state.substituted_ingredient = "양파"
                st.session_state.chat_log = [("user", "감자 대신 양파 넣어도 돼?"), ("ai", "네, 양파로 대체했어요.")]
                goto("cooking_step")

        if st.button("🎙️ “바지락 넣어도 돼?” (다른 레시피로 교체 제안 예시)"):
            goto("substitution_confirm")

        if st.button("🎙️ “문어랑 성게 같이 넣어도 돼?” (매칭 실패 예시)"):
            goto("no_match")

        if st.button("음성 인식 실패 Fallback 예시 보기"):
            goto("unclassified")
