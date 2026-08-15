# results/ — 평가 결과물

## 이 폴더가 하는 일

STT/TTS 파인튜닝 전/후 정량 비교 자료(WER, 추론 속도 등)를 쌓는 곳. 발표자료(AC-16 딥러닝 검증)에
직접 쓰일 수치들이 여기서 나온다.

## 현재 상태 (확인: 2026-08-16)

`stt/`, `tts/` 둘 다 `.gitkeep`만 있고 결과 파일 없음 — 아직 파인튜닝/실측이 진행되지 않았기 때문
([src/stt/README.md](../src/stt/README.md), [src/tts/README.md](../src/tts/README.md) 참고).

| 폴더 | 예정 산출물 | 만드는 스크립트 |
|---|---|---|
| `stt/` | `wer_rtf_epoch*.csv`, `loss_curve.png` | `src/stt/infer.py`의 `run_batch_test()` (WER), `finetune_whisper.py`(학습 곡선, 미작성) |
| `tts/` | `wer_rtf_epoch*.csv`, `final_comparison.png`, `cpu_inference_test.csv` | `finetune_qwen3tts.py`(미작성), `tests/tts_cpu_inference_test.py`(이미 있음 — 실행하면 `cpu_inference_test.csv` 자동 생성) |

## 진행 방법

지금 바로 만들어낼 수 있는 결과는 `tests/tts_cpu_inference_test.py` 실행 결과(`results/tts/cpu_inference_test.csv`)
뿐이다. 나머지는 각 파인튜닝 스크립트가 먼저 작성·실행돼야 한다.

## 관련 문서

`docs/ChefEar_PRD_SDD_v0.8.md` AC-16(TTS 딥러닝 검증, 파인튜닝 전후 개선폭을 수치로 제시).
