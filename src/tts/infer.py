"""ChefEar TTS - 런타임 음성 합성 (조리 단계 안내 문장 등을 음성으로).

[모델]
Base:
    Qwen/Qwen3-TTS-12Hz-1.7B-Base

QLoRA 파인튜닝 + merge_and_unload (KSS 데이터셋):
    kimseunguk/qwen3-tts-kss-finetuned (private repo)

파인튜닝 시 화자 임베딩을 spk_id 3000에 "kss_speaker_a100"이라는 이름으로 심어뒀기 때문에
(train_qwen3_tts.py 참고), 합성은 사전학습 CustomVoice 모델과 동일한 generate_custom_voice()
경로를 그대로 쓰고 speaker만 이 이름으로 지정하면 된다.

private repo라 로딩에 HF_TOKEN이 필요하다(.env, HF Spaces 배포 시엔 Repository secret으로 등록).

[호출 예시]

from src.tts.infer import tts_synthesize

waveform, sample_rate = tts_synthesize("약불로 5분간 끓여주세요")
# app.py에서: st.audio(waveform, sample_rate=sample_rate)
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import torch
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# ============================================================
# 모델 설정
# ============================================================

# .env의 HF_TTS_MODEL_REPO로 덮어쓸 수 있게 하되(.env.example.local 참고), 기본값은 확정된 모델로 고정.
MODEL_ID = os.environ.get("HF_TTS_MODEL_REPO") or "kimseunguk/qwen3-tts-kss-finetuned"

SPEAKER = "kss_speaker_a100"


# 모델은 최초 1번만 로드하고 이후 호출에서 재사용
_model = None


# ============================================================
# TTS 모델 로드
# ============================================================

def load_tts_model():

    global _model

    # 이미 모델이 로드되어 있으면 재사용
    if _model is not None:

        return _model


    from qwen_tts import Qwen3TTSModel


    token = os.environ.get("HF_TOKEN")

    if not token:

        raise RuntimeError(
            f"HF_TOKEN이 필요함 ({MODEL_ID}는 private repo) — .env에 설정하거나 "
            "HF Spaces 배포 시엔 Repository secret으로 등록할 것"
        )


    if torch.cuda.is_available():

        device_map, dtype = "cuda:0", torch.bfloat16

    else:

        # HF Spaces CPU Basic 배포 환경 — tests/tts_cpu_inference_test.py의 실측 조건과 동일하게 맞춤
        device_map, dtype = "cpu", torch.float32

        torch.set_num_threads(2)


    try:

        import flash_attn  # noqa: F401

        attn_impl = "flash_attention_2"

    except ImportError:

        attn_impl = "sdpa"


    _model = Qwen3TTSModel.from_pretrained(

        MODEL_ID,

        token=token,

        device_map=device_map,

        dtype=dtype,

        attn_implementation=attn_impl,
    )


    print(f"✅ ChefEar TTS 모델 로드 완료: {MODEL_ID} (device={device_map}, attn={attn_impl})")


    return _model


# ============================================================
# 런타임 음성 합성
# ============================================================

def tts_synthesize(
    text: str,
    *,
    language: str = "Korean",
    instruct: str = "",
) -> tuple[np.ndarray, int]:
    """조리 안내 문장 하나 -> (waveform, sample_rate).

    호출부(app.py/pipeline.py)가 반환값을 st.audio(waveform, sample_rate=sample_rate)에
    그대로 넘기면 재생된다. 파일로 저장해야 하면 soundfile.write(path, waveform, sample_rate)를
    호출부에서 직접 쓰면 된다(이 함수는 파일 I/O를 하지 않음).
    """

    model = load_tts_model()

    wavs, sample_rate = model.generate_custom_voice(

        text=text,

        language=language,

        speaker=SPEAKER,

        instruct=instruct,
    )

    return wavs[0], sample_rate
