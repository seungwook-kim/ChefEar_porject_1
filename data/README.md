# data/ — 데이터 작업 공간

## 이 폴더가 하는 일

STT/TTS 학습 데이터, 조리순서 실데이터, 의도분류 기준예문, 평가용 데이터를 담는다. 대용량
파일(`kss/`, `synthesized/`, `standard/*.csv`, `kadx_raw/*.csv`, `models/`)은 `.gitignore`에 의해
git 대상이 아니다 — 팀원 간 별도 공유(드라이브 등) 필요.

## 하위 폴더 상태 (확인: 2026-08-16)

| 폴더 | 상태 | 용도 |
|---|---|---|
| `standard/` | **실물 미확보** | 요리명별_조리과정 60,282건 CSV — 서비스가 쓰는 조리순서 전량(실데이터). `load_data.py --csv`로 Supabase 적재. git-ignored |
| `kadx_raw/` | **실물 미확보** | KADX 원본 CSV 4개(234,538건 시드: 재료·요리명·메타). git-ignored |
| `intent_examples/기준예문.csv` | **확보됨(49줄)** | 의도별 예문 세트(진행/재청취/긍정 등) — `intent_classifier.py`가 참조 |
| `kss/wavs/` | **확보됨(412개 wav)** | TTS·STT 학습 원본 음성(공개 데이터셋, CC BY-NC-SA 4.0). git-ignored |
| `synthesized/` | **비어있음** | Qwen3-TTS가 만들 합성음(STT 학습용 페어) — TTS 파인튜닝이 먼저 끝나야 채워짐. git-ignored |
| `evaluation_scripts/stt/` | **확보됨** | `ChefEar_test_fixed_100.csv` + `test_audio_100/`(mp3 100개) — STT WER 실측용 검증셋 |
| `mos_participants/` | 비어있음(.gitkeep) | TTS 청취평가(MOS) 참여자 기록(5명 이상), 학습용 아님 |
| `consent/` | 비어있음(.gitkeep) | KSS 라이선스 확인 기록 |

## 진행 방법

- `standard/`, `kadx_raw/`는 확보 경로가 아직 미확정 상태(`docs/ChefEar_팀_진행_가이드_v2.md` 2장
  ⚠️ 표시 항목) — 팀장(김승욱)에게 확보 경로 확인 필요
- `synthesized/`는 [../src/tts/README.md](../src/tts/README.md)의 파인튜닝이 끝나야 생성 가능,
  그 산출물을 [../src/stt/README.md](../src/stt/README.md)가 기다리는 중
- `evaluation_scripts/stt/`, `intent_examples/기준예문.csv`는 이미 확보됐으므로 바로 사용 가능

## 관련 문서

`docs/ChefEar_팀_진행_가이드_v2.md` 2장 디렉토리 구조, `docs/decisions.md`(실물 미확보 항목 추적).
