"""ChefEar 실제 서비스 엔트리포인트 (HF Spaces 배포 대상, `docs/specs/app_e2e.md`).

마이크 입력 -> STT(`stt.infer.stt_transcribe`) -> 오케스트레이션(`orchestration.pipeline.
handle_utterance`) -> TTS(`tts.infer.tts_synthesize`) 재생까지 한 화면 루프로 엮는다.
화면 컴포넌트(CSS/아이콘/카드 등)는 `ui/theme.py`를 그대로 재사용한다(PRD 3.3 "핵심 기능
완료 후 여유 시간에 다듬는다" — 화면 디자인은 새로 만들지 않음, Out of Scope).

`ui/streamlit_screens/*.py`(mock 프로토타입)는 그대로 재사용하지 않는다 — 그 화면들은
버튼마다 시나리오를 하드코딩해서 요리명/재료명 추출 문제를 우회했는데(예: "바지락 넣어도
돼?" 버튼이 requested_ingredient=["바지락"]을 코드에 미리 박아둠), 실제 자유발화는 그
우회가 불가능하다. 그래서 이 파일은 화면 흐름을 직접 다시 짜되, 시각 컴포넌트만 theme.py에서
가져다 쓴다.

실행: streamlit run src/app.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "ui"))

import numpy as np
import soundfile as sf
import streamlit as st

from orchestration.db import get_client, load_env
from orchestration.entity_extract import extract_substitution_ingredients
from orchestration.entity_extract_llm import extract_dish_name_llm
from orchestration.pipeline import get_precomputed_steps, handle_utterance, manual_fallback
from orchestration.registration import register_recipe

from theme import (
    ICON_CHECK_CIRCLE,
    ICON_CHECK_SMALL,
    ICON_QUESTION_CIRCLE,
    ICON_SPARKLE,
    ICON_X_CIRCLE,
    inject_css,
    render_badge,
    render_big_mic,
    render_brand,
    render_chat,
    render_chips,
    render_dots,
    render_mic_bar,
    render_spacer,
    render_step_card,
)

load_env()

# ============================================================
# 세션 상태
# ============================================================

# handle_utterance()/advance_step()/register_recipe()가 그대로 받아쓰는 딕셔너리 — 이
# 프로젝트의 오케스트레이션 계약을 그대로 따른다(새 세션 구조를 따로 만들지 않음).
_DEFAULT_PIPELINE_SESSION = {
    "current_recipe_id": None,
    "step_number": 1,
    "previous_recipe_id": None,
    "registration": None,
    "owner_id": None,
}


def init_state() -> None:
    st.session_state.setdefault("screen", "start")
    st.session_state.setdefault("pipeline_session", dict(_DEFAULT_PIPELINE_SESSION))
    st.session_state.setdefault("chat_log", [])
    st.session_state.setdefault("recipe_view", None)  # {"recipe_id","dish_name","ingredients_raw","steps"}
    st.session_state.setdefault("pending_dish_name", None)  # no_match -> 등록 유도용
    # listen()의 위젯 키에 붙는 턴 번호. text_input/audio_input 값은 Streamlit 세션에
    # 그대로 남아있어서, goto()의 st.rerun() 이후에도 "다음" 같은 이전 입력이 그대로
    # 다시 읽혀 process_utterance()가 무한 반복 호출되는 버그가 있었다(2026-08-19,
    # AppTest로 발견 — "다음" 한 번 입력했는데 스텝이 끝없이 올라가다 타임아웃).
    # 매번 새 키를 쓰게 해서 이전 위젯 값이 절대 재사용되지 않게 한다.
    st.session_state.setdefault("input_turn", 0)


def goto(screen: str) -> None:
    st.session_state.screen = screen
    st.rerun()


def get_owner_id() -> str | None:
    """쿠키 UUID(작업3, FR-08). 컴포넌트가 없거나 실패해도 서비스는 계속 동작한다 —
    select_standard_recipe()가 owner_id=None을 "개인화 없이 표준만" 취급하도록 이미
    설계돼 있어서(하위 호환), 쿠키가 안 돼도 조회/진행 자체는 죽지 않는다(EC-04와 같은
    "손대지 않는 최소 fallback" 정신)."""
    cached = st.session_state.pipeline_session.get("owner_id")
    if cached:
        return cached
    try:
        from orchestration.identity import build_cookie_manager, get_or_create_anon_id

        cookies = build_cookie_manager()
        if not cookies.ready():
            st.stop()
        anon_id = get_or_create_anon_id(cookies)
        st.session_state.pipeline_session["owner_id"] = anon_id
        return anon_id
    except Exception:
        return None


# ============================================================
# STT / TTS 연결
# ============================================================


def speak(message: str) -> None:
    """TTS로 응답을 재생하고 채팅 로그에 남긴다. 합성 실패는 조용히 삼키지 않는다(EC-05) —
    화면 텍스트는 항상 남고, 음성만 실패했다는 걸 사용자에게 알린다."""
    st.session_state.chat_log.append(("ai", message))
    try:
        from tts.infer import tts_synthesize

        waveform, sample_rate = tts_synthesize(message)
        st.audio(waveform, sample_rate=sample_rate)
    except Exception as exc:  # noqa: BLE001 — 사용자에게 보여줄 실패이지 숨길 실패가 아님
        st.warning(f"음성 재생에 실패했어요(텍스트는 위에 표시돼요): {exc}")


def listen(key_prefix: str) -> str | None:
    """마이크 녹음 또는 텍스트 입력으로 발화 하나를 받는다.

    반환값이 None이면 아직 입력이 없거나(정상) 무음/인식 실패(EC-01)라는 뜻 — 호출부는
    아무 것도 안 하고 다음 rerun을 기다리면 된다. 마이크 권한이 없어도 텍스트 입력으로
    그대로 진행할 수 있다(EC-04).
    """
    turn = st.session_state.input_turn
    audio_file = st.audio_input("말씀해주세요", key=f"{key_prefix}_mic_{turn}")
    typed = st.text_input(
        "또는 텍스트로 입력",
        key=f"{key_prefix}_typed_{turn}",
        placeholder="마이크 대신 직접 타이핑해도 돼요",
    )

    if audio_file is not None:
        data, sample_rate = sf.read(io.BytesIO(audio_file.getvalue()))
        if data.ndim > 1:  # 스테레오면 모노로
            data = data.mean(axis=1)
        from stt.infer import stt_transcribe

        text = stt_transcribe(data.astype(np.float32), sample_rate=sample_rate)
        if not text:
            st.info("잘 못 들었어요. 다시 말씀해주시거나 아래에 텍스트로 입력해주세요.")
            return None
        st.session_state.input_turn += 1  # 다음 rerun에서 새 위젯 키를 쓰게 함(재제출 방지)
        return text

    if typed and typed.strip():
        st.session_state.input_turn += 1
        return typed.strip()

    return None


# ============================================================
# 레시피 표시용 데이터 (recipes 테이블 — handle_utterance() 응답엔 재료 원문이 없음)
# ============================================================


def _fetch_recipe_view(recipe_id: str, client) -> dict:
    row = client.table("recipes").select("*").eq("id", recipe_id).single().execute().data
    steps_result = get_precomputed_steps(recipe_id, client=client)
    return {
        "recipe_id": recipe_id,
        "dish_name": row["dish_name"],
        "ingredients_raw": row.get("ingredients") or "",
        "steps": steps_result.get("steps", []) if steps_result.get("available") else [],
    }


def refresh_recipe_view(force: bool = False) -> None:
    recipe_id = st.session_state.pipeline_session.get("current_recipe_id")
    if not recipe_id:
        st.session_state.recipe_view = None
        return
    cached = st.session_state.recipe_view
    if not force and cached and cached.get("recipe_id") == recipe_id:
        return
    st.session_state.recipe_view = _fetch_recipe_view(recipe_id, get_client())


def _ingredients_to_chips(raw: str) -> list[dict]:
    """"[재료] 두부| 감자| 애호박" 같은 원문 텍스트를 render_chips()가 기대하는
    {"name","qty","emoji"} 목록으로 바꾼다. 실제 DB엔 분량 필드가 따로 없어서(qty는
    재료 문자열 안에 섞여 있음, 예: "애호박 3분의 2개") 통째로 name에 넣고 qty는 비운다
    — 화면 디자인을 새로 짜지 않는 선에서의 최소 변환."""
    import re

    if not raw:
        return []
    text = re.sub(r"\[[^\]]*\]", "", raw)
    items = [seg.strip() for seg in text.split("|") if seg.strip()]
    return [{"name": item, "qty": "", "emoji": "🥕"} for item in items]


# ============================================================
# 발화 처리 (핵심 디스패처) — start/cooking_step/unclassified 화면이 공유
# ============================================================


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
        speak("새 레시피 등록을 도와드릴게요.")
        goto("register_intro")
        return

    intent = result.get("intent")

    if intent == "미분류":
        speak(result.get("fallback_message", "죄송해요, 잘 이해하지 못했어요."))
        goto("unclassified")
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
            speak(step["text"])
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
                    speak(result["step"]["text"])
                goto("cooking_step")


# ============================================================
# 화면
# ============================================================


def screen_start() -> None:
    render_spacer()
    st.markdown(
        '<div class="ce-center"><h1>무엇을 만들고 싶으세요?</h1>'
        "<p>숫자 메뉴 없이, 하고 싶은 말을 편하게 그대로 말씀해주세요.</p>"
        '<p style="color:var(--text-faint); font-size:13.5px;">예: "된장찌개 어떻게 만들어?"</p></div>',
        unsafe_allow_html=True,
    )
    render_big_mic()

    text = listen("start")
    if text:
        process_utterance(text)


def screen_recipe_confirm() -> None:
    view = st.session_state.recipe_view
    if not view:
        goto("start")
        return

    render_badge("조회수 1위 표준 레시피 자동 선택 · 되묻지 않음 (FR-05)")
    render_chat(st.session_state.chat_log)

    st.markdown("**재료 미리보기**")
    render_chips(_ingredients_to_chips(view["ingredients_raw"]))

    # "응"(긍정) 확인은 classify_intent()가 처리하지 않는다(의도적 제외,
    # tests/integration_test.md 기록) — 이 화면 안에서만 문자열로 직접 우회 처리.
    text = listen("recipe_confirm")
    if text:
        norm = text.strip().rstrip("?!. ")
        if norm in ("응", "네", "좋아", "좋아요", "그래", "그래요", "응, 시작할게요"):
            st.session_state.pipeline_session["step_number"] = 1
            speak(view["steps"][0]["text"] if view["steps"] else "1단계 정보를 찾지 못했어요.")
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

    render_badge(f'{view["dish_name"]} · {step_number} / {total} 단계')
    render_step_card(total, step_number, current["text"], minutes=None)

    st.markdown("**오늘의 재료**")
    render_chips(_ingredients_to_chips(view["ingredients_raw"]))

    if st.session_state.chat_log:
        render_chat(st.session_state.chat_log[-4:])

    render_mic_bar("듣는 중", '"다음" · "다시" · "재료 바꾸기"', listening=True)

    text = listen("cooking_step")
    if text:
        process_utterance(text)

    fallback_buttons("cooking_step")


def screen_no_match() -> None:
    render_spacer()
    st.markdown(f'<div class="ce-lead-icon warn">{ICON_X_CIRCLE}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ce-center"><h1>이 조합의 레시피는 없어요</h1>'
        "<p>요리명과 재료 내용, 두 가지 기준으로 모두 찾아봤지만 없어서 정직하게 말씀드려요.</p></div>",
        unsafe_allow_html=True,
    )
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
    st.markdown('<p class="ce-hint">새 레시피 등록 · 1 / 3 · 요리명</p>', unsafe_allow_html=True)
    render_dots(3, 1)
    st.markdown("**어떤 요리인가요?**")

    dish_name = st.text_input(
        "요리명", value=st.session_state.pending_dish_name or "", key="reg_dish_name_input"
    )
    if st.button("다음", type="primary", use_container_width=True):
        if not dish_name.strip():
            st.warning("요리 이름을 입력해주세요.")
        else:
            register_recipe(st.session_state.pipeline_session, "dish_name", dish_name.strip(), client=get_client())
            goto("register_ingredients")
    if st.button("취소", use_container_width=True):
        goto("register_intro")


def screen_register_ingredients() -> None:
    reg = st.session_state.pipeline_session.get("registration")
    if not reg:
        goto("register_intro")
        return

    st.markdown(f'<p class="ce-hint">{reg["dish_name"]} · 2 / 3 · 재료</p>', unsafe_allow_html=True)
    render_dots(3, 2)
    st.markdown("**재료를 알려주세요**")
    render_chips([{"name": ing, "qty": "", "emoji": "🥄"} for ing in reg["ingredients"]])

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

    st.markdown(f'<p class="ce-hint">{reg["dish_name"]} · 3 / 3 · 조리 순서</p>', unsafe_allow_html=True)
    render_dots(3, 3)
    st.markdown("**조리 순서를 알려주세요**")
    for i, step_text in enumerate(reg["instructions"], start=1):
        st.markdown(f"**{i}.** {step_text}")

    new_step = st.text_input("순서 추가", key="reg_step_new", placeholder="새 단계 추가")
    if st.button("단계 추가") and new_step.strip():
        register_recipe(st.session_state.pipeline_session, "instructions", [new_step.strip()], client=get_client())
        st.rerun()

    if reg["instructions"] and st.button("네, 저장할게요", type="primary", use_container_width=True):
        register_recipe(st.session_state.pipeline_session, "confirm", None, client=get_client())
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
    st.markdown(
        '<div style="text-align:center;">'
        f'<span class="ce-status-badge">{ICON_CHECK_SMALL} 원본 레시피 보존됨</span>'
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


SCREENS = {
    "start": screen_start,
    "recipe_confirm": screen_recipe_confirm,
    "cooking_step": screen_cooking_step,
    "no_match": screen_no_match,
    "unclassified": screen_unclassified,
    "register_intro": screen_register_intro,
    "register_dish_name": screen_register_dish_name,
    "register_ingredients": screen_register_ingredients,
    "register_steps": screen_register_steps,
    "complete": screen_complete,
}


def main() -> None:
    st.set_page_config(page_title="ChefEar", page_icon="🍲", layout="centered", initial_sidebar_state="collapsed")
    init_state()
    inject_css()
    render_brand()
    SCREENS[st.session_state.screen]()


if __name__ == "__main__":
    main()
