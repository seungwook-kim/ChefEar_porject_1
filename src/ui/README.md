# src/ui/ — 담당: 홍민하 (Streamlit 화면 컴포넌트)

## 이 폴더가 하는 일

Streamlit 화면 컴포넌트 모음(마이크 입력, 단계 표시, 재료대체 확인 등). `src/app.py`가
엔트리포인트이고 이 폴더는 그 안에서 쓰일 화면 조각들을 분리해두는 자리다.

## 현재 상태 (확인: 2026-08-16)

`.gitkeep`만 있고 컴포넌트 파일이 아직 하나도 없다. `src/app.py`(엔트리포인트)도 비어있어서
화면 흐름 자체가 아직 안 짜여 있는 상태 — 이 폴더보다 `app.py` 골격을 먼저 잡는 게 순서.

## 진행 방법

1. `src/app.py`에서 전체 화면 흐름부터 잡는다: 마이크 입력 → STT → `orchestration.pipeline` 호출 →
   TTS 응답 재생 → 단계 표시. 처음엔 `ui/` 없이 `app.py` 하나에 다 몰아써도 되고, 화면이 늘어나면
   이 폴더로 컴포넌트를 분리해도 된다.
2. 익명 사용자 식별에는 `src/orchestration/identity.py`의 `get_or_create_anon_id(cookies)`를 쓴다
   (로그인 없음, `streamlit-cookies-manager` 필요).

## 필요한 것 / 막힌 것

- `src/orchestration/pipeline.py`의 통합 진입점(STT→의도분류→라우팅→TTS 조립, 아직 미완성)
- `src/stt/infer.py`의 런타임 추론 함수, `src/tts/infer.py`의 `tts_synthesize()` — 둘 다 현재 비어있음
- 이 셋이 갖춰지기 전까지는 화면에 "그럴듯한 흐름"만 mock 텍스트로 시연 가능(`orchestration/mock_client.py`
  시드 데이터로 조회 흐름은 이미 실제로 돌아감)

## 관련 문서

`docs/ChefEar_PRD_SDD_v0.8.md` 3.4(UI, 최소구현 우선), `docs/ChefEar_팀_진행_가이드_v2.md` 디렉토리 구조.
