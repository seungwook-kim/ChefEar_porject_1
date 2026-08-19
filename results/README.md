# results/ — 평가 결과물

## 이 폴더가 하는 일

STT/TTS 파인튜닝 전/후 정량 비교 자료(WER, 추론 속도 등)를 쌓는 곳. 발표자료(AC-16 딥러닝 검증)에
직접 쓰일 수치들이 여기서 나온다.

## 현재 상태 (확인: 2026-08-19)

`stt/`엔 아직 `.gitkeep`만 있다 — STT 평가 자체는 끝났지만([src/stt/README.md](../src/stt/README.md)
참고) 그 결과 CSV는 하주성님 로컬/별도 작업공간에만 있고 아직 이 폴더로 안 옮겨짐.

`tts/`는 체크포인트를 두 번 교체하며(epoch-8 → epoch-24 → 13에포크) 결과가 여러 번 갱신됐다.
상세 이력은 [src/tts/README.md](../src/tts/README.md) 참고:

| 파일 | 상태 | 만드는 스크립트 | 결과 요약 |
|---|---|---|---|
| `tts/cpu_inference_test_20260816_164450.csv` | **main 브랜치에 커밋됨(2026-08-17)** | `tests/tts_cpu_inference_test.py` (Colab 2 vCPU 실행) | epoch-8 모델 기준 3문장 전부 FAIL, 전체 평균 197.48초(목표 5초의 약 39.5배). 13에포크+voice-clone 경로로는 **아직 재측정 안 함** — 코드 경로 자체가 달라져서 이 수치를 그대로 믿을 수 없음. 상세: `../src/tts/README.md` |
| `tts/roundtrip_cer.csv` | **git 커밋됨, 최신 결과로 갱신(2026-08-19)** | `tests/tts_stt_roundtrip_test.py` (GPU 환경) | **13에포크 체크포인트 기준 5문장 전부 CER 0.0000** — 이전 epoch-8(평균 1.37)·epoch-24(평균 14.26, 아래 참고) 대비 완전 해소 |
| `tts/roundtrip_cer_epoch24.csv` | **로컬에만 있음, git 미커밋(의도적 결정, 2026-08-19)** | 동일(화자명 이슈 우회 스크립트) | epoch-24 체크포인트에서 나온 회귀 데이터(평균 CER 14.26, 반복 루프 발화 다수) — 필요시 로컬에서 참고, 저장소엔 안 올림 |
| `tts/roundtrip_audio/`, `tts/roundtrip_audio_epoch24/` | **git 미커밋(의도적, `.gitignore`)** | 위와 동일 | 합성 오디오 wav — 용량 문제로 커밋 대상에서 제외, CSV 결과만 기록으로 남김. 청취 확인은 로컬에서 직접 재생 |

파일명이 기존 계획(`roundtrip_wer.csv`)과 다른 이유: WER 대신 CER로 지표를 바꿔서
(`tests/README.md` 참고, 공백 제거 정규화와 WER 조합이 오류율을 왜곡시켜서 CER로 변경).

## 진행 방법

- TTS→STT 품질(CER)은 13에포크 체크포인트로 **해결됨** — `AC-16`(TTS 딥러닝 검증)에 이 수치를
  바로 쓸 수 있다.
- 남은 건 CPU 속도: `cpu_inference_test_20260816_164450.csv`는 epoch-8/구 코드 경로 기준이라
  13에포크+voice-clone 경로로 재측정이 필요하다(`../src/tts/README.md` 참고).
- `roundtrip_audio*/`(오디오 wav)는 git 업로드 제외로 확정 — CSV만 기록으로 남기는 쪽으로 결정됨.
- 나머지(STT 3모델 비교 CSV)는 이미 실행은 됐으니 결과 파일만 이 폴더로 옮겨 담으면 된다.

## 관련 문서

`docs/ChefEar_PRD_SDD_v0.8.md` AC-16(TTS 딥러닝 검증, 파인튜닝 전후 개선폭을 수치로 제시).
