# src/ — 전체 소스 맵

## 하위 폴더

| 폴더 | 담당 | 상태 요약 | 상세 |
|---|---|---|---|
| `orchestration/` | 김승욱 | 완성 — `pipeline.py`에 `handle_utterance()`(STT→의도분류→라우팅) 포함 | [orchestration/README.md](orchestration/README.md) |
| `stt/` | 하주성 | 모델 확정(whisper-large-v3-turbo) + 평가 완료. **배포용 `stt_transcribe()`(faster-whisper/CTranslate2 int8) 작성 완료(2026-08-19, `docs/specs/stt_deploy.md`)** — 오프라인 변환 스크립트 `export_ct2.py`도 신규 추가 | [stt/README.md](stt/README.md) |
| `tts/` | 홍민하 | 파인튜닝 완료(HF Hub 업로드, 13에포크 체크포인트, 2026-08-19 전체 리포 재업로드). `infer.py`에 `tts_synthesize()` 작성됨. ✅ roundtrip CER 0.0000(5문장 전부) — 품질 문제 해소. ⚠️ CPU 배포 속도 **재측정 완료, 여전히 FAIL**(26.11초/목표 5초) — GPU는 SDPA+`torch.compile`로 5.21초까지 근접. "닭을" 등 발음 오류 패치(`pronunciation.py`)도 추가 | [tts/README.md](tts/README.md) |
| `ui/`(`src/ui/`) | 홍민하 | 정식 위치는 비어있음 — 대신 최상위 `ui/`(별도 폴더, mock 데이터 프로토타입)에 화면 11개 구현됨 | [ui/README.md](ui/README.md) |

## app.py (확인: 2026-08-19)

`src/app.py` **작성 완료(568줄, `docs/specs/app_e2e.md` Spec 기준)** — 마이크 입력 → STT
(`stt.infer.stt_transcribe`) → `orchestration.pipeline.handle_utterance()` → TTS
(`tts.infer.tts_synthesize`) 재생까지 한 화면 루프로 엮었다. 화면 컴포넌트는 최상위
`ui/theme.py`를 그대로 재사용(최상위 `ui/streamlit_screens/*.py` mock 프로토타입은 시나리오
하드코딩이라 자유발화엔 못 씀, `docs/specs/app_e2e.md` 참고). 아직 git 미커밋 상태.

- 루트 `README.md`엔 YAML frontmatter(`sdk: streamlit`, `app_file: src/app.py`)가 이미 추가돼
  있음 — HF Spaces 배포 메타데이터 쪽은 준비 완료
- 요리명/재료명 추출은 `orchestration/entity_extract.py`(신규, 규칙 기반, LLM 미사용)가 담당
- 실행: `streamlit run src/app.py`
