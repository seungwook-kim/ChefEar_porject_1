# models/ — 로컬 학습 산출물 스테이징

## 이 폴더가 하는 일

STT/TTS 파인튜닝 체크포인트를 로컬에 임시로 두는 곳. **git 대상 아님**(`.gitignore`). 실제 배포는
이 폴더를 직접 읽지 않고 HF Hub(`.env`의 `HF_STT_MODEL_REPO`/`HF_TTS_MODEL_REPO`)에서 가중치를
다운로드해서 쓴다 — 그러니 여기 체크포인트를 쌓아두는 건 "학습 중 로컬 확인용"이지 배포 경로가 아니다.

## 현재 상태 (확인: 2026-08-16)

| 폴더 | 상태 |
|---|---|
| `stt_finetuned/` | `.gitkeep`만 있음, 로컬 체크포인트 없음. 다만 HF Hub에 `leeony/chefear-stt-large-v3-turbo` 어댑터가 이미 올라가 있어서([src/stt/infer.py](../src/stt/README.md) 참고) 로컬 체크포인트가 없어도 그걸로 대체 가능 |
| `tts_finetuned/` | `.gitkeep`만 있음, 로컬 체크포인트도 HF Hub 업로드본도 아직 없음 — TTS는 완전히 미착수 상태([src/tts/README.md](../src/tts/README.md) 참고) |

`tests/tts_cpu_inference_test.py`는 `tts_finetuned/` 안에서 가장 최근 수정된 체크포인트 폴더를 자동으로
찾아 쓰고, 없으면 사전학습 베이스 모델로 폴백하도록 이미 짜여 있다.

## 진행 방법

- 학습이 끝나면 체크포인트를 `stt_finetuned/`, `tts_finetuned/` 아래 하위 폴더로 저장
- 검증이 끝나면 HF Hub 저장소에 업로드하고 `.env`의 `HF_STT_MODEL_REPO`/`HF_TTS_MODEL_REPO`에 repo id 기록
  (이게 실제 배포가 참조하는 값)

## 관련 문서

`docs/ChefEar_팀_진행_가이드_v2.md` 2장(`models/` 역할), `.env.example.local`(HF repo 환경변수).
