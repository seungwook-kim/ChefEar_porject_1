"""ChefEar TTS→STT 라운드트립 검증 (읽기 전용 벤치마크).

파인튜닝된 TTS(src/tts/infer.py의 tts_synthesize)로 조리 안내 문장을 합성하고, 실제
ChefEar STT(src/stt/infer.py, whisper-large-v3-turbo + QLoRA)로 다시 인식시켜 WER을
잰다. "우리 TTS 음성을 우리 STT가 얼마나 잘 알아듣는가"를 보는 것 — 합성음을 STT
학습데이터(data/synthesized/)로 재사용할 수 있는지 사전 확인하는 목적도 겸한다.

⚠️ GPU 환경 필요: STT 로딩(src/stt/infer.py)이 bitsandbytes 4bit(NF4)를 쓰는데, 이 양자화는
CUDA 커널 기반이라 GPU 없는 환경에선 사실상 동작하지 않는다(requirements-stt.txt도
torch==2.5.1+cu124로 CUDA 빌드 고정). tests/tts_cpu_inference_test.py(CPU 벤치마크)와는
다른 목적이니 혼동하지 말 것.

⚠️ HF_TOKEN 필요: TTS 모델(kimseunguk/qwen3-tts-kss-finetuned)이 private HF repo라 .env의
HF_TOKEN이 있어야 로딩된다.

결과: results/tts/roundtrip_wer.csv (text, hypothesis, wer)
"""

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import jiwer
import soundfile as sf

from stt.infer import _transcribe_audio, load_stt_model
from tts.infer import tts_synthesize

RESULTS_CSV = PROJECT_ROOT / "results" / "tts" / "roundtrip_wer.csv"
TMP_WAV = RESULTS_CSV.parent / "_roundtrip_tmp.wav"

# 조리 안내 문장 (tests/tts_cpu_inference_test.py의 SENTENCES와 동일 — 실제 TTS가
# 서비스에서 읽게 될 문장 스타일과 맞춤)
SENTENCES = [
    "약불로 5분간 끓여주세요",
    "양파와 마늘을 다진 뒤, 팬에 기름을 두르고 중불에서 노릇하게 볶아주세요",
    "1.5컵의 물을 넣고 뚜껑을 덮은 채로 10분간 졸인 다음, 불을 끄고 5분 정도 뜸을 들여주세요",
    "두부와 감자를 먹기 좋은 크기로 썰어 넣습니다",
    "된장을 풀어줍니다",
]


def normalize(text: str) -> str:
    """한국어 띄어쓰기 차이로 WER이 왜곡되는 걸 막기 위해 공백을 전부 제거하고 비교한다."""
    return "".join(text.split())


def main():
    print("[STT 모델 로드 중 — 최초 1회만 시간 걸림]")
    load_stt_model()

    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    for text in SENTENCES:
        waveform, sample_rate = tts_synthesize(text)
        sf.write(TMP_WAV, waveform, sample_rate)

        hypothesis = _transcribe_audio(TMP_WAV)
        wer = jiwer.wer(normalize(text), normalize(hypothesis))

        rows.append((text, hypothesis, f"{wer:.4f}"))
        print(f"[WER={wer:.3f}] 원문='{text}' | 인식='{hypothesis}'")

    TMP_WAV.unlink(missing_ok=True)

    with open(RESULTS_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "hypothesis", "wer"])
        writer.writerows(rows)

    avg_wer = sum(float(r[2]) for r in rows) / len(rows)
    print(f"\n평균 WER: {avg_wer:.4f}")
    print(f"결과 저장: {RESULTS_CSV}")


if __name__ == "__main__":
    main()
