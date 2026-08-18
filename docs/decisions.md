# Open Issues / 결정 안 된 것들

가이드(`ChefEar_팀_진행_가이드_v2.md`) 기준으로, 착수 초반 반드시 실측/확정해야 할 항목.

| 항목 | 상태 | 담당 | 비고 |
|---|---|---|---|
| Qwen3-TTS 1.7B 파인튜닝 — 노트북(RTX 4060 8GB)/데스크탑(RTX 5070 12GB) OOM 없이 완주 가능한지 | **해결** | 김승욱 | Colab A100에서 QLoRA로 checkpoint-epoch-8까지 완주, merge 후 HF Hub(`kimseunguk/qwen3-tts-kss-finetuned`) 업로드 완료 |
| HF Spaces CPU Basic에서 Qwen3-TTS 추론이 목표 응답시간(5초) 이내인지 | **확인됨 — FAIL** (2026-08-17, 전체 평균 197.48초, 목표의 약 39.5배. `tests/cpu_inference_test_20260816_164450.csv`, 상세: `src/tts/README.md`) | 홍민하 | 가이드 9. 대안 결정 필요: ① Modal 등 GPU 플랫폼 ② Tailscale로 데스크탑 상시 노출 ③ Qwen3-TTS 0.6B로 축소 |
| STT 학습 스택(transformers/peft/accelerate/bitsandbytes) 버전 | 학습용은 확정(`requirements-stt.txt`) | 하주성 | 가이드 6.2 |
| **[2026-08-16] STT+TTS 통합 실행환경 버전 충돌** | **해결** | 하주성 | `qwen-tts==0.1.1`이 `transformers==4.57.3`을 요구해서 `requirements-stt.txt`의 기존 고정 버전(`4.46.3`)과 충돌(`ImportError: cannot import name 'ALL_ATTENTION_FUNCTIONS'`)했던 건 — `transformers`를 낮추지 않고 `4.57.3`으로 올리는 쪽으로 `requirements-stt.txt` 자체를 갱신해서 해결(Whisper+PEFT+bitsandbytes 로딩도 최신 transformers에서 문제없이 동작 확인). 이 조합(`transformers==4.57.3` + `qwen-tts==0.1.1`)으로 `tests/tts_stt_roundtrip_test.py`를 2026-08-17 실제로 통과 실행해서 결과까지 확보함(`results/tts/roundtrip_cer.csv`, 상세: `tests/README.md`) |
| TTS 학습 LoRA 저장소 버전 (instavar/qwen3-tts-lora-finetuning 등, 비공식) | **해결** | 김승욱 | 자체 QLoRA 스크립트(`train_qwen3_tts.py`)로 진행, 위 항목 참고 |
| TTS 추론 저장소 버전 | **해결** | 김승욱 | `qwen-tts==0.1.1` 패키지, `src/tts/infer.py` 참고. 위 통합환경 충돌 해결로 `transformers==4.57.3`과의 조합이 실측 검증됨 — 다만 이 버전 고정은 아직 `requirements-stt.txt`(STT 학습 환경)에만 반영돼 있고, TTS/배포가 쓰는 `requirements.txt`·`requirements-main.txt`에는 `qwen_tts`/`python-dotenv` 버전이 아직 없음(아래 참고) |
| **[신규 2026-08-17] `src/tts/infer.py`·`src/stt/infer.py` 브랜치 간 불일치** | **미해결, 병합 전 정리 필요** | 김승욱 | `main`(`fix/stt-dotenv`, `fix/tts-dotenv` PR)은 두 파일 모두 `python-dotenv`로 `.env`를 읽도록 바꿨는데, `requirements.txt`/`requirements-main.txt`(배포·TTS가 실제 쓰는 파일)엔 `python-dotenv`가 없어서 그대로면 HF Spaces 배포 시 `ModuleNotFoundError` 위험이 있음(`requirements-stt.txt`에만 추가됨). `seunguk` 브랜치의 `src/tts/infer.py`는 같은 문제를 `src/orchestration/db.py`의 의존성 없는 `load_env()` 재사용으로 우회 해결(이미 실측 검증됨, 아래 tests/README.md 참고) — 병합 시 어느 방식으로 통일할지 결정 필요. 또한 `main`의 `pipeline.py`는 재료대체 매칭 실패 시 `match_type`을 응답에 안 넣는데(`seunguk`은 시나리오 C 실측 중 발견해서 넣도록 수정함, `tests/integration_test.md` 참고), pytest 스위트에 이를 지키는 회귀 테스트가 없어 병합 시 조용히 빠질 위험 있음 |
