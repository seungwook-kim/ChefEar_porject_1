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

import librosa
import pandas as pd
import torch

from jiwer import wer
from peft import PeftModel

from transformers import (
    BitsAndBytesConfig,
    WhisperForConditionalGeneration,
    WhisperProcessor,
)


# ============================================================
# 모델 설정
# ============================================================

MODEL_ID = "openai/whisper-large-v3-turbo"

HF_ADAPTER_ID = "leeony/chefear-stt-large-v3-turbo"


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