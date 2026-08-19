# src/tts/ — 담당: 홍민하 (B, TTS 파인튜닝/UI)

## 이 폴더가 하는 일

Qwen3-TTS-12Hz-1.7B(VoiceDesign)를 KSS 데이터셋으로 파인튜닝하고, HF Spaces CPU Basic(무료)
환경에서 목표 응답시간(5초) 안에 추론이 되는지가 핵심 리스크(R-13/OI-11, `docs/decisions.md`).

## 파일별 상태 (확인: 2026-08-19)

| 파일 | 상태 | 역할 |
|---|---|---|
| `prepare_data.py` | **비어있음(0줄)** | KSS 24kHz 리샘플링 — 실제로는 별도 개인 작업 공간(`test/scripts/prepare_qwen3_tts_data.py`)에서 이미 진행됨, 이 정식 위치로는 아직 이식 안 됨 |
| `finetune_qwen3tts.py` | **비어있음(0줄)** | Qwen3-TTS QLoRA 파인튜닝 — 마찬가지로 `test/scripts/train_qwen3_tts.py`에서 이미 진행됨(체크포인트 이력은 아래 참고), 이 정식 위치로는 아직 이식 안 됨 |
| `infer.py` | **완성, 13에포크 체크포인트 + voice-clone 방식으로 전면 교체(2026-08-19), max_new_tokens/시드 튜닝 완료(2026-08-19)** | `tts_synthesize(text) -> (waveform, sample_rate)`. 로드한 체크포인트의 `tts_model_type`을 보고 자동 분기: `"base"`(현재 기준 체크포인트)면 `assets/kss_reference.wav`로 목소리를 복제하는 `generate_voice_clone()`, `"custom_voice"`(과거 체크포인트로 되돌아갈 경우 대비)면 화자명 `SPEAKER="kss_speaker"`로 `generate_custom_voice()`. GPU 있으면 cuda/bfloat16, 없으면 CPU/float32로 자동 분기. `max_new_tokens` 기본값 **250**(600→170→180→190→195→200→300 순으로 실측 후 195로 확정했다가, **팀원 요청으로 195에서도 잘리는 게 확인돼 250으로 재조정(2026-08-19)**, 아래 실측 결과 ③ 참고). 매 합성 직전 `torch.manual_seed(42)`로 시드 고정(재현성 확보 — 이전엔 `do_sample=True`인데 시드 고정이 전혀 없어 같은 문장도 호출마다 결과가 달랐음) |
| `assets/kss_reference.wav` | **신규 추가(2026-08-19)** | voice-clone 레퍼런스 음성. KSS 원본 000008번(`나는 살아오면서 감기를 앓은 적이 한 번도 없다`) — `data/kss/metadata.csv`와 대본 페어 확인됨. Qwen 공식 데모의 영어 샘플 대신 실제 KSS 화자 목소리를 쓰려고 이걸로 골랐다 |

## 체크포인트 이력 — epoch-8 → epoch-24(품질 저하) → 13에포크(현재, known-good)

**파인튜닝 자체는 끝났다**: `Qwen3-TTS-12Hz-1.7B-Base`를 KSS로 QLoRA 파인튜닝 후 merge_and_unload해서
HF Hub `kimseunguk/qwen3-tts-kss-finetuned`(private)에 업로드. 학습 코드
(`prepare_data.py`/`finetune_qwen3tts.py`에 해당하는 것)는 이 저장소가 아니라 별도 개인 작업 공간
(`test/`, git 추적 안 됨)에만 있다 — 나중에 정식 위치로 옮겨 담아야 재현 가능한 상태가 된다.

체크포인트를 두 번 교체하면서 화자/품질 이슈를 겪었다:

1. **checkpoint-epoch-8**(08-16 업로드) — 화자명 `kss_speaker_a100`, 5문장 평균 CER 1.37(편차 큼)
2. **checkpoint-epoch-24**(08-17 업로드) — 화자명이 코드 모르게 `kss_speaker`로 바뀌어
   `tts_synthesize()`가 100% 실패했고, 화자명만 우회해서 재측정해보니 CER이 **14.26**으로 급격히
   악화(반복 루프 발화 다수) — 상세 원인 분석은
   [tests/integration_issues_2026-08-18.md](../../tests/integration_issues_2026-08-18.md) 참고.
   결과 파일은 그대로 보존: `results/tts/roundtrip_cer_epoch24.csv`
3. **13에포크 체크포인트**(현재, 2026-08-19) — epoch-24의 과적합 의심으로 더 이전 에포크로
   되돌렸고, 동시에 `tts_model_type`이 `"base"`로 바뀌어 있어(화자 임베딩 테이블 없음) 코드를
   voice-clone 방식으로 전환. 아래 실측 결과 참고. 로컬 known-good 백업은
   `result_test_backup_ep13_working/`(git 미추적, 4.3GB) — 이후 다른 에포크와 비교할 때 기준으로 삼을 것

## 실측 결과

**① TTS→STT roundtrip 재측정(2026-08-19, 13에포크 + voice-clone) — 5문장 전부 CER 0.0000**

`tests/tts_stt_roundtrip_test.py`를 GPU 환경에서 실행, 어제(epoch-24)와 동일한 5문장으로 재측정:

| 문장 | epoch-8 CER | epoch-24 CER | **13에포크 CER** |
|---|---|---|---|
| 약불로 5분간 끓여주세요 | 1.00 | 40.36 | **0.00** |
| 양파와 마늘을... 볶아주세요 | 0.70 | 18.70 | **0.00** |
| 1.5컵의 물을... 뜸을 들여주세요 | 5.84 | 0.92 | **0.00** |
| 두부와 감자를... 썰어 넣습니다 | 0.05 | 10.05 | **0.00** |
| 된장을 풀어줍니다 | 0.00 | 1.25 | **0.00** |
| **평균** | **1.37** | **14.26** | **0.00** |

결과 CSV: `results/tts/roundtrip_cer.csv`(git 커밋 대상). 합성 오디오는 `results/tts/new_sentences_test/*.wav`
— `tts_stt_roundtrip_test.py`의 `--sentences-file`로 어떤 문장 세트를 넣어도 오디오는 항상 이 폴더에
쌓이도록 통일함(2026-08-19, 파일명이 `{순번:02d}_{텍스트슬러그}.wav`라 세트가 달라도 구분됨).
용량 문제로 git 미커밋(개인 `.git/info/exclude`, 검증만 로컬에서 하면 됨).

`tests/integration_issues_2026-08-18.md`에 기록된 🔴 #1(화자명 불일치)·#2(품질 저하) 이슈는 이
체크포인트/코드 전환으로 **해소됨**. `AC-16`(TTS 딥러닝 검증)에 이 수치를 쓸 수 있다.

**② CPU 속도 — 미재측정, 이전 수치(FAIL) 그대로 참고만 할 것**

`tests/tts_cpu_inference_test.py`(Colab 2 vCPU) 마지막 실측은 2026-08-17, epoch-8·
`generate_custom_voice()` 경로 기준으로 3문장 평균 197.48초(목표 5초의 약 39.5배 FAIL).
CSV: `results/tts/cpu_inference_test_20260816_164450.csv`. **13에포크 + voice-clone 경로는 코드
경로 자체가 다르므로(레퍼런스 오디오 인코딩 단계 추가 등) 이 수치를 그대로 믿을 수 없다** — 재측정
전까지는 "속도 문제가 여전히 있을 가능성이 높다" 정도로만 취급할 것.

**③ `max_new_tokens` 튜닝(2026-08-19) — 600 → 170 → 180 → 190 → 195 → 200 → 300, 최종 250(팀원 요청)**

qwen_tts 라이브러리 기본값(2048)은 `do_sample=True`와 같이 쓰이면 운 나쁘게 멈춤 토큰을 늦게
뽑을 때 생성이 폭주할 위험이 있어(2026-08-17 확인) 상한을 낮춰왔는데, 값을 너무 낮추면 이번엔
정상적으로 긴 문장이 중간에 잘리는 반대 문제가 생긴다. 재료 목록이 긴 문장(분수 표현 다수 —
"소금8분의1스푼, 간장2분의1스푼, ..." 총 8개 재료) 하나로 상한값별 실측:

| max_new_tokens | 생성 길이 | 토큰 사용률 | 결과 |
|---|---|---|---|
| 170(≈14.17초) | 13.52초 | 95.4% | **잘림**(사용자 청취로 확인) |
| 180(≈15.00초) | 14.32초 | 95.5% | 잘림(추정) |
| 190(≈15.83초) | 15.12초 | 95.5% | **잘림**(사용자 청취로 확인, "잘려서 나왔네") |
| 195(≈16.25초) | 15.52초 | 95.5% | 잘림(추정) |
| 200(≈16.67초) | 15.92초 | 95.4% | **정상 완결** |
| 250(≈20.83초) | 15.92초 | 76.4% | **정상 완결** |
| 300(≈25.00초) | 15.92초 | 63.7% | **정상 완결** — EOS까지 자연스럽게 도달 후 정지 |

이 문장의 자연 완결 지점은 약 191토큰(15.92초)이다 — 200 미만 상한은 전부 그 지점보다 짧아
매번 강제로 끊겼다(생성 불안정 문제가 아니라 단순 상한 부족), 200 이상은 전부 15.92초로
동일하게 정상 완결됨을 실측으로 확인. `DEFAULT_MAX_NEW_TOKENS`는 처음 195로 확정했으나,
**팀원이 195에서도 잘린다고 확인해줘서 250으로 재조정(2026-08-19, 250 실측도 15.92초 정상
완결로 확인됨)** — 600(폭주 방지 목적)보다는 훨씬 낮게 유지.

## 진행 방법

1. ~~`data/kss/` 24kHz 리샘플링~~ → 완료(`test/` 쪽에서)
2. ~~QLoRA 파인튜닝~~ → 완료(체크포인트 이력은 위 참고)
3. ~~TTS→STT roundtrip 품질 검증~~ → 완료, **PASS**(13에포크 기준 CER 0.00, 위 실측 결과 ① 참고)
4. **CPU 5초 목표 재측정** — 13에포크 + voice-clone 경로 기준으로 다시 돌려야 함(위 실측 결과 ②),
   그 결과에 따라 대안 결정: ① Modal 등 GPU 플랫폼 ② 데스크탑을 Tailscale로 상시 노출 ③ Qwen3-TTS 0.6B로 축소
5. `prepare_data.py`/`finetune_qwen3tts.py`를 `test/scripts/`의 대응 코드로 채워서 이 저장소 안에서도
   재현 가능하게 이식(팀 문서상 정식 위치이므로 언젠가 필요)
6. `infer.py`의 `tts_synthesize()`를 `src/orchestration/pipeline.py`/`src/app.py`에 연결
   (`handle_utterance()`의 텍스트 응답을 이 함수에 넘기고 반환값을 `st.audio()`로 재생) — 품질
   문제는 해소됐으니 이제 CPU 속도(위 4번)만 확인되면 연결 가능
7. `requirements.txt`/`requirements-main.txt`에 `qwen_tts`·`python-dotenv` 패키지 버전 확정해서
   추가(`requirements-stt.txt`엔 이미 `qwen-tts==0.1.1`+`transformers==4.57.3` 조합이 실측 검증돼
   반영됨, `docs/decisions.md` 참고 — 다만 그건 STT 학습 환경이고 TTS/배포 쪽 requirements엔 아직
   없음)
8. `Qwen3TTSModel.from_pretrained(MODEL_ID, ...)`에 `revision=`(커밋 SHA) 고정 — 지금처럼 `main`
   최신을 그냥 참조하면 나중에 체크포인트가 또 바뀔 때 코드는 안 건드렸는데 서비스가 조용히 깨질
   수 있음(epoch-8→epoch-24 전환 때 실제로 겪은 문제, `tests/integration_issues_2026-08-18.md` #1)

## 필요한 것 / 막힌 것

- **CPU 배포 속도 재측정 필요** — 13에포크 + voice-clone 경로 기준 수치가 아직 없음(위 실측 결과 ②),
  결과에 따라 대안 결정까지 팀 논의 필요
- `qwen_tts`·`python-dotenv` 패키지가 `requirements.txt`/`requirements-main.txt`엔 아직 없음(버전은
  실측 검증됨) — private repo라 배포 시 `HF_TOKEN`을 HF Spaces Repository secret으로 등록도 필요
- `prepare_data.py`/`finetune_qwen3tts.py` 이식 — 지금은 재현 코드가 이 저장소 밖에만 있음
- HF 모델 `revision` 고정 — 재발 방지용, 아직 미적용(위 진행 방법 8번)
- TTS 합성음을 STT 학습데이터로 쓰려면(`data/synthesized/`) `prepare_data.py`/`finetune_qwen3tts.py`
  이식이 선행되는 게 안전함
- **겹받침(복합 종성) 발음이 간헐적으로 부자연스러움** — G2P(발음열 변환) 전처리가 파이프라인에
  전혀 없고(`prepare_data.py`가 비어있음, 위 표 참고), KSS(~1.2만 문장)가 다양한 겹받침
  재음절화 맥락을 충분히 커버 못 했을 가능성이 원인으로 추정됨(확정 원인 규명은 안 됨) — G2P
  전처리 추가는 아직 계획에 없음

## 관련 문서

`docs/decisions.md`(OOM/CPU 속도 미확인 항목), `docs/ChefEar_팀_진행_가이드_v2.md` 6.1/9장,
`docs/ChefEar_PRD_SDD_v0.8.md` R-13/OI-11, `tests/integration_issues_2026-08-18.md`(화자명 불일치·
품질 저하 이슈의 최초 발견 기록).
