# src/tts/ — 담당: 홍민하 (B, TTS 파인튜닝/UI)

## 이 폴더가 하는 일

Qwen3-TTS-12Hz-1.7B(VoiceDesign)를 KSS 데이터셋으로 파인튜닝하고, HF Spaces CPU Basic(무료)
환경에서 목표 응답시간(5초) 안에 추론이 되는지가 핵심 리스크(R-13/OI-11, `docs/decisions.md`).

## 파일별 상태 (확인: 2026-08-17)

| 파일 | 상태 | 역할 |
|---|---|---|
| `prepare_data.py` | **비어있음(0줄)** | KSS 24kHz 리샘플링 — 실제로는 별도 개인 작업 공간(`test/scripts/prepare_qwen3_tts_data.py`)에서 이미 진행됨, 이 정식 위치로는 아직 이식 안 됨 |
| `finetune_qwen3tts.py` | **비어있음(0줄)** | Qwen3-TTS QLoRA 파인튜닝 — 마찬가지로 `test/scripts/train_qwen3_tts.py`에서 이미 완료(checkpoint-epoch-8까지, Colab A100), 이 정식 위치로는 아직 이식 안 됨 |
| `infer.py` | **완성, `max_new_tokens` 상한 추가(2026-08-17)** | `tts_synthesize(text) -> (waveform, sample_rate)`. 파인튜닝 모델(`kimseunguk/qwen3-tts-kss-finetuned`, private HF repo, 화자 `kss_speaker_a100`)을 로드해 합성. GPU 있으면 cuda/bfloat16, 없으면 CPU/float32로 자동 분기. `max_new_tokens` 기본값을 600으로 제한(라이브러리 기본 2048 + `do_sample=True` 조합에서 멈춤 토큰을 늦게 뽑아 20배 이상 느려지는 경우가 있어서) |

**파인튜닝 자체는 끝났다**: `Qwen3-TTS-12Hz-1.7B-Base`를 KSS로 QLoRA 파인튜닝(checkpoint-epoch-8) 후
merge_and_unload해서 HF Hub `kimseunguk/qwen3-tts-kss-finetuned`(private)에 업로드 완료. 다만 학습에
쓴 코드(`prepare_data.py`/`finetune_qwen3tts.py`에 해당하는 것)는 이 저장소가 아니라 별도 개인 작업
공간(`test/`, git 추적 안 됨)에만 있다 — 나중에 정식 위치로 옮겨 담아야 재현 가능한 상태가 된다.

## 실측 결과 (2026-08-17)

**① CPU 속도 실측(`tests/tts_cpu_inference_test.py`, Colab 2 vCPU, 파인튜닝 모델 기준) — FAIL**

3문장 전부 5초 목표 미달, 전체 평균 197.48초(목표의 약 39.5배). CSV:
`results/tts/cpu_inference_test_20260816_164450.csv`. 짧은 문장("약불로 5분간 끓여주세요")도
50초대라 목표와 자릿수 자체가 다름 — `docs/decisions.md`에 기록된 대로 대안(Modal 등 GPU 플랫폼 /
Tailscale로 데스크탑 상시 노출 / Qwen3-TTS 0.6B로 축소) 중 하나를 곧 결정해야 함.

**② TTS→STT roundtrip 실측(`tests/tts_stt_roundtrip_test.py`, GPU 환경) — 결과는 나왔으나 품질 불안정**

5문장 평균 CER 1.37. 문장별 편차가 큼:

| 문장 | CER | 비고 |
|---|---|---|
| 된장을 풀어줍니다 | 0.00 | 양호 |
| 두부와 감자를 먹기 좋은 크기로 썰어 넣습니다 | 0.05 | 양호 |
| 양파와 마늘을 다진 뒤, 팬에 기름을 두르고... | 0.70 | STT가 문장을 도중에 끊어 인식 |
| 약불로 5분간 끓여주세요 | 1.00 | STT가 "야!"로 잘못 인식 |
| 1.5컵의 물을 넣고 뚜껑을 덮은 채로... | 5.84 | STT가 "아, 아, 아..." 반복만 출력 |

CSV: `results/tts/roundtrip_cer.csv`, 오디오: `results/tts/roundtrip_audio/*.wav`(둘 다 아직
git 미커밋). CER이 나쁜 문장들은 `max_new_tokens=600` 제한 때문에 오디오가 중간에 잘렸을
가능성이 있어(위 ①의 극심한 지연 문제와 원인이 겹칠 수 있음) 상한값 재조정 또는 근본 원인
분석이 필요 — CPU 속도 문제(①)와 이 품질 불안정(②)이 같은 뿌리(생성이 예측 불가능하게
길어지거나 조기 종료되는 문제)일 가능성을 열어두고 같이 조사하는 게 효율적일 것으로 보임.

## 진행 방법

1. ~~`data/kss/` 24kHz 리샘플링~~ → 완료(`test/` 쪽에서)
2. ~~QLoRA 파인튜닝~~ → 완료(checkpoint-epoch-8, HF Hub 업로드까지 끝남)
3. ~~CPU 5초 목표 재측정~~ → 완료, **FAIL**(위 실측 결과 ① 참고) — 대안 결정이 다음 단계
4. `prepare_data.py`/`finetune_qwen3tts.py`를 `test/scripts/`의 대응 코드로 채워서 이 저장소 안에서도
   재현 가능하게 이식(팀 문서상 정식 위치이므로 언젠가 필요)
5. `infer.py`의 `tts_synthesize()`를 `src/orchestration/pipeline.py`/`src/app.py`에 연결
   (`handle_utterance()`의 텍스트 응답을 이 함수에 넘기고 반환값을 `st.audio()`로 재생) — CER 편차
   문제(위 실측 결과 ②)가 해소되기 전까진 연결해도 응답 품질이 불안정할 수 있음
6. `requirements.txt`/`requirements-main.txt`에 `qwen_tts`·`python-dotenv` 패키지 버전 확정해서
   추가(`requirements-stt.txt`엔 이미 `qwen-tts==0.1.1`+`transformers==4.57.3` 조합이 실측 검증돼
   반영됨, `docs/decisions.md` 참고 — 다만 그건 STT 학습 환경이고 TTS/배포 쪽 requirements엔 아직
   없음)
7. 5초 목표 미달 대안 결정: ① Modal 등 GPU 플랫폼 ② 데스크탑을 Tailscale로 상시 노출 ③ Qwen3-TTS 0.6B로 축소

## 필요한 것 / 막힌 것

- **CPU 배포 속도 FAIL(약 40배 초과) 대안 결정** — 위 실측 결과 ① 참고, 팀 논의 필요
- **일부 문장 CER 급등 원인 규명** — 위 실측 결과 ② 참고, `max_new_tokens` 상한 재조정 또는 근본
  원인(생성 길이 불안정) 확인 필요
- `qwen_tts`·`python-dotenv` 패키지가 `requirements.txt`/`requirements-main.txt`엔 아직 없음(버전은
  실측 검증됨) — private repo라 배포 시 `HF_TOKEN`을 HF Spaces Repository secret으로 등록도 필요
- `prepare_data.py`/`finetune_qwen3tts.py` 이식 — 지금은 재현 코드가 이 저장소 밖에만 있음
- TTS 합성음을 STT 학습데이터로 쓰려면(`data/synthesized/`) 위 이식이 선행되는 게 안전함

## 관련 문서

`docs/decisions.md`(OOM/CPU 속도 미확인 항목), `docs/ChefEar_팀_진행_가이드_v2.md` 6.1/9장,
`docs/ChefEar_PRD_SDD_v0.8.md` R-13/OI-11.
