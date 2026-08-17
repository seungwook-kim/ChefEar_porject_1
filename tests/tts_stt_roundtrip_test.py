"""ChefEar TTS→STT 라운드트립 검증 (읽기 전용 벤치마크).

파인튜닝된 TTS(src/tts/infer.py의 tts_synthesize)로 조리 안내 문장을 합성하고, 실제
ChefEar STT(src/stt/infer.py, whisper-large-v3-turbo + QLoRA)로 다시 인식시켜 WER을
잰다. "우리 TTS 음성을 우리 STT가 얼마나 잘 알아듣는가"를 보는 것 — 합성음을 STT
학습데이터(data/synthesized/)로 재사용할 수 있는지 사전 확인하는 목적도 겸한다.

⚠️ TTS와 STT를 완전히 분리된 프로세스로 실행함(2026-08-17 실측 확인): 4bit(NF4)로 양자화된
STT와 bf16 TTS를 같은 파이썬 프로세스에 같이 로드하면 TTS 합성이 극심하게 느려진다
(bitsandbytes 4bit 양자화가 CUDA/cuBLAS 전역 상태를 건드려서 같은 프로세스의 다른 모델
연산까지 같이 느려지는 것으로 보임) — 실측치: TTS 단독 17초 vs 같은 프로세스에서 STT
로드 후 TTS는 15분 넘게 걸려도 문장 1개조차 못 끝냄(50배 이상 차이). 그래서 이 스크립트는
`python tests/tts_stt_roundtrip_test.py`로 그냥 실행하면 내부적으로 자기 자신을
`--phase synthesize`(TTS만) -> `--phase transcribe`(STT만) 순서로 별도 프로세스 두 개를
띄워서 실행한다 — 쓰는 사람은 신경 쓸 필요 없이 한 줄이면 되지만, 각 phase는 독립된 CUDA
컨텍스트를 쓰게 된다.

⚠️ GPU 환경 필요: STT 로딩(src/stt/infer.py)이 bitsandbytes 4bit(NF4)를 쓰는데, 이 양자화는
CUDA 커널 기반이라 GPU 없는 환경에선 사실상 동작하지 않는다(requirements-stt.txt도
torch==2.5.1+cu124로 CUDA 빌드 고정). tests/tts_cpu_inference_test.py(CPU 벤치마크)와는
다른 목적이니 혼동하지 말 것.

⚠️ HF_TOKEN 필요: TTS 모델(kimseunguk/qwen3-tts-kss-finetuned)이 private HF repo라 .env의
HF_TOKEN이 있어야 로딩된다(src/tts/infer.py가 모듈 로드 시점에 자동으로 .env를 읽는다).

⚠️ 패키지 버전 충돌 주의(2026-08-16 실측 확인, docs/decisions.md 참고): requirements-stt.txt를
그대로 설치한 뒤 qwen-tts를 깔면 transformers 버전 충돌이 난다(requirements-stt.txt는
transformers==4.46.3 고정, qwen-tts 0.1.1은 transformers==4.57.3 요구). requirements-stt.txt는
STT 학습 때 실제로 쓴 버전의 기록이라 그대로 두고, 이 스크립트를 돌릴 땐 transformers를 낮추지
말고 qwen-tts가 요구하는 쪽(4.57.3)으로 맞춰서 설치할 것 — whisper+peft+bitsandbytes 로딩 자체는
최신 transformers에서도 문제없이 동작함을 실측으로 확인함.

⚠️ CER(글자 단위)을 씀, WER 아님: 비교 전 정규화가 공백을 다 없애기 때문에(한국어 띄어쓰기
차이로 오류율이 왜곡되는 걸 막으려고) jiwer.wer()를 쓰면 문장 전체가 "단어 1개" 취급되어
글자 하나만 달라도 100% 오류로 잘못 나온다(2026-08-17 실측 중 발견, 처음엔 이 실수로 5문장
전부 WER=1.0000이 나왔었음). 그래서 jiwer.cer()로 계산한다.

⚠️ max_new_tokens=600으로 상한을 걺(src/tts/infer.py의 DEFAULT_MAX_NEW_TOKENS): qwen_tts
기본값(2048) + do_sample=True(확률적 샘플링) 조합이라, 운 나쁘면 짧은 문장도 멈춤 토큰을
늦게 뽑아서 최대치까지 계속 생성하는 경우가 있었다(실측: 문장 1개가 15분+ 걸림). 600으로
낮춘 뒤로는 5문장 전체가 5분 안에 끝남 — 다만 제일 긴 문장은 이 상한 때문에 오디오가
잘렸을 가능성이 있으니(2026-08-17 실측: CER이 유독 나쁜 문장이 있었음) 상한값이 적절한지
결과를 보고 재조정이 필요할 수 있음.

결과: results/tts/roundtrip_cer.csv (text, hypothesis, cer)
      results/tts/roundtrip_audio/*.wav (합성된 오디오, 두 phase 사이에 이 폴더로 전달됨)
"""

import argparse
import csv
import string
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

RESULTS_DIR = PROJECT_ROOT / "results" / "tts"
AUDIO_DIR = RESULTS_DIR / "roundtrip_audio"
RESULTS_CSV = RESULTS_DIR / "roundtrip_cer.csv"

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
    """비교 전 정규화: 띄어쓰기·구두점 차이로 오류율이 왜곡되는 걸 막는다.

    공백을 전부 없애기 때문에, 이후 비교는 jiwer.wer()(단어 단위)가 아니라 반드시
    jiwer.cer()(글자 단위)로 해야 한다 — 공백이 없으면 문장 전체가 "단어 1개"로 취급되어
    글자 하나만 달라도 WER이 100%로 나와버린다(2026-08-17 실측 중 발견).
    """
    text = text.translate(str.maketrans("", "", string.punctuation + "？！。，"))
    return "".join(text.split())


def _run_synthesize():
    """1단계(별도 프로세스): TTS만 로드해서 문장들을 wav 파일로 저장."""
    import soundfile as sf

    from tts.infer import tts_synthesize

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    for i, text in enumerate(SENTENCES):
        waveform, sample_rate = tts_synthesize(text)
        sf.write(AUDIO_DIR / f"{i}.wav", waveform, sample_rate)
        print(f"[합성 완료] {i}: {text}")


def _run_transcribe():
    """2단계(별도 프로세스): STT만 로드해서 1단계가 만든 wav들을 인식하고 CER 계산."""
    import jiwer

    from stt.infer import _transcribe_audio, load_stt_model

    print("[STT 모델 로드 중 — 최초 1회만 시간 걸림]")
    load_stt_model()

    rows = []
    for i, text in enumerate(SENTENCES):
        audio_path = AUDIO_DIR / f"{i}.wav"
        hypothesis = _transcribe_audio(audio_path)
        cer = jiwer.cer(normalize(text), normalize(hypothesis))
        rows.append((text, hypothesis, f"{cer:.4f}"))
        print(f"[CER={cer:.3f}] 원문='{text}' | 인식='{hypothesis}'")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "hypothesis", "cer"])
        writer.writerows(rows)

    avg_cer = sum(float(r[2]) for r in rows) / len(rows)
    print(f"\n평균 CER: {avg_cer:.4f}")
    print(f"결과 저장: {RESULTS_CSV}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=["synthesize", "transcribe"],
        default=None,
        help="내부용 — 지정 안 하면 두 phase를 별도 프로세스로 순서대로 실행함",
    )
    args = parser.parse_args()

    if args.phase == "synthesize":
        _run_synthesize()
        return
    if args.phase == "transcribe":
        _run_transcribe()
        return

    # phase 지정 없이 실행: 자기 자신을 두 번 별도 프로세스로 재실행(위 모듈 docstring의
    # ⚠️ 설명 참고 — 같은 프로세스에 STT+TTS를 같이 두면 안 됨).
    import subprocess

    print("=== 1단계: TTS 합성 (별도 프로세스) ===")
    subprocess.run([sys.executable, __file__, "--phase", "synthesize"], check=True)

    print("\n=== 2단계: STT 인식 + WER 계산 (별도 프로세스) ===")
    subprocess.run([sys.executable, __file__, "--phase", "transcribe"], check=True)


if __name__ == "__main__":
    main()
