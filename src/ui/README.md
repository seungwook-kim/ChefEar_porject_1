# src/ui/ — 담당: 홍민하 (Streamlit 화면 컴포넌트)

## 이 폴더가 하는 일

Streamlit 화면 컴포넌트 모음(마이크 입력, 단계 표시, 재료대체 확인 등). `src/app.py`가
엔트리포인트이고 이 폴더는 그 안에서 쓰일 화면 조각들을 분리해두는 자리다.

## 현재 상태 (확인: 2026-08-16)

`.gitkeep`만 있고 컴포넌트 파일이 아직 하나도 없다. `src/app.py`(엔트리포인트)도 여전히 비어있다.

다만 **동일한 화면 구조가 최상위 `ui/`(저장소 루트, 이 폴더와 다른 위치)에 이미 프로토타입으로
구현돼 있다** — mock 데이터 기준이지만 11개 화면 전부 상태 전이까지 실제로 동작한다
(`../../ui/README.md` 참고, `streamlit run ui/app.py`로 바로 확인 가능). 여기(`src/ui/`)로 옮겨
담을 때는 그 구조를 그대로 가져와서 mock 데이터 대신 실제 백엔드 호출로 바꾸면 된다.

## 진행 방법

1. 최상위 `ui/streamlit_screens/`·`ui/app.py`·`ui/theme.py`·`ui/nav.py` 구조를 이 폴더로 옮겨온다.
2. `ui/mock_data.py` 호출 부분을 실제 백엔드로 교체: `orchestration.pipeline.handle_utterance()`로
   응답 텍스트를 받고, `tts.infer.tts_synthesize()`로 음성을 합성해 `st.audio()`로 재생한다.
3. 익명 사용자 식별에는 `src/orchestration/identity.py`의 `get_or_create_anon_id(cookies)`를 쓴다
   (로그인 없음, `streamlit-cookies-manager` 필요).
4. 레시피 확인 화면의 "응"(긍정) 응답은 `classify_intent()`가 처리하지 않으므로(`tests/integration_test.md`
   참고) 이 레이어에서 별도로 처리해야 한다.

## 필요한 것 / 막힌 것

- `src/orchestration/pipeline.py`의 `handle_utterance()`, `src/tts/infer.py`의 `tts_synthesize()`는
  준비됐다. 남은 건 `src/stt/infer.py`의 배포용 단일 발화 함수(`stt_transcribe()`, faster-whisper
  변환) 정리뿐 — 이거 하나만 끝나면 mock 대신 실제 백엔드로 완전히 교체 가능

## 관련 문서

`docs/ChefEar_PRD_SDD_v0.8.md` 3.4(UI, 최소구현 우선), `docs/ChefEar_팀_진행_가이드_v2.md` 디렉토리 구조.
