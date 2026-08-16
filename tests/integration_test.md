# 1주차 통합테스트 — 수동 시나리오 체크리스트

`docs/ChefEar_PRD_SDD_v0.8.md` 6장 AC-14~16(GWT), 5장 시나리오 A~D 기준. **pytest가 아니라 사람이
직접 실행하며 체크하는 문서**다(`docs/ChefEar_팀_진행_가이드_v2.md` 106행). 담당: 김승욱(A, 통합주관).

## 지금 실행 가능한 범위 (확인: 2026-08-16)

- `src/app.py`가 아직 비어있어서(홍민하 담당) **화면으로 눌러보는 통합테스트는 불가능**. 지금은
  `src/orchestration/pipeline.py`의 `handle_utterance()`를 Python에서 직접 호출해서 오케스트레이션
  레이어(의도분류→라우팅→DB)까지만 검증한다. `app.py`가 준비되면 아래 시나리오를 화면에서 그대로
  다시 확인해야 한다.
- TTS(`src/tts/infer.py`)가 아직 비어있어서(파인튜닝 진행 중) **AC-16(TTS 딥러닝 검증)은 지금 실행
  불가** — 아래 해당 절에 결과 기록 자리만 만들어두고 TTS 준비되면 채운다.
- STT는 배포 완료됐지만, 이 문서의 시나리오는 마이크 입력이 아니라 "STT가 이렇게 인식했다고 가정한
  텍스트"를 `handle_utterance()`에 직접 넣는 방식으로 진행한다(STT 인식 자체의 정확도는 이 문서의
  범위가 아니라 STT 자체 평가 스크립트의 몫).
- 지금 DB의 조리과정(`COOKING_STEPS`)은 원본 실데이터가 아니라 LLM 생성 텍스트다(`../db/README.md`
  참고). 아래 결과 텍스트가 실제 만개의레시피 원문과 다를 수 있으나, 이 문서가 검증하는 건 "로직이
  올바른 레시피/단계를 골라오는가"이지 조리과정 문장 자체의 정확성이 아니므로 무방하다.
- **발견한 설계상 공백**: 시나리오 A의 "이걸로 시작할까요?" → "응" 확인 단계는 `classify_intent()`가
  처리하지 않는다(`VALID_INTENTS`에 "긍정"이 없음 — 기준예문.csv엔 있지만 의도적으로 분류 대상에서
  제외돼 있음). 즉 "응"에 반응해서 1단계를 보여주는 로직은 아직 오케스트레이션 레이어에 없고
  `app.py`가 별도로 처리해야 한다는 뜻 — 아래 시나리오 A에서는 이 부분을 우회해서 검증한다.

## 실행 방법

```bash
uv run --with sentence-transformers==5.6.1 --with supabase==2.31.0 --python 3.12 python
```

```python
import sys; sys.path.insert(0, "src")
from orchestration.pipeline import handle_utterance
from orchestration.pipeline import get_precomputed_steps, get_current_step
from orchestration.db import get_client

client = get_client(allow_mock=False)  # 실제 Supabase 연결(.env 필요)
session = {}
```

이후 각 시나리오의 `handle_utterance(session, "발화", ..., client=client)` 호출을 순서대로 실행하고,
반환값이 기대값과 맞는지 확인한다.

---

## AC-14 핵심 시나리오 완주 (주 기준)

> GIVEN 손에 재료가 묻은 상태를 가정한 시나리오(표준레시피 기준)
> WHEN 화면 터치 없이 음성만으로 전체 조리 과정 진행
> THEN 마지막 단계까지 중단 없이 완료 — 반복 테스트 성공률 목표치는 미정, 착수 후 실측해 확정

### 시나리오 A — 조회 및 진행 (5장 시나리오 A)

| # | GIVEN | WHEN (발화/호출) | THEN (기대값) | 결과 |
|---|---|---|---|---|
| A-1 | 새 세션 | `handle_utterance(session, "된장찌개 어떻게 만들어?", dish_name="된장찌개")` | `intent == "조회"`, `session["current_recipe_id"]`가 채워짐, `session["step_number"] == 1` | [ ] PASS / [ ] FAIL |
| A-2 | A-1 이후 (확인 단계는 위 "설계상 공백" 참고, 여기선 우회) | `get_current_step(session["current_recipe_id"], 1, client=client)` | 1단계 텍스트가 반환됨(`text` 키 존재, 빈 문자열 아님) | [ ] PASS / [ ] FAIL |
| A-3 | A-1 이후 | `handle_utterance(session, "다음", client=client)` | `intent == "진행"`, `step_number == 2`, `step["text"]`가 1단계와 다른 문장 | [ ] PASS / [ ] FAIL |
| A-4 | A-3 이후 | `handle_utterance(session, "다시", client=client)` | `intent == "재청취"`, `step_number`는 2 그대로 | [ ] PASS / [ ] FAIL |
| A-5 | A-4 이후 | `handle_utterance(session, "이전", client=client)` | `intent == "이전"`, `step_number == 1` | [ ] PASS / [ ] FAIL |
| A-6 | 처음부터 끝까지 | 마지막 step_number까지 "다음"을 반복 호출 | 중간에 예외 없이 마지막 단계까지 도달, 마지막 이후 "다음"을 눌러도 서비스가 죽지 않음(단, 범위 밖 step_number 동작은 7.1.1에 명시 없음 — 실측 후 팀 논의 필요) | [ ] PASS / [ ] FAIL |

### 시나리오 B — 진행 중 재료 대체 (5장 시나리오 B)

| # | GIVEN | WHEN | THEN | 결과 |
|---|---|---|---|---|
| B-1 | session의 `current_recipe_id`가 "된장찌개"(A-1 이어서, 또는 새로 조회) | `handle_utterance(session, "바지락 넣어도 돼?", requested_ingredient=["바지락"], client=client)` | `intent == "재료대체"`, `result_dish_name == "바지락된장찌개"`, `match_type == "exact_name"`, `session["current_recipe_id"]`가 바뀜 | [ ] PASS / [ ] FAIL |
| B-2 | B-1 이후 | `handle_utterance(session, "다음", client=client)` | 대체된(바지락된장찌개) 레시피 기준으로 진행 계속(`step_number` 증가), 에러 없음 | [ ] PASS / [ ] FAIL |
| B-3 | B-1 이후 | `handle_utterance(session, "취소해줘", client=client)` | `intent == "취소"`, `rolled_back == True`, `session["current_recipe_id"]`가 대체 이전(된장찌개)으로 복원 | [ ] PASS / [ ] FAIL |

### 시나리오 C — 재료대체 매칭 완전 실패 시 정직한 안내 (5장 시나리오 C)

| # | GIVEN | WHEN | THEN | 결과 |
|---|---|---|---|---|
| C-1 | session의 `current_recipe_id`가 된장찌개 | `handle_utterance(session, "문어랑 성게 같이 넣어도 돼?", requested_ingredient=["문어", "성게"], client=client)` | `intent == "재료대체"`, `match_type == "none"`, `message`에 "레시피는 없어요" 계열 문구(그럴싸하게 지어내지 않음, 1.5 원칙) | [ ] PASS / [ ] FAIL |

### 시나리오 D — 표준 데이터 밖 요리 요청 시 신규 등록 유도 (5장 시나리오 D)

주의: PRD 원문 예시는 "문어초무침"이지만, 지금 DB(LLM 생성 데이터)엔 실제로 "문어초무침"이 존재해서
이 테스트 목적(미등록 요리 처리)엔 안 맞는다. 대신 DB에 없는 걸 확인한 임의 요리명으로 대체함.

| # | GIVEN | WHEN | THEN | 결과 |
|---|---|---|---|---|
| D-1 | 새 세션, "은하수비빔밥"은 DB에 없음(확인됨) | `handle_utterance(session, "은하수비빔밥 어떻게 만들어?", dish_name="은하수비빔밥", client=client)` | `intent == "조회"`, `message == "죄송해요, 그 요리는 아직 없어요."`, `session`에 `current_recipe_id`가 새로 생기지 않음 | [ ] PASS / [ ] FAIL |
| D-2 | D-1 이후, 신규 등록으로 유도 | `handle_utterance(session, "새 레시피 등록하고 싶어", registration_step="dish_name", registration_value="은하수비빔밥", client=client)` | `intent == "등록"`, `prompt`에 재료를 묻는 문구, `session["registration"]["dish_name"] == "은하수비빔밥"` | [ ] PASS / [ ] FAIL |

---

## AC-15 반복 질의 일관성 (보조 기준)

> GIVEN 동일 레시피에 동일 질의 반복
> WHEN 10~20회 반복 테스트
> THEN 정확한 레시피/재료 반영 비율 — 목표치 미정, 1차 실측 후 확정

시나리오 A-1(`"된장찌개 어떻게 만들어?"` 조회)과 시나리오 B-1(`"바지락 넣어도 돼?"` 재료대체)을
각각 10~20회 반복 호출해서, 매번 같은 `recipe_id`/`result_dish_name`이 나오는지 기록한다.
(임베딩 유사도 기반이라 이론상 같은 입력엔 항상 같은 출력이 나와야 하지만, 의도분류 임계값/마진
근처의 발화는 흔들릴 수 있어 실측이 필요함 — `intent_classifier.py`의 `THRESHOLD=0.5`, `MARGIN=0.05`가
아직 "임시값"으로 표시돼 있음, `OI-09`.)

| 반복 회차 | A-1 결과 일치 (Y/N) | B-1 결과 일치 (Y/N) |
|---|---|---|
| 1 | | |
| 2 | | |
| ... | | |
| 10~20 | | |

**일치율**: A-1 ___ / ___회, B-1 ___ / ___회

---

## AC-16 딥러닝 검증 (TTS) — 현재 블로킹

> GIVEN TTS 파인튜닝 전/후 동일 텍스트셋
> WHEN WER·청취 평가 실시
> THEN 파인튜닝 후 지표가 파인튜닝 전 대비 개선됨을 수치로 제시(발표자료 필수 포함)

**상태: TTS 모델 학습 중이라 실행 불가.** TTS 파인튜닝 완료 후 아래를 채운다.

| 항목 | 파인튜닝 전 | 파인튜닝 후 | 개선폭 |
|---|---|---|---|
| WER | | | |
| 청취 평가(주관 점수) | | | |

관련: `src/tts/README.md`, `docs/decisions.md`(OOM/CPU 속도 미확인 항목).

---

## 종합 결과

| AC | 상태 |
|---|---|
| AC-14 (핵심 시나리오 완주) | [ ] 전체 PASS / [ ] 일부 FAIL(사유: ) / [ ] 미실행 |
| AC-15 (반복 질의 일관성) | [ ] 전체 PASS / [ ] 일부 FAIL(사유: ) / [ ] 미실행 |
| AC-16 (TTS 딥러닝 검증) | [ ] 블로킹(TTS 학습 대기) |

**실행일**: ____________ **실행자**: ____________
