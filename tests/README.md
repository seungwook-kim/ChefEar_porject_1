# tests/ — 테스트 작업 공간

## 이 폴더가 하는 일

두 가지 서로 다른 성격의 테스트가 섞여 있다.

1. **pytest 유닛테스트** — `src/orchestration/`의 로직을 `FakeSupabaseClient`로 격리해서 검증
2. **수동 통합테스트 문서/벤치마크 스크립트** — pytest가 아니라 사람이 직접 실행/체크하는 형태로
   의도된 것(`docs/ChefEar_팀_진행_가이드_v2.md` 106번째 줄에 명시)

## 파일별 상태 (확인: 2026-08-16)

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
| `integration_test.md` | **작성 완료(137줄)** | AC-14~16(GWT) 기준 **수동** 시나리오 체크리스트(시나리오 A~D + AC-15 반복테스트 + AC-16 자리) — `handle_utterance()`를 파이썬에서 직접 호출하는 방식, `app.py`가 없어도 지금 바로 실행 가능. AC-16(TTS)만 아직 블로킹 표시 |
| `integration_scenario_test.py` | 작성됨(신규) | 위 `integration_test.md`의 시나리오 A~D + AC-15를 코드로 그대로 옮겨 순차 실행하는 진단 스크립트. 실제 DB 연결(`allow_mock=False`) 필요, GPU 불필요. 실행 결과(PASS/FAIL)를 보고 `integration_test.md` 체크박스를 채우는 용도 — pytest 아님, assert로 죽지 않고 끝까지 돌고 마지막에 요약 출력 |
| `tts_cpu_inference_test.py` | 작성됨(신규, untracked) | Qwen3-TTS CPU 추론 속도 실측(HF Spaces CPU Basic 2 vCPU 흉내), 5초 목표 PASS/FAIL 판정. `qwen_tts` 패키지 필요 |
| `tts_stt_roundtrip_test.py` | 작성됨(신규) | `src/tts/infer.py`로 합성 → `src/stt/infer.py`로 재인식 → WER 계산(AC-16 관련). **GPU 필요**(STT의 4bit 로딩이 CUDA 전용) + private TTS repo라 `HF_TOKEN` 필요 |

## 진행 방법

- 유닛테스트는 지금 바로 실행 가능: `pytest tests/ -k "not tts_cpu_inference"`
  (`tts_cpu_inference_test.py`는 pytest 규약이 아니라 `python tests/tts_cpu_inference_test.py`로 직접 실행)
- `integration_test.md`는 이미 채워졌다 — 문서에 적힌 `uv run` 명령으로 파이썬 셸을 열고, 각
  시나리오의 `handle_utterance(...)` 호출을 순서대로 실행하며 PASS/FAIL 체크박스를 채우면 된다.
- `tts_cpu_inference_test.py`는 GPU 없는 머신(또는 `CUDA_VISIBLE_DEVICES=""` 강제)에서 실행해서
  실제 HF Spaces CPU 환경과 비슷한 조건으로 측정한다. 결과는 `results/tts/cpu_inference_test.csv`.

## 필요한 것 / 막힌 것

- AC-16(TTS)은 파인튜닝 결과가 나와야 채울 수 있음 — TTS 자체는 완료됐으니(`../src/tts/README.md`
  참고) WER/청취 평가 수치만 채우면 됨
- `src/app.py`가 비어있어 "화면에서 실제로 눌러보는" 통합테스트는 아직 불가능 — 지금은
  `integration_test.md`대로 함수 단위(`handle_utterance()`)로 확인하는 수준까지만 가능. 최상위
  `ui/`(mock 데이터 프로토타입, `../ui/README.md`)로 화면 흐름 자체는 미리 볼 수 있음

## 관련 문서

`docs/ChefEar_PRD_SDD_v0.8.md` 6장 AC-14~16, `docs/ChefEar_팀_진행_가이드_v2.md` Day5~7 일정.
