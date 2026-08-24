"""HF Spaces 유료 GPU 백엔드 원격 호출 클라이언트 — 2026-08-24 프론트/백엔드 분리 결정.

[배경]
Streamlit Community Cloud(프론트, `src/app.py`)는 GPU가 없다. STT(faster-whisper)/
TTS(Qwen3-TTS)/LLM(EXAONE)은 그대로 `src/stt/infer.py`·`src/tts/infer.py`·
`src/llm/infer.py`에 남아있지만, 이 세 모듈은 이제 이 Streamlit 프로세스가 아니라
별도 HF Spaces 유료 GPU(T4) Space(`hf_backend/app.py`, Gradio SDK)에서 돈다. 이
파일은 그 Space를 `gradio_client`로 원격 호출하는 얇은 클라이언트다 — `stt_transcribe`/
`tts_synthesize`/`generate_json`과 함수 시그니처(입출력)를 최대한 맞춰서, 호출부
(`src/ui/voice_io.py`, `src/orchestration/entity_extract_llm.py`)가 로컬/원격 여부를
거의 신경 안 쓰게 한다.

[아직 안 된 것 — 결제 후 실제 확인 필요]
`hf_backend/`가 실제 Space로 배포되고 `HF_BACKEND_SPACE`가 설정되기 전까진 아래
함수들은 전부 RuntimeError를 던진다(EC-05 — 호출부가 이미 try/except로 감싸고
"음성 인식이 안 될 수 있어요" 식으로 사용자에게 알린다, 서비스 자체는 안 죽는다).
gradio_client의 실제 요청/응답 형식은 `hf_backend/app.py`의 Gradio 컴포넌트 타입과
맞춰 설계했지만, 진짜 Space에 대고 실행해서 확인한 적은 없다 — Space를 띄운 뒤
`tests/`에 왕복 테스트를 추가해서 검증할 것.

[설정]
.env 또는 Streamlit Cloud secrets:
    HF_BACKEND_SPACE=<계정>/<space-이름>   (예: kimseunguk/chefear-backend)
    HF_TOKEN=<Space가 private일 때만 필요>
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from orchestration.db import load_env

load_env()

BACKEND_SPACE = os.environ.get("HF_BACKEND_SPACE")
_TOKEN = os.environ.get("HF_TOKEN")

_client = None  # gradio_client.Client — 첫 호출 때 만들어서 재사용(연결 비용 절약)


def backend_configured() -> bool:
    """HF_BACKEND_SPACE가 설정돼 있어 원격 백엔드를 쓸 수 있는 상태인지.

    호출부가 "원격 백엔드 vs 로컬 직접 로드" 중 어느 경로를 탈지 고르는 스위치로 쓴다
    (로컬 직접 로드는 requirements-main.txt 전체 스택이 깔린 개발 환경 전용).
    """
    return bool(BACKEND_SPACE)


def _get_client():
    global _client
    if _client is None:
        if not BACKEND_SPACE:
            raise RuntimeError(
                "HF_BACKEND_SPACE가 설정 안 됨 — 원격 추론 백엔드(HF Spaces 유료 GPU)가 "
                "아직 배포/연결되지 않았습니다. hf_backend/README.md 참고해서 Space를 "
                "만들고 .env(로컬) 또는 Streamlit Cloud secrets(배포)에 HF_BACKEND_SPACE를 "
                "등록할 것."
            )
        from gradio_client import Client  # 지연 import — 이 함수가 실제로 불릴 때만 필요

        _client = Client(BACKEND_SPACE, hf_token=_TOKEN)
    return _client


def stt_transcribe_remote(audio: np.ndarray, sample_rate: int) -> str:
    """`stt.infer.stt_transcribe(audio, sample_rate=...)`와 같은 계약(입력 오디오 ->
    인식 텍스트) — hf_backend의 `/stt_transcribe` 엔드포인트로 wav 파일을 올려서 부른다.

    gr.Audio(type="filepath") 입력이라 파일로 먼저 써야 한다(원시 배열을 JSON으로
    직렬화해서 보내는 것보다 gradio_client 표준 패턴 — 업로드가 훨씬 효율적).
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        sf.write(tmp_path, audio, sample_rate)
        result = _get_client().predict(tmp_path, api_name="/stt_transcribe")
        return result or ""
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def tts_synthesize_remote(text: str) -> tuple[np.ndarray, int]:
    """`tts.infer.tts_synthesize(text)`와 같은 계약((waveform, sample_rate) 반환) —
    hf_backend의 `/tts_synthesize`가 wav 파일 경로를 돌려주면 그걸 다시 읽어서 맞춘다.
    """
    result_path = _get_client().predict(text, api_name="/tts_synthesize")
    waveform, sample_rate = sf.read(result_path)
    return waveform.astype(np.float32), sample_rate


def generate_json_remote(prompt: str) -> dict | None:
    """`llm.infer.generate_json(prompt)`와 같은 계약 — 형식 오류/실패 시 None(1.5 원칙,
    그럴듯하게 지어내지 않음). hf_backend는 None 대신 빈 dict `{}`를 돌려주므로(Gradio
    JSON 컴포넌트가 None을 못 실어서) 여기서 다시 None으로 되돌린다.
    """
    result = _get_client().predict(prompt, api_name="/generate_json")
    return result or None
