# src/orchestration/ — 담당: 김승욱 (A, 오케스트레이션/통합 주관)

## 이 폴더가 하는 일

의도분류·조리순서 조회·재료대체·신규등록·DB 연결을 담당하는 순수 로직 계층. LLM을 쓰지 않고
sentence-transformers 임베딩 유사도 + Supabase 실데이터 조회로만 동작한다(AGENTS.md 절대 원칙).
Streamlit 세션(`st.session_state`)을 함수 인자로 받는 형태라 Streamlit 없이도 dict만으로 테스트 가능.

## 파일별 상태 (확인: 2026-08-16)

| 파일 | 상태 | 역할 |
|---|---|---|
| `db.py` | 완성 | `get_client()` — Supabase 자격증명 없으면 자동으로 `mock_client.py`로 폴백 |
| `mock_client.py` | 완성 | 강사 체크리스트 4번용 가짜 Supabase 클라이언트, 문서 5장 시나리오 시드 데이터 포함 |
| `identity.py` | 완성 | 쿠키 기반 익명 UUID(`get_or_create_anon_id`), FR-08 |
| `intent_classifier.py` | 완성 | `classify_intent()` — `jhgan/ko-sroberta-multitask` 임베딩 유사도, `THRESHOLD` 상수 |
| `recipe_search.py` | 완성 | `select_standard_recipe` / `search_variant_recipe` / `search_by_ingredient_content` |
| `substitution.py` | 완성 | `apply_substitution` / `cancel_substitution`(롤백, AC-11) |
| `registration.py` | 완성 | `register_recipe`(다단계 세션) / `save_recipe`(최종 저장) |
| `load_data.py` | 완성 | CSV → Supabase 적재 CLI. `python src/orchestration/load_data.py --csv <경로> [--dry-run]` |
| `pipeline.py` | **부분 완성** | `get_precomputed_steps`/`get_current_step`/`advance_step`/`manual_fallback`(7.4/7.1.1)만 구현됨. 팀 가이드가 명시한 "STT → 의도분류 → 라우팅 → TTS 전체 조립" 함수는 **아직 없음** |

## 진행 방법

1. `.env`에 `SUPABASE_URL`/`SUPABASE_KEY`를 채우면 코드 수정 없이 mock → 실제 DB로 자동 전환된다(`db.py` docstring 참고).
2. `data/standard/`의 60,282건 CSV가 확보되면 `load_data.py --csv`로 적재한다.
3. `pipeline.py`에 최종 조립 함수를 추가해야 한다: STT 결과 텍스트 → `classify_intent()` → 의도별로 `recipe_search`/`substitution`/`registration` 라우팅 → 응답 텍스트를 TTS로 넘기는 흐름. 이게 `app.py`에서 직접 호출될 진입점이다.
4. 이 조립은 `src/stt/infer.py`의 런타임 추론 함수, `src/tts/infer.py`의 `tts_synthesize()`가 먼저 있어야 실제로 연결할 수 있다 — 둘 다 현재 비어있으므로([../stt/README.md](../stt/README.md), [../tts/README.md](../tts/README.md) 참고) 그 전까지는 텍스트 인터페이스만으로 조립해두고 나중에 STT/TTS 함수만 갈아끼우는 방식이 안전하다.

## 테스트

`tests/test_pipeline.py`, `test_intent_classifier.py`, `test_recipe_search.py`, `test_registration.py`,
`test_substitution.py`, `test_identity.py`, `test_mock_client.py` — 전부 `FakeSupabaseClient`로 격리해서 검증한다.
실제 Supabase(PostgREST) 연동 자체는 자격증명 확보 후 별도로 확인해야 한다(mock으로는 잡히지 않음).

```
pytest tests/ -k "not tts_cpu_inference"
```

## 관련 문서

`docs/ChefEar_PRD_SDD_v0.8.md` 7.1~7.6(함수 목록), AC-01~13. 코드 자체 주석이 각 문서 절 번호를 인용하고 있어
함수별 상세 근거는 각 파일 docstring이 더 빠르다(문서 재검색 불필요).
