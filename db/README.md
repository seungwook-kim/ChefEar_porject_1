# db/ — Supabase 스키마

## 이 폴더가 하는 일

Supabase에 수동으로 실행할 DDL(`schema.sql`) 하나만 담는다. `supabase-py`는 SELECT/INSERT/UPDATE/DELETE
같은 데이터 조작만 가능하고 테이블 생성 문법(DDL)은 실행할 수 없어서, 이 파일은 파이썬 코드가 아니라
사람이 Supabase 대시보드 SQL Editor에 직접 붙여넣고 실행하는 용도다. 별도 마이그레이션 도구는 안 쓴다.

## 현재 상태 (확인: 2026-08-16)

`schema.sql` 완성됨 — 테이블 2개.

- `recipes`: 레시피 1건당 1행. `source` 컬럼은 `api_standard`/`user_custom`만 허용(check 제약).
  `origin_id`는 자기참조(user_custom이 어떤 표준 레시피 기반인지), `owner_id`는 작업3(쿠키 UUID)용
- `recipe_steps`: 레시피 1건당 여러 행(단계별). `(recipe_id, step_number)` 복합 기본키,
  `on delete cascade`로 레시피 삭제 시 단계도 같이 삭제됨

인덱스 3개(`dish_name`, `source`, `owner_id`) 이미 포함.

## 진행 방법

1. Supabase 프로젝트 생성 → SQL Editor에 `schema.sql` 내용 그대로 붙여넣고 실행
2. `.env`에 `SUPABASE_URL`/`SUPABASE_KEY` 채우기 → `src/orchestration/db.py`의 `get_client()`가
   자동으로 mock 대신 이 진짜 DB를 씀(코드 수정 불필요)
3. 스키마를 바꿔야 하면 이 파일을 직접 수정한 뒤 다시 SQL Editor에서 수동 실행(마이그레이션 이력
   관리 없음 — 실행 순서를 팀이 직접 챙겨야 함)

## 필요한 것 / 막힌 것

- Supabase 프로젝트 자체가 아직 없음(자격증명 없음) — 이게 없어도 `mock_client.py`로 개발은 계속
  가능하지만, 실제 조회 성능·PostgREST 동작은 프로젝트 생성 후에만 확인 가능

## 관련 문서

`docs/ChefEar_PRD_SDD_v0.8.md` 6.7(Supabase 테이블), `docs/decisions.md` OI-08(SQL 함수 대신 Python 필터).
