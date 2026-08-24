"""ChefEar 추론 백엔드 — HF Spaces 유료 GPU(T4)에서 도는 Gradio API 서버.

2026-08-24 프론트(Streamlit Community Cloud)/백엔드(HF Spaces 유료 GPU) 분리 결정
(docs/decisions.md #2)으로 신설. 이전엔 "HF Spaces 하나에 Streamlit + STT/TTS/LLM을
전부 올리는 모놀리식" 안을 검토했었는데(같은 날 먼저 논의됨), 그 안 대신 이 구조로
바뀌었다 — Streamlit 쪽(GPU 없는 Streamlit Cloud)은 UI와 실시간 마이크(WebRTC)만
맡고, 무거운 GPU 추론은 이 Space가 API로 노출한다.

`src/stt/infer.py`·`src/tts/infer.py`·`src/llm/infer.py`는 그대로 재사용한다(로직
변경 없음, 새로 안 만듦) — 이 파일은 그 세 모듈을 Gradio 함수로 감싸서 API로 노출하는
얇은 어댑터일 뿐이다. 프론트 쪽 호출부는 `src/orchestration/inference_backend.py`.

[배포 방법 — 아직 안 함, 결제 후 진행]
1) huggingface.co에서 새 Space 생성 — SDK: Gradio, Hardware: T4
2) 이 저장소 전체를 그 Space의 git remote로 push(레포 루트 구조를 그대로 유지해야
   아래 sys.path 설정이 맞는다 — "src/"가 이 파일과 형제 폴더로 있다고 가정함).
   Space가 실제로 실행할 앱 파일은 Space 자체 설정(README.md 프론트매터의 app_file
   또는 Space 생성 시 지정)에서 이 파일(hf_backend/app.py)로 지정할 것 — 레포 루트의
   README.md(Streamlit용, app_file: src/app.py)와 충돌하지 않게, 이 Space에는
   hf_backend/README.md(아래 참고, sdk: gradio)를 그 Space의 실제 README.md로 써야 함.
3) requirements.txt는 이 폴더의 hf_backend/requirements.txt(무거운 GPU 스택)를
   Space가 쓰게 할 것 — 레포 루트 requirements.txt(Streamlit Cloud용, 가벼움)와는
   역할이 다르다. HF Spaces는 기본적으로 레포 루트의 requirements.txt만 자동 인식하므로,
   Space 저장소 루트를 아예 이 폴더 내용으로 구성하거나(권장) Space 설정에서 경로를
   맞출 것 — 정확한 방법은 실제 Space 생성 시 확인 필요(아직 안 해봄).
4) Space Settings -> Repository secrets: HF_TOKEN(TTS private repo용),
   HF_STT_CT2_REPO=kimseunguk/chefear-stt-ct2-int8 등록
5) Streamlit 쪽(.env 로컬 / Streamlit Cloud secrets)에 HF_BACKEND_SPACE=<계정>/<이
   Space 이름>, HF_TOKEN(이 Space가 private이면) 등록

[아직 검증 못 한 것]
- gradio_client <-> 이 Space 간 실제 왕복(오디오 업로드/응답, JSON 반환)이 설계대로
  동작하는지 — Space가 실제로 뜬 뒤 확인 필요.
- T4에서 bf16 지원 여부·VRAM 여유·CUDA 빌드(torch cu126 가정, hf_backend/requirements.txt
  참고) — 전부 T4 실측 전이라 미확인.
"""
from __future__ import annotations

import sys
from pathlib import Path

import gradio as gr
import numpy as np
import soundfile as sf

BACKEND_ROOT = Path(__file__).resolve().parent
# 배치 구조가 두 가지라 어느 쪽이든 맞게 판단한다(2026-08-24 실제 배포에서
# ModuleNotFoundError: orchestration로 확인된 문제 — 처음엔 "로컬에서 hf_backend/ 밑에
# 중첩, src/는 그 위 폴더의 형제"만 가정했었다):
#   1) 로컬 개발(`python hf_backend/app.py`, hf_backend/README.md 안내대로): 이 파일이
#      <레포 루트>/hf_backend/app.py에 있고, src/는 <레포 루트>/src — 즉 이 파일의
#      부모의 부모.
#   2) 실제 HF Space 배포: Space 저장소 루트에 이 파일을 app.py로 올리고(중첩 없이
#      평탄화), src/ 폴더도 그 루트에 형제로 같이 올린다(hf_backend/README.md 배포
#      방법 참고) — 이 경우 src/는 이 파일의 바로 부모.
# (BACKEND_ROOT / "src")가 있으면 2)번 배치, 없으면 1)번 배치로 판단한다.
if (BACKEND_ROOT / "src").is_dir():
    PROJECT_ROOT = BACKEND_ROOT
else:
    PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from orchestration.db import load_env  # noqa: E402

load_env()


def _api_stt_transcribe(audio_path: str) -> str:
    """gr.Audio(type='filepath') 입력을 stt.infer.stt_transcribe()에 그대로 넘긴다.
    src/orchestration/inference_backend.py의 stt_transcribe_remote()가 이 계약대로
    wav 파일을 업로드한다고 가정한다."""
    from stt.infer import stt_transcribe

    data, sample_rate = sf.read(audio_path)
    if data.ndim > 1:  # 스테레오면 모노로
        data = data.mean(axis=1)
    return stt_transcribe(data.astype(np.float32), sample_rate=sample_rate) or ""


def _api_tts_synthesize(text: str) -> str:
    """반환값은 gr.Audio(type='filepath') — 클라이언트가 로컬로 받은 파일을 soundfile로
    다시 읽어 (waveform, sample_rate)로 쓴다(voice_io.speak()와 같은 반환 계약을 맞추기 위함).
    임시 파일은 요청마다 이름이 겹치지 않게 tempfile을 쓴다(동시 요청 대비)."""
    import tempfile

    from tts.infer import tts_synthesize

    waveform, sample_rate = tts_synthesize(text)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=str(BACKEND_ROOT)) as tmp:
        out_path = tmp.name
    sf.write(out_path, waveform, sample_rate)
    return out_path


def _api_generate_json(prompt: str) -> dict:
    """llm.infer.generate_json()은 실패/불확실 시 None을 돌려주는데(1.5 원칙 — 지어내지
    않음), Gradio의 JSON 출력 컴포넌트는 None을 못 실어서 빈 dict로 감싸 보낸다 —
    inference_backend.generate_json_remote()가 다시 None으로 되돌린다."""
    from llm.infer import generate_json

    result = generate_json(prompt)
    return result or {}


with gr.Blocks(title="ChefEar 추론 백엔드 (내부용 API)") as demo:
    gr.Markdown(
        "## ChefEar STT/TTS/LLM 추론 백엔드\n"
        "Streamlit Cloud 프론트(`src/app.py`)가 `gradio_client`로 이 Space를 원격 호출합니다. "
        "사람이 직접 쓰는 화면이 아니라 API 전용입니다 — 아래 컴포넌트는 API 계약 확인/수동 "
        "디버깅용으로만 남겨뒀습니다."
    )
    with gr.Tab("STT"):
        stt_in = gr.Audio(type="filepath", label="오디오")
        stt_out = gr.Textbox(label="인식 텍스트")
        gr.Button("변환").click(_api_stt_transcribe, stt_in, stt_out, api_name="stt_transcribe")
    with gr.Tab("TTS"):
        tts_in = gr.Textbox(label="문장")
        tts_out = gr.Audio(type="filepath", label="합성 음성")
        gr.Button("합성").click(_api_tts_synthesize, tts_in, tts_out, api_name="tts_synthesize")
    with gr.Tab("LLM"):
        llm_in = gr.Textbox(label="프롬프트")
        llm_out = gr.JSON(label="결과")
        gr.Button("실행").click(_api_generate_json, llm_in, llm_out, api_name="generate_json")

def _warm_up_models() -> None:
    """STT/LLM/TTS 모델을 Gradio 서버가 요청을 받기 시작하기 *전에* 미리 로드해둔다.

    2026-08-24 프론트/백엔드 분리 이전엔 이 워밍업이 src/app.py::_warm_up_models()로
    Streamlit 화면이 뜰 때 실행됐는데, 분리 이후 그 함수는 HF_BACKEND_SPACE가 설정돼
    있으면(=지금 이 배포 구조) 곧장 반환하도록 바뀌었다("여기서 워밍업할 게 없다") —
    실제 모델 로딩은 이제 이 Space(hf_backend)가 전담하는데 여기엔 그 워밍업이 아예
    없어서, 리포트("모델 다운 엄청 오래함") 그대로 **첫 실제 API 요청이 로딩/다운로드
    비용을 통째로 떠안는** 구조였다. src/app.py의 원래 로직(모델별 개별 try/except —
    하나가 실패해도 나머지는 계속 쓸 수 있게, EC-05와 같은 정신)을 그대로 옮기되, 여긴
    Streamlit이 아니라서 st.spinner/st.warning 대신 print()로 진행 상황을 남긴다(HF
    Space 빌드/시작 로그에서 그대로 보임).

    load_ct2_model()/load_llm()/load_tts_model() 셋 다 전역 캐시(각 모듈의 `_model`류
    전역 변수)라서 여기서 한 번 불러두면, 그 뒤 _api_stt_transcribe() 등이 실제로
    호출될 때는 이미 로드된 모델을 즉시 재사용한다(비용 없음) — src/app.py 문서의
    설명과 동일.
    """
    print("[WARMUP] STT 모델 준비 중...", flush=True)
    try:
        from stt.infer import load_ct2_model

        load_ct2_model()
    except Exception as exc:  # noqa: BLE001 — 하나 실패해도 나머지 워밍업/서버 시작은 계속
        print(f"[WARMUP] STT 모델 준비 실패(첫 실제 요청 때 다시 시도됨): {exc!r}", flush=True)

    print("[WARMUP] LLM(EXAONE) 모델 준비 중...", flush=True)
    try:
        from llm.infer import load_llm

        load_llm()
    except Exception as exc:  # noqa: BLE001
        print(f"[WARMUP] LLM 모델 준비 실패(첫 실제 요청 때 다시 시도됨): {exc!r}", flush=True)

    print("[WARMUP] TTS(Qwen3-TTS) 모델 준비 중...", flush=True)
    try:
        from tts.infer import load_tts_model

        load_tts_model()
    except Exception as exc:  # noqa: BLE001
        print(f"[WARMUP] TTS 모델 준비 실패(첫 실제 요청 때 다시 시도됨): {exc!r}", flush=True)

    print("[WARMUP] 완료", flush=True)


if __name__ == "__main__":
    _warm_up_models()
    demo.queue().launch()
