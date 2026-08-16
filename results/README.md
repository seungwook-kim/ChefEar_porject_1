# results/ — 평가 결과물

## 이 폴더가 하는 일

STT/TTS 파인튜닝 전/후 정량 비교 자료(WER, 추론 속도 등)를 쌓는 곳. 발표자료(AC-16 딥러닝 검증)에
직접 쓰일 수치들이 여기서 나온다.

## 현재 상태 (확인: 2026-08-16)

`stt/`, `tts/` 둘 다 폴더 자체엔 `.gitkeep`만 있고 결과 파일이 아직 이 저장소로 안 들어왔다 —
**파인튜닝/평가 자체는 STT·TTS 둘 다 이미 끝났다**([src/stt/README.md](../src/stt/README.md),
[src/tts/README.md](../src/tts/README.md) 참고), 다만 그 결과 수치·CSV가 각자 로컬/별도 작업
공간에만 있고 아직 이 폴더로 옮겨지지 않은 상태.

| 폴더 | 예정 산출물 | 만드는 스크립트 | 비고 |
|---|---|---|---|
| `stt/` | `ChefEar_STT_3model_comparison_final.csv` 등 | `src/stt/infer.py`의 `run_batch_test()` | 하주성님 쪽에 Whisper Small/wav2vec2/Large-v3-turbo 비교 결과가 이미 있음 — 이 폴더로 아직 안 옮겨짐 |
| `tts/` | `cpu_inference_test.csv`, 라운드트립 WER 결과 | `tests/tts_cpu_inference_test.py`(이미 있음), 별도 작업 공간의 라운드트립 평가 노트북 | CPU 속도는 아직 베이스 모델 기준으로만 측정됨(파인튜닝 모델로 재측정 필요) |

## 진행 방법

지금 바로 만들어낼 수 있는 결과는 `tests/tts_cpu_inference_test.py` 실행 결과(`results/tts/cpu_inference_test.csv`)
뿐이다. 나머지(STT 3모델 비교 CSV, TTS 라운드트립 WER)는 이미 실행은 됐으니 결과 파일만 이 폴더로
옮겨 담으면 된다.

## 관련 문서

`docs/ChefEar_PRD_SDD_v0.8.md` AC-16(TTS 딥러닝 검증, 파인튜닝 전후 개선폭을 수치로 제시).
