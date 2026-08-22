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
import os
import sys
import threading
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
from orchestration.registration import delete_recipe, register_recipe, update_recipe

from theme import (
    ICON_BASKET_SM,
    ICON_CHECK_CIRCLE,
    ICON_CHECK_SMALL,
    ICON_QUESTION_CIRCLE,
    ICON_SPARKLE,
    ICON_X_CIRCLE,
    inject_css,
    render_audio_autoplay,
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
    render_typewriter_message,
)

load_env()

# 2026-08-21: 로그인 화면의 목업 계정 아이디/비밀번호가 소스에 리터럴로 박혀 있어서
# (CWE-798, 하드코딩된 자격증명) PR 리뷰에서 거부됐다 — .env의 TEST_LOGIN_ID/
# TEST_LOGIN_PASSWORD로 옮기고, 소스에는 값 자체를 남기지 않는다(다른 자격증명과
# 같은 방식 — orchestration/db.py의 SUPABASE_URL/KEY, orchestration/identity.py의
# COOKIE_SECRET 참고). .env에 없으면 로그인 화면 자체를 막는다(fallback으로 다시
# 하드코딩된 기본값을 두면 같은 문제가 재발함).
TEST_LOGIN_ID = os.environ.get("TEST_LOGIN_ID")
TEST_LOGIN_PASSWORD = os.environ.get("TEST_LOGIN_PASSWORD")

# 2026-08-21: st.audio()는 Streamlit이 rerun마다 <audio> 태그를 새로 만드는 방식이라
# 자동재생은 물론 수동 재생 버튼도 안 먹히는 문제가 실측으로 확인됐다(브라우저에서 재생
# 버튼을 눌러도 반응 없음). 대신 ui/streamlit_screens/cooking_step.py에서 이미 실제로
# 잘 작동하는 render_audio_player()(진짜 <audio autoplay> + JS 우회)를 그대로 쓴다 —
# 그 화면이 쓰는 것과 같은 ui/assets/audio/ 경로를 그대로 재사용해서, 같은 레시피의
# 조리 단계 음성 캐시를 두 앱이 같이 쓸 수 있게 한다(2026-08-20 실측: 문장당 최대
# 4분 걸리는 로컬 CPU 합성을 두 번 반복하지 않아도 됨).
_AUDIO_DIR = PROJECT_ROOT / "ui" / "assets" / "audio"

# 2026-08-22: TTS 합성 자체는 GPU에서도 문장 길이에 따라 3~9초 걸리는 게 실측으로 확인됐고
# (docs/decisions.md #2), torch.compile 등으로 더 줄이려는 시도는 재컴파일 스톨 위험이 더
# 커서 보류했다(합성 속도 자체는 그대로 두기로 함) — 대신 다음 조리 단계 음성을 사용자가
# 지금 단계를 듣고 있는 동안 백그라운드에서 미리 합성해둬서, 실제 "다음" 발화 시점엔
# 이미 캐싱돼 있게 만든다(prefetch_next_step_audio() 참고). 이 락은 백그라운드 프리페치와
# speak()의 실시간 합성이 동시에 같은 GPU 모델 인스턴스를 호출하는 걸 막는다 — qwen_tts
# 모델이 동시 호출에 안전한지 보장이 없어서, 항상 한 번에 하나씩만 GPU에 올리게 직렬화한다.
_TTS_LOCK = threading.Lock()

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
    """speak()로 이미 이 문구를 말한 적 있다면(캐시 존재) 음성만 자동재생한다(재생바는 없음).

    screen_cooking_step()과 같은 이유로 필요하다 — speak()가 그 자리에서 그리는
    재생 위젯은 바로 뒤따르는 goto()의 st.rerun()에 지워진다. 그래서 이 문구로
    전환해 들어온 화면 자신이 매번 다시 그려질 때도 캐시를 직접 찾아 재생해야
    실제로 음성이 나온다. 캐시가 아직 없으면(예: speak() 실패) 조용히 아무것도 안
    한다 — 화면 텍스트는 이미 위에 따로 표시돼 있어서다.

    2026-08-21: "저장이 완료됐어요!" 화면에서 재생바(원형 버튼+파형)는 안 보이고
    음성만 나오면 좋겠다는 요청으로 render_audio_player() 대신 화면 없는
    render_audio_autoplay()를 쓴다.
    """
    path = _common_audio_path(message)
    if path.exists():
        render_audio_autoplay(path)


def speak(
    message: str,
    *,
    recipe_id: str | None = None,
    step_number: int | None = None,
    hidden: bool = False,
) -> None:
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

    hidden=True: register_steps의 "네, 저장할게요"처럼 speak() 직후 바로 goto()로
    다른 화면으로 넘어가는 호출부에서 쓴다. render_audio_player()(재생바)로 그려도
    goto()의 st.rerun()이 곧장 화면을 바꿔버려서 재생바가 "떴다가 사라지는" 것처럼
    보일 뿐 실제로 남지도 않는데, 그 순간 그려지는 재생바 자체가 화면 깜빡임으로
    보인다는 지적(2026-08-21)으로 추가됨 — 합성/캐싱은 그대로 하되 화면에는
    render_audio_autoplay()(화면 없는 자동재생)만 그린다. 도착 화면이 같은 문구를
    _render_cached_speech()로 다시 찾아 들려주는 경우, 실제로 들리는 소리는 그쪽이다.
    """
    st.session_state.chat_log.append(("ai", message))
    try:
        if recipe_id and step_number:
            audio_path = _AUDIO_DIR / str(recipe_id) / f"{step_number:02d}.wav"
        else:
            audio_path = _common_audio_path(message)

        if not audio_path.exists():
            # 2026-08-19 팀 결정(docs/decisions.md #2)으로 배포가 GPU 데스크탑 상시 노출로
            # 확정되면서 tts.infer.load_tts_model()이 CPU 폴백 없이 GPU를 필수로 요구한다 —
            # "로컬 CPU라 오래 걸릴 수 있어요" 문구는 더 이상 해당하지 않아 제거했다.
            with st.spinner("음성 합성 중이에요... 잠시만 기다려주세요."):
                # prefetch_next_step_audio()의 백그라운드 스레드와 동시에 GPU 모델을
                # 호출하지 않도록 _TTS_LOCK으로 직렬화(위 정의부 주석 참고). 프리페치가
                # 이미 이 문구를 캐싱해뒀다면 락을 기다리는 동안 아래 audio_path.exists()가
                # True가 될 수 있어, 락 안에서 한 번 더 확인해 중복 합성을 피한다.
                with _TTS_LOCK:
                    if not audio_path.exists():
                        from tts.infer import tts_synthesize

                        waveform, sample_rate = tts_synthesize(message)
                        audio_path.parent.mkdir(parents=True, exist_ok=True)
                        sf.write(audio_path, waveform, sample_rate)

        if hidden:
            render_audio_autoplay(audio_path)
        else:
            render_audio_player(audio_path)
    except Exception as exc:  # noqa: BLE001 — 사용자에게 보여줄 실패이지 숨길 실패가 아님
        st.warning(f"음성 재생에 실패했어요(텍스트는 위에 표시돼요): {exc}")


def _synthesize_and_cache(text: str, audio_path: Path) -> None:
    """백그라운드 스레드에서 실행되는 합성 함수 — speak()와 캐싱 규칙은 같지만 st.* API를
    전혀 안 쓴다(Streamlit 위젯 호출은 ScriptRunContext가 있는 메인 스레드에서만 안전해서,
    백그라운드 스레드에서 st.spinner/st.warning 등을 쓰면 경고가 뜨거나 깨질 수 있음).
    실패해도 조용히 넘어간다 — 프리페치일 뿐이라 실패하면 나중에 speak()가 그 자리에서
    다시 시도한다(EC-05는 speak() 쪽에서 이미 담당)."""
    if audio_path.exists():
        return
    try:
        with _TTS_LOCK:
            if audio_path.exists():
                return
            from tts.infer import tts_synthesize

            waveform, sample_rate = tts_synthesize(text)
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(audio_path, waveform, sample_rate)
    except Exception:  # noqa: BLE001 — 프리페치 실패는 speak()가 다시 시도하므로 조용히 넘어감
        pass


def prefetch_next_step_audio(view: dict, step_number: int) -> None:
    """지금 보고 있는 조리 단계 화면에서, 다음 단계 음성을 백그라운드에서 미리 합성해
    캐싱해둔다. TTS 합성 자체는 GPU에서도 문장 길이에 따라 3~9초 걸리는 게 실측됐고
    (docs/decisions.md #2), 더 줄이려던 torch.compile 시도는 재컴파일 스톨 위험으로
    보류했다(2026-08-22) — 그래서 합성 속도 자체 대신, 사용자가 지금 단계를 읽거나
    요리하며 마이크에 말을 거는 그 시간(수 초~수십 초) 동안 다음 단계를 미리 합성해서,
    실제로 "다음"이라고 말했을 때는 이미 캐싱된 파일을 즉시 재생하게 만든다 — 체감
    속도 개선.

    같은 (recipe_id, step_number) 조합에 대해 세션당 한 번만 스레드를 띄운다
    (st.session_state의 "_prefetch_started" 집합으로 추적) — screen_cooking_step()이
    매 rerun(마이크 입력 대기 등)마다 다시 호출돼도 스레드가 중복으로 쌓이지 않게 한다.
    """
    steps = view["steps"]
    if step_number >= len(steps):  # 이미 마지막 단계 — 다음 단계 없음
        return

    next_step = steps[step_number]  # steps는 0-indexed라 steps[step_number]가 다음 단계
    recipe_id = view["recipe_id"]
    next_step_number = next_step.get("step_number", step_number + 1)
    audio_path = _AUDIO_DIR / str(recipe_id) / f"{next_step_number:02d}.wav"
    if audio_path.exists():
        return

    started = st.session_state.setdefault("_prefetch_started", set())
    key = (recipe_id, next_step_number)
    if key in started:
        return
    started.add(key)

    threading.Thread(
        target=_synthesize_and_cache,
        args=(next_step["text"], audio_path),
        daemon=True,
    ).start()


def listen(key_prefix: str, *, show_mic: bool = True) -> str | None:
    """마이크 녹음 또는 텍스트 입력으로 발화 하나를 받는다.

    반환값이 None이면 아직 입력이 없거나(정상) 무음/인식 실패(EC-01)라는 뜻 — 호출부는
    아무 것도 안 하고 다음 rerun을 기다리면 된다. 마이크 권한이 없어도 텍스트 입력으로
    그대로 진행할 수 있다(EC-04).

    show_mic=False면 실제 녹음 위젯(st.audio_input, "말씀해주세요" 라벨 + 녹음 버튼)을
    안 그린다 — register_intro처럼 화면에 이미 "듣는 중" 표시줄이 따로 있어서 녹음
    위젯까지 있으면 마이크 안내가 중복돼 보이는 화면에서 쓴다(2026-08-21). 텍스트
    입력 대체 경로는 이 경우에도 그대로 남는다.
    """
    turn = st.session_state.input_turn
    audio_file = st.audio_input("말씀해주세요", key=f"{key_prefix}_mic_{turn}") if show_mic else None
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
    return [{"name": item, "qty": "", "emoji": "🟠"} for item in items]


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
    # 한 글자씩 나타나는 순수 텍스트로 보여준다. 세 줄 문구는 process_utterance()의
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


# ============================================================
# 신규 등록 플로우(no_match -> register_intro -> ... -> complete) 안내 문구
# ============================================================
# register_recipe()가 돌려주는 prompt/summary는 대화 중간(재료·순서 누적)에만 있고,
# 화면 전환 시점의 고정 안내문(인트로/순서 질문 등)은 없다 — 그 화면 자신이 자신의
# 안내문을 "무슨 말을 했는지" 알아야 _render_cached_speech()로 같은 캐시를 다시 찾을
# 수 있어서, 전환 직전(호출부)과 도착 화면 양쪽이 똑같이 이 함수들을 불러 쓴다.
# (register_intro 자체는 2026-08-21부터 음성 안내를 뺐다 — 아래 screen_register_intro()
# 참고. _register_intro_message()는 그때 쓰던 문구 생성 함수라 지금은 안 쓰지만, 다시
# 음성을 붙일 수도 있어 남겨뒀었는데 완전히 안 쓰이는 게 확인돼 제거함.)


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

    st.markdown(f'<p class="ce-hint">{reg["dish_name"]} · 2 / 3 · 재료</p>', unsafe_allow_html=True)
    render_dots(3, 2)
    st.markdown("**재료를 알려주세요**")
    render_chips([{"name": ing, "qty": "", "emoji": "🥄"} for ing in reg["ingredients"]])

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

    st.markdown(f'<p class="ce-hint">{reg["dish_name"]} · 3 / 3 · 조리 순서</p>', unsafe_allow_html=True)
    render_dots(3, 3)
    st.markdown("**조리 순서를 알려주세요**")
    if reg["instructions"]:
        steps_html = "".join(
            f'<div class="ce-step-row"><span class="ce-step-num">{i}</span><p>{step_text}</p></div>'
            for i, step_text in enumerate(reg["instructions"], start=1)
        )
        st.markdown(f'<div class="ce-step-list">{steps_html}</div>', unsafe_allow_html=True)

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


# ============================================================
# 마이 레시피(로그인 -> 내가 등록한 레시피 목록 -> 수정/삭제)
# ============================================================
# 목업 로그인이다 — 실제 회원가입/비밀번호 저장 없이 .env의 TEST_LOGIN_ID/
# TEST_LOGIN_PASSWORD 계정 하나만으로 확인한다(2026-08-21, 소스 하드코딩 제거).
# 이 로그인은 FR-08의 쿠키 owner_id(누가 어떤
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
    render_spacer()

    if not TEST_LOGIN_ID or not TEST_LOGIN_PASSWORD:
        st.error("로그인이 아직 설정되지 않았어요 — .env에 TEST_LOGIN_ID/TEST_LOGIN_PASSWORD를 채워주세요.")
        return

    user_id = st.text_input("아이디", key="login_id_input")
    password = st.text_input("비밀번호", type="password", key="login_pw_input")
    if st.button("로그인", type="primary", use_container_width=True):
        if user_id == TEST_LOGIN_ID and password == TEST_LOGIN_PASSWORD:
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
            c1, c_actions = st.columns([5, 2])
            with c1:
                st.markdown(
                    f'<div class="ce-recipe-name"><span class="icon">{ICON_BASKET_SM}</span>{row["dish_name"]}</div>',
                    unsafe_allow_html=True,
                )
            with c_actions:
                # st.columns([1,1])는 c_actions 칸 자체가 넓어지면 두 버튼도 같이
                # 벌어진다(각 컬럼이 그 절반씩을 차지) - 화면이 넓을수록 간격이
                # 커지는 문제가 실측으로 확인됐다(2026-08-21). 컬럼 대신 세로
                # 블록 하나에 버튼 둘을 넣고 CSS로 가로 정렬 + 오른쪽 붙임
                # 처리해서, 화면 폭과 무관하게 항상 붙어있게 한다.
                with st.container(key=f"my_recipe_actions_{row['id']}"):
                    if st.button(":material/edit:", key=f"edit_{row['id']}", help="수정"):
                        st.session_state.editing_recipe_id = row["id"]
                        goto("edit_recipe")
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


def _warm_up_models() -> None:
    """STT/LLM/TTS 모델을 화면이 뜨는 시점에 미리 로드해둔다(`tests/test_ui.py`와 동일 패턴).

    셋 다 첫 로딩 비용이 있어서(원인은 서로 다름, 아래 참고) 미리 안 해두면 사용자가
    실제로 말을 걸거나("start" 화면 listen()) 첫 응답을 들을 때(speak()) 그 비용을
    그대로 보게 된다 — speak()/listen()/process_utterance()가 stt.infer.stt_transcribe,
    tts.infer.tts_synthesize, orchestration.entity_extract_llm.extract_dish_name_llm을
    그 자리에서 lazy import해서 쓰기 때문이다. load_ct2_model()/load_llm()/
    load_tts_model() 셋 다 전역 캐시라서(stt/infer.py의 _ct2_model, llm/infer.py의
    _model, tts/infer.py의 전역 캐시) 이미 로드됐으면 즉시 반환 — 매 rerun(사용자
    조작)마다 이 함수를 다시 호출해도 안전하고 빠르다.

    STT: 처음엔 "CUDA 초기화가 느리다"고 짐작했으나(2026-08-20), 실측해보니 GPU/CPU
    사용률이 로딩 내내 0%였다 — 프로젝트 폴더가 네트워크 공유 드라이브(CIFS, ~9MB/s)에
    있어서 model.bin(778MB) 읽기 자체가 87초 걸렸던 것. .env의 STT_LOCAL_CACHE_DIR로
    로컬 디스크 사본을 우선 읽게 고쳐서 1.2초로 줄었다(`src/stt/infer.py` 참고).
    LLM: EXAONE 가중치는 원래 ~/.cache/huggingface(로컬 디스크)에 캐시되므로 이 문제가
    없다 — 최초 1회 인터넷에서 받는 것만 느리고(수 분), 그다음부턴 13초 정도로 빠르다.
    TTS: LLM과 마찬가지로 ~/.cache/huggingface에서 읽어서 네트워크 드라이브 문제는
    없다 — 7.9GB 모델이라 로딩 자체에 17초 정도 걸리는 게 정상(실측).

    test_ui.py는 파일 하나짜리 수동 테스트 화면이라 로딩 실패 시 그냥 죽어도 되지만,
    이 파일(app.py)은 실제 서비스 화면 전체를 띄우는 진입점이다 — 세 모델 중 하나라도
    준비가 안 돼 있으면(예: 아직 `src/stt/export_ct2.py`로 변환 전이라 CT2 모델이 없는
    개발 환경) 여기서 예외가 그대로 올라가 화면 자체가 뜨지도 못하고 죽는다. speak()가
    이미 따르는 EC-05 원칙(화면 텍스트는 항상 남고, 음성 관련 실패만 사용자에게 알림)과
    똑같이 각 모델 로딩을 개별로 감싸서, 준비 안 된 모델이 있어도 앱은 계속 뜨고 나머지
    기능(텍스트 입력 흐름 등)은 그대로 쓸 수 있게 한다.
    """
    from llm.infer import load_llm
    from stt.infer import load_ct2_model
    from tts.infer import load_tts_model

    with st.spinner("STT 모델 준비 중... (최초 1회만, 몇 초 걸릴 수 있음)"):
        try:
            load_ct2_model()
        except Exception as exc:  # noqa: BLE001 — EC-05, 화면은 계속 뜨게 함
            st.warning(f"STT 모델을 준비하지 못했어요(음성 인식이 안 될 수 있어요, 텍스트 입력은 계속 됩니다): {exc}")

    with st.spinner("LLM(EXAONE) 모델 준비 중... (최초 1회는 다운로드로 몇 분 걸릴 수 있음)"):
        try:
            load_llm()
        except Exception as exc:  # noqa: BLE001
            st.warning(f"LLM 모델을 준비하지 못했어요(요리명 추출이 안 될 수 있어요): {exc}")

    with st.spinner("TTS(Qwen3-TTS) 모델 준비 중... (약 17초, 최초 1회만)"):
        try:
            load_tts_model()
        except Exception as exc:  # noqa: BLE001
            st.warning(f"TTS 모델을 준비하지 못했어요(음성 응답이 안 나올 수 있어요, 텍스트는 계속 표시돼요): {exc}")


def main() -> None:
    st.set_page_config(page_title="ChefEar", page_icon="🍲", layout="centered", initial_sidebar_state="collapsed")
    init_state()
    _warm_up_models()
    inject_css()
    # 로그인 아이콘은 start 화면에서만 "ChefEar" 제목과 나란히 보여준다(2026-08-21 요청).
    if render_brand(show_login=(st.session_state.screen == "start")):
        goto("login")
    SCREENS[st.session_state.screen]()


if __name__ == "__main__":
    main()

