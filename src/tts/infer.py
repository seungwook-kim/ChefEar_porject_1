"""ChefEar TTS - 런타임 음성 합성 (조리 단계 안내 문장 등을 음성으로).

[모델]
Base:
    Qwen/Qwen3-TTS-12Hz-1.7B-Base

QLoRA 파인튜닝 + merge_and_unload (KSS 데이터셋):
    kimseunguk/qwen3-tts-kss-finetuned (private repo)

[2026-08-19] 13에포크 체크포인트로 교체하면서 `tts_model_type`이 "base"로 바뀌었다(이전
체크포인트는 "custom_voice"였음, `config.json`으로 실측 확인). base 타입은
generate_custom_voice()를 지원하지 않아서(모델 자체에 화자 임베딩 테이블이 없음, `spk_id={}`),
레퍼런스 음성으로 목소리를 복제하는 generate_voice_clone() 방식으로 전환했다. 레퍼런스는
`assets/kss_reference.wav`(KSS 원본 음성 000008번, `data/kss/metadata.csv` 대본과 페어) —
Qwen 공식 데모의 영어 샘플이 아니라 실제 KSS 화자 목소리를 쓰기 위해 이걸로 골랐다.

혹시 나중에 custom_voice 타입 체크포인트로 되돌아가는 경우를 대비해 그 경로도 남겨뒀다
(SPEAKER="kss_speaker" — 화자명이 "kss_speaker_a100"이 아니라 "kss_speaker"로 심어져 있었음,
2026-08-18 실측 확인). `load_tts_model()`이 로드한 모델의 `tts_model_type`을 보고 자동으로
분기한다.

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

from orchestration.db import load_env
from tts.pronunciation import apply_pronunciation_fixes

# db.py의 get_client()와 동일한 방식 — python-dotenv 없이 .env를 os.environ에 채워 넣는다.
# 아래 MODEL_ID가 이 시점의 os.environ을 바로 읽으므로, HF_TOKEN을 쓰는 load_tts_model()보다
# 먼저(모듈 import 시점에) 호출해야 한다.
load_env()

# ============================================================
# 모델 설정
# ============================================================

# .env의 HF_TTS_MODEL_REPO로 덮어쓸 수 있게 하되(.env.example.local 참고), 기본값은 확정된 모델로 고정.
MODEL_ID = os.environ.get("HF_TTS_MODEL_REPO") or "kimseunguk/qwen3-tts-kss-finetuned"


# custom_voice 타입 체크포인트로 되돌아갈 경우를 대비한 화자명("kss_speaker_a100"이 아니라
# "kss_speaker"로 심어져 있었음, 2026-08-18 실측 확인).
SPEAKER = "kss_speaker"

# base 타입 체크포인트(현재 기준, 2026-08-19)의 목소리 복제용 레퍼런스 — KSS 원본 음성.
_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
VOICE_CLONE_REF_AUDIO = str(_ASSETS_DIR / "kss_reference.wav")
VOICE_CLONE_REF_TEXT = "나는 살아오면서 감기를 앓은 적이 한 번도 없다."  # data/kss/metadata.csv 000008



# 모델은 최초 1번만 로드하고 이후 호출에서 재사용
_model = None

# base 타입 체크포인트일 때만 쓰는 voice-clone 프롬프트 — 레퍼런스 오디오가 고정이라 최초
# 1번만 만들고 재사용(모델 로드와 마찬가지로 매 합성마다 다시 만들 필요 없음).
_voice_clone_prompt = None


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


    print(f"[TTS] 모델 로드 완료: {MODEL_ID} (device={device_map}, attn={attn_impl})")


    return _model


# ============================================================
# 런타임 음성 합성
# ============================================================

# qwen_tts 기본값은 max_new_tokens=2048(라이브러리 하드 디폴트) — do_sample=True(확률적
# 샘플링)와 같이 쓰이다 보니, 운이 나쁘면(멈춤 토큰을 늦게 뽑으면) 짧은 문장도 최대치까지
# 생성을 계속해서 실측상 20배 이상 느려지는 경우가 있었다(2026-08-17 확인). ChefEar는 조리
# 안내 한 문장(몇 초 분량)만 읽으면 되므로 훨씬 낮게 잡아도 충분하다.
# 170→180→190→195→200→300 순으로 실측(2026-08-19, 재료 분수 표현이 많은 긴 문장 기준) —
# 이 문장의 자연 완결 지점은 약 191토큰(15.92초)이라 200 이상이어야 안 잘린다. 195로
# 확정했다가 팀원이 195에서도 잘린다는 걸 확인해줘서 250으로 재조정(2026-08-19).
# 200/300 실측상 200 이상은 자연 완결됐으니 250도 여유 있게 안전할 것으로 판단
# (src/tts/README.md 실측 결과 ③ 참고).
DEFAULT_MAX_NEW_TOKENS = 250

# do_sample=True(확률적 샘플링)라 시드 고정 없이는 같은 문장도 호출마다 결과가 달라진다
# (2026-08-19 확인: 그동안 시드 고정이 전혀 없었음). 재현 가능한 테스트/비교를 위해 매
# 합성 직전에 이 시드로 리셋한다(팀원 노트북 test_epoch1_inference2.ipynb와 동일 패턴).
DEFAULT_SEED = 42


def tts_synthesize(
    text: str,
    *,
    language: str = "Korean",
    instruct: str = "",
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    seed: int = DEFAULT_SEED,
) -> tuple[np.ndarray, int]:
    """조리 안내 문장 하나 -> (waveform, sample_rate).

    호출부(app.py/pipeline.py)가 반환값을 st.audio(waveform, sample_rate=sample_rate)에
    그대로 넘기면 재생된다. 파일로 저장해야 하면 soundfile.write(path, waveform, sample_rate)를
    호출부에서 직접 쓰면 된다(이 함수는 파일 I/O를 하지 않음).
    """

    global _voice_clone_prompt

    torch.manual_seed(seed)

    if torch.cuda.is_available():

        torch.cuda.manual_seed_all(seed)

    model = load_tts_model()

    model_type = getattr(model.model, "tts_model_type", None)

    # 화면 표시/로그/DB용 원문(text)은 그대로 두고, TTS에 넘길 사본에만 발음 보정을 적용.
    tts_text = apply_pronunciation_fixes(text)

    if model_type == "base":

        # custom_voice 화자 임베딩이 없는 체크포인트 — 레퍼런스 음성으로 목소리를 복제해서 생성.
        if _voice_clone_prompt is None:

            _voice_clone_prompt = model.create_voice_clone_prompt(
                ref_audio=VOICE_CLONE_REF_AUDIO,
                ref_text=VOICE_CLONE_REF_TEXT,
            )

        wavs, sample_rate = model.generate_voice_clone(

            text=tts_text,

            language=language,

            voice_clone_prompt=_voice_clone_prompt,

            max_new_tokens=max_new_tokens,
        )

    elif model_type == "custom_voice":

        wavs, sample_rate = model.generate_custom_voice(

            text=tts_text,

            language=language,

            speaker=SPEAKER,

            instruct=instruct,

            max_new_tokens=max_new_tokens,
        )

    else:

        raise ValueError(
            f"tts_synthesize()가 아직 지원하지 않는 tts_model_type={model_type!r} "
            f"({MODEL_ID})"
        )

    return wavs[0], sample_rate
