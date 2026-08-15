-- ChefEar Supabase 스키마 (PRD/SDD v0.8, 6.7 Supabase 테이블)
-- Supabase 대시보드 SQL Editor에서 직접 실행할 것 (supabase-py는 SELECT/INSERT/UPDATE/DELETE
-- 같은 데이터 조작만 할 수 있고, 테이블을 만드는 DDL 문법은 실행할 수 없다. 그래서 이
-- schema.sql은 파이썬 코드가 아니라 사람이 Supabase 웹 화면에서 직접 붙여넣고 실행한다.)

-- gen_random_uuid() 함수(레시피 id를 자동으로 만들어줄 때 씀)를 쓰려면 이 확장이 필요하다.
-- Supabase는 보통 기본으로 켜져 있지만, 혹시 몰라 안전하게 한 번 더 켠다(이미 켜져 있으면 무시됨).
create extension if not exists pgcrypto;

-- recipes: 레시피 "한 건"의 기본 정보. 요리 하나당 딱 한 행이다.
create table if not exists recipes (
    -- uuid: 숫자를 1,2,3... 순서로 매기는 대신 무작위에 가까운 긴 문자열로 id를 만드는 방식.
    -- gen_random_uuid()가 자동으로 값을 채워주므로, insert할 때 id는 안 넣어도 된다.
    id uuid primary key default gen_random_uuid(),
    dish_name text not null,       -- 요리명(예: "된장찌개")
    ingredients text,               -- 재료 목록. 가공하지 않고 원문 텍스트 그대로 저장(6.1/6.2)
    -- source: 이 레시피가 어디서 왔는지 구분하는 값. api_standard = 표준 데이터(작업1로
    -- 대량 적재), user_custom = 사용자가 직접 등록/수정한 버전. check 제약으로 이 두 값
    -- 이외의 오타(예: "API_STANDARD")가 실수로 들어가는 걸 DB 차원에서 막는다.
    source text not null check (source in ('api_standard', 'user_custom')),
    -- origin_id: user_custom 레시피가 "어떤 표준 레시피를 기반으로 수정한 것인지" 가리키는
    -- 자기 자신 테이블 참조(self-reference). references recipes(id)라서 recipes 테이블이
    -- 자기 자신을 가리킬 수 있다.
    origin_id uuid references recipes(id),
    -- 6.7 표에는 없지만 7.6 select_standard_recipe() 응답(view_count)과
    -- EC-19(조회수 0일 때 등록일 최신순 대체 정렬)를 충족하려면 필요해서 추가함
    view_count integer not null default 0,
    created_at timestamptz not null default now(),  -- default now(): insert할 때 안 넣으면 현재 시각이 자동으로 들어감
    -- 작업3(쿠키 UUID 개인화, FR-08): user_custom 레시피를 발급한 익명 사용자 식별.
    -- api_standard 행은 항상 null(특정 개인 소유가 아니므로). 로그인 없이 쿠키 UUID만 저장한다.
    owner_id text
);

-- recipe_steps: 레시피 하나의 "조리순서 한 단계"씩. 레시피 하나당 여러 행(1단계, 2단계, ...)이 붙는다.
create table if not exists recipe_steps (
    -- recipe_id는 recipes.id를 가리키는 외래키(foreign key)다. "이 단계가 어느 레시피
    -- 소속인지"를 나타낸다. on delete cascade: 만약 recipes에서 레시피 하나가 삭제되면,
    -- 그 레시피에 딸린 recipe_steps 행들도 자동으로 같이 삭제된다(고아 데이터 방지).
    recipe_id uuid not null references recipes(id) on delete cascade,
    step_number integer not null,   -- 몇 번째 단계인지 (1, 2, 3, ...)
    step_text text not null,        -- 그 단계의 안내 문장
    source text not null check (source in ('api_standard', 'user_custom')),
    -- primary key를 (recipe_id, step_number) 두 컬럼을 합쳐서 만든 이유: 같은 레시피 안에서
    -- "1단계"는 하나뿐이어야 하지만(중복 방지), 다른 레시피끼리는 둘 다 "1단계"를 가질 수
    -- 있어야 한다. 두 컬럼을 묶은 이 조합을 복합 기본키(composite primary key)라고 부른다.
    primary key (recipe_id, step_number)
);

-- 인덱스: 자주 검색하는 컬럼에 인덱스를 만들어두면, 그 컬럼으로 WHERE 조건을 걸 때
-- 테이블 전체를 다 훑지 않고 훨씬 빠르게 찾을 수 있다(책 뒤의 "찾아보기"와 비슷한 개념).
create index if not exists idx_recipes_dish_name on recipes(dish_name);  -- 요리명으로 조회할 때(select_standard_recipe 등)
create index if not exists idx_recipes_source on recipes(source);        -- api_standard/user_custom 구분 조회할 때
create index if not exists idx_recipes_owner_id on recipes(owner_id);    -- 특정 사용자의 user_custom만 찾을 때
