# Open Issues / 결정 안 된 것들

가이드(`ChefEar_팀_진행_가이드_v2.md`) 기준으로, 착수 초반 반드시 실측/확정해야 할 항목.

| 항목 | 상태 | 담당 | 비고 |
|---|---|---|---|
| Qwen3-TTS 1.7B 파인튜닝 — 노트북(RTX 4060 8GB)/데스크탑(RTX 5070 12GB) OOM 없이 완주 가능한지 | 미확인 | | 가이드 6.1 |
| HF Spaces CPU Basic에서 Qwen3-TTS 추론이 목표 응답시간(5초) 이내인지 | 미확인 | | 가이드 9. 안 되면: ① Modal 등 GPU 플랫폼 ② Tailscale로 데스크탑 상시 노출 ③ Qwen3-TTS 0.6B로 축소 |
| STT 학습 스택(transformers/peft/accelerate/bitsandbytes) 버전 | 재검증 필요 | | 가이드 6.2 |
| TTS 학습 LoRA 저장소 버전 (instavar/qwen3-tts-lora-finetuning 등, 비공식) | 미정 | | 가이드 6.2 |
| TTS 추론 저장소 버전 | 미정 | | 가이드 6.2 |
