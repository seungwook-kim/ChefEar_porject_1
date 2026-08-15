# src/tts/ — 담당: 홍민하 (B, TTS 파인튜닝/UI)

## 이 폴더가 하는 일

Qwen3-TTS-12Hz-1.7B(VoiceDesign)를 KSS 데이터셋으로 파인튜닝하고, HF Spaces CPU Basic(무료)
환경에서 목표 응답시간(5초) 안에 추론이 되는지가 핵심 리스크(R-13/OI-11, `docs/decisions.md`).

## 파일별 상태 (확인: 2026-08-16)

| 파일 | 상태 | 역할 |
|---|---|---|
| `prepare_data.py` | **비어있음(0줄)** | KSS 24kHz 리샘플링 예정(Qwen3-TTS는 24kHz 아니면 코덱이 거부함) |
| `finetune_qwen3tts.py` | **비어있음(0줄)** | Qwen3-TTS 파인튜닝(학습, GPU 전용) 예정 |
| `infer.py` | **비어있음(0줄)** | 런타임 음성 합성 `tts_synthesize()` 예정 |

이 폴더 자체는 아직 코드가 하나도 없다. 대신 `tests/tts_cpu_inference_test.py`(새로 추가된 읽기 전용
벤치마크 스크립트)가 CPU 추론 속도 실측을 임시로 담당하고 있다 — 체크포인트 없으면 사전학습 베이스
모델(`Qwen/Qwen3-TTS-12Hz-1.7B-Base`, voice clone 모드)로 자동 폴백한다.

## 진행 방법

1. `data/kss/`(wav 412개 확보됨)를 24kHz로 리샘플링 → `prepare_data.py`
2. `finetune_qwen3tts.py`로 파인튜닝(GPU, VRAM 제약 큼 — 노트북 4060 8GB는 사실상 어렵고 데스크탑
   5070 12GB도 배치사이즈 최소화 필요, OOM 없이 완주 가능한지 아직 미확인 — `docs/decisions.md` 1번 항목)
3. 체크포인트를 `models/tts_finetuned/`에 저장
4. `tests/tts_cpu_inference_test.py` 실행 → CPU 5초 목표 실측(`docs/decisions.md` 2번 항목), 결과는
   `results/tts/cpu_inference_test.csv`에 자동 저장됨. 이 스크립트는 `qwen_tts` 패키지가 필요한데
   `requirements-main.txt`엔 아직 없음(버전 미정 상태) — 로컬에 별도 설치 필요
5. `infer.py`에 `tts_synthesize()` 런타임 함수 작성 → `src/orchestration/pipeline.py`/`app.py` 통합용
6. 5초 목표 미달 시 대안: ① Modal 등 GPU 플랫폼 ② 데스크탑을 Tailscale로 상시 노출 ③ Qwen3-TTS 0.6B로 축소

## 필요한 것 / 막힌 것

- GPU 환경, `qwen_tts` 패키지(버전 미정)
- `models/tts_finetuned/`가 현재 비어있어 벤치마크가 베이스 모델로만 돌아가는 중 — 실제 파인튜닝
  모델로 재측정 필요
- TTS가 끝나야 STT 학습데이터(`data/synthesized/`)도 생성 가능 — STT 쪽이 이 폴더 산출물을 기다리는 중

## 관련 문서

`docs/decisions.md`(OOM/CPU 속도 미확인 항목), `docs/ChefEar_팀_진행_가이드_v2.md` 6.1/9장,
`docs/ChefEar_PRD_SDD_v0.8.md` R-13/OI-11.
