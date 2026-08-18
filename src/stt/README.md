# src/stt/ — 담당: 하주성 (C, STT 파인튜닝)

## 이 폴더가 하는 일

`openai/whisper-large-v3-turbo`를 QLoRA(4-bit NF4) 방식으로 ChefEar 요리 도메인에 파인튜닝하고, 평가 및 통합환경에서 STT 추론을 담당합니다.

Whisper Small, wav2vec2 비교 실험을 거쳐 Whisper Large-v3-turbo를 최종 STT 모델로 선정했습니다.

현재 V1 STT Adapter를 기준으로 추론 및 통합 테스트가 가능하며, 기존 모델이 어려워했던 숫자·단위·온도·시간·복합 조리 표현을 보강하기 위한 STT V2 추가 파인튜닝 실험을 준비하고 있습니다.

학습 환경 및 패키지 버전은 `docs/stt.md`, `requirements-stt.txt`를 기준으로 합니다.

## 파일별 상태 (확인: 2026-08-17)

`prepare_data.py`는 STT 학습 데이터 준비 및 전처리에 사용합니다.

`finetune_whisper.py`는 현재 비어 있으며, V2 추가 파인튜닝 코드 작성 예정입니다.

`infer.py`는 최종 Adapter 로딩 및 STT 추론에 사용하며, 2026-08-17 기준 `.env` 기반 모델 경로 로딩 방식으로 수정했습니다.

## 현재 STT 모델

Base Model은 `openai/whisper-large-v3-turbo`를 사용합니다.

현재 V1 Adapter는 `leeony/chefear-stt-large-v3-turbo`이며, 로컬 최종 Adapter는 `BEST_FINAL_mix750_replay_numeric`을 기준으로 사용합니다.

V2 실험은 새로운 Adapter를 처음부터 만드는 방식이 아니라, 기존 V1 최종 Adapter를 학습 가능한 상태로 다시 로드한 뒤 신규 데이터로 추가 파인튜닝하는 방향으로 진행합니다.

## infer.py 환경변수 적용

기존 `infer.py`에서는 STT Adapter Repo가 코드 내부에 직접 하드코딩되어 있었습니다.

기존 방식은 다음과 같습니다.

`HF_ADAPTER_ID = "leeony/chefear-stt-large-v3-turbo"`

2026-08-17 수정 후에는 프로젝트 루트의 `.env`에서 `HF_STT_MODEL_REPO` 값을 읽도록 변경했습니다.

현재 `infer.py`에서는 `import os`, `Path`, `load_dotenv`를 사용하여 프로젝트 루트의 `.env`를 불러옵니다.

프로젝트 루트 `.env`에서는 다음과 같이 STT 모델 Repo를 관리합니다.

`HF_STT_MODEL_REPO=leeony/chefear-stt-large-v3-turbo`

이 구조를 사용하면 향후 STT V2 Adapter가 완성된 뒤에도 `infer.py`를 직접 수정하지 않고 `.env`의 Repo 주소만 변경하여 V1 / V2 모델을 전환할 수 있습니다.

## 현재까지 진행

1. Whisper Small 파인튜닝 및 평가 완료
2. Whisper Large-v3-turbo QLoRA 파인튜닝 완료
3. Fixed100 / New500 평가 완료
4. wav2vec2 비교군 실험 완료
5. 비교 결과 기준 Whisper Large-v3-turbo 최종 선정
6. V1 최종 Adapter 구성 완료
7. `infer.py` 내부 STT Adapter Repo 하드코딩 제거
8. `.env`의 `HF_STT_MODEL_REPO` 기반 모델 로딩 적용
9. STT 통합환경 패키지 버전 재검증
10. `requirements-stt.txt`를 현재 검증된 통합환경 기준으로 수정
11. V2용 전체 학습 후보 CSV 전처리 보강
12. 기존 학습 / Validation / Test 데이터와 신규 V2 후보 문장 중복 검사
13. 기존 데이터와 겹치지 않는 신규 V2 학습 문장 300개 선정
14. 신규 300문장에 대한 STT 학습용 합성음성 생성 진행

## V2 데이터 전처리

V2에서는 기존 모델이 상대적으로 어려워했던 숫자·단위·온도·시간·복합 조리 표현을 추가로 학습하기 위해 기존 요리 텍스트 데이터의 정규화를 보강했습니다.

V2 전체 후보 데이터는 `ChefEar_STT_V2_train.csv`를 사용합니다.

전체 후보 문장 약 207,000건을 대상으로 전처리 및 중복 제거를 수행했습니다.

영문 단위가 실제 서비스에서 잘못 읽히는 문제를 줄이기 위해 숫자와 단위를 한국어 표현으로 정규화했습니다.

예시는 다음과 같습니다.

`185 g → 185그램`

`13 ml → 13밀리리터`

`5 mg → 5밀리그램`

`1.5 L → 1.5리터`

`2 T → 2큰술`

`1 tsp → 1작은술`

`187 도에서 → 187도에서`

추가로 `그램 을 → 그램을`, `밀리리터 을 → 밀리리터를`, `도 에서 → 도에서`, `분 간 → 분간`과 같은 단위와 조사 사이의 불필요한 공백도 정리했습니다.

전처리 후 `g`, `kg`, `mg`, `ml`, `L/l`, `T`, `TS`, `tsp`, `tbsp` 등의 대상 영문 단위가 남아있는지 다시 검사했고, 현재 대상 패턴은 모두 0건으로 확인했습니다.

## V2 신규 학습 문장 300개

V2는 기존 학습 데이터를 그대로 반복해서 사용하는 방식이 아니라, 기존 모델이 학습하지 않은 독립 문장을 새로 선정하는 방식으로 진행합니다.

최종 신규 학습 파일은 `ChefEar_train_sample_300.csv`입니다.

신규 300문장은 기존 STT 학습 데이터, Numeric reinforcement 데이터, Replay / Mix 학습 데이터, Validation 500, Fixed Test 100, 별도 외부 검증 문장과 겹치지 않도록 중복 검사를 수행했습니다.

V2 신규 문장은 단순 랜덤 추출이 아니라 기존 모델이 상대적으로 어려워했던 표현을 우선 포함하도록 구성했습니다.

주요 대상은 숫자 + 단위, 단위 + 조사, 온도 표현, 시간 표현, 수량 표현, 긴 조리 문장, 여러 조리 동작이 포함된 문장, 생소한 재료명 및 복합 요리 표현, 일반 조리 지시문입니다.

현재 신규 독립 학습 문장 300개 선정 및 CSV 저장까지 완료했습니다.

## V2 신규 학습 음성

신규 300문장에 대응하는 STT 학습용 음성을 별도로 생성합니다.

음성 파일은 CSV의 `v2_id`와 1:1로 연결합니다.

예시는 다음과 같습니다.

`v2_0001 → v2_0001.mp3`

`v2_0002 → v2_0002.mp3`

`v2_0003 → v2_0003.mp3`

현재 신규 학습 음성은 `ko-KR-SunHiNeural` 기반으로 생성하고 있습니다.

현재 수정 중인 ChefEar 팀 TTS 모델은 STT V2 신규 학습 데이터 생성에 사용하지 않습니다.

STT V2 학습용 음성 생성은 팀 TTS와 분리하여 진행합니다.

## V2 파인튜닝 계획

V2는 기존 V1 최종 Adapter인 `BEST_FINAL_mix750_replay_numeric`에서 이어서 추가 학습합니다.

V1 Adapter를 `is_trainable=True` 상태로 로드한 뒤 신규 독립 문장 300개와 이에 대응하는 신규 음성 300개를 사용하여 추가 QLoRA 파인튜닝을 진행할 예정입니다.

기존 V1 Adapter는 덮어쓰지 않고 V2 Adapter를 별도 경로에 저장합니다.

현재 단계에서는 V2용 전체 텍스트 전처리, 기존 데이터와의 중복 제거, 신규 독립 학습 문장 300개 선정 및 저장까지 완료했고, 신규 학습 음성 생성 단계까지 진행합니다.

V2 실제 파인튜닝 및 Hugging Face 업로드는 신규 음성 생성 및 검수 후 진행할 예정입니다.

## V2 평가 계획

V2 학습에 사용된 신규 300개 데이터는 최종 성능 평가에 다시 사용하지 않습니다.

기존에 분리해 둔 Validation 500과 Fixed Test 100을 그대로 유지하여 V1과 V2를 동일한 조건에서 비교합니다.

Validation 데이터는 `ChefEar_validation_new_500.csv`와 `validation_audio_500`을 사용합니다.

Test 데이터는 `ChefEar_test_fixed_100.csv`와 `test_audio_100`을 사용합니다.

추가로 기존 모델이 학습하지 않은 별도 합성음성 테스트 세트도 유지하여 숫자·단위·희귀 표현 등에 대한 V1 / V2 차이를 비교할 예정입니다.

## 모델 비교

Whisper Small은 경량 비교군으로 사용했습니다.

wav2vec2는 타 STT 구조 비교군으로 사용했으며, ChefEar 요리 문장에서 숫자·단위·일부 한국어 음절 처리 시 토크나이저 제약이 확인되었습니다.

wav2vec2는 300개 파인튜닝 후에도 Whisper 계열 대비 성능이 낮아 추가 실험을 중단했습니다.

Whisper Large-v3-turbo는 최종 STT 모델로 선정했으며, 현재 V1 Adapter를 기준으로 V2 추가 파인튜닝을 준비하고 있습니다.

상세 결과는 다음 파일에서 확인할 수 있습니다.

`ChefEar_STT_3model_comparison_final.csv`

`ChefEar_Whisper_small_실험요약.csv`

`wav2vec2_experiment_summary.csv`

## TTS → STT 통합 테스트

TTS → STT 통합 테스트 스크립트는 `tests/tts_stt_roundtrip_test.py`입니다.

통합 테스트에서는 TTS가 생성한 음성을 STT로 전달하고, 원문과 STT 인식 결과를 비교하여 WER을 계산합니다.

`tts_stt_roundtrip_test.py`는 STT 모델 Repo를 별도로 하드코딩하지 않고 `src/stt/infer.py`를 통해 현재 설정된 STT Adapter를 사용합니다.

따라서 향후 `.env`의 `HF_STT_MODEL_REPO`를 V2 Repo로 변경하면 동일한 통합 테스트 구조에서 V2 모델을 검증할 수 있습니다.

현재 팀 TTS 모델은 수정 작업이 진행 중이므로, STT V2 데이터 준비와 추가 파인튜닝 작업은 별도로 진행합니다.

## 현재 진행 / 남은 작업

* TTS → STT 검증 통합 — `tests/tts_stt_roundtrip_test.py`로 2026-08-17 실행 완료(GPU 환경, `python tests/tts_stt_roundtrip_test.py`), 결과는 `results/tts/roundtrip_cer.csv`(지표를 WER에서 CER로 변경, 상세는 `../../tests/README.md`·`../tts/README.md` 참고). 5문장 평균 CER 1.37, 문장별 편차가 커서(0.00~5.84) 추가 원인 분석 필요
* STT+TTS를 한 환경에 같이 설치할 때 `transformers` 버전 충돌(`4.46.3` vs `qwen-tts`가 요구하는 `4.57.3`)이 있었는데, `requirements-stt.txt`를 `4.57.3`으로 올려서 해결·검증함(`../../docs/decisions.md` 참고) — Whisper+PEFT+bitsandbytes 로딩은 최신 transformers에서도 문제없이 동작
* 실제 통합환경에서 오류 유형 수집
* `stt_transcribe()` 단일 발화 추론 함수 정리
* V2 신규 음성 300개 생성 및 검수
* `finetune_whisper.py` V2 추가 파인튜닝 코드 작성
* 기존 `BEST_FINAL_mix750_replay_numeric` Adapter에서 V2 추가 파인튜닝
* V2 Adapter 별도 저장
* Validation 500 기준 V1 / V2 성능 비교
* Fixed Test 100 기준 V1 / V2 성능 비교
* 별도 외부 음성 기준 V1 / V2 성능 비교
* V2 성능 개선 확인 후 Hugging Face Adapter 업데이트
* 팀 TTS 수정 완료 후 TTS → STT 통합 재검증
* `src/orchestration/pipeline.py` 연결 확인
* Streamlit / HF Spaces 배포 환경 검증
* 필요 시 faster-whisper / CTranslate2 기반 경량화 검토

## 주의

현재 학습 및 평가용 STT는 `transformers + peft + bitsandbytes + Whisper Large-v3-turbo + LoRA Adapter` 구조를 사용합니다.

V2 학습 시 기존 V1 Adapter를 덮어쓰지 않고 별도의 V2 결과 경로에 저장해야 합니다.

Validation / Test 데이터는 V2 학습에 포함하지 않습니다.

현재 수정 중인 팀 TTS 모델의 출력 음성은 STT V2 신규 학습 데이터에 사용하지 않습니다.

HF Spaces 배포에서는 현재 구조를 그대로 사용하기보다 메모리와 추론 속도를 고려해 `faster-whisper` 또는 별도의 경량화 경로를 검토해야 합니다.

## 관련 문서

* `docs/stt.md`
* `docs/ChefEar_PRD_SDD_v0.8.md`
* `docs/ChefEar_팀_진행_가이드_v2.md`
* `requirements-stt.txt`
* `src/tts/README.md`
* `tests/tts_stt_roundtrip_test.py`