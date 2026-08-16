"""Qwen3-TTS 1.7B CPU 추론 속도 실측 (HF Spaces CPU Basic, 2 vCPU 흉내).

읽기 전용 벤치마크. 학습 스크립트/체크포인트를 건드리지 않는다.

사용 체크포인트 우선순위:
  1) models/tts_finetuned/ 아래 가장 최근 체크포인트
  2) 없으면 사전학습 베이스 Qwen/Qwen3-TTS-12Hz-1.7B-Base (Base 모델은
     voice clone 전용이라 공개 데모 참조 오디오로 프롬프트를 만든다)

결과: results/tts/cpu_inference_test.csv (text, run, inference_seconds)
"""

import csv
import os
import time
from pathlib import Path

os.environ["CUDA_VISIBLE_DEVICES"] = ""

import torch

torch.set_num_threads(2)

from qwen_tts import Qwen3TTSModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_DIR = PROJECT_ROOT / "models" / "tts_finetuned"
RESULTS_CSV = PROJECT_ROOT / "results" / "tts" / "cpu_inference_test.csv"
BASE_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"

# 공식 예제 저장소의 공개 데모 참조 오디오 (Base 모델은 voice clone 필수)
DEMO_REF_AUDIO = "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-TTS-Repo/clone.wav"
DEMO_REF_TEXT = (
    "Okay. Yeah. I resent you. I love you. I respect you. "
    "But you know what? You blew it! And thanks to you."
)

SENTENCES = [
    "약불로 5분간 끓여주세요",
    "양파와 마늘을 다진 뒤, 팬에 기름을 두르고 중불에서 노릇하게 볶아주세요",
    "1.5컵의 물을 넣고 뚜껑을 덮은 채로 10분간 졸인 다음, 불을 끄고 5분 정도 뜸을 들여주세요",
]

RUNS_PER_SENTENCE = 3  # 1회차 워밍업 제외, 2·3회차 평균
TARGET_SECONDS = 5.0


def find_latest_checkpoint(checkpoint_dir: Path) -> Path | None:
    if not checkpoint_dir.exists():
        return None
    candidates = [
        p for p in checkpoint_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def main():
    checkpoint = find_latest_checkpoint(CHECKPOINT_DIR)
    if checkpoint is not None:
        model_path = str(checkpoint)
        model_source_desc = f"파인튜닝 체크포인트: {checkpoint}"
    else:
        model_path = BASE_MODEL_ID
        model_source_desc = f"체크포인트 없음 -> 사전학습 베이스 모델 사용: {BASE_MODEL_ID}"

    print(f"[모델 소스] {model_source_desc}")
    print("[양자화] 없음 (float32, CPU, 2 threads)")
    print("[디바이스] CPU 강제 고정 (CUDA_VISIBLE_DEVICES=\"\", torch.set_num_threads(2))")
    print()

    load_start = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map="cpu",
        dtype=torch.float32,
    )
    load_seconds = time.perf_counter() - load_start
    print(f"[모델 로딩 시간] {load_seconds:.2f}초\n")

    is_base_model = getattr(model.model, "tts_model_type", None) == "base"

    voice_clone_prompt = None
    if is_base_model:
        prompt_start = time.perf_counter()
        voice_clone_prompt = model.create_voice_clone_prompt(
            ref_audio=DEMO_REF_AUDIO,
            ref_text=DEMO_REF_TEXT,
        )
        prompt_seconds = time.perf_counter() - prompt_start
        print(
            f"[참조 오디오 프롬프트 준비 시간] {prompt_seconds:.2f}초 "
            "(로딩 단계로 취급, 문장별 추론 시간에는 미포함)\n"
        )

    rows = []  # (text, run, inference_seconds)
    per_sentence_avg = {}

    for sentence in SENTENCES:
        timings = []
        for run in range(1, RUNS_PER_SENTENCE + 1):
            start = time.perf_counter()
            if is_base_model:
                model.generate_voice_clone(
                    text=sentence,
                    language="Korean",
                    voice_clone_prompt=voice_clone_prompt,
                )
            else:
                model.generate_voice_clone(
                    text=sentence,
                    language="Korean",
                    ref_audio=DEMO_REF_AUDIO,
                    ref_text=DEMO_REF_TEXT,
                )
            elapsed = time.perf_counter() - start

            tag = "워밍업(제외)" if run == 1 else f"{run}회차"
            print(f"  [{sentence[:20]}...] run {run} ({tag}): {elapsed:.2f}초")

            rows.append((sentence, run, f"{elapsed:.4f}"))
            if run > 1:
                timings.append(elapsed)

        avg = sum(timings) / len(timings)
        per_sentence_avg[sentence] = avg

    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "run", "inference_seconds"])
        writer.writerows(rows)

    print(f"\n결과 저장: {RESULTS_CSV}")

    print("\n=== 결과 요약 ===")
    print(f"모델 로딩 시간(1회): {load_seconds:.2f}초")
    print()
    for sentence, avg in per_sentence_avg.items():
        status = "PASS" if avg <= TARGET_SECONDS else "FAIL"
        print(f"[{status}] 평균 {avg:.2f}초 (목표 {TARGET_SECONDS}초) - \"{sentence}\"")

    overall_avg = sum(per_sentence_avg.values()) / len(per_sentence_avg)
    overall_status = "PASS" if overall_avg <= TARGET_SECONDS else "FAIL"
    print(f"\n[전체 평균] {overall_avg:.2f}초 -> {overall_status}")


if __name__ == "__main__":
    main()
