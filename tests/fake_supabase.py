"""테스트 전용 supabase-py 대역(가짜 객체, 흔히 "테스트 더블(test double)"이라고 부름).

## 왜 진짜 Supabase 대신 이런 가짜 클라이언트를 만들었나

recipe_search.py 같은 코드를 테스트하려면 진짜 Supabase 프로젝트에 접속해야
한다. 그런데 이 프로젝트는 아직 Supabase 자격증명이 없어서(작업1 보고 참고)
그게 불가능했다. 그렇다고 테스트를 아예 안 짤 수는 없으니, "supabase-py
클라이언트가 하는 일 중 우리가 실제로 쓰는 부분만" 파이썬 메모리(딕셔너리)로
흉내 낸 가짜 버전을 만들었다.

핵심 아이디어: recipe_search.py의 함수들은 client.table("recipes").select(...)
처럼 진짜 supabase 객체의 "메서드 체이닝(하나의 메서드가 다시 자기 자신 같은
객체를 반환해서 .을 계속 이어붙일 수 있는 문법)"을 쓴다. FakeTable/FakeQuery는
겉모습(메서드 이름과 체이닝 방식)만 진짜와 똑같이 흉내 내고, 속은 실제 네트워크
요청 대신 그냥 파이썬 딕셔너리를 뒤져서 답을 준다. 그래서 recipe_search.py 코드는
"이게 진짜 클라이언트인지 가짜인지" 전혀 신경 쓸 필요가 없다(같은 인터페이스라서).
이런 설계를 "덕 타이핑(duck typing)" — "오리처럼 걷고 오리처럼 운다면 오리로
취급한다" — 이라고 부른다.

## 이 파일은 껍데기일 뿐이다

실제 가짜 클라이언트 엔진(FakeResult/FakeQuery/FakeTable/FakeSupabaseClient)은
src/orchestration/mock_client.py에 있다. 강사 체크리스트 4번("백엔드 골격 —
가짜 응답 먼저 돌려준다") 때문에, Supabase 자격증명이 없을 때 db.get_client()가
런타임에도 이 엔진을 실제로 사용하게 됐다 — 그래서 테스트용으로만 있던 로직을
"진짜 제품 코드"인 src/orchestration/ 쪽으로 옮기고, 여기서는 테스트 코드가
예전처럼 `from fake_supabase import FakeSupabaseClient`로 쓸 수 있게 이름만
다시 내보내준다(re-export). 로직이 한 곳(mock_client.py)에만 있어야 두 군데를
따로 고치다가 서로 어긋나는 일이 없다.

주의: 이건 어디까지나 "우리 필터링 로직이 의도대로 동작하는가"만 검증해줄 뿐,
실제 Supabase(PostgREST)와 통신했을 때도 똑같이 동작하는지는 보장하지 않는다.
진짜 통합 검증은 Supabase 자격증명 확보 후 따로 해야 한다.
"""
from orchestration.mock_client import (  # noqa: F401 (테스트 파일들이 이 이름으로 import함)
    FakeQuery,
    FakeResult,
    FakeSupabaseClient,
    FakeTable,
)
