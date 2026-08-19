"""
ChefEar STT - 100개 음성 일괄 테스트 로직

[모델]
Base Model:
    openai/whisper-large-v3-turbo

QLoRA Adapter:
    leeony/chefear-stt-large-v3-turbo

[필요한 입력]
1. ChefEar_test_fixed_100.csv
2. test_audio_100 폴더

CSV 구조:
    test_id : test_001
    text    : 정답 문장

오디오 구조:
    test_001.mp3
    test_002.mp3
    ...

[호출 예시]

from src.stt.infer import run_batch_test

result = run_batch_test(
    csv_path="ChefEar_test_fixed_100.csv",
    audio_dir="test_audio_100",
    result_path="ChefEar_STT_test100_result.csv"
)

print(result)
"""

from pathlib import Path
from typing import Optional
import os
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

# 모델은 최초 1번만 로드하고
# 100개 음성에서 계속 재사용
_processor: Optional[WhisperProcessor] = None
_model = None
_input_dtype: Optional[torch.dtype] = None


# ============================================================
# 입력 dtype 확인
# ============================================================

def get_input_dtype(model) -> torch.dtype:

    for name, module in model.named_modules():

        if name.endswith("encoder.conv1"):

            if hasattr(module, "bias") and module.bias is not None:

                return module.bias.dtype

    return torch.float16


# ============================================================
# STT 모델 로드
# ============================================================

def load_stt_model():

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

        print("✅ Processor: Hugging Face Adapter Repo에서 로드")

    except Exception:

        _processor = WhisperProcessor.from_pretrained(
            MODEL_ID
        )

        print("⚠ Processor: Base Model에서 로드")


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

    base_model = WhisperForConditionalGeneration.from_pretrained(

        MODEL_ID,

        quantization_config=bnb_config,

        device_map="auto",
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


    _input_dtype = get_input_dtype(_model)


    print("✅ ChefEar STT 모델 로드 완료")

    print("Input dtype:", _input_dtype)


    return _model, _processor


# ============================================================
# 내부 음성 추론
# ============================================================

def _transcribe_audio(audio_path: Path) -> str:
    """
    run_batch_test 내부에서 사용하는 함수입니다.

    외부에서 직접 호출하기 위한 함수가 아니라,
    100개 음성을 순차적으로 처리하기 위해 사용합니다.
    """

    model, processor = load_stt_model()


    # 16kHz 로드
    audio, _ = librosa.load(

        str(audio_path),

        sr=16000,
    )


    inputs = processor(

        audio,

        sampling_rate=16000,

        return_tensors="pt",

        return_attention_mask=True,
    )


    input_dtype = _input_dtype or get_input_dtype(model)


    input_features = inputs.input_features.to(

        device=model.device,

        dtype=input_dtype,
    )


    attention_mask = inputs.attention_mask.to(

        model.device
    )


    # --------------------------------------------------------
    # STT 추론
    # --------------------------------------------------------

    with torch.no_grad():

        generated_ids = model.generate(

            input_features=input_features,

            attention_mask=attention_mask,

            language="ko",

            task="transcribe",
        )


    prediction = processor.batch_decode(

        generated_ids,

        skip_special_tokens=True,

    )[0].strip()


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
# ============================================================

def run_batch_test(
    csv_path,
    audio_dir,
    result_path="ChefEar_STT_test100_result.csv",
):
    """
    ChefEar 테스트용 음성 100개를 순차적으로 STT 처리합니다.

    Parameters
    ----------
    csv_path
        ChefEar_test_fixed_100.csv 경로

    audio_dir
        test_audio_100 폴더 경로

    result_path
        STT 결과를 저장할 CSV 경로


    Returns
    -------
    pandas.DataFrame

        test_id
        audio_file
        reference
        prediction
        wer
        status
    """


    csv_path = Path(csv_path)

    audio_dir = Path(audio_dir)

    result_path = Path(result_path)


    # --------------------------------------------------------
    # 경로 확인
    # --------------------------------------------------------

    if not csv_path.exists():

        raise FileNotFoundError(
            f"CSV 파일을 찾을 수 없습니다: {csv_path}"
        )


    if not audio_dir.exists():

        raise FileNotFoundError(
            f"오디오 폴더를 찾을 수 없습니다: {audio_dir}"
        )


    # --------------------------------------------------------
    # CSV 읽기
    # --------------------------------------------------------

    df = pd.read_csv(csv_path)


    # 우리가 확인한 실제 CSV 구조
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

    print("ChefEar STT 100개 테스트 시작")

    print("CSV:", csv_path)

    print("Audio:", audio_dir)

    print("테스트 개수:", len(df))

    print("=" * 60)


    # 모델은 여기서 한 번만 먼저 로드
    load_stt_model()


    results = []


    # ========================================================
    # 100개 순차 추론
    # ========================================================

    for idx, row in df.iterrows():


        test_id = str(
            row["test_id"]
        ).strip()


        reference = str(
            row["text"]
        ).strip()


        # 우리가 실제 확인한 규칙
        #
        # test_001
        #     ↓
        # test_001.mp3

        audio_path = (
            audio_dir
            / f"{test_id}.mp3"
        )


        print(
            f"\n[{idx + 1}/{len(df)}] "
            f"{audio_path.name}"
        )


        # ----------------------------------------------------
        # 파일 존재 확인
        # ----------------------------------------------------

        if not audio_path.exists():

            print("❌ 오디오 파일 없음")


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

            prediction = _transcribe_audio(
                audio_path
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
                f"WER  : {sentence_wer:.4f}"
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
    # 전체 WER 계산
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


        print("\n" + "=" * 60)

        print("✅ ChefEar STT 테스트 완료")

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