"""
ChefEar STT Runtime / Evaluation

Base Model:
    openai/whisper-large-v3-turbo

QLoRA Adapter:
    leeony/chefear-stt-large-v3-turbo

핵심 처리 흐름
--------------
audio
→ Whisper STT
→ 단위 표기 정규화
→ 현재 레시피 재료 문맥이 있을 때만 고위험 패턴 조건부 보정
→ 최종 텍스트

중요
----
숫자를 무조건 변경하지 않습니다.

예:
    "소고기다짐 600그램"
        ↓

현재 레시피 재료에
    "소고기다짐육 100그램" 존재
그리고
    "소고기다짐육 600그램" 없음

위 조건을 모두 만족할 때만
    "소고기다짐육 100그램"
으로 보정합니다.
"""

from pathlib import Path
from typing import Optional, Sequence, Union

import os
import re

import librosa
import numpy as np
import pandas as pd
import torch

from jiwer import wer
from peft import PeftModel
from transformers import (
    BitsAndBytesConfig,
    WhisperForConditionalGeneration,
    WhisperProcessor,
)

from orchestration.db import load_env

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# python-dotenv는 requirements-stt.txt(학습 전용)에만 있고 배포용 requirements.txt에는
# 없다 — src/tts/infer.py와 동일하게 orchestration.db.load_env()를 재사용해서 새 의존성
# 없이 .env를 읽는다(2026-08-19, tests/integration_issues_2026-08-18.md 이슈 #3 수정). 이
# import가 성립하려면 호출부가 미리 sys.path에 "src"를 넣어둬야 한다(tts/infer.py와 동일한
# 전제 — tests/conftest.py, tests/tts_stt_roundtrip_test.py가 이미 그렇게 하고 있음).
load_env()

# ============================================================
# 모델 설정
# ============================================================

MODEL_ID = "openai/whisper-large-v3-turbo"

HF_ADAPTER_ID = (
    os.environ.get("HF_STT_MODEL_REPO")
    or "leeony/chefear-stt-large-v3-turbo"
)


# 모델은 최초 1번만 로드하고 계속 재사용
_processor: Optional[WhisperProcessor] = None
_model = None
_input_dtype: Optional[torch.dtype] = None


# ============================================================
# 고위험 재료 사전
# ============================================================

# canonical:
# 실제 ChefEar에서 사용할 표준 재료명
#
# risky_patterns:
# STT 고위험군 테스트에서 실제 반복 확인된 표현
#
# 숫자는 여기에서 지정하지 않습니다.
# 숫자 보정 여부는 현재 레시피 문맥을 확인한 뒤 결정합니다.

HIGH_RISK_INGREDIENTS = {
    "소고기다짐육": [
        r"소고기\s*다짐육",
        r"소고기\s*다짐",
        r"소고기\s*다진",
    ],

    "돼지고기다짐육": [
        r"돼지고기\s*다짐육",
        r"돼지고기\s*다짐",
        r"돼지고기\s*다진",
    ],

    "한우다짐육": [
        r"한우\s*다짐육",
        r"한우\s*다짐",
        r"한우\s*다진",
    ],

    "다짐육": [
        r"(?<![가-힣])다짐육",
        r"(?<![가-힣])다짐",
    ],
}


# ============================================================
# 입력 dtype 확인
# ============================================================

def get_input_dtype(model) -> torch.dtype:
    """
    Whisper encoder 입력 dtype을 확인합니다.
    """

    for name, module in model.named_modules():

        if name.endswith("encoder.conv1"):

            if hasattr(module, "bias") and module.bias is not None:
                return module.bias.dtype

    return torch.float16


# ============================================================
# STT 모델 로드
# ============================================================

def load_stt_model():
    """
    Whisper Base + ChefEar QLoRA Adapter를 로드합니다.

    최초 1회만 로드하고 이후 호출에서는 재사용합니다.
    """

    global _processor
    global _model
    global _input_dtype

    # 이미 모델이 로드되어 있으면 재사용
    if _model is not None and _processor is not None:
        return _model, _processor


    # --------------------------------------------------------
    # Processor
    # --------------------------------------------------------

    try:

        _processor = WhisperProcessor.from_pretrained(
            HF_ADAPTER_ID
        )

        print(
            "✅ Processor: "
            "Hugging Face Adapter Repo에서 로드"
        )

    except Exception:

        _processor = WhisperProcessor.from_pretrained(
            MODEL_ID
        )

        print(
            "⚠ Processor: "
            "Base Model에서 로드"
        )


    # --------------------------------------------------------
    # 4bit QLoRA 설정
    # --------------------------------------------------------

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )


    # --------------------------------------------------------
    # Whisper Base Model
    # --------------------------------------------------------

    base_model = (
        WhisperForConditionalGeneration
        .from_pretrained(
            MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
        )
    )

    base_model.config.forced_decoder_ids = None

    base_model.generation_config.forced_decoder_ids = None


    # --------------------------------------------------------
    # ChefEar QLoRA Adapter 결합
    # --------------------------------------------------------

    _model = PeftModel.from_pretrained(
        base_model,
        HF_ADAPTER_ID,
    )

    _model.eval()

    _model.config.forced_decoder_ids = None

    _model.generation_config.forced_decoder_ids = None


    # --------------------------------------------------------
    # 입력 dtype 확인
    # --------------------------------------------------------

    _input_dtype = get_input_dtype(
        _model
    )

    print(
        "✅ ChefEar STT 모델 로드 완료"
    )

    print(
        "Input dtype:",
        _input_dtype
    )

    return _model, _processor


# ============================================================
# 1차 후처리
# 단위 표기 정규화
# ============================================================

def normalize_stt_text(text: str) -> str:
    """
    STT가 의미는 맞게 인식했지만
    단위를 영어로 출력한 경우 한글 표기로 통일합니다.

    이 함수에서는 숫자 값을 절대 변경하지 않습니다.

    예
    --
    100 g
        → 100그램

    1 kg
        → 1킬로그램

    200 ml
        → 200밀리리터

    1 L
        → 1리터
    """

    # kg → 킬로그램
    # g보다 먼저 처리
    text = re.sub(
        r"(\d+)\s*[kK][gG](?![A-Za-z])",
        r"\1킬로그램",
        text,
    )

    # ml → 밀리리터
    # l보다 먼저 처리
    text = re.sub(
        r"(\d+)\s*[mM][lL](?![A-Za-z])",
        r"\1밀리리터",
        text,
    )

    # g → 그램
    text = re.sub(
        r"(\d+)\s*[gG](?![A-Za-z])",
        r"\1그램",
        text,
    )

    # l / L → 리터
    text = re.sub(
        r"(\d+)\s*[lL](?![A-Za-z])",
        r"\1리터",
        text,
    )

    return text


# ============================================================
# 재료 문맥 정규화
# ============================================================

def normalize_ingredient_context(
    ingredient_context: Optional[
        Union[str, Sequence[str]]
    ],
) -> str:
    """
    현재 레시피의 재료 정보를
    비교하기 쉬운 하나의 문자열로 변환합니다.

    지원 입력
    --------
    문자열:
        "소고기다짐육 100g, 당근 20g"

    리스트:
        [
            "소고기다짐육 100g",
            "당근 20g",
        ]
    """

    if ingredient_context is None:
        return ""

    if isinstance(
        ingredient_context,
        (list, tuple, set),
    ):

        context = " ".join(
            str(item)
            for item in ingredient_context
        )

    else:

        context = str(
            ingredient_context
        )


    # 재료 DB의 g / kg / ml 등도
    # 같은 기준으로 맞춤
    context = normalize_stt_text(
        context
    )


    # 비교에 방해되는 연속 공백 정리
    context = re.sub(
        r"\s+",
        " ",
        context,
    ).strip()

    return context


# ============================================================
# 재료 문맥에서 수량 존재 여부 확인
# ============================================================

def context_has_quantity(
    context: str,
    ingredient: str,
    quantity: int,
) -> bool:
    """
    현재 레시피 재료 문맥에

        재료명 + 특정 그램 수

    가 존재하는지 확인합니다.

    예
    --
    소고기다짐육 100그램
    """

    # 비교 시 재료명 내부 공백 허용
    ingredient_pattern = (
        r"\s*".join(
            map(
                re.escape,
                ingredient,
            )
        )
    )

    pattern = (
        ingredient_pattern
        + rf"\s*{quantity}\s*그램"
    )

    return bool(
        re.search(
            pattern,
            context,
        )
    )


# ============================================================
# 2차 후처리
# 고위험 음향 경계 조건부 보정
# ============================================================

def correct_high_risk_with_context(
    text: str,
    ingredient_context: Optional[
        Union[str, Sequence[str]]
    ],
) -> str:
    """
    고위험군 테스트에서 반복 확인된
    '다짐육 + 백그램 → 다짐 + 육백그램'
    음향 경계 문제를 조건부로 보정합니다.

    매우 중요한 안전 조건
    ----------------------
    현재 레시피 재료 정보가 없으면
    아무것도 수정하지 않습니다.

    또한:

        현재 레시피 = 100그램
        현재 레시피 != 600그램

    이 두 조건을 모두 만족할 때만
    600 → 100 보정을 허용합니다.

    따라서 일반적인 600그램 발화를
    무조건 100그램으로 바꾸지 않습니다.
    """

    context = normalize_ingredient_context(
        ingredient_context
    )


    # --------------------------------------------------------
    # 재료 문맥이 없으면 숫자 보정 금지
    # --------------------------------------------------------

    if not context:
        return text


    corrected_text = text


    # ========================================================
    # 고위험 재료별 검사
    # ========================================================

    for canonical_name, risky_patterns in (
        HIGH_RISK_INGREDIENTS.items()
    ):

        # ----------------------------------------------------
        # 현재 레시피가 실제로 100그램인지 확인
        # ----------------------------------------------------

        has_100g = context_has_quantity(
            context,
            canonical_name,
            100,
        )


        # ----------------------------------------------------
        # 현재 레시피가 실제 600그램이면
        # 절대 100그램으로 바꾸지 않음
        # ----------------------------------------------------

        has_600g = context_has_quantity(
            context,
            canonical_name,
            600,
        )


        # 안전 조건
        if not has_100g:
            continue

        if has_600g:
            continue


        # ----------------------------------------------------
        # STT 결과에서
        # 고위험 표현 + 600그램 확인
        # ----------------------------------------------------

        for risky_pattern in risky_patterns:

            pattern = (
                rf"{risky_pattern}"
                rf"\s*600그램"
            )


            # ------------------------------------------------
            # 현재 레시피가 100그램이라고 확인된 경우에만
            # 표준 재료명 + 100그램으로 보정
            # ------------------------------------------------

            corrected_text = re.sub(
                pattern,
                f"{canonical_name} 100그램",
                corrected_text,
            )


    return corrected_text


# ============================================================
# 내부 음성 추론
# ============================================================

def _transcribe_audio(
    audio_path: Path,
    ingredient_context: Optional[
        Union[str, Sequence[str]]
    ] = None,
) -> str:
    """
    음성 파일 1개를 ChefEar STT로 인식합니다.

    Parameters
    ----------
    audio_path
        음성 파일 경로

    ingredient_context
        현재 레시피의 재료 정보.

        이 값이 있을 때만
        고위험 숫자 조건부 보정이 작동합니다.

    흐름
    ----
    audio
        ↓
    Whisper
        ↓
    raw_prediction
        ↓
    단위 표기 정규화
        ↓
    현재 재료 문맥 기반 조건부 보정
        ↓
    최종 prediction
    """

    model, processor = load_stt_model()


    # --------------------------------------------------------
    # 16kHz 로드
    # --------------------------------------------------------

    audio, _ = librosa.load(
        str(audio_path),
        sr=16000,
    )


    # --------------------------------------------------------
    # Whisper 입력 생성
    # --------------------------------------------------------

    inputs = processor(
        audio,
        sampling_rate=16000,
        return_tensors="pt",
        return_attention_mask=True,
    )


    input_dtype = (
        _input_dtype
        or get_input_dtype(model)
    )


    input_features = (
        inputs.input_features.to(
            device=model.device,
            dtype=input_dtype,
        )
    )


    attention_mask = (
        inputs.attention_mask.to(
            model.device
        )
    )


    # --------------------------------------------------------
    # STT 추론
    # --------------------------------------------------------

    with torch.inference_mode():

        generated_ids = model.generate(
            input_features=input_features,
            attention_mask=attention_mask,
            language="ko",
            task="transcribe",
        )


    # --------------------------------------------------------
    # Whisper 원본 출력
    # --------------------------------------------------------

    raw_prediction = (
        processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
        )[0].strip()
    )


    # --------------------------------------------------------
    # 1차: 단위 표기 정규화
    # --------------------------------------------------------

    prediction = normalize_stt_text(
        raw_prediction
    )


    # --------------------------------------------------------
    # 2차: 현재 레시피 문맥 기반 고위험 보정
    # --------------------------------------------------------

    prediction = correct_high_risk_with_context(
        prediction,
        ingredient_context,
    )


    return prediction


# ============================================================
# 배포용 단일 발화 추론 (faster-whisper, CPU) — docs/specs/stt_deploy.md
# ============================================================
#
# 위 load_stt_model()/_transcribe_audio()는 4bit(NF4) 양자화라 CUDA 전용이라(GPU 없는
# HF Spaces CPU Basic에서 로드 자체가 안 됨), 배포는 별도로 faster-whisper(int8, CPU)를 쓴다.
# faster-whisper는 HF transformers 체크포인트를 직접 못 읽어서, 먼저 src/stt/export_ct2.py로
# (LoRA 병합 → CTranslate2 int8 변환) 오프라인 변환해둔 결과물을 읽는다.

# 변환 결과물 우선순위: 1) 로컬 models/stt_finetuned/ct2_int8/(export_ct2.py 산출물)
# 2) .env의 HF_STT_CT2_REPO(HF Hub에 올린 변환본 — 아직 업로드 여부 미정, Open Issue)
CT2_LOCAL_DIR = PROJECT_ROOT / "models" / "stt_finetuned" / "ct2_int8"
HF_STT_CT2_REPO = os.environ.get("HF_STT_CT2_REPO")

_ct2_model = None


def _resolve_ct2_model_path() -> str:
    """CTranslate2 변환 모델의 경로/repo를 우선순위대로 결정한다.

    로컬에도 없고 HF_STT_CT2_REPO도 없으면, 조용히 다른 모델로 폴백하지 않고 바로
    에러를 던진다(EC-04, docs/specs/stt_deploy.md) — 잘못된 모델로 응답하는 게 더 위험하다.
    """
    if CT2_LOCAL_DIR.exists():
        return str(CT2_LOCAL_DIR)
    if HF_STT_CT2_REPO:
        return HF_STT_CT2_REPO
    raise FileNotFoundError(
        f"CTranslate2 변환 모델을 찾을 수 없음 — {CT2_LOCAL_DIR}도 없고 .env의 "
        "HF_STT_CT2_REPO도 안 설정됨. 먼저 `python src/stt/export_ct2.py`를 실행해서 "
        "변환본을 만들 것(docs/specs/stt_deploy.md 참고)."
    )


def load_ct2_model():
    """faster-whisper 모델을 최초 1번만 로드하고 이후 재사용한다."""

    global _ct2_model

    if _ct2_model is not None:
        return _ct2_model

    from faster_whisper import WhisperModel

    model_path = _resolve_ct2_model_path()

    # HF Spaces CPU Basic(2 vCPU)을 흉내낸 조건 — tests/tts_cpu_inference_test.py와 동일.
    _ct2_model = WhisperModel(model_path, device="cpu", compute_type="int8", cpu_threads=2)

    print(f"✅ ChefEar STT(faster-whisper, int8) 로드 완료: {model_path}")

    return _ct2_model


def stt_transcribe(audio: "str | Path | np.ndarray", *, sample_rate: int | None = None) -> str:
    """오디오 하나 -> 인식된 텍스트. faster-whisper(int8, CPU) 기반, HF Spaces 배포용.

    app.py가 직접 호출할 곳 — orchestration.pipeline.handle_utterance()에 반환값을
    그대로 넘기면 된다.

    Parameters
    ----------
    audio
        파일 경로(mp3/wav 등) 또는 numpy 파형 배열. 배열로 줄 경우 sample_rate가 필수이며,
        16kHz가 아니면 librosa로 16kHz 모노로 리샘플링한 뒤 넘긴다(EC-03).

    Returns
    -------
    str
        인식된 텍스트. 무음/너무 짧은 오디오 등으로 인식된 구간이 없으면 빈 문자열을
        반환한다(예외 아님, EC-01) — 호출부(app.py)가 "다시 말씀해주세요"로 안내할 수 있게.
    """

    model = load_ct2_model()

    if isinstance(audio, np.ndarray):
        if sample_rate is None:
            raise ValueError("audio가 numpy 배열이면 sample_rate가 필수임")
        if sample_rate != 16000:
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)

    # vad_filter=True: 무음 구간을 걸러내서, 순수 무음 입력에서 whisper 특유의 환각
    # (silence hallucination) 없이 자연스럽게 빈 결과가 나오게 한다(EC-01).
    segments, _info = model.transcribe(audio, language="ko", vad_filter=True)

    text = " ".join(segment.text.strip() for segment in segments).strip()

    return text


# ============================================================
# 100개 음성 일괄 테스트
# 서비스 파이프라인용 STT 함수
# ============================================================

def stt_transcribe(
    audio_path,
    ingredient_context: Optional[
        Union[str, Sequence[str]]
    ] = None,
) -> str:
    """
    ChefEar 서비스에서 사용할 STT 함수입니다.

    예
    --
    prediction = stt_transcribe(
        audio_path="user.wav",
        ingredient_context=[
            "소고기다짐육 100g",
            "당근 20g",
            "깻잎 3장",
        ],
    )

    ingredient_context가 None이면
    숫자 의미 보정은 수행하지 않습니다.
    """

    audio_path = Path(
        audio_path
    )


    if not audio_path.exists():

        raise FileNotFoundError(
            "오디오 파일을 찾을 수 없습니다: "
            f"{audio_path}"
        )


    return _transcribe_audio(
        audio_path,
        ingredient_context=ingredient_context,
    )


# ============================================================
# 음성 일괄 평가
# ============================================================

def run_batch_test(
    csv_path,
    audio_dir,
    result_path="ChefEar_STT_test100_result.csv",
):
    """
    기존 ChefEar STT 평가용 함수입니다.

    중요
    ----
    모델 평가에서는 reference를
    재료 문맥으로 사용하지 않습니다.

    그렇게 하면 정답을 미리 보고
    STT를 보정하는 셈이 되어
    평가 결과가 왜곡되기 때문입니다.

    따라서 run_batch_test에서는
    문맥 기반 숫자 보정을 사용하지 않습니다.
    """

    csv_path = Path(
        csv_path
    )

    audio_dir = Path(
        audio_dir
    )

    result_path = Path(
        result_path
    )


    # --------------------------------------------------------
    # 경로 확인
    # --------------------------------------------------------

    if not csv_path.exists():

        raise FileNotFoundError(
            "CSV 파일을 찾을 수 없습니다: "
            f"{csv_path}"
        )


    if not audio_dir.exists():

        raise FileNotFoundError(
            "오디오 폴더를 찾을 수 없습니다: "
            f"{audio_dir}"
        )


    # --------------------------------------------------------
    # CSV 읽기
    # --------------------------------------------------------

    df = pd.read_csv(
        csv_path
    )


    required_columns = [
        "test_id",
        "text",
    ]


    for column in required_columns:

        if column not in df.columns:

            raise ValueError(
                f"CSV에 '{column}' 컬럼이 없습니다."
            )


    print("=" * 60)

    print(
        "ChefEar STT 테스트 시작"
    )

    print(
        "CSV:",
        csv_path
    )

    print(
        "Audio:",
        audio_dir
    )

    print(
        "테스트 개수:",
        len(df)
    )

    print("=" * 60)


    # 모델 최초 1회 로드
    load_stt_model()


    results = []


    # ========================================================
    # 순차 추론
    # ========================================================

    for idx, row in df.iterrows():


        test_id = str(
            row["test_id"]
        ).strip()


        reference = str(
            row["text"]
        ).strip()


        audio_path = (
            audio_dir
            / f"{test_id}.mp3"
        )


        print(
            f"\n[{idx + 1}/{len(df)}] "
            f"{audio_path.name}"
        )


        # ----------------------------------------------------
        # 파일 확인
        # ----------------------------------------------------

        if not audio_path.exists():

            print(
                "❌ 오디오 파일 없음"
            )


            results.append({
                "test_id": test_id,
                "audio_file": audio_path.name,
                "reference": reference,
                "prediction": "",
                "wer": None,
                "status": "file_not_found",
            })


            continue


        # ----------------------------------------------------
        # STT
        # ----------------------------------------------------

        try:

            # 평가에서는 정답 문맥을 넣지 않음
            prediction = _transcribe_audio(
                audio_path,
                ingredient_context=None,
            )


            sentence_wer = wer(
                reference,
                prediction,
            )


            print(
                "정답 :",
                reference
            )


            print(
                "예측 :",
                prediction
            )


            print(
                f"WER  : "
                f"{sentence_wer:.4f}"
            )


            results.append({
                "test_id": test_id,
                "audio_file": audio_path.name,
                "reference": reference,
                "prediction": prediction,
                "wer": sentence_wer,
                "status": "success",
            })


        except Exception as error:


            print(
                "❌ 추론 오류:",
                error
            )


            results.append({
                "test_id": test_id,
                "audio_file": audio_path.name,
                "reference": reference,
                "prediction": "",
                "wer": None,
                "status": f"error: {error}",
            })


    # ========================================================
    # 결과 저장
    # ========================================================

    result_df = pd.DataFrame(
        results
    )


    result_df.to_csv(
        result_path,
        index=False,
        encoding="utf-8-sig",
    )


    # ========================================================
    # 전체 WER
    # ========================================================

    success_df = result_df[
        result_df["status"]
        == "success"
    ]


    if len(success_df) > 0:


        total_wer = wer(

            success_df[
                "reference"
            ].tolist(),

            success_df[
                "prediction"
            ].tolist(),
        )


        print(
            "\n"
            + "=" * 60
        )


        print(
            "✅ ChefEar STT 테스트 완료"
        )


        print(
            "성공:",
            len(success_df)
        )


        print(
            "실패:",
            len(result_df)
            - len(success_df)
        )


        print(
            f"전체 WER: "
            f"{total_wer:.4f}"
        )


        print(
            f"전체 WER(%): "
            f"{total_wer * 100:.2f}%"
        )


        print(
            "결과 CSV:",
            result_path
        )


        print("=" * 60)


    return result_df


# ============================================================
# 단일 발화 실시간 추론 (faster-whisper, 원본 모델) — 2026-08-20 추가
# ============================================================
#
# 위 load_stt_model()/run_batch_test()는 파인튜닝된 4bit QLoRA Adapter를 쓰는데
# bitsandbytes 4bit 양자화가 GPU(CUDA) 전용이라, GPU 없는 환경(예: 이 저장소를
# 로컬 CPU에서 테스트할 때)에서는 아예 로드가 안 된다. 그리고 배포용으로 정해둔
# faster-whisper(requirements.txt)로 쓰려면 파인튜닝된 Adapter를 CTranslate2
# 포맷으로 변환해야 하는데, 이 변환은 위 README의 "faster-whisper/CTranslate2
# 기반 경량화 검토" 항목대로 아직 안 된 상태다(2026-08-20 확인) — 이 파일 담당자
# (하주성)의 파인튜닝 검증 작업 영역이라 여기서 대신 변환하지 않는다.
#
# 그래서 이 함수는 일단 파인튜닝 안 된 원본 openai/whisper-large-v3-turbo를
# faster-whisper로 돌린다 — "마이크 → VAD → 텍스트 → 요리명 인식" 파이프라인
# 자체가 동작하는지 먼저 확인하려는 용도다(2026-08-20, 상시 마이크 테스트 화면
# 요청). 요리 도메인 파인튜닝이 아니라서 인식 정확도는 V1 Adapter보다 낮을 수
# 있다 — 나중에 CTranslate2 변환이 끝나면 아래 REALTIME_MODEL_SIZE만 그 경로로
# 바꾸면 된다(이 함수를 호출하는 쪽 코드는 안 바뀜).
REALTIME_MODEL_SIZE = os.environ.get("HF_STT_REALTIME_MODEL") or "large-v3-turbo"

_realtime_model = None


def load_realtime_stt_model():
    """faster-whisper 모델을 최초 1번만 로드하고 이후 호출에서 재사용한다
    (tts.infer.load_tts_model()과 같은 지연 로딩·캐싱 패턴)."""
    global _realtime_model
    if _realtime_model is not None:
        return _realtime_model

    from faster_whisper import WhisperModel

    _realtime_model = WhisperModel(REALTIME_MODEL_SIZE, device="cpu", compute_type="int8")
    print(f"[STT] 실시간 추론용 faster-whisper 모델 로드 완료: {REALTIME_MODEL_SIZE} (원본, 파인튜닝 아님)")
    return _realtime_model


def stt_transcribe(waveform, sample_rate: int = 16000) -> str:
    """오디오 배열 하나(예: VAD로 잘라낸 발화 한 구간) -> 인식된 텍스트 한 줄.

    orchestration.pipeline.handle_utterance()에 그대로 넣을 수 있는 형태로 반환한다
    — src/tts/infer.py의 tts_synthesize()와 대칭되는 STT 쪽 단일 발화 함수(위
    run_batch_test()용 _transcribe_audio()는 "파일 경로"를 받는 배치 전용이라
    실시간 마이크 오디오 배열엔 그대로 못 쓴다).

    waveform은 float32 numpy 배열(모노)이어야 한다 — sample_rate가 16000이 아니면
    whisper가 기대하는 16kHz로 리샘플링한다(librosa는 이미 이 파일 상단에서 씀).
    """
    import numpy as np

    waveform = np.asarray(waveform, dtype=np.float32)
    if sample_rate != 16000:
        waveform = librosa.resample(waveform, orig_sr=sample_rate, target_sr=16000)

    model = load_realtime_stt_model()
    segments, _ = model.transcribe(waveform, language="ko", task="transcribe")
    return "".join(segment.text for segment in segments).strip()