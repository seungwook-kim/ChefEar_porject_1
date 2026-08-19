# src/ — 전체 소스 맵

## 하위 폴더

| 폴더 | 담당 | 상태 요약 | 상세 |
|---|---|---|---|
| `orchestration/` | 김승욱 | 완성 — `pipeline.py`에 `handle_utterance()`(STT→의도분류→라우팅) 포함 | [orchestration/README.md](orchestration/README.md) |
| `stt/` | 하주성 | 모델 확정(whisper-large-v3-turbo) + 평가 완료. `infer.py`는 배치 평가용, 배포용 단일 발화 함수(`stt_transcribe()`, faster-whisper 변환)는 아직 정리 필요 | [stt/README.md](stt/README.md) |
| `tts/` | 홍민하 | 파인튜닝 완료(HF Hub 업로드, 13에포크 체크포인트). `infer.py`에 `tts_synthesize()` 작성됨. ✅ roundtrip CER 0.0000(5문장 전부, 2026-08-19) — 품질 문제 해소. ⚠️ CPU 배포 속도는 옛 코드 경로 기준 FAIL(목표 5초의 약 40배) 수치뿐, 새 경로로 재측정 필요 | [tts/README.md](tts/README.md) |
| `ui/`(`src/ui/`) | 홍민하 | 정식 위치는 비어있음 — 대신 최상위 `ui/`(별도 폴더, mock 데이터 프로토타입)에 화면 11개 구현됨 | [ui/README.md](ui/README.md) |

## app.py (확인: 2026-08-16)

`src/app.py`는 HF Spaces 배포 엔트리포인트인데 **현재 완전히 비어있음(0줄)**. Streamlit 앱 자체가
아직 시작되지 않은 상태. 팀 가이드(`docs/ChefEar_팀_진행_가이드_v2.md` 2장)에 따르면:

- 루트 `README.md`엔 YAML frontmatter(`sdk: streamlit`, `app_file: src/app.py`)가 이미 추가돼
  있음(2026-08-18 재확인) — HF Spaces 배포 메타데이터 쪽은 준비 완료
- `app.py`가 하는 일: 마이크 입력 → STT → `orchestration.pipeline` 라우팅 → TTS 응답 재생을
  한 화면 루프로 엮는 것. 화면 자체는 최상위 `ui/`(프로토타입, mock 데이터)의 구조를 그대로
  가져다 쓰면 됨 — `../../ui/README.md` 참고

`orchestration/pipeline.py`의 `handle_utterance()`와 `tts/infer.py`의 `tts_synthesize()`는 이제
준비됐다. 남은 건 `stt/infer.py`의 배포용 단일 발화 함수와, 그 셋을 실제로 엮는 `app.py` 본체뿐이다.
참고로 레시피 확인 화면의 "응"(긍정) 응답은 `classify_intent()`가 처리하지 않으므로(의도적 제외,
`tests/integration_test.md` 참고) `app.py`가 이 부분만 별도로 처리해야 한다.
