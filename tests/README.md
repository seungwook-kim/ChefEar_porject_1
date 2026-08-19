# tests/ — 테스트 작업 공간

## 이 폴더가 하는 일

두 가지 서로 다른 성격의 테스트가 섞여 있다.

1. **pytest 유닛테스트** — `src/orchestration/`의 로직을 `FakeSupabaseClient`로 격리해서 검증
2. **수동 통합테스트 문서/벤치마크 스크립트** — pytest가 아니라 사람이 직접 실행/체크하는 형태로
   의도된 것(`docs/ChefEar_팀_진행_가이드_v2.md` 106번째 줄에 명시)

## 파일별 상태 (확인: 2026-08-17)

| 파일 | 상태 | 성격 |
|---|---|---|
| `conftest.py` | 완성 | `src/`를 `sys.path`에 등록 |
| `fake_supabase.py` | 완성 | `orchestration/mock_client.py`와 동일 엔진(그걸 그대로 가져다 씀) |
| `test_pipeline.py` | 완성 | AC-07~09, AC-12/13 |
| `test_intent_classifier.py` | 완성 | AC-01/02/10, EC-01~05 |
| `test_recipe_search.py` | 완성 | AC-03~05, EC-06~09, EC-18~20 |
| `test_registration.py` | 완성 | AC-06, EC-14~17 |
| `test_substitution.py` | 완성 | EC-21/AC-11 |
| `test_identity.py` | 완성 | 쿠키 UUID(작업3) |
| `test_mock_client.py` | 완성 | `db.get_client()` mock 자동 폴백 확인 |
| `test_tts_pronunciation.py` | **신규(2026-08-19)** | `src/tts/pronunciation.py`의 발음 보정(겹받침 연음 오발음 패치, 예: "닭을"→"달글") 회귀테스트. `torch`/`qwen_tts` 불필요 — 순수 문자열 치환이라 pytest 전체 스위트에 GPU 의존성 안 늘림(일부러 `infer.py`와 분리) |
| `test-audio/` | **신규(2026-08-19), git 미커밋 상태** | pytest 대상 아님 — TTS 발음/속도 실험하며 만든 청취 확인용 wav 모음(GPU 벤치마크 문장, "닭을" 겹받침 연음 비교 등). `roundtrip_audio/`와 마찬가지로 용량 문제로 커밋 안 하는 쪽이 기존 관례와 맞음, 커밋 여부 팀 확인 필요 |
| `integration_test.md` | **작성 완료(137줄), AC-14/15 전체 PASS(2026-08-16)** | AC-14~16(GWT) 기준 **수동** 시나리오 체크리스트(시나리오 A~D + AC-15 반복테스트 + AC-16 자리) — `handle_utterance()`를 파이썬에서 직접 호출하는 방식, `app.py`가 없어도 지금 바로 실행 가능. AC-16(TTS)만 아직 블로킹 표시 |
| `integration_scenario_test.py` | 작성됨, **31/31 PASS(2026-08-16)** | 위 `integration_test.md`의 시나리오 A~D + AC-15를 코드로 그대로 옮겨 순차 실행하는 진단 스크립트. 실제 DB 연결(`allow_mock=False`) 필요, GPU 불필요. 실행 결과(PASS/FAIL)를 보고 `integration_test.md` 체크박스를 채우는 용도 — pytest 아님, assert로 죽지 않고 끝까지 돌고 마지막에 요약 출력. ⚠️ 이 파일은 아직 `seunguk` 브랜치에만 있고 `main`엔 없음 — 병합 필요 |
| `tts_cpu_inference_test.py` | 버그 2개 수정 후 Colab(2 vCPU)에서 정식 실행 완료(2026-08-17) | Qwen3-TTS CPU 추론 속도 실측(HF Spaces CPU Basic 2 vCPU 흉내), 5초 목표 PASS/FAIL 판정. `qwen_tts` 패키지 필요. **결과: 3문장 전부 FAIL, 전체 평균 197.48초(목표의 약 39.5배)** — CSV는 `cpu_inference_test_20260816_164450.csv`, 상세는 `../src/tts/README.md` 참고 |
| `tts_stt_roundtrip_test.py` | **실행 완료(2026-08-17), 결과 확보** | `src/tts/infer.py`로 합성 → `src/stt/infer.py`로 재인식 → CER 계산(AC-16 관련, WER 아니라 CER로 변경됨). **GPU 필요**(STT의 4bit 로딩이 CUDA 전용) + private TTS repo라 `HF_TOKEN` 필요. `requirements-stt.txt`(`transformers==4.46.3`)와 `qwen-tts`(`transformers==4.57.3` 요구) 버전 충돌은 `requirements-stt.txt`를 `4.57.3`으로 올려서 해결(`docs/decisions.md` 참고). TTS↔STT를 같은 프로세스에서 로드하면 bitsandbytes 4bit 양자화가 CUDA 전역 상태를 오염시켜 TTS가 50배 이상 느려지는 문제도 발견해 `--phase synthesize`/`--phase transcribe` 별도 프로세스 구조로 우회. **결과(5문장): 평균 CER 1.37(문장 2개는 CER 0.05·0.00으로 양호, 나머지는 CER 0.70·1.00·5.84로 매우 나쁨)** — CER 5.84 문장은 `max_new_tokens=600` 제한으로 오디오가 잘렸을 가능성 있음. 상세: `results/README.md`, `../src/tts/README.md`의 "품질 문제"와 같은 이슈로 보임(원인 공통 조사 필요) |

## 진행 방법

- 유닛테스트는 지금 바로 실행 가능: `pytest tests/ -k "not tts_cpu_inference"`
  (`tts_cpu_inference_test.py`는 pytest 규약이 아니라 `python tests/tts_cpu_inference_test.py`로 직접 실행)
- `integration_test.md`는 이미 채워졌다 — 문서에 적힌 `uv run` 명령으로 파이썬 셸을 열고, 각
  시나리오의 `handle_utterance(...)` 호출을 순서대로 실행하며 PASS/FAIL 체크박스를 채우면 된다.
- `tts_cpu_inference_test.py`는 GPU 없는 머신(또는 `CUDA_VISIBLE_DEVICES=""` 강제)에서 실행해서
  실제 HF Spaces CPU 환경과 비슷한 조건으로 측정한다. 결과는 `results/tts/cpu_inference_test.csv`.

## 필요한 것 / 막힌 것

- AC-16(TTS)은 이제 CPU 속도(FAIL, 197초)와 roundtrip CER(문장별 편차 큼, 평균 1.37) 두 수치 다
  나왔음 — ⚠️ 다만 둘 다 "목표 미달/품질 불안정" 상태라 그대로 AC-16을 PASS로 채울 수는 없고,
  ① CPU 배포 속도 대안(`docs/decisions.md` 참고) ② 일부 문장에서 CER이 튀는 원인(잘림 vs 발음
  품질) 규명이 먼저 필요
- `src/app.py`가 비어있어 "화면에서 실제로 눌러보는" 통합테스트는 아직 불가능 — 지금은
  `integration_test.md`대로 함수 단위(`handle_utterance()`)로 확인하는 수준까지만 가능. 최상위
  `ui/`(mock 데이터 프로토타입, `../ui/README.md`)로 화면 흐름 자체는 미리 볼 수 있음
- pytest 전체 스위트(`test_pipeline.py` 등 9개 파일, 50개 테스트) 2026-08-17 재확인 — **50/50 PASS**.
  단, `pipeline.py`의 재료대체 매칭 실패 응답에 `match_type: "none"`이 들어가는지는 어떤 pytest도
  검증하지 않음(`test_substitution.py`는 `apply_substitution()` 자체만 봄) — `main` 브랜치엔 이
  필드가 빠져 있어(`docs/decisions.md` 2026-08-17 항목 참고) 회귀 테스트 없이는 병합 중 조용히
  없어질 수 있음

## 관련 문서

`docs/ChefEar_PRD_SDD_v0.8.md` 6장 AC-14~16, `docs/ChefEar_팀_진행_가이드_v2.md` Day5~7 일정.
