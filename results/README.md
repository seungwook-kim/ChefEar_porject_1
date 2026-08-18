# results/ — 평가 결과물

## 이 폴더가 하는 일

STT/TTS 파인튜닝 전/후 정량 비교 자료(WER, 추론 속도 등)를 쌓는 곳. 발표자료(AC-16 딥러닝 검증)에
직접 쓰일 수치들이 여기서 나온다.

## 현재 상태 (확인: 2026-08-17)

`stt/`엔 아직 `.gitkeep`만 있다 — STT 평가 자체는 끝났지만([src/stt/README.md](../src/stt/README.md)
참고) 그 결과 CSV는 하주성님 로컬/별도 작업공간에만 있고 아직 이 폴더로 안 옮겨짐.

`tts/`는 이제 실제 결과가 들어왔다:

| 파일 | 상태 | 만드는 스크립트 | 결과 요약 |
|---|---|---|---|
| `tts/cpu_inference_test_20260816_164450.csv` | **main 브랜치에 커밋됨(2026-08-17)** | `tests/tts_cpu_inference_test.py` (Colab 2 vCPU 실행) | 파인튜닝 모델 기준 3문장 전부 FAIL, 전체 평균 197.48초(목표 5초의 약 39.5배). 상세: `../src/tts/README.md` |
| `tts/roundtrip_cer.csv` | **로컬 실행 완료(2026-08-17), 아직 미커밋(untracked)** | `tests/tts_stt_roundtrip_test.py` (GPU 환경) | 5문장 평균 CER 1.37 — 2문장은 CER 0.05/0.00으로 양호, 3문장은 0.70/1.00/5.84로 매우 나쁨. `results/tts/roundtrip_audio/*.wav`(합성 오디오 5개)도 함께 생성됨, 마찬가지로 미커밋 |

파일명이 기존 계획(`roundtrip_wer.csv`)과 다른 이유: WER 대신 CER로 지표를 바꿔서
(`tests/README.md` 참고, 공백 제거 정규화와 WER 조합이 오류율을 왜곡시켜서 CER로 변경).

## 진행 방법

- `tts/cpu_inference_test_20260816_164450.csv`, `tts/roundtrip_cer.csv` 둘 다 이미 만들어졌다 —
  다만 CPU 속도(FAIL)와 CER 편차가 둘 다 "품질/속도 문제"를 가리키고 있어서, AC-16을 채우기 전에
  원인 규명이 먼저 필요하다(`docs/decisions.md`, `../src/tts/README.md` 참고).
- `roundtrip_cer.csv`와 `roundtrip_audio/`는 아직 git에 커밋되지 않은 상태 — 오디오 파일(수 MB)까지
  커밋할지, CSV만 기록으로 남길지 결정 필요.
- 나머지(STT 3모델 비교 CSV)는 이미 실행은 됐으니 결과 파일만 이 폴더로 옮겨 담으면 된다.

## 관련 문서

`docs/ChefEar_PRD_SDD_v0.8.md` AC-16(TTS 딥러닝 검증, 파인튜닝 전후 개선폭을 수치로 제시).
