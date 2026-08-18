# src/stt/ — 담당: 하주성 (C, STT 파인튜닝)

## 이 폴더가 하는 일

`openai/whisper-large-v3-turbo`를 QLoRA(4-bit NF4)로 ChefEar 요리 도메인에 파인튜닝하고, 평가 및 통합환경에서 STT 추론을 담당합니다.

현재 Whisper Small, wav2vec2 비교 실험을 거쳐 Whisper Large 계열을 최종 STT 모델로 선정했으며, TTS 생성 음성을 검증하는 통합 테스트를 진행 중입니다.

학습 환경 및 패키지 버전은 `docs/stt.md`, `requirements-stt.txt`를 기준으로 합니다.

## 파일별 상태 (확인: 2026-08-16)

| 파일                    | 상태     | 역할                            |
| --------------------- | ------ | ----------------------------- |
| `prepare_data.py`     | 재확인 필요 | STT 학습 데이터 준비 및 전처리           |
| `finetune_whisper.py` | 재확인 필요 | Whisper QLoRA 파인튜닝            |
| `infer.py`            | 작성됨    | 최종 Adapter 로딩, 배치 평가 및 STT 추론 |

현재 `infer.py`는 배치 평가 중심이며, 통합환경에서 사용할 단일 발화 추론 함수 `stt_transcribe()`는 추가 정리가 필요합니다.

## 현재까지 진행

1. Whisper Small 파인튜닝 및 평가 완료
2. Whisper Large-v3-turbo QLoRA 파인튜닝 완료
3. Fixed100 / New500 평가 완료
4. wav2vec2 비교군 실험 완료
5. 비교 결과 기준 Whisper Large 최종 선정
6. 현재 TTS 생성 음성을 최종 STT 모델로 검증하는 통합 테스트 진행 중

## 모델 비교

* **Whisper Small**: 경량 비교군
* **wav2vec2**: 타 STT 구조 비교군
* **Whisper Large-v3-turbo**: 최종 선정 모델

wav2vec2는 ChefEar 요리 문장에서 숫자·단위·일부 한국어 음절 처리 시 토크나이저 제약이 확인되었고, 300개 파인튜닝 후에도 Whisper 계열 대비 성능이 낮아 추가 실험을 중단했습니다.

상세 결과:

* `ChefEar_STT_3model_comparison_final.csv`
* `ChefEar_Whisper_small_실험요약.csv`
* `wav2vec2_experiment_summary.csv`

## 현재 진행 / 남은 작업

* TTS → STT 검증 통합 — `tests/tts_stt_roundtrip_test.py`로 2026-08-17 실행 완료(GPU 환경, `python tests/tts_stt_roundtrip_test.py`), 결과는 `results/tts/roundtrip_cer.csv`(지표를 WER에서 CER로 변경, 상세는 `../../tests/README.md`·`../tts/README.md` 참고). 5문장 평균 CER 1.37, 문장별 편차가 커서(0.00~5.84) 추가 원인 분석 필요
* STT+TTS를 한 환경에 같이 설치할 때 `transformers` 버전 충돌(`4.46.3` vs `qwen-tts`가 요구하는 `4.57.3`)이 있었는데, `requirements-stt.txt`를 `4.57.3`으로 올려서 해결·검증함(`../../docs/decisions.md` 참고) — Whisper+PEFT+bitsandbytes 로딩은 최신 transformers에서도 문제없이 동작
* 실제 통합환경에서 오류 유형 수집
* `stt_transcribe()` 단일 발화 추론 함수 정리
* `src/orchestration/pipeline.py` 연결 확인
* Streamlit / HF Spaces 배포 환경 검증
* 필요 시 faster-whisper / CTranslate2 기반 경량화

## 주의

현재 학습/평가용 `infer.py`는 `transformers + peft + bitsandbytes` 기반입니다.

HF Spaces 배포에서는 현재 구조를 그대로 사용하기보다, 메모리와 추론 속도를 고려해 `faster-whisper` 또는 별도 경량화 경로를 검토해야 합니다.

## 관련 문서

* `docs/stt.md`
* `docs/ChefEar_PRD_SDD_v0.8.md`
* `docs/ChefEar_팀_진행_가이드_v2.md`
* `requirements-stt.txt`
* `src/tts/README.md`