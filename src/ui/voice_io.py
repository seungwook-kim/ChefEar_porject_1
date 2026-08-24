"""ChefEar STT/TTS 연결(speak/listen) — src/app.py에서 분리(2026-08-22, 화면 컴포넌트화).

세션 상태는 ui/session.py, 발화 디스패처는 ui/dispatch.py, 화면별 함수는 ui/screens/ 참고.
"""
from __future__ import annotations

import io
import threading
from pathlib import Path

import numpy as np
import soundfile as sf
import streamlit as st

from orchestration.inference_backend import (
    backend_configured,
    stt_transcribe_remote,
    tts_synthesize_remote,
)
from theme import render_audio_autoplay, render_audio_player

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _stt_transcribe(audio: np.ndarray, sample_rate: int) -> str:
    """`stt.infer.stt_transcribe`를 직접 부르는 대신 이 얇은 래퍼를 거친다 — 2026-08-24
    프론트/백엔드 분리 결정으로, HF_BACKEND_SPACE가 설정돼 있으면(Streamlit Cloud 배포)
    원격 호출하고, 없으면(로컬 전체 스택 개발 환경) 기존처럼 로컬에서 직접 로드해 쓴다."""
    if backend_configured():
        return stt_transcribe_remote(audio, sample_rate)
    from stt.infer import stt_transcribe  # 지연 import — 로컬 전체 스택 환경에서만 필요

    return stt_transcribe(audio, sample_rate=sample_rate)


def _tts_synthesize(text: str) -> tuple[np.ndarray, int]:
    """`_stt_transcribe`와 같은 이유의 로컬/원격 분기 — TTS 버전."""
    if backend_configured():
        return tts_synthesize_remote(text)
    from tts.infer import tts_synthesize  # 지연 import — 로컬 전체 스택 환경에서만 필요

    return tts_synthesize(text)

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
            # 2026-08-22 요청 — 버튼 바로 아래 "음성 합성 중이에요..." 글씨가 튀어
            # 보인다는 지적으로 문구는 없애고 스피너 아이콘만 남긴다.
            with st.spinner(""):
                # prefetch_next_step_audio()의 백그라운드 스레드와 동시에 GPU 모델을
                # 호출하지 않도록 _TTS_LOCK으로 직렬화(위 정의부 주석 참고). 프리페치가
                # 이미 이 문구를 캐싱해뒀다면 락을 기다리는 동안 아래 audio_path.exists()가
                # True가 될 수 있어, 락 안에서 한 번 더 확인해 중복 합성을 피한다.
                with _TTS_LOCK:
                    if not audio_path.exists():
                        waveform, sample_rate = _tts_synthesize(message)
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
            waveform, sample_rate = _tts_synthesize(text)
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
        text = _stt_transcribe(data.astype(np.float32), sample_rate)
        if not text:
            st.info("잘 못 들었어요. 다시 말씀해주시거나 아래에 텍스트로 입력해주세요.")
            return None
        st.session_state.input_turn += 1  # 다음 rerun에서 새 위젯 키를 쓰게 함(재제출 방지)
        return text

    if typed and typed.strip():
        st.session_state.input_turn += 1
        return typed.strip()

    return None


def listen_realtime(key_prefix: str, on_utterance) -> None:
    """상시 마이크(WebRTC 실시간) — 2026-08-24 추가, `listen()`의 클릭-녹음-전송 방식과
    달리 마이크를 켜두면 계속 듣고 있다가 말이 끝날 때마다 자동으로 인식한다.

    `ui/streamlit_screens/stt_tts_test.py`의 실험적 `_render_always_on_mic()` 패턴을
    프로덕션으로 옮긴 것(2026-08-24 요청) — STT 호출만 `_stt_transcribe()`(로컬/원격
    분기)로 바꿨다. `on_utterance(text)` 콜백으로 인식된 발화를 넘긴다 — 이 모듈이
    `ui.dispatch`를 직접 import하면 dispatch.py가 이미 `ui.voice_io.speak`를 가져다 쓰는
    구조라 순환 import가 생겨서(ui/README.md의 계층 방향 참고), 호출부(화면)가
    `dispatch.process_utterance`를 직접 넘겨주는 방식으로 피했다.

    streamlit-webrtc 표준 실시간 처리 패턴 그대로 — webrtc가 재생 중인 동안 이 함수
    안에서 while 루프를 돌며 프레임을 계속 받는다. 이 루프가 도는 동안은 이 함수를
    호출한 화면의 나머지 렌더링이 멈춰 있으므로, 상태 표시(듣는 중/인식 중)를 이 함수
    안에서 st.empty() 플레이스홀더로 직접 그린다. 마이크를 끄면 루프가 끝나고 화면
    나머지가 정상적으로 계속 그려진다.

    ⚠️ 원격 백엔드(HF Spaces)를 쓸 때는 발화 하나마다 오디오를 업로드해 왕복하므로,
    로컬 직접 호출보다 지연이 클 수 있다 — 아직 실측 못 했음, Space 배포 후 확인 필요.
    """
    from streamlit_webrtc import WebRtcMode, webrtc_streamer

    webrtc_ctx = webrtc_streamer(
        key=f"{key_prefix}_realtime_mic",
        mode=WebRtcMode.SENDONLY,
        audio_receiver_size=256,
        media_stream_constraints={"video": False, "audio": True},
        rtc_configuration=_ice_servers(),
    )

    status_ph = st.empty()

    if not webrtc_ctx.state.playing:
        status_ph.caption("상시 마이크가 꺼져 있어요. 위 Start를 눌러 켜주세요.")
        return

    segmenter_key = f"{key_prefix}_mic_segmenter"
    if segmenter_key not in st.session_state:
        from mic_vad import MicVadSegmenter  # ui/ 최상위 폴더(theme.py와 같은 위치) 모듈

        st.session_state[segmenter_key] = MicVadSegmenter()
    segmenter = st.session_state[segmenter_key]

    import queue

    status_ph.info("🎙️ 듣고 있어요...")
    while webrtc_ctx.state.playing:
        if webrtc_ctx.audio_receiver is None:
            break
        try:
            audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
        except queue.Empty:
            continue

        for frame in audio_frames:
            utterance_audio = segmenter.feed(frame.to_ndarray(), frame.sample_rate)
            if utterance_audio is None:
                continue

            status_ph.info("🧠 인식 중...")
            text = _stt_transcribe(utterance_audio, 16000)
            if text.strip():
                on_utterance(text)
            status_ph.info("🎙️ 듣고 있어요...")

    status_ph.caption("상시 마이크가 꺼졌어요.")


def _ice_servers() -> dict:
    """TURN 서버 설정 — 2026-08-24 기준 실제 TURN 발급(Metered.ca 가입 등)은 아직 보류
    (팀 결정, HF Spaces T4 배포 작업 논의 당시 미룸). 코드는 .env의 TURN_HOST/
    TURN_USERNAME/TURN_PASSWORD/TURN_PORT가 있으면 자동으로 읽어 구글 공개 STUN에
    더해 쓰도록 미리 만들어뒀다 — TURN_HOST가 비어있으면(지금 기본 상태) STUN만
    쓴다. 나중에 Metered.ca 등에서 값을 받으면 .env/Space secret에 채우기만 하면
    되고, 이 함수는 손댈 필요 없다. Streamlit Cloud처럼 인바운드 UDP를 넓게 못 여는
    호스트에서는 STUN만으로 연결 안 되는 클라이언트가 있을 수 있다(발신자가 대칭형
    NAT 뒤에 있는 경우 등) — 실제로 그런 사례가 확인되면 그때 TURN을 발급받아 채운다."""
    import os

    servers = [{"urls": ["stun:stun.l.google.com:19302"]}]
    turn_host = os.environ.get("TURN_HOST")
    if turn_host:
        servers.append(
            {
                "urls": [f"turn:{turn_host}:{os.environ.get('TURN_PORT', '3478')}"],
                "username": os.environ.get("TURN_USERNAME", ""),
                "credential": os.environ.get("TURN_PASSWORD", ""),
            }
        )
    return {"iceServers": servers}
