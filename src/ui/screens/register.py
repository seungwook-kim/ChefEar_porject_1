"""ChefEar 신규 등록 플로우 화면(no_match -> register_intro -> ... -> complete) —
src/app.py에서 분리(2026-08-22, 화면 컴포넌트화).

register_recipe()가 돌려주는 prompt/summary는 대화 중간(재료·순서 누적)에만 있고,
화면 전환 시점의 고정 안내문(인트로/순서 질문 등)은 없다 — 그 화면 자신이 자신의
안내문을 "무슨 말을 했는지" 알아야 voice_io._render_cached_speech()로 같은 캐시를
다시 찾을 수 있어서, 전환 직전(호출부)과 도착 화면 양쪽이 똑같이 이 함수들을 불러 쓴다.
(register_intro 자체는 2026-08-21부터 음성 안내를 뺐다 — 아래 screen_register_intro()
참고.)
"""
from __future__ import annotations

import streamlit as st

from theme import (
    ICON_CHECK_CIRCLE,
    ICON_CHECK_SMALL,
    ICON_QUESTION_CIRCLE,
    ICON_SPARKLE,
    ICON_X_CIRCLE,
    render_back_link,
    render_chat,
    render_chips,
    render_dots,
    render_mic_bar,
    render_spacer,
)
from orchestration.db import get_client
from orchestration.registration import register_recipe
from ui.dispatch import fallback_buttons, process_utterance
from ui.session import _DEFAULT_PIPELINE_SESSION, get_owner_id, goto
from ui.voice_io import _render_cached_speech, listen, speak

_REGISTER_SAVED_MESSAGE = "저장이 완료됐어요!"


def screen_no_match() -> None:
    render_spacer()
    st.markdown(f'<div class="ce-lead-icon warn">{ICON_X_CIRCLE}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ce-center"><h1>이 조합의 레시피는 없어요</h1>'
        "<p>요리명과 재료 내용, 두 가지 기준으로 모두 찾아봤지만 없어서 정직하게 말씀드려요.</p></div>",
        unsafe_allow_html=True,
    )
    chat_log = st.session_state.chat_log
    if chat_log and chat_log[-1][0] == "ai":
        # dispatch.py가 이 화면으로 넘어오기 직전 speak(..., hidden=True)로 미리 합성/캐싱만
        # 해둔 문구를 여기서 다시 찾아 들려준다(2026-08-22 리포트 — 화면 전환 중 재생바가
        # "떴다 사라짐" 깜빡이는 문제, recipe_confirm과 같은 패턴).
        _render_cached_speech(chat_log[-1][1])
    render_chat(st.session_state.chat_log[-2:])
    st.caption("실데이터 검색만으로 판단해요 — 없는 레시피를 지어내지 않아요 (1.5 원칙).")
    render_spacer()

    c1, c2 = st.columns(2)
    with c1:
        if st.session_state.pipeline_session.get("current_recipe_id") and st.button(
            "원래 레시피로 계속하기", type="primary", use_container_width=True
        ):
            goto("cooking_step")
    with c2:
        if st.button("새 레시피로 등록할래요", use_container_width=True):
            goto("register_intro")


def screen_unclassified() -> None:
    render_spacer()
    st.markdown(f'<div class="ce-lead-icon warn">{ICON_QUESTION_CIRCLE}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ce-center"><h1>잘 이해하지 못했어요</h1>'
        "<p>죄송해요, 다시 한번 말씀해주시겠어요? 안 될 때는 아래 버튼으로도 진행할 수 있어요.</p></div>",
        unsafe_allow_html=True,
    )
    chat_log = st.session_state.chat_log
    if chat_log and chat_log[-1][0] == "ai":
        # screen_no_match()와 같은 이유(2026-08-22) — dispatch.py의 hidden=True speak()가
        # 미리 캐싱해둔 문구를 여기서 다시 들려준다.
        _render_cached_speech(chat_log[-1][1])
    render_spacer()
    render_mic_bar("다시 말씀해주세요", "또는 아래 버튼을 눌러주세요", listening=False)

    text = listen("unclassified")
    if text:
        process_utterance(text)

    fallback_buttons("unclassified")


def screen_register_intro() -> None:
    render_spacer()
    st.markdown(f'<div class="ce-lead-icon neutral">{ICON_SPARKLE}</div>', unsafe_allow_html=True)
    dish_hint = st.session_state.pending_dish_name or "그 요리"
    st.markdown(
        '<div class="ce-center"><h1>표준 데이터에 없는 요리예요</h1>'
        f"<p>{dish_hint}는 표준 레시피 안에는 없지만, 직접 알려주시면 회원님 레시피로 등록해드릴게요.</p></div>",
        unsafe_allow_html=True,
    )
    render_spacer()
    render_mic_bar("듣는 중", '"네" 또는 "등록할래요"라고 말해보세요', listening=True)

    # 2026-08-21: 위 "듣는 중" 표시줄이 이미 마이크가 켜져 있다는 걸 보여주고 있어서,
    # listen()이 따로 그리는 실제 녹음 위젯(제목 "말씀해주세요" + 녹음 버튼)까지 있으면
    # 같은 화면에 마이크 관련 표시가 두 번 겹쳐 보인다는 지적이 있었다 — 일단 이 화면만
    # show_mic=False로 꺼둔다(완전히 지우진 않음, 나중에 되돌릴 수 있게). 텍스트로
    # "네, 등록할래요"/"괜찮아요"를 입력하는 대체 경로는 그대로 남아있다.
    text = listen("register_intro", show_mic=False)
    if text:
        norm = text.strip().rstrip("?!. ")
        if norm in ("네", "응", "좋아", "좋아요", "그래", "그래요", "등록", "등록할래요", "네, 등록할래요"):
            get_owner_id()
            goto("register_dish_name")
        elif norm in ("아니", "아니요", "괜찮아", "괜찮아요", "취소"):
            goto("start")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("네, 등록할래요", type="primary", use_container_width=True):
            get_owner_id()
            goto("register_dish_name")
    with c2:
        if st.button("괜찮아요", use_container_width=True):
            goto("start")


def screen_register_dish_name() -> None:
    """FR-06 1단계: 요리명 질문. no_match에서 넘어온 추측값(pending_dish_name)을
    그대로 쓰지 않고 사용자가 직접 확인/수정하게 한다 — 규칙 기반 추출은 틀릴 수 있어서
    (entity_extract.py 참고) 등록처럼 DB에 실제로 남는 데이터는 검증 없이 넘기면 안 된다."""
    if render_back_link("처음 화면으로"):
        goto("start")
    st.markdown('<p class="ce-hint">새 레시피 등록 · 1 / 3 · 요리명</p>', unsafe_allow_html=True)
    render_dots(3, 1)
    st.markdown("**어떤 요리인가요?**")
    if st.session_state.pending_dish_name:
        st.caption(f'짐작한 이름: "{st.session_state.pending_dish_name}" — 맞으면 "네", 다르면 이름을 말씀해주세요')
    render_mic_bar("듣는 중", "요리 이름을 말씀해주세요", listening=True)

    # register_intro와 같은 이유로(2026-08-21) 실제 녹음 위젯("말씀해주세요" 박스)은
    # 일단 꺼둔다 - 위 "듣는 중" 아이콘이 펄스 애니메이션으로 이미 마이크가 활성화된
    # 상태를 보여주고 있어서, 텍스트 대체 입력만으로 충분하다고 판단됨.
    text = listen("register_dish_name", show_mic=False)
    if text:
        norm = text.strip().rstrip("?!. ")
        if norm in ("네", "응", "맞아", "맞아요", "그래", "그래요") and st.session_state.pending_dish_name:
            dish_name = st.session_state.pending_dish_name
        else:
            dish_name = text.strip()
        # 2026-08-21: 여기서 speak(result["prompt"])로 음성 합성을 하고 있었지만, 그
        # 재생 위젯은 바로 뒤 goto()의 st.rerun()에 지워지고, 도착 화면인
        # register_ingredients는 텍스트 입력 전용(마이크 바·재생바 없음)이라 이 안내문을
        # _render_cached_speech()로 다시 보여주지도 않는다. chat_log에도 남지만 등록
        # 화면들은 render_chat()을 안 써서 그것도 어차피 안 보인다 — 즉 매번 로컬 CPU로
        # 몇 분씩 걸리는 합성을 하고도 아무도 못 듣는 죽은 호출이라 제거했다.
        register_recipe(st.session_state.pipeline_session, "dish_name", dish_name, client=get_client())
        goto("register_ingredients")

    if st.button("취소", use_container_width=True):
        goto("register_intro")


def screen_register_ingredients() -> None:
    reg = st.session_state.pipeline_session.get("registration")
    if not reg:
        goto("register_intro")
        return

    if render_back_link("처음 화면으로"):
        goto("start")
    st.markdown(f'<p class="ce-hint">{reg["dish_name"]} · 2 / 3 · 재료</p>', unsafe_allow_html=True)
    render_dots(3, 2)
    st.markdown("**재료를 알려주세요**")
    render_chips([{"name": ing, "qty": "", "emoji": "✅"} for ing in reg["ingredients"]])

    # 2026-08-21: 이 화면은 텍스트 입력 전용으로 되돌렸다 — STT/TTS(마이크 바·재생바·
    # listen())를 붙였던 버전 대신, 원래의 순수 텍스트 폼(요청받은 화면 그대로)을 쓴다.
    new_item = st.text_input("재료 추가(쉼표로 여러 개 가능)", key="reg_ing_new", placeholder="예: 두부, 감자")
    if st.button("추가") and new_item.strip():
        items = [x.strip() for x in new_item.split(",") if x.strip()]
        register_recipe(st.session_state.pipeline_session, "ingredients", items, client=get_client())
        st.rerun()

    if reg["ingredients"] and st.button("네, 맞아요", type="primary", use_container_width=True):
        goto("register_steps")


def screen_register_steps() -> None:
    reg = st.session_state.pipeline_session.get("registration")
    if not reg:
        goto("register_intro")
        return

    if render_back_link("처음 화면으로"):
        goto("start")
    st.markdown(f'<p class="ce-hint">{reg["dish_name"]} · 3 / 3 · 조리 순서</p>', unsafe_allow_html=True)
    render_dots(3, 3)
    st.markdown("**조리 순서를 알려주세요**")
    # 2026-08-22 요청 - 순서 각 줄에 수정/삭제 버튼을 붙인다. register_recipe()의 "confirm"
    # step(아래 "네, 저장할게요")이 그 시점의 reg["instructions"]를 그대로 읽어서
    # save_recipe()에 넘기므로(registration.py 참고), 여기서 이 리스트 자체를 고치면
    # 수정한 문장/삭제로 뺀 항목이 백엔드 저장에도 자동으로 그대로 반영된다 — 별도로
    # "제외 목록"을 만들어 나중에 필터링할 필요가 없다.
    editing_idx = st.session_state.get("reg_step_editing_idx")
    for i, step_text in enumerate(reg["instructions"]):
        with st.container(key=f"reg_step_row_{i}"):
            if editing_idx == i:
                new_text = st.text_input(
                    "단계 수정", value=step_text, key=f"reg_step_edit_input_{i}", label_visibility="collapsed"
                )
                ec1, ec2 = st.columns(2)
                with ec1:
                    if st.button(
                        "저장", key=f"reg_step_edit_save_{i}", type="primary", use_container_width=True
                    ):
                        reg["instructions"][i] = new_text.strip()
                        st.session_state.reg_step_editing_idx = None
                        st.rerun()
                with ec2:
                    if st.button("취소", key=f"reg_step_edit_cancel_{i}", use_container_width=True):
                        st.session_state.reg_step_editing_idx = None
                        st.rerun()
            else:
                c1, c_actions = st.columns([5, 2])
                with c1:
                    st.markdown(
                        f'<div style="display:flex; align-items:center; gap:12px;">'
                        f'<span class="ce-step-num">{i + 1}</span>'
                        f'<p style="margin:0; font-size:14.5px; line-height:1.55; color:var(--text);">{step_text}</p>'
                        "</div>",
                        unsafe_allow_html=True,
                    )
                with c_actions:
                    # my_recipes.py의 my_recipe_actions_와 같은 이유(2026-08-21) - st.columns로
                    # 나누면 칸이 넓어질수록 버튼 두 개가 같이 벌어져서, 세로 블록 하나에
                    # 담고 CSS로 가로 배치 + 오른쪽 붙임 처리한다(theme.py 참고).
                    with st.container(key=f"reg_step_actions_{i}"):
                        if st.button(":material/edit:", key=f"reg_step_edit_{i}", help="수정"):
                            st.session_state.reg_step_editing_idx = i
                            st.rerun()
                        if st.button(":material/delete:", key=f"reg_step_delete_{i}", help="삭제"):
                            reg["instructions"].pop(i)
                            st.rerun()

    # register_ingredients와 같은 이유로(2026-08-21) 텍스트 입력 전용으로 되돌렸다.
    new_step = st.text_input("순서 추가", key="reg_step_new", placeholder="새 단계 추가")
    if st.button("단계 추가") and new_step.strip():
        register_recipe(st.session_state.pipeline_session, "instructions", [new_step.strip()], client=get_client())
        st.rerun()

    if reg["instructions"] and st.button("네, 저장할게요", type="primary", use_container_width=True):
        register_recipe(st.session_state.pipeline_session, "confirm", None, client=get_client())
        speak(_REGISTER_SAVED_MESSAGE, hidden=True)
        goto("complete")


def screen_complete() -> None:
    dish_name = (st.session_state.recipe_view or {}).get("dish_name") or "레시피"
    render_spacer()
    st.markdown(f'<div class="ce-lead-icon positive">{ICON_CHECK_CIRCLE}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="ce-center"><h1>저장이 완료됐어요!</h1>'
        f"<p>{dish_name}, 다음에 다시 찾으면 회원님 버전으로 먼저 안내해드릴게요.</p></div>",
        unsafe_allow_html=True,
    )
    _render_cached_speech(_REGISTER_SAVED_MESSAGE)
    st.markdown(
        '<div style="text-align:center;">'
        f'<span class="ce-status-badge">{ICON_CHECK_SMALL} 나만의 레시피로 저장됨</span></div>',
        unsafe_allow_html=True,
    )
    render_spacer()

    if st.button("처음 화면으로", type="primary", use_container_width=True):
        st.session_state.pipeline_session = dict(_DEFAULT_PIPELINE_SESSION)
        st.session_state.chat_log = []
        st.session_state.recipe_view = None
        st.session_state.pending_dish_name = None
        goto("start")
