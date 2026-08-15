# src/ — 전체 소스 맵

## 하위 폴더

| 폴더 | 담당 | 상태 요약 | 상세 |
|---|---|---|---|
| `orchestration/` | 김승욱 | 대부분 완성, `pipeline.py` 통합 함수만 남음 | [orchestration/README.md](orchestration/README.md) |
| `stt/` | 하주성 | `infer.py`만 작성됨(배치 평가용), 학습·배포 변환은 미착수 | [stt/README.md](stt/README.md) |
| `tts/` | 홍민하 | 전부 미착수(0줄) | [tts/README.md](tts/README.md) |
| `ui/` | 홍민하 | 컴포넌트 없음 | [ui/README.md](ui/README.md) |

## app.py (확인: 2026-08-16)

`src/app.py`는 HF Spaces 배포 엔트리포인트인데 **현재 완전히 비어있음(0줄)**. Streamlit 앱 자체가
아직 시작되지 않은 상태. 팀 가이드(`docs/ChefEar_팀_진행_가이드_v2.md` 2장)에 따르면:

- 루트 `README.md`에 아직 YAML frontmatter(`sdk: streamlit`, `app_file: src/app.py`)가 없음 —
  HF Spaces 배포 전에 반드시 추가해야 함
- `app.py`가 하는 일: 마이크 입력 → STT → `orchestration.pipeline` 라우팅 → TTS 응답 재생을
  한 화면 루프로 엮는 것. 세부 컴포넌트는 `ui/`로 분리 가능

app.py를 짜려면 `orchestration/pipeline.py`의 통합 진입점, `stt/infer.py`·`tts/infer.py`의 런타임
함수가 먼저 있어야 실제 연결이 가능하다 — 지금은 이 세 조각이 각자 폴더에서 별도로 진행 중이다.
