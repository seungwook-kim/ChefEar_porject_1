# src/tts/ — 담당: 홍민하 (B, TTS 파인튜닝/UI)

## 이 폴더가 하는 일

Qwen3-TTS-12Hz-1.7B(VoiceDesign)를 KSS 데이터셋으로 파인튜닝하고, HF Spaces CPU Basic(무료)
환경에서 목표 응답시간(5초) 안에 추론이 되는지가 핵심 리스크(R-13/OI-11, `docs/decisions.md`).

## 파일별 상태 (확인: 2026-08-16)

| 파일 | 상태 | 역할 |
|---|---|---|
| `prepare_data.py` | **비어있음(0줄)** | KSS 24kHz 리샘플링 — 실제로는 별도 개인 작업 공간(`test/scripts/prepare_qwen3_tts_data.py`)에서 이미 진행됨, 이 정식 위치로는 아직 이식 안 됨 |
| `finetune_qwen3tts.py` | **비어있음(0줄)** | Qwen3-TTS QLoRA 파인튜닝 — 마찬가지로 `test/scripts/train_qwen3_tts.py`에서 이미 완료(checkpoint-epoch-8까지, Colab A100), 이 정식 위치로는 아직 이식 안 됨 |
| `infer.py` | **완성** | `tts_synthesize(text) -> (waveform, sample_rate)`. 파인튜닝 모델(`kimseunguk/qwen3-tts-kss-finetuned`, private HF repo, 화자 `kss_speaker_a100`)을 로드해 합성. GPU 있으면 cuda/bfloat16, 없으면 CPU/float32로 자동 분기 |

**파인튜닝 자체는 끝났다**: `Qwen3-TTS-12Hz-1.7B-Base`를 KSS로 QLoRA 파인튜닝(checkpoint-epoch-8) 후
merge_and_unload해서 HF Hub `kimseunguk/qwen3-tts-kss-finetuned`(private)에 업로드 완료. 다만 학습에
쓴 코드(`prepare_data.py`/`finetune_qwen3tts.py`에 해당하는 것)는 이 저장소가 아니라 별도 개인 작업
공간(`test/`, git 추적 안 됨)에만 있다 — 나중에 정식 위치로 옮겨 담아야 재현 가능한 상태가 된다.

`tests/tts_cpu_inference_test.py`(CPU 추론 속도 벤치마크)는 아직 이 파인튜닝 모델이 아니라
`models/tts_finetuned/`(비어있음) 또는 사전학습 베이스 모델 기준으로만 실측했다 — 실제 파인튜닝
모델로 5초 목표 재측정이 아직 안 됨.

## 진행 방법

1. ~~`data/kss/` 24kHz 리샘플링~~ → 완료(`test/` 쪽에서)
2. ~~QLoRA 파인튜닝~~ → 완료(checkpoint-epoch-8, HF Hub 업로드까지 끝남)
3. `prepare_data.py`/`finetune_qwen3tts.py`를 `test/scripts/`의 대응 코드로 채워서 이 저장소 안에서도
   재현 가능하게 이식(팀 문서상 정식 위치이므로 언젠가 필요)
4. `models/tts_finetuned/`에 체크포인트를 받아두고 `tests/tts_cpu_inference_test.py`로 CPU 5초 목표
   재측정(`docs/decisions.md` 2번 항목, 지금은 베이스 모델 기준 수치만 있음)
5. `infer.py`의 `tts_synthesize()`를 `src/orchestration/pipeline.py`/`src/app.py`에 연결
   (`handle_utterance()`의 텍스트 응답을 이 함수에 넘기고 반환값을 `st.audio()`로 재생)
6. `requirements.txt`/`requirements-main.txt`에 `qwen_tts` 패키지 버전 확정해서 추가(아직 미정)
7. 5초 목표 미달 시 대안: ① Modal 등 GPU 플랫폼 ② 데스크탑을 Tailscale로 상시 노출 ③ Qwen3-TTS 0.6B로 축소

## 필요한 것 / 막힌 것

- `qwen_tts` 패키지(버전 미정, `requirements.txt`에 아직 없음), private repo라 배포 시 `HF_TOKEN`을
  HF Spaces Repository secret으로 등록 필요
- `models/tts_finetuned/`가 로컬에 비어있어 CPU 속도 벤치마크가 아직 베이스 모델 기준 — 실제
  파인튜닝 모델로 재측정 필요
- `prepare_data.py`/`finetune_qwen3tts.py` 이식 — 지금은 재현 코드가 이 저장소 밖에만 있음
- TTS 합성음을 STT 학습데이터로 쓰려면(`data/synthesized/`) 위 이식이 선행되는 게 안전함

## 관련 문서

`docs/decisions.md`(OOM/CPU 속도 미확인 항목), `docs/ChefEar_팀_진행_가이드_v2.md` 6.1/9장,
`docs/ChefEar_PRD_SDD_v0.8.md` R-13/OI-11.
