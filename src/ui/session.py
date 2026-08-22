"""ChefEar 세션 상태 부트스트랩·화면 전환 — src/app.py에서 분리(2026-08-22, 화면 컴포넌트화).

speak()/listen() 같은 STT/TTS 연결은 ui/voice_io.py, 화면별 함수는 ui/screens/ 참고.

주의: 이 패키지 이름(`ui`)은 `src/app.py`가 `sys.path.insert(0, PROJECT_ROOT/"ui")`로
따로 얹는 최상위 `ui/`(theme.py 등, `from theme import ...`로 씀) 폴더와 이름이 같지만
서로 다른 경로다 — 이쪽은 `src/ui/`이고 `src`가 sys.path에 있어서 `ui.session`처럼
패키지로 import된다. 헷갈리지 않도록 참고.
"""
from __future__ import annotations

import streamlit as st

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
