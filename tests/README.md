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
| `integration_test.md` | **비어있음** | AC-14~16(GWT) 기준 **수동** 시나리오 체크리스트 — pytest 아님, 통합테스트 당일 팀원이 직접 따라갈 문서. 아직 안 써짐 |
| `tts_cpu_inference_test.py` | 작성됨(신규, untracked) | Qwen3-TTS CPU 추론 속도 실측(HF Spaces CPU Basic 2 vCPU 흉내), 5초 목표 PASS/FAIL 판정. `qwen_tts` 패키지 필요 |

## 진행 방법

- 유닛테스트는 지금 바로 실행 가능: `pytest tests/ -k "not tts_cpu_inference"`
  (`tts_cpu_inference_test.py`는 pytest 규약이 아니라 `python tests/tts_cpu_inference_test.py`로 직접 실행)
- `integration_test.md`는 통합테스트(내일/모레) 전에 AC-14(핵심 시나리오 완주)·AC-15(반복 질의
  일관성)·AC-16(TTS WER 비교) 기준으로 Given-When-Then 시나리오를 채워야 한다. 아직 없으므로
  이게 이 폴더에서 제일 시급한 작업.
- `tts_cpu_inference_test.py`는 GPU 없는 머신(또는 `CUDA_VISIBLE_DEVICES=""` 강제)에서 실행해서
  실제 HF Spaces CPU 환경과 비슷한 조건으로 측정한다. 결과는 `results/tts/cpu_inference_test.csv`.

## 필요한 것 / 막힌 것

- `integration_test.md` 시나리오 작성 자체가 비어있음(최우선)
- 통합테스트를 "파인튜닝 1차 모델 포함"으로 하려면 `models/stt_finetuned/`·`models/tts_finetuned/`에
  체크포인트가 있어야 함(현재 둘 다 비어있음, [../models/README.md](../models/README.md) 참고)
- `src/app.py`가 비어있어 "화면에서 실제로 눌러보는" 통합테스트는 아직 불가능 — 지금은 각 모듈을
  함수 단위로 이어붙여 확인하는 수준까지만 가능

## 관련 문서

`docs/ChefEar_PRD_SDD_v0.8.md` 6장 AC-14~16, `docs/ChefEar_팀_진행_가이드_v2.md` Day5~7 일정.
