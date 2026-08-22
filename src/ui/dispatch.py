"""ChefEar 발화 처리(핵심 디스패처) — src/app.py에서 분리(2026-08-22, 화면 컴포넌트화).

start/cooking_step/unclassified 화면이 공유한다.
"""
from __future__ import annotations

import streamlit as st

from orchestration.db import get_client
from orchestration.entity_extract import extract_substitution_ingredients
from orchestration.entity_extract_llm import extract_dish_name_llm
from orchestration.pipeline import handle_utterance, manual_fallback
from ui.recipe_view import refresh_recipe_view
from ui.session import goto
from ui.voice_io import speak


def process_utterance(text: str) -> None:
    st.session_state.chat_log.append(("user", text))

    session = st.session_state.pipeline_session
    client = get_client()

    dish_name_guess = extract_dish_name_llm(text)
    requested, excluded = extract_substitution_ingredients(text)
    try:
        result = handle_utterance(
            session,
            text,
            dish_name=dish_name_guess,
            requested_ingredient=requested,
            excluded_ingredient=excluded,
            client=client,
        )
    except ValueError:
        # "등록"/"정정" 의도인데 registration_step 없이 자유발화로 들어온 경우 등 —
        # 서비스를 죽이는 대신 신규 등록 유도 화면으로 안전하게 보낸다.
        st.session_state.pending_dish_name = dish_name_guess
        goto("register_intro")
        return

    intent = result.get("intent")

    if intent == "미분류":
        # 문장 패턴 분류(classify_intent)가 "조회"로 못 알아들은 경우 전부 여기로 온다 —
        # "분홍코끼리 어떻게 만들어?"처럼 LLM이 요리명을 뽑아낸 경우뿐 아니라, "111"처럼
        # LLM조차 요리명으로 확신 못 해 dish_name_guess가 None인 경우도 포함한다.
        # "잘 이해하지 못했어요"로 되묻고 끝내는 대신, 표준 데이터에 없는 요리일
        # 가능성으로 보고 항상 등록 유도 화면으로 보낸다(2026-08-21 요청) — 등록
        # 화면 자체가 "이 이름 맞아요?"로 다시 확인/수정을 받으므로, 여기서 추측이
        # 틀려도 안전하다. LLM이 아무것도 못 뽑았으면 발화 원문을 그대로 짐작값으로 쓴다.
        st.session_state.pending_dish_name = dish_name_guess or text.strip()
        goto("register_intro")
        return

    if intent == "조회":
        if "message" in result:  # DISH_NOT_FOUND_MESSAGE — 표준 데이터 밖(시나리오 D)
            st.session_state.pending_dish_name = dish_name_guess
            speak(result["message"])
            goto("no_match")
            return
        refresh_recipe_view(force=True)
        speak(f'{result["dish_name"]}, 조회수 1위 표준 레시피예요. 이걸로 시작할까요?')
        goto("recipe_confirm")
        return

    if intent in ("진행", "재청취", "이전"):
        step = result.get("step")
        if result.get("no_previous"):
            speak("1단계예요, 이전 단계가 없어요.")
        elif step is None:
            speak("마지막 단계까지 다 왔어요. 수고하셨어요!")
        else:
            # "다시"는 같은 파일을 다시 재생하는 거라 오디오 콘텐츠 자체가 안 바뀌어서
            # nonce 없이는 iframe이 안 바뀐 걸로 보고 autoplay가 재실행되지 않는다. "다음"/
            # "이전"도 이전에 방문했던 단계로 돌아갈 때(예: 2단계->1단계->2단계) 같은 문제가
            # 재현될 수 있어 실제 단계 오디오를 다시 들려줄 때만 nonce를 올려 항상 새로
            # 로드되게 한다(theme.py render_audio_player() 참고).
            #
            # 2026-08-22 리포트: 이 nonce 증가를 "1단계예요..."/"마지막 단계까지..." 안내
            # 분기 앞에서 공통으로 하고 있었는데, 그 두 경우엔 현재 화면의 단계 번호가
            # 안 바뀐다 — 그런데도 nonce를 올리면 goto()의 rerun 직후 screen_cooking_step()이
            # 화면에 그대로 남아있는 그 단계 카드의 캐시 오디오를 "새로 로드된 것"으로 보고
            # 다시 자동재생해서, 방금 speak()로 들려준 안내 음성과 동시에 겹쳐 들렸다. 실제
            # 단계 오디오를 다시 보여주는 이 분기에서만 nonce를 올려서 막는다.
            st.session_state["_audio_replay_nonce"] = st.session_state.get("_audio_replay_nonce", 0) + 1
            speak(step["text"], recipe_id=session.get("current_recipe_id"), step_number=step.get("step_number"))
        goto("cooking_step")
        return

    if intent == "재료대체":
        if result.get("match_type") == "none":
            speak(result["message"])
            goto("no_match")
            return
        refresh_recipe_view(force=True)
        speak(f'네, {result["result_dish_name"]}로 바꿔드렸어요. "취소해줘"라고 하면 원래대로 되돌려드려요.')
        goto("cooking_step")
        return

    if intent == "취소":
        if result.get("rolled_back"):
            refresh_recipe_view(force=True)
            speak(f'네, {result["dish_name"]}로 되돌렸어요.')
        else:
            speak("지금은 되돌릴 대체가 없어요.")
        goto("cooking_step")
        return

    if intent in ("등록", "정정"):
        prompt = result.get("prompt") or result.get("summary") or result.get("message")
        if prompt:
            speak(prompt)
        goto("register_intro")
        return

    # 알 수 없는 intent(방어적 처리) — 서비스가 죽는 대신 fallback으로.
    speak("죄송해요, 잘 처리하지 못했어요. 다시 한 번 말씀해주시겠어요?")
    goto("unclassified")


def fallback_buttons(key_prefix: str) -> None:
    """FR-16 — 음성 인식/의도분류 실패 시 수동 [이전][다시][다음]. 항상 노출한다."""
    session = st.session_state.pipeline_session
    if not session.get("current_recipe_id"):
        return
    st.caption("음성이 잘 안 될 땐 아래 버튼으로도 진행할 수 있어요.")
    c1, c2, c3 = st.columns(3)
    client = get_client()
    for col, button in ((c1, "이전"), (c2, "다시"), (c3, "다음")):
        with col:
            if st.button(button, key=f"{key_prefix}_{button}", use_container_width=True):
                result = manual_fallback(session, button, client=client)
                if result.get("no_previous"):
                    speak("1단계예요, 이전 단계가 없어요.")
                elif result.get("step") is None:
                    speak("마지막 단계까지 다 왔어요. 수고하셨어요!")
                else:
                    # process_utterance()의 같은 분기와 동일한 이유(2026-08-22) — 실제 단계
                    # 오디오를 다시 보여줄 때만 nonce를 올린다. "1단계예요..."/"마지막
                    # 단계까지..." 안내는 화면의 단계가 안 바뀌는데 nonce만 올리면, rerun
                    # 후 그 자리에 남아있는 단계 카드의 캐시 오디오가 다시 자동재생되면서
                    # 방금 들려준 안내 음성과 겹쳐 들린다.
                    st.session_state["_audio_replay_nonce"] = st.session_state.get("_audio_replay_nonce", 0) + 1
                    speak(
                        result["step"]["text"],
                        recipe_id=session.get("current_recipe_id"),
                        step_number=result["step"].get("step_number"),
                    )
                goto("cooking_step")
