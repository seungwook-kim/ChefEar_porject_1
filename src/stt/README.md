# src/stt/ — 담당: 하주성 (C, STT 파인튜닝)

## 이 폴더가 하는 일

`openai/whisper-large-v3-turbo`를 QLoRA(4-bit NF4)로 도메인 파인튜닝하고, 배포용으로는
faster-whisper(int8)로 변환해 추론하는 STT 파이프라인. 학습 스택 버전은 `docs/stt.md`,
`requirements-stt.txt` 기준(팀 공용 `requirements-main.txt`와 다를 수 있음, 재검증 필요 상태).

## 파일별 상태 (확인: 2026-08-16)

| 파일 | 상태 | 역할 |
|---|---|---|
| `prepare_data.py` | **비어있음(0줄)** | KSS 음성 + Qwen3-TTS 합성음 페어링 예정 |
| `finetune_whisper.py` | **비어있음(0줄)** | Whisper QLoRA 파인튜닝(학습, GPU 전용) 예정 |
| `infer.py` | 작성됨(596줄) | `run_batch_test()` — 100개 음성 일괄 WER 테스트 로직. HF Hub 어댑터 `leeony/chefear-stt-large-v3-turbo`를 `transformers`+`peft`+`bitsandbytes`(QLoRA 4bit)로 직접 로드 |

⚠️ **주의**: 현재 `infer.py`는 **오프라인 배치 평가용**(학습 검증 스택 그대로 로드)이지,
팀 가이드가 요구하는 "파인튜닝 체크포인트를 faster-whisper(int8, CTranslate2)로 변환 +
런타임 단일 발화 추론용 `stt_transcribe()`"는 **아직 없다**. `requirements.txt`(배포용)엔
`faster-whisper`만 있고 `peft`/`bitsandbytes`는 없으므로, 지금 `infer.py`를 그대로 HF Spaces에
올리면 동작하지 않는다 — 배포 경로용 변환 함수를 별도로 추가해야 한다.

## 진행 방법

1. `data/kss/`(원문 음성, wav 412개 확보됨) + `data/synthesized/`(Qwen3-TTS 합성음, 현재 비어있음 —
   TTS 파인튜닝이 먼저 끝나야 생성 가능, [../tts/README.md](../tts/README.md) 참고) 페어링 → `prepare_data.py`
2. `finetune_whisper.py`로 QLoRA 파인튜닝 (GPU 필요, `requirements-stt.txt` 스택: torch 2.5.1+cu124 /
   transformers 4.46.3 / peft 0.20.0 / bitsandbytes 0.50.0, `docs/stt.md` 참고)
3. 파인튜닝 체크포인트로 `infer.py`의 `run_batch_test(csv_path, audio_dir, result_path)`를 돌려
   `data/evaluation_scripts/stt/`(100개 검증셋, 이미 확보됨)에 대해 WER 실측 → `results/stt/`에 저장
4. faster-whisper(CTranslate2) 변환 + `stt_transcribe()` 런타임 함수 추가 — `src/orchestration/pipeline.py`
   통합 및 HF Spaces 배포에 필요, 아직 미작성

## 필요한 것 / 막힌 것

- GPU 환경(노트북 RTX 4060 8GB / 데스크탑 RTX 5070 12GB)
- `data/synthesized/`는 TTS 파인튜닝 산출물이 있어야 채워짐 — TTS 팀 진행에 의존
- 배포용 faster-whisper 변환 스크립트 자체가 없음(신규 작성 필요)

## 관련 문서

`docs/stt.md`(모델/패키지 버전), `docs/ChefEar_PRD_SDD_v0.8.md` FR-09/FR-11(파인튜닝·WER 평가 요건).
