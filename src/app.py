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
from orchestration.entity_extract import extract_dish_name, extract_substitution_ingredients
from orchestration.pipeline import get_precomputed_steps, handle_utterance, manual_fallback
from orchestration.registration import (
    _final_summary,
    _ingredient_summary,
    delete_recipe,
    register_recipe,
    update_recipe,
)

from theme import (
    ICON_BASKET_SM,
    ICON_CHECK_CIRCLE,
    ICON_CHECK_SMALL,
    ICON_QUESTION_CIRCLE,
    ICON_SPARKLE,
    ICON_X_CIRCLE,
    inject_css,
    render_audio_player,
    render_back_link,
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

# 2026-08-21: st.audio()는 Streamlit이 rerun마다 <audio> 태그를 새로 만드는 방식이라
# 자동재생은 물론 수동 재생 버튼도 안 먹히는 문제가 실측으로 확인됐다(브라우저에서 재생
# 버튼을 눌러도 반응 없음). 대신 ui/streamlit_screens/cooking_step.py에서 이미 실제로
# 잘 작동하는 render_audio_player()(진짜 <audio autoplay> + JS 우회)를 그대로 쓴다 —
# 그 화면이 쓰는 것과 같은 ui/assets/audio/ 경로를 그대로 재사용해서, 같은 레시피의
# 조리 단계 음성 캐시를 두 앱이 같이 쓸 수 있게 한다(2026-08-20 실측: 문장당 최대
# 4분 걸리는 로컬 CPU 합성을 두 번 반복하지 않아도 됨).
_AUDIO_DIR = PROJECT_ROOT / "ui" / "assets" / "audio"

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
    # 마이 레시피(로그인 -> 내가 등록한 레시피 목록 -> 수정/삭제) 관련 상태.
    # logged_in은 목업 로그인(test/1234) 성공 여부만 기억한다 — 실제 회원 시스템이
    # 아니라서 세션이 끝나면(브라우저 새로고침 등) 다시 로그인해야 한다.
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("editing_recipe_id", None)  # edit_recipe 화면이 수정 중인 레시피
    st.session_state.setdefault("confirm_delete_id", None)  # my_recipes 화면의 삭제 확인 대상
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


def _common_audio_path(message: str) -> Path:
    """조리 단계처럼 recipe_id/step_number가 없는 1회성 문구(확인 질문·안내 등)의
    캐시 경로 — 문구 자체의 해시를 키로 쓴다. speak()와 _render_cached_speech()가
    같은 문구에 대해 항상 같은 경로를 계산해야 캐시가 서로 맞물린다."""
    import hashlib

    digest = hashlib.sha1(message.encode("utf-8")).hexdigest()[:16]
    return _AUDIO_DIR / "_common" / f"{digest}.wav"


def _render_cached_speech(message: str) -> None:
    """speak()로 이미 이 문구를 말한 적 있다면(캐시 존재) 재생바를 다시 그린다.

    screen_cooking_step()과 같은 이유로 필요하다 — speak()가 그 자리에서 그리는
    재생 위젯은 바로 뒤따르는 goto()의 st.rerun()에 지워진다. 그래서 이 문구로
    전환해 들어온 화면 자신이 매번 다시 그려질 때도 캐시를 직접 찾아 보여줘야
    실제로 화면에 남아있는 재생바가 된다. 캐시가 아직 없으면(예: speak() 실패)
    조용히 아무것도 안 그린다 — 화면 텍스트는 이미 위에 따로 표시돼 있어서다.
    """
    path = _common_audio_path(message)
    if path.exists():
        render_audio_player(path)


def speak(message: str, *, recipe_id: str | None = None, step_number: int | None = None) -> None:
    """TTS로 응답을 재생하고 채팅 로그에 남긴다. 합성 실패는 조용히 삼키지 않는다(EC-05) —
    화면 텍스트는 항상 남고, 음성만 실패했다는 걸 사용자에게 알린다.

    2026-08-21: st.audio()는 Streamlit이 rerun마다 <audio> 태그를 새로 만드는 방식이라
    자동재생·수동 재생 버튼 둘 다 안 먹히는 문제가 실측으로 확인됐다(브라우저에서 재생
    버튼을 눌러도 무반응). 대신 ui/streamlit_screens/cooking_step.py에서 이미 실제로
    잘 작동하는 render_audio_player()(진짜 <audio autoplay> + JS 우회)를 그대로 쓴다.

    recipe_id·step_number가 둘 다 주어지면(=이 메시지가 특정 레시피의 특정 조리 단계
    안내문일 때) ui/assets/audio/<recipe_id>/<step:02d>.wav로 캐싱한다 — cooking_step.py와
    같은 경로 규칙이라 두 화면이 같은 캐시를 공유한다. 그 외(확인 메시지·에러 안내 등
    1회성 문구)는 문구 자체의 해시를 캐시 키로 써서, 자주 반복되는 고정 문구
    ("1단계예요, 이전 단계가 없어요." 등)도 같이 재사용된다. 둘 다 로컬 CPU 기준
    문장당 최대 몇 분 걸리는 재합성을 피하기 위함이다(2026-08-20 실측).
    """
    st.session_state.chat_log.append(("ai", message))
    try:
        if recipe_id and step_number:
            audio_path = _AUDIO_DIR / str(recipe_id) / f"{step_number:02d}.wav"
        else:
            audio_path = _common_audio_path(message)

        if not audio_path.exists():
            from tts.infer import tts_synthesize

            with st.spinner("음성 합성 중이에요... 로컬 CPU라 오래 걸릴 수 있어요(최대 몇 분). 잠시만 기다려주세요."):
                waveform, sample_rate = tts_synthesize(message)
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(audio_path, waveform, sample_rate)

        render_audio_player(audio_path)
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

    import time as _t
    with open(r"C:\Users\hlkm1\AppData\Local\Temp\claude\c--Users-hlkm1-Desktop-minha-portpolio-chefEar\74e331ba-ea6f-44df-b612-02d394d3af74\scratchpad\_debug_process_utterance.log", "a", encoding="utf-8") as _f:
        _f.write(f"{_t.time()} LISTEN turn={turn} audio_file_is_none={audio_file is None}\n")

    if audio_file is not None:
        data, sample_rate = sf.read(io.BytesIO(audio_file.getvalue()))
        if data.ndim > 1:  # 스테레오면 모노로
            data = data.mean(axis=1)
        from stt.infer import stt_transcribe

        text = stt_transcribe(data.astype(np.float32), sample_rate=sample_rate)
        with open(r"C:\Users\hlkm1\AppData\Local\Temp\claude\c--Users-hlkm1-Desktop-minha-portpolio-chefEar\74e331ba-ea6f-44df-b612-02d394d3af74\scratchpad\_debug_process_utterance.log", "a", encoding="utf-8") as _f:
            _f.write(f"{_t.time()} STT_RESULT turn={turn} audio_bytes={len(audio_file.getvalue())} duration_sec={len(data)/sample_rate:.3f} text={text!r}\n")
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
    return [{"name": item, "qty": "", "emoji": "⭐"} for item in items]


# ============================================================
# 발화 처리 (핵심 디스패처) — start/cooking_step/unclassified 화면이 공유
# ============================================================


def process_utterance(text: str) -> None:
    import time as _t
    with open(r"C:\Users\hlkm1\AppData\Local\Temp\claude\c--Users-hlkm1-Desktop-minha-portpolio-chefEar\74e331ba-ea6f-44df-b612-02d394d3af74\scratchpad\_debug_process_utterance.log", "a", encoding="utf-8") as _f:
        _f.write(f"{_t.time()} CALLED text={text!r}\n")
    st.session_state.chat_log.append(("user", text))

    session = st.session_state.pipeline_session
    client = get_client()

    dish_name_guess = extract_dish_name(text)
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
        speak(_register_intro_message())
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
        # "다시"는 같은 파일을 다시 재생하는 거라 오디오 콘텐츠 자체가 안 바뀌어서
        # nonce 없이는 iframe이 안 바뀐 걸로 보고 autoplay가 재실행되지 않는다. "다음"/
        # "이전"도 이전에 방문했던 단계로 돌아갈 때(예: 2단계->1단계->2단계) 같은 문제가
        # 재현될 수 있어 세 경우 모두 매번 nonce를 올려 항상 새로 로드되게 한다(theme.py
        # render_audio_player() 참고).
        st.session_state["_audio_replay_nonce"] = st.session_state.get("_audio_replay_nonce", 0) + 1
        if result.get("no_previous"):
            speak("1단계예요, 이전 단계가 없어요.")
        elif step is None:
            speak("마지막 단계까지 다 왔어요. 수고하셨어요!")
        else:
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
                st.session_state["_audio_replay_nonce"] = st.session_state.get("_audio_replay_nonce", 0) + 1
                result = manual_fallback(session, button, client=client)
                if result.get("no_previous"):
                    speak("1단계예요, 이전 단계가 없어요.")
                elif result.get("step") is None:
                    speak("마지막 단계까지 다 왔어요. 수고하셨어요!")
                else:
                    speak(
                        result["step"]["text"],
                        recipe_id=session.get("current_recipe_id"),
                        step_number=result["step"].get("step_number"),
                    )
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
        if norm in ("응", "네", "좋아", "좋아요", "그래", "그래요", "시작", "응, 시작할게요"):
            st.session_state.pipeline_session["step_number"] = 1
            if view["steps"]:
                first_step = view["steps"][0]
                speak(first_step["text"], recipe_id=view["recipe_id"], step_number=first_step.get("step_number", 1))
            else:
                speak("1단계 정보를 찾지 못했어요.")
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

    # 2026-08-21: speak()가 만드는 재생 위젯은 그 직후 goto()의 st.rerun()으로 화면이
    # 바로 새로고침되면서 같이 사라진다 — speak() 안에서 렌더링한 건 "그 rerun 전까지만"
    # 유효하다. 그래서 이 화면(cooking_step) 자체가 매번 다시 그려질 때도 캐시된 오디오를
    # 직접 찾아서 render_step_card()에 넘겨야 실제로 화면에 남아있는 재생바가 된다
    # (speak()가 쓰는 것과 같은 ui/assets/audio/<recipe_id>/<step:02d>.wav 캐시 경로).
    cached_audio_path = _AUDIO_DIR / str(view["recipe_id"]) / f"{step_number:02d}.wav"
    if cached_audio_path.exists():
        render_step_card(
            total,
            step_number,
            current["text"],
            audio_path=cached_audio_path,
            audio_nonce=st.session_state.get("_audio_replay_nonce", 0),
        )
    else:
        render_step_card(total, step_number, current["text"])

    st.markdown("**오늘의 재료**")
    render_chips(_ingredients_to_chips(view["ingredients_raw"]))

    if st.session_state.chat_log:
        render_chat(st.session_state.chat_log[-4:])

    render_mic_bar("듣는 중", '"다음" · "다시" · "재료 바꾸기"', listening=True)

    text = listen("cooking_step")
    if text:
        process_utterance(text)

    fallback_buttons("cooking_step")


# ============================================================
# 신규 등록 플로우(no_match -> register_intro -> ... -> complete) 안내 문구
# ============================================================
# register_recipe()가 돌려주는 prompt/summary는 대화 중간(재료·순서 누적)에만 있고,
# 화면 전환 시점의 고정 안내문(인트로/순서 질문 등)은 없다 — 그 화면 자신이 자신의
# 안내문을 "무슨 말을 했는지" 알아야 _render_cached_speech()로 같은 캐시를 다시 찾을
# 수 있어서, 전환 직전(호출부)과 도착 화면 양쪽이 똑같이 이 함수들을 불러 쓴다.


def _register_intro_message() -> str:
    dish_hint = st.session_state.pending_dish_name or "그 요리"
    return f"{dish_hint}는 표준 레시피 안에는 없지만, 직접 알려주시면 회원님 레시피로 등록해드릴게요. 등록할까요?"


_REGISTER_DISH_NAME_PROMPT = "어떤 요리인가요? 요리 이름을 말씀해주세요."
_REGISTER_STEPS_PROMPT = "조리 순서를 알려주세요. 한 단계씩 말씀해주시면 돼요."
_REGISTER_SAVED_MESSAGE = "저장이 완료됐어요!"


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
            speak(_register_intro_message())
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
    _render_cached_speech(_register_intro_message())
    render_spacer()
    render_mic_bar("듣는 중", '"네" 또는 "등록할래요"라고 말해보세요', listening=True)

    text = listen("register_intro")
    if text:
        norm = text.strip().rstrip("?!. ")
        if norm in ("네", "응", "좋아", "좋아요", "그래", "그래요", "등록", "등록할래요", "네, 등록할래요"):
            get_owner_id()
            speak(_REGISTER_DISH_NAME_PROMPT)
            goto("register_dish_name")
        elif norm in ("아니", "아니요", "괜찮아", "괜찮아요", "취소"):
            goto("start")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("네, 등록할래요", type="primary", use_container_width=True):
            get_owner_id()
            speak(_REGISTER_DISH_NAME_PROMPT)
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
    if st.session_state.pending_dish_name:
        st.caption(f'짐작한 이름: "{st.session_state.pending_dish_name}" — 맞으면 "네", 다르면 이름을 말씀해주세요')
    _render_cached_speech(_REGISTER_DISH_NAME_PROMPT)
    render_mic_bar("듣는 중", "요리 이름을 말씀해주세요", listening=True)

    text = listen("register_dish_name")
    if text:
        norm = text.strip().rstrip("?!. ")
        if norm in ("네", "응", "맞아", "맞아요", "그래", "그래요") and st.session_state.pending_dish_name:
            dish_name = st.session_state.pending_dish_name
        else:
            dish_name = text.strip()
        result = register_recipe(st.session_state.pipeline_session, "dish_name", dish_name, client=get_client())
        speak(result["prompt"])
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
    if reg["ingredients"]:
        _render_cached_speech(_ingredient_summary(reg["ingredients"]))
    render_mic_bar("듣는 중", '재료를 말씀해주세요 (다 됐으면 "맞아요")', listening=True)

    text = listen("register_ingredients")
    if text:
        norm = text.strip().rstrip("?!. ")
        is_confirm = norm in ("네", "응", "맞아요", "됐어요", "다 됐어요", "그래요")
        if is_confirm and reg["ingredients"]:
            speak(_REGISTER_STEPS_PROMPT)
            goto("register_steps")
        elif is_confirm:
            # 재료를 하나도 안 넣은 채로 확인 발화만 온 경우 — "맞아요"를 재료로
            # 잘못 등록하지도, 다음 화면으로 그냥 넘기지도 않는다. 대신 왜 안
            # 넘어가는지 화면에 분명히 알려준다(전에는 여기서 아무 반응 없이
            # 조용히 무시돼서 먹통처럼 보이는 문제가 있었다, 2026-08-21).
            st.warning('아직 재료를 안 알려주셨어요. 재료를 먼저 말씀해주세요.')
        else:
            items = [x.strip() for x in text.split(",") if x.strip()]
            result = register_recipe(st.session_state.pipeline_session, "ingredients", items, client=get_client())
            speak(result["summary"])
            st.rerun()

    if reg["ingredients"] and st.button("네, 맞아요", type="primary", use_container_width=True):
        speak(_REGISTER_STEPS_PROMPT)
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
    if reg["instructions"]:
        _render_cached_speech(_final_summary(reg["ingredients"], reg["instructions"]))
    render_mic_bar("듣는 중", '한 단계씩 말씀해주세요 (다 됐으면 "저장해줘")', listening=True)

    text = listen("register_steps")
    if text:
        norm = text.strip().rstrip("?!. ")
        is_confirm = norm in ("네", "응", "저장", "저장해줘", "저장할게요", "맞아요")
        if is_confirm and reg["instructions"]:
            register_recipe(st.session_state.pipeline_session, "confirm", None, client=get_client())
            speak(_REGISTER_SAVED_MESSAGE)
            goto("complete")
        elif is_confirm:
            # register_ingredients와 같은 이유 — 순서를 하나도 안 넣은 채 "저장해줘"만
            # 오면 조용히 무시하지 않고 왜 안 되는지 알려준다.
            st.warning("아직 조리 순서를 안 알려주셨어요. 순서를 먼저 말씀해주세요.")
        else:
            result = register_recipe(
                st.session_state.pipeline_session, "instructions", [text.strip()], client=get_client()
            )
            speak(result["summary"])
            st.rerun()

    if reg["instructions"] and st.button("네, 저장할게요", type="primary", use_container_width=True):
        register_recipe(st.session_state.pipeline_session, "confirm", None, client=get_client())
        speak(_REGISTER_SAVED_MESSAGE)
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


# ============================================================
# 마이 레시피(로그인 -> 내가 등록한 레시피 목록 -> 수정/삭제)
# ============================================================
# 목업 로그인이다 — 실제 회원가입/비밀번호 저장 없이 아이디 "test"/비밀번호 "1234"
# 하나만 하드코딩해서 확인한다. 이 로그인은 FR-08의 쿠키 owner_id(누가 어떤
# user_custom을 등록했는지 익명 식별)와는 별개 개념이라, 로그인 성공 후 보여주는
# "내가 등록한 레시피"는 계정별로 걸러내지 않고 source="user_custom"인 레시피 전체를
# 보여준다 — 목업 계정이 하나뿐이라 계정별 소유권을 구분할 방법 자체가 없어서다.


def screen_login() -> None:
    if render_back_link("첫화면으로 가기"):
        goto("start")

    render_spacer()
    st.markdown(
        '<div class="ce-center"><h1>로그인</h1>'
        "<p>등록한 레시피를 관리하려면 로그인해주세요.</p></div>",
        unsafe_allow_html=True,
    )
    st.caption("테스트 계정: 아이디 test / 비밀번호 1234")
    render_spacer()

    user_id = st.text_input("아이디", key="login_id_input")
    password = st.text_input("비밀번호", type="password", key="login_pw_input")
    if st.button("로그인", type="primary", use_container_width=True):
        if user_id == "test" and password == "1234":
            st.session_state.logged_in = True
            goto("my_recipes")
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않아요.")


def screen_my_recipes() -> None:
    if not st.session_state.logged_in:
        goto("login")
        return
    if render_back_link("첫화면으로 가기"):
        goto("start")

    client = get_client()
    rows = (
        client.table("recipes")
        .select("id,dish_name,created_at")
        .eq("source", "user_custom")
        .order("created_at", desc=True)
        .execute()
        .data
    )

    render_badge(f"내가 등록한 레시피 · {len(rows)}개")

    if not rows:
        st.info("아직 등록한 레시피가 없어요.")
        return

    confirm_id = st.session_state.confirm_delete_id
    for row in rows:
        with st.container(key=f"my_recipe_card_{row['id']}"):
            c1, c2, c3 = st.columns([6, 1, 1])
            with c1:
                st.markdown(
                    f'<div class="ce-recipe-name"><span class="icon">{ICON_BASKET_SM}</span>{row["dish_name"]}</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button(":material/edit:", key=f"edit_{row['id']}", help="수정"):
                    st.session_state.editing_recipe_id = row["id"]
                    goto("edit_recipe")
            with c3:
                if st.button(":material/delete:", key=f"delete_{row['id']}", help="삭제"):
                    st.session_state.confirm_delete_id = row["id"]
                    st.rerun()

            if confirm_id == row["id"]:
                st.warning(f'"{row["dish_name"]}"를 정말 삭제할까요? 되돌릴 수 없어요.')
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button(
                        "네, 삭제할게요", key=f"confirm_delete_{row['id']}", type="primary", use_container_width=True
                    ):
                        delete_recipe(row["id"], client=client)
                        st.session_state.confirm_delete_id = None
                        st.rerun()
                with cc2:
                    if st.button("취소", key=f"cancel_delete_{row['id']}", use_container_width=True):
                        st.session_state.confirm_delete_id = None
                        st.rerun()


def screen_edit_recipe() -> None:
    recipe_id = st.session_state.editing_recipe_id
    if not recipe_id:
        goto("my_recipes")
        return

    client = get_client()
    recipe = client.table("recipes").select("*").eq("id", recipe_id).single().execute().data
    steps = (
        client.table("recipe_steps")
        .select("step_number,step_text")
        .eq("recipe_id", recipe_id)
        .order("step_number")
        .execute()
        .data
    )

    if render_back_link("첫화면으로 가기"):
        st.session_state.editing_recipe_id = None
        goto("start")

    st.markdown(f'**{recipe["dish_name"]} 수정**')

    dish_name = st.text_input("요리명", value=recipe["dish_name"], key="edit_dish_name")
    ingredients_text = st.text_area(
        "재료 (쉼표로 구분)", value=recipe.get("ingredients") or "", key="edit_ingredients"
    )
    instructions_text = st.text_area(
        "조리 순서 (한 줄에 한 단계씩)",
        value="\n".join(s["step_text"] for s in steps),
        key="edit_instructions",
        height=200,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("저장", type="primary", use_container_width=True):
            ingredients = [x.strip() for x in ingredients_text.split(",") if x.strip()]
            instructions = [x.strip() for x in instructions_text.split("\n") if x.strip()]
            update_recipe(recipe_id, dish_name.strip(), ingredients, instructions, client=client)
            st.session_state.editing_recipe_id = None
            goto("my_recipes")
    with c2:
        if st.button("취소", use_container_width=True):
            st.session_state.editing_recipe_id = None
            goto("my_recipes")


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
    "login": screen_login,
    "my_recipes": screen_my_recipes,
    "edit_recipe": screen_edit_recipe,
}


def main() -> None:
    st.set_page_config(page_title="ChefEar", page_icon="🍲", layout="centered", initial_sidebar_state="collapsed")
    init_state()
    inject_css()
    # 로그인 아이콘은 start 화면에서만 "ChefEar" 제목과 나란히 보여준다(2026-08-21 요청).
    if render_brand(show_login=(st.session_state.screen == "start")):
        goto("login")
    SCREENS[st.session_state.screen]()


if __name__ == "__main__":
    main()

