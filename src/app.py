"""ChefEar — 실제 배포 엔트리포인트 (Streamlit). 실행: streamlit run src/app.py

## 지금 버전이 하는 일 / 안 하는 일

마이크·STT를 아직 못 붙여서(로컬 환경에서 실제 확인 불가), 텍스트 입력으로
"STT가 이 문장을 알아들었다"고 흉내 내는 최소 버전이다. 여기 입력한 텍스트는
orchestration.pipeline.handle_utterance()로 그대로 들어간다 — 요리명 추출
(extract_dish_name, 완전일치→부분일치→편집거리), 의도분류(classify_intent,
임베딩 유사도), 레시피 조회·단계 진행까지 전부 진짜 로직·진짜 Supabase다.
ui/ 폴더의 화면 프로토타입과 달리 mock_data.py를 안 쓴다.

TTS는 아직 안 붙였다 — 이 로컬 환경(CPU, GPU 없음)에서 tts_synthesize() 한
문장 실측 결과 239.2초가 걸려서(2026-08-20 확인), 문장마다 그만큼 기다리는
경험은 지금 붙일 이유가 없다고 판단해 텍스트 흐름부터 먼저 검증하기로 했다.
나중에 단계별 "음성 듣기" 버튼을 추가해서 tts_synthesize()(src/tts/infer.py)를
누른 단계에서만(전체 자동 아님) 호출하는 방식이 현실적일 것이다.

재료대체/신규등록 의도는 requested_ingredient/registration_step 같은 세부
정보를 발화에서 자동으로 뽑는 로직이 아직 없어서(handle_utterance() 문서
참고), 이 텍스트 입력만으로는 제대로 동작하지 않는다 — "다음/다시/이전"으로
진행하거나 요리명을 말해서 조회하는 흐름만 이 화면으로 검증 가능하다.
"""
import streamlit as st

from orchestration.db import get_client
from orchestration.pipeline import get_precomputed_steps, handle_utterance

st.set_page_config(page_title="ChefEar (dev)", page_icon="🍲")

if "session" not in st.session_state:
    st.session_state.session = {}
if "log" not in st.session_state:
    st.session_state.log = []
if "client" not in st.session_state:
    # get_client()는 부를 때마다 새 클라이언트 객체를 만든다(db.py 설계). Streamlit은
    # 상호작용마다 이 스크립트 전체를 다시 실행하므로, 매번 새로 부르면
    # recipe_search._all_dish_names()의 캐시(client 객체별로 캐시)가 매번 새
    # 객체를 키로 받아 절대 재사용되지 않는다 — 그러면 "조회"할 때마다 60,196건을
    # 다시 다 끌어와서 12~18초씩 걸린다(실측). session_state에 담아 같은 세션
    # 안에서는 항상 같은 client 객체를 재사용하도록 고정한다.
    st.session_state.client = get_client()

client = st.session_state.client

st.title("ChefEar — 텍스트 발화 테스트 (STT/TTS 전 단계)")
st.caption(
    "마이크 대신 텍스트로 발화를 흉내 냅니다. 요리명 조회·다음/다시/이전 진행만 검증 가능 — "
    "재료대체·신규등록은 발화에서 세부 정보를 자동으로 뽑는 로직이 아직 없어 이 화면으론 제대로 안 됩니다."
)

with st.form("utterance_form", clear_on_submit=True):
    utterance = st.text_input(
        "발화 입력", placeholder="예: 부대찌개 어떻게 만들어? / 다음 / 다시 / 이전"
    )
    submitted = st.form_submit_button("전송")

if submitted and utterance.strip():
    result = handle_utterance(st.session_state.session, utterance, client=client)
    st.session_state.log.append((utterance, result))

for utterance, result in reversed(st.session_state.log):
    with st.chat_message("user"):
        st.write(utterance)
    with st.chat_message("assistant"):
        st.json(result)

st.divider()

recipe_id = st.session_state.session.get("current_recipe_id")
if recipe_id:
    steps = get_precomputed_steps(recipe_id, client=client)
    if steps.get("available"):
        st.subheader("전체 조리순서")
        current_step_number = st.session_state.session.get("step_number", 1)
        for step in steps["steps"]:
            marker = "👉 " if step["step_number"] == current_step_number else ""
            st.write(f"{marker}{step['step_number']}. {step['text']}")

with st.expander("세션 상태 (디버그용)"):
    st.json(st.session_state.session)
