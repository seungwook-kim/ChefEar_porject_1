"""ChefEar STT 배포용 CTranslate2 변환 스크립트 (오프라인, 1회 실행).

`docs/specs/stt_deploy.md`의 "변환 파이프라인" 절 그대로 구현한 것 — 배포 런타임에서 실행되는
코드가 아니라, 개발자가 로컬/Colab에서 한 번 돌려서 결과물(CTranslate2 int8 모델)을 만들어두는
오프라인 스크립트다. `src/stt/infer.py`의 `stt_transcribe()`가 이 결과물을 읽는다.

왜 필요한가: faster-whisper는 HuggingFace transformers 체크포인트를 직접 못 읽고 CTranslate2
포맷만 읽는다. 지금 STT는 base(openai/whisper-large-v3-turbo) + LoRA 어댑터
(leeony/chefear-stt-large-v3-turbo) 구조라, 변환 전에 merge_and_unload()로 먼저 하나의
체크포인트로 합쳐야 한다(TTS가 이미 쓰는 merge 패턴과 동일, src/tts/infer.py 상단 주석 참고).

출력:
    models/stt_finetuned/_merged_fp16/   병합된 HF 포맷 체크포인트 (중간 산출물)
    models/stt_finetuned/ct2_int8/       CTranslate2 int8 변환 결과 (stt_transcribe()가 읽음)
둘 다 git 미추적(.gitignore의 "models/" 패턴).

실행: python src/stt/export_ct2.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# 병합(merge_and_unload)은 GPU가 필요 없는 순수 가중치 연산이다. 이 환경은 GPU가 남아있어서
# peft의 어댑터 로딩이 CUDA를 잡으려다 충돌한 적이 있어(2026-08-19,
# "CUDA-capable device(s) is/are busy or unavailable") 아예 GPU를 안 보이게 하고 CPU로 강제한다.
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import torch
from peft import PeftModel
from transformers import WhisperForConditionalGeneration, WhisperProcessor

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from orchestration.db import load_env

load_env()

BASE_MODEL_ID = "openai/whisper-large-v3-turbo"
ADAPTER_ID = os.environ.get("HF_STT_MODEL_REPO") or "leeony/chefear-stt-large-v3-turbo"

MERGED_DIR = PROJECT_ROOT / "models" / "stt_finetuned" / "_merged_fp16"
CT2_DIR = PROJECT_ROOT / "models" / "stt_finetuned" / "ct2_int8"


def main() -> None:
    print(f"[1/3] base 모델 로드: {BASE_MODEL_ID} (fp16 — merge_and_unload()는 4bit 양자화 상태로는 안 됨)")
    base_model = WhisperForConditionalGeneration.from_pretrained(
        BASE_MODEL_ID, torch_dtype=torch.float16
    )
    processor = WhisperProcessor.from_pretrained(ADAPTER_ID)

    print(f"[2/3] LoRA 어댑터 병합: {ADAPTER_ID}")
    merged = PeftModel.from_pretrained(base_model, ADAPTER_ID).merge_and_unload()
    merged.config.forced_decoder_ids = None
    merged.generation_config.forced_decoder_ids = None

    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(MERGED_DIR)
    processor.save_pretrained(MERGED_DIR)
    print(f"    병합 모델 저장: {MERGED_DIR}")

    print(f"[3/3] CTranslate2 int8 변환 -> {CT2_DIR}")
    if CT2_DIR.exists():
        shutil.rmtree(CT2_DIR)
    subprocess.run(
        [
            "ct2-transformers-converter",
            "--model", str(MERGED_DIR),
            "--output_dir", str(CT2_DIR),
            "--quantization", "int8",
        ],
        check=True,
    )

    # ct2-transformers-converter가 preprocessor_config.json을 안 옮겨서(2026-08-19 실측
    # 확인), whisper-large-v3-turbo(feature_size=128, v3부터 mel bin이 80→128로 바뀜)인데도
    # faster-whisper가 기본값 80으로 특징을 뽑아서 "Invalid input features shape: expected
    # (1, 128, 3000), but got (1, 80, 3000)"로 죽는다. 병합 모델 쪽 파일을 직접 복사해서
    # feature_size=128을 명시해준다.
    preprocessor_src = MERGED_DIR / "preprocessor_config.json"
    if preprocessor_src.exists():
        shutil.copy(preprocessor_src, CT2_DIR / "preprocessor_config.json")
        print(f"    preprocessor_config.json 복사 완료(feature_size=128 유지)")
    else:
        print("    ⚠ preprocessor_config.json이 병합 모델에도 없음 — 수동 확인 필요")

    print(f"✅ 변환 완료: {CT2_DIR}")
    print("   반입(HF Hub 업로드 여부)은 별도 결정 필요 — docs/specs/stt_deploy.md의 Open Issue 참고.")


if __name__ == "__main__":
    main()
