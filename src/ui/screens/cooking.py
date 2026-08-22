"""ChefEar 조리 흐름 화면(start/recipe_confirm/cooking_step) — src/app.py에서 분리
(2026-08-22, 화면 컴포넌트화)."""
from __future__ import annotations

import streamlit as st

from theme import (
    render_badge,
    render_big_mic,
    render_chat,
    render_chips,
    render_mic_bar,
    render_spacer,
    render_step_card,
    render_typewriter_message,
)
from ui.dispatch import fallback_buttons, process_utterance
from ui.recipe_view import _ingredients_to_chips, refresh_recipe_view
from ui.session import goto
from ui.voice_io import _AUDIO_DIR, listen, prefetch_next_step_audio, speak


def screen_start() -> None:
    render_spacer()
    st.markdown(
        '<div class="ce-center"><h1>무엇을 만들고 싶으세요?</h1>'
        "<p>숫자 메뉴 없이, 하고 싶은 말을 편하게 그대로 말씀해주세요.</p>"
        '<p style="color:var(--text-faint); font-size:13.5px;">예: "된장찌개 어떻게 만들어?"</p></div>',
        unsafe_allow_html=True,
    )
    render_big_mic()

    # register_intro/register_dish_name과 같은 이유로(2026-08-21) listen()이 따로 그리는
    # "말씀해주세요" 녹음 위젯은 꺼둔다 - 이 화면엔 이미 render_big_mic()이 그리는 원형
    # 마이크 아이콘 + "마이크 켜기" 버튼으로 여는 자체 녹음 위젯이 있어서, 같은 화면에
    # 마이크 녹음 위젯이 두 벌 겹쳐 보이는 문제가 있었다. 텍스트 입력 대체 경로는 그대로
    # 남아있고, 실제 음성 녹음은 render_big_mic() 쪽 위젯으로 여전히 가능하다.
    text = listen("start", show_mic=False)
    if text:
        process_utterance(text)

    # 2026-08-21: 위쪽에만 render_spacer()가 있고 아래쪽엔 없어서, block-container의
    # flex:1 남는 공간이 전부 위에만 쌓여 콘텐츠가 화면 아래쪽으로 밀렸다 - 뷰포트가
    # 높을수록(세로로 긴 화면비) 남는 공간 자체가 커져서 그만큼 더 크게 벌어져 보였다.
    # 다른 화면들(register_intro, complete, login 등)처럼 아래에도 render_spacer()를
    # 넣어 남는 공간을 위아래로 똑같이 나눠 화면 비율과 무관하게 수직 중앙 정렬되게 한다.
    render_spacer()


def screen_recipe_confirm() -> None:
    view = st.session_state.recipe_view
    if not view:
        goto("start")
        return

    render_badge("조회수 1위 표준 레시피 자동 선택 · 되묻지 않음 (FR-05)")
    # 2026-08-22 재요청: 이전 대화 기록(사용자 질문 등)은 아예 안 보여주고, 마지막 AI
    # 메시지를 챗봇 말풍선 없이 요리명/문장 두 줄로 줄바꿈해서(요리명은 크게) 타자기처럼
    # 한 글자씩 나타나는 순수 텍스트로 보여준다. 세 줄 문구는 dispatch.process_utterance()의
    # 조회 확인 메시지(`speak(f'{dish_name}, 조회수 1위 표준 레시피예요. 이걸로
    # 시작할까요?')`)와 내용이 같아야 한다 — 그쪽은 TTS로 자연스럽게 읽히려고 한 문장
    # 그대로 두고, 화면 표시만 여기서 줄 단위로 다시 나눈다.
    chat_log = st.session_state.chat_log
    if chat_log and chat_log[-1][0] == "ai":
        # render_spacer()로 뱃지와의 사이를 벌려서, 텍스트 블록이 위쪽에 바짝 붙지 않고
        # 아래쪽 "재료 미리보기" 사이 빈 공간의 세로 중앙쯤에 오게 한다(2026-08-22
        # 스크린샷 지적 — screen_start() 등 다른 화면의 render_spacer() 패턴과 동일).
        render_spacer()
        render_typewriter_message(
            [view["dish_name"], "조회수 1위 표준 레시피예요.", "이걸로 시작할까요?"],
            key=f"recipe_confirm:{chat_log[-1][1]}",
        )

    st.markdown("**재료 미리보기**")
    render_chips(_ingredients_to_chips(view["ingredients_raw"]))

    render_mic_bar("듣는 중", '"응" 또는 다른 요청을 말씀해주세요', listening=True)

    # "응"(긍정) 확인은 classify_intent()가 처리하지 않는다(의도적 제외,
    # tests/integration_test.md 기록) — 이 화면 안에서만 문자열로 직접 우회 처리.
    # cooking_step/register_intro/register_dish_name과 같은 이유(2026-08-21/22) — 바로 위
    # render_mic_bar()가 이미 "듣는 중" 펄스 애니메이션으로 마이크가 켜져 있음을 보여주고
    # 있어서, listen()이 따로 그리는 실제 녹음 위젯("말씀해주세요" 박스)까지 있으면 마이크
    # 안내가 중복돼 보인다는 지적(2026-08-22)으로 show_mic=False로 꺼둔다(완전히 지우진
    # 않음, 나중에 되돌릴 수 있게). 텍스트 입력 대체 경로는 그대로 남아있다.
    text = listen("recipe_confirm", show_mic=False)
    if text:
        norm = text.strip().rstrip("?!. ")
        if norm in ("응", "네", "좋아", "좋아요", "그래", "그래요", "시작", "응, 시작할게요"):
            st.session_state.pipeline_session["step_number"] = 1
            # register_steps의 "네, 저장할게요"와 같은 이유(2026-08-22 리포트) — 여기서
            # speak()가 그리는 재생바는 바로 다음 줄 goto()의 st.rerun()에 곧장 지워져서
            # "떴다가 사라지는" 화면 깜빡임만 만든다. 도착 화면(cooking_step)이 같은
            # 음성을 캐시에서 다시 찾아 들려주므로(render_step_card()) hidden=True로
            # 화면 없는 자동재생만 하고, 실제로 들리는 소리는 도착 화면 쪽에 맡긴다.
            if view["steps"]:
                first_step = view["steps"][0]
                speak(
                    first_step["text"],
                    recipe_id=view["recipe_id"],
                    step_number=first_step.get("step_number", 1),
                    hidden=True,
                )
            else:
                speak("1단계 정보를 찾지 못했어요.", hidden=True)
            goto("cooking_step")
        else:
            process_utterance(text)

    if st.button("다른 레시피 찾을래요", use_container_width=True):
        goto("start")


def screen_cooking_step() -> None:
    refresh_recipe_view()
    view = st.session_state.recipe_view
    session = st.session_state.pipeline_session
    if not view or not view["steps"]:
        goto("start")
        return

    total = len(view["steps"])
    step_number = min(session.get("step_number", 1), total)
    current = view["steps"][step_number - 1]

    # 사용자가 지금 단계를 보고/듣고 있는 동안 다음 단계 음성을 미리 합성해둔다 —
    # prefetch_next_step_audio() 정의부 주석 참고(2026-08-22, TTS 체감 속도 개선).
    prefetch_next_step_audio(view, step_number)

    render_badge(f'{view["dish_name"]} · {step_number} / {total} 단계')

    # 2026-08-21: speak()가 만드는 재생 위젯은 그 직후 goto()의 st.rerun()으로 화면이
    # 바로 새로고침되면서 같이 사라진다 — speak() 안에서 렌더링한 건 "그 rerun 전까지만"
    # 유효하다. 그래서 이 화면(cooking_step) 자체가 매번 다시 그려질 때도 캐시된 오디오를
    # 직접 찾아서 render_step_card()에 넘겨야 실제로 화면에 남아있는 재생바가 된다
    # (speak()가 쓰는 것과 같은 ui/assets/audio/<recipe_id>/<step:02d>.wav 캐시 경로).
    cached_audio_path = _AUDIO_DIR / str(view["recipe_id"]) / f"{step_number:02d}.wav"
    if cached_audio_path.exists():
        nav_target = render_step_card(
            total,
            step_number,
            current["text"],
            audio_path=cached_audio_path,
            audio_nonce=st.session_state.get("_audio_replay_nonce", 0),
        )
    else:
        nav_target = render_step_card(total, step_number, current["text"])

    # 2026-08-21: 점을 눌러 그 단계로 바로 이동하거나 화살표로 이전/다음 단계로 넘어간
    # 경우 - render_step_card()는 표시만 하고 실제 상태 전환은 여기서 한다(theme.py는
    # orchestration을 몰라서). [이전][다음] 버튼(fallback_buttons)이 manual_fallback()으로
    # 하는 것과 같은 효과(세션 갱신 + 음성 재생 + 재생 nonce 증가)를 낸다 - 단, 점 클릭은
    # 임의의 단계로 바로 건너뛸 수 있어야 해서 manual_fallback()(상대 이동만 지원)
    # 대신 view["steps"]에서 바로 읽는다(get_precomputed_steps()로 이미 전체를
    # 가져와서 recipe_view에 캐싱돼 있어 추가 조회가 필요 없다).
    if nav_target is not None:
        session["step_number"] = nav_target
        st.session_state["_audio_replay_nonce"] = st.session_state.get("_audio_replay_nonce", 0) + 1
        target_step = view["steps"][nav_target - 1]
        speak(target_step["text"], recipe_id=view["recipe_id"], step_number=target_step.get("step_number", nav_target))
        goto("cooking_step")

    st.markdown("**오늘의 재료**")
    render_chips(_ingredients_to_chips(view["ingredients_raw"]))

    if st.session_state.chat_log:
        render_chat(st.session_state.chat_log[-4:])

    render_mic_bar("듣는 중", '"이전" · "다시" · "다음"', listening=True)

    # register_intro/register_dish_name과 같은 이유(2026-08-21) — 바로 위 render_mic_bar()가
    # 이미 "듣는 중" 펄스 애니메이션으로 마이크가 켜져 있음을 보여주고 있어서, listen()이
    # 따로 그리는 실제 녹음 위젯("말씀해주세요" 박스)까지 있으면 마이크 안내가 중복돼
    # 보인다는 지적(2026-08-22)으로 여기도 show_mic=False로 꺼둔다(완전히 지우진 않음,
    # 나중에 되돌릴 수 있게). 텍스트 입력 대체 경로는 그대로 남아있다.
    text = listen("cooking_step", show_mic=False)
    if text:
        process_utterance(text)

    fallback_buttons("cooking_step")
