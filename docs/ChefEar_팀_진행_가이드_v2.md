# 셰프이어(ChefEar) — 팀 진행 가이드 (v2, 2026-08-14 원본 → 갱신)

작성자: 김승욱 (팀장) · 원본 작성일: 2026-08-14 · 이 버전: 착수 후 갱신(PRD/SDD v0.8 기준 동기화)
이 문서는 팀원 전원이 읽고 시작하는 문서입니다. 원본(Day1 배포본)에서 여러 항목이 바뀌었으니, 예전에 이미 읽었더라도 아래 변경 표시(⚠️)는 다시 확인해주세요.

---

## 0. 한 줄 정의

부모님과 따로 살기 시작한 직후, 요리를 거의 해본 적 없는 완전 초보가, 칼질·반죽 등으로 손을 못 쓰는 상황에서 음성으로 레시피를 한 단계씩 안내받고 재료도 그 자리에서 바꿔가며 진행하는 에이전트. 자기만의 레시피로 저장되어 다음에도 재현된다.

---

## 1. 반드시 먼저 이해해야 할 핵심 원칙 4가지

### 원칙 1. 딥러닝 과제 범위는 STT/TTS 둘 다입니다 ⚠️ TTS 베이스 모델 변경
지도 강사 요구사항(공고 주제: "TTS·STT 서비스")에 따라, **파인튜닝하는 건 STT(Whisper)와 TTS(Qwen3-TTS 1.7B) 두 개**입니다.

- **TTS 베이스는 Piper → Qwen3-TTS로 변경됐습니다.** Piper 원본 저장소가 2025년 10월 아카이브(유지보수 중단)되고 후속 포크가 GPL-3.0으로 전환되어 배제했습니다. Qwen3-TTS는 강사 가이드의 TTS 권장 목록에도 포함된 도구입니다.
- **STT도 실제로 파인튜닝합니다.** 강사 가이드상 STT는 API 활용만으로도 감점이 없지만, 정량 지표(WER 전/후 비교)를 더 탄탄히 갖추기 위해 팀에서 파인튜닝하기로 확정했습니다. 학습 데이터는 KSS 원문 음성 + 파인튜닝된 Qwen3-TTS가 생성한 합성 음성(텍스트-음성 쌍)입니다.

### 원칙 2. 서비스가 실행되는 동안 외부 LLM API를 호출하는 코드는 절대 넣지 않습니다
지도 강사 가이드("1차 팀 프로젝트 가이드")에 따라, **완성된 서비스 코드 안에 OpenAI·Anthropic·Gemini·Groq 같은 외부 LLM API를 호출하는 부분이 있으면 요건 미충족**입니다. "API 한 번 호출하면 끝나는 패턴을 의도적으로 배제"한다는 게 명시되어 있습니다.

**아래 세 곳은 런타임 LLM 없이 처리합니다:**

| 상황 | 처리 방식(LLM 없음) |
|---|---|
| 의도 판단 | **임베딩 유사도 매칭**(sentence-transformers) — 발화를 벡터로 바꿔서, 미리 준비한 예문들과 제일 비슷한 걸 고름 |
| 재료대체 요청이 DB에 없음 | **그 자리에서 답을 지어내지 않고, "그런 레시피는 없어요"라고 정직하게 말함** |
| 조리순서 문의 | ⚠️ **60,282건 표준 데이터(실데이터)에서 조회만 함** — 아래 원칙 3 참고 |

**개발 도구로서 LLM(Claude 등)을 코드 작성·자료조사·문서화에 쓰는 건 자유롭게 허용됩니다.** 경계선은 "언제 호출하느냐"입니다 — 개발 중이면 OK, 서비스 실행 중이면 안 됨.

### 원칙 3. 조리순서 데이터는 LLM으로 생성합니다

요리명·재료 등 메타데이터(60,282건)는 만개의레시피 실데이터 기준이며, 동일 요리명이 여러 건 있을 때 조회수(INQ_CNT) 1위를 표준 레시피로 채택합니다. 조리순서(`COOKING_STEPS`) 텍스트는 ChatGPT(LLM)로 작성한 것이며, `source=api_standard`로 태깅되지만 조리순서 원문 자체는 실사용자가 작성한 문장이 아닙니다. 지도 강사 승인 하에 사용 중입니다(내용 검토 결과 조리법 자체는 사람마다 표현이 달라도 무방한 수준으로 확인됨, `db/README.md` 참고).

표준 데이터 밖의 요리명을 요청받으면, 재료대체 매칭 실패와 동일하게 정직하게 "없다"고 안내하고 신규 등록으로 유도합니다.

### 원칙 4. 절대 임의로 지어내지 않습니다
개발 중 애매한 상황이 생기면, 데이터를 직접 확인하고 없으면 "없다"고 인정합니다. 그럴듯하게 짐작해서 채우지 않습니다. (경쟁앱 조사도 마찬가지 — 실사용 테스트 없이 앱스토어 설명만 보고 단정하지 않습니다. 2장 참고.)

---

## 2. 디렉토리 구조 ⚠️ 대폭 변경 (2026-08-13 재갱신 — 런타임 실행 가능 구조로 보완)

```
ChefEar/
├── README.md                             # 프로젝트 소개. ⚠️ HF Spaces 배포 전 맨 위에 YAML frontmatter(sdk: streamlit, app_file: src/app.py) 추가 필요 — 아직 없음
├── requirements.txt                      # ⚠️ 신규 — HF Spaces 배포용 최소 의존성만(streamlit, sentence-transformers, faster-whisper, supabase). HF Spaces가 자동 인식하는 파일명은 이것뿐, requirements-main.txt는 안 읽음
├── .env.example                          # ⚠️ 신규 — Supabase URL/KEY, HF Hub 모델 repo id 등 필요한 환경변수 이름만(값 없이) 기록
├── docs/
│   ├── ChefEar_PRD_SDD_v0.8.md          # 최신 PRD+SDD, 모르는 게 있으면 여기부터 확인
│   ├── ChefEar_기획안.docx
│   ├── decisions.md                      # 결정 안 된 것들(Open Issues) 추적
│   └── meetings/                         # 회의록(킥오프, Sync, PoC Review 등)
│
├── env-main/                             # 오케스트레이션·STT·TTS 파인튜닝·서비스 전부 통합(로컬 개발·학습용, git 대상 아님)
├── requirements-main.txt                 # env-main 로컬 개발·학습 전체 의존성(peft/bitsandbytes 등 학습 패키지 포함, 배포엔 안 씀 — 위 requirements.txt와 역할 분리)
│
├── src/
│   ├── orchestration/                    # A(김승욱) 담당
│   │   ├── intent_classifier.py             # 임베딩 유사도 매칭(LLM 아님) — classify_intent()
│   │   ├── recipe_search.py                 # 순수 DB 조회 함수 모음: 표준레시피 선정·대체후보 검색·조리순서 조회(select_standard_recipe, search_variant_recipe, search_by_ingredient_content, get_precomputed_steps, get_current_step)
│   │   ├── substitution.py                  # 재료 대체 세션 흐름 + 취소 롤백(cancel_substitution) — recipe_search.py 호출해서 상태만 관리
│   │   ├── registration.py                  # ⚠️ 신규 — 신규 레시피 등록 세션(요리명→재료→재료확인→순서→최종확인), register_recipe()/save_recipe() → Supabase에 바로 insert(로컬 파일 저장 아님)
│   │   └── pipeline.py                      # 전체 흐름 조립: STT → 의도분류 → 조회/등록/재료대체 라우팅 → TTS
│   ├── stt/                              # C(하주성) 담당 — 파인튜닝
│   │   ├── prepare_data.py                  # KSS 음성 + Qwen3-TTS 합성음 페어링
│   │   ├── finetune_whisper.py              # Whisper 파인튜닝(학습, GPU 전용)
│   │   └── infer.py                         # ⚠️ 신규 — 파인튜닝 체크포인트를 faster-whisper(int8, CTranslate2)로 변환 + 런타임 추론, stt_transcribe()
│   ├── tts/                              # B(홍민하) 담당 — 파인튜닝
│   │   ├── prepare_data.py                  # KSS 24kHz 리샘플링
│   │   ├── finetune_qwen3tts.py             # Qwen3-TTS 파인튜닝(학습, GPU 전용)
│   │   └── infer.py                         # ⚠️ 신규 — 파인튜닝 체크포인트 로드, 런타임 음성 합성, tts_synthesize()
│   ├── ui/                               # B(홍민하) 담당(Streamlit), 화면 컴포넌트
│   └── app.py                            # HF Spaces 배포 엔트리포인트 — README frontmatter의 app_file 경로와 반드시 일치시킬 것
│
├── db/
│   └── schema.sql                        # recipes, recipe_steps 테이블(Supabase) — Supabase SQL 에디터에 수동 실행, 별도 마이그레이션 도구 안 씀
│
├── data/
│   ├── standard/
│   │   └── 요리명별_조리과정_60282건.csv    # ⚠️ 실물 미확보 — 서비스가 쓰는 조리순서 전량(실데이터), 확보 경로 확인 필요
│   ├── kadx_raw/                         # ⚠️ 신규, 실물 미확보 — KADX 원본 CSV 4개(234,538건 시드: 재료·요리명·메타), 확보 경로 확인 필요
│   ├── intent_examples/
│   │   └── 기준예문.csv                     # ⚠️ 실물 미확보 — 녹음용_문장스크립트_v1.csv 카테고리 재활용 예정(취소 카테고리 포함), 원본 파일 위치 확인 필요
│   ├── kss/                              # TTS·STT 학습 원본 음성(공개 데이터셋, CC BY-NC-SA 4.0) — 다운로드 스크립트로 채움
│   ├── synthesized/                      # Qwen3-TTS가 만든 합성음(STT 학습용 페어)
│   ├── evaluation_scripts/
│   │   └── 평가문장_200개.csv               # WER 평가용 텍스트(레시피 질문)
│   ├── mos_participants/                 # MOS 청취평가 참여자 기록(5명 이상, 학습용 아님)
│   └── consent/                          # KSS 라이선스 확인 기록
│
├── models/                               # 로컬 학습 산출물 스테이징(git 대상 아님) — 실배포는 HF Hub에서 다운로드해서 씀, 여기서 바로 안 읽음
│   ├── stt_finetuned/
│   └── tts_finetuned/
│
├── results/
│   ├── stt/                              # wer_rtf_epoch*.csv, loss_curve.png
│   └── tts/                              # wer_rtf_epoch*.csv, final_comparison.png
│
└── tests/
    └── integration_test.md               # 수동 시나리오 체크리스트(AC-14~16 GWT 기준) — pytest 아님, 의도된 형태
```

**바뀐 점(v2 최초)**: `env-piper-train/`(Piper 폐기로 삭제), `data/recipe_batches/`(5,100건 배치 방식 폐기로 삭제), `data/recording_scripts/`·`data/recordings/`(팀원 녹음 안 함, KSS로 대체되어 삭제), `docs/조리순서_생성_프롬프트_가이드.md`(LLM 생성 자체 폐기로 삭제) — 전부 지웠습니다. 대신 `db/`, `results/`, `data/kss/`, `data/synthesized/`, `data/mos_participants/`를 새로 추가했습니다.

**추가 변경(2026-08-13, 실행 가능 구조로 보완)**: PRD_SDD 7.1 함수 목록·8.2 배포 아키텍처와 대조해서 빠진 부분을 채웠습니다.
- 신규 파일: `requirements.txt`(HF Spaces 배포용, 루트), `.env.example`, `src/orchestration/registration.py`(신규등록 로직 담을 곳이 없었음), `src/stt/infer.py`·`src/tts/infer.py`(학습 스크립트만 있고 런타임 추론 코드가 없었음), `data/kadx_raw/`(원본 시드 CSV 자리 자체가 없었음)
- 코멘트 재정의: `recipe_search.py`/`substitution.py` 역할 분담이 애매했던 걸 "순수 DB 조회 vs 세션 상태 관리"로 명확히 나눔
- ⚠️ 표시된 데이터 파일(60,282건 조리순서 CSV, KADX 원본 4개, 녹음용_문장스크립트_v1.csv)은 **실물이 어디 있는지 아직 확인 안 됨** — 구조만 파놓은 상태, 착수 전 확보 경로부터 확정 필요

---

## 3. 팀 역할 분담 ⚠️ 담당자 확정(기존 문서에 반대로 적혀있던 것 정정)

| 파트 | 담당 업무 |
|---|---|
| **A. 오케스트레이션/통합(김승욱)** | 의도분류(임베딩 유사도 매칭), 기준 예문 세트 관리, 재료대체·취소 로직(실데이터 검색만, LLM 없음), 조리순서 실데이터(60,282건) 전처리·적재, Supabase 검색, Hugging Face Spaces 배포, 1주차 통합테스트 주관 |
| **B. TTS 파인튜닝/UI(홍민하)** | Qwen3-TTS 1.7B 학습 환경 구성 및 KSS 기반 파인튜닝, Streamlit UI 구현 |
| **C. STT 파인튜닝(하주성)** | KSS 원문 음성 + Qwen3-TTS 합성 음성으로 STT 학습데이터 구성, Whisper 파인튜닝, WER 평가(전/후 비교) |

**임시로 파트 정리했으며, 팀원 간 회의 후 조정 가능합니다.**

---

## 4. 재료 대체가 실제로 어떻게 처리되는지 (LLM 없이) ⚠️ 취소 케이스 추가

```
사용자: "바지락 넣어도 돼?"
   │
   ① Supabase에서 "바지락된장찌개" 같은 요리명이 정확히 있는지 검색
   │  있으면 → 그 레시피로 전환 제안 (끝)
   │
   ② 없으면, 재료 목록 안에 "바지락"이 들어간 다른 요리(예: "해물된장찌개")가 있는지 검색
   │  있으면 → 그 레시피 제시 (끝)
   │
   ③ 그것도 없으면 → "죄송해요, 이 조합의 레시피는 없어요"라고 정직하게 답함
      (LLM이 그럴듯한 답을 만들어내지 않음)

사용자: "아니 그냥 원래대로" / "취소해줘" (신규)
   │
   └─ 세션에 기록된 직전 recipe_id로 롤백(cancel_substitution())
```

이번 스프린트는 **1:1 단순 재료 치환까지만** 지원합니다. 조리법 자체를 바꾸는 재구성(볶음→찜 등)이나 양념 비율 재계산은 범위 밖이고, 동시 대체도 최대 2개까지만 지원합니다.

## 5. 조리순서 문의 처리 (LLM 없이) ⚠️ 전면 변경

```
사용자: "OO 어떻게 만들어?"
   │
   ├─ 60,282건 표준 데이터 안에 있음 → 재료+조리순서 다 안내 (대부분 이 경우)
   │
   └─ 표준 데이터 밖(전혀 새로운 조합 등) → 재료조차 확인 불가
       "죄송해요, 이 요리는 아직 등록된 레시피가 없어요. 직접 알려주시면 등록해드릴까요?"
       → 신규 등록 흐름으로 유도
```

~~5,100건 안/밖으로 나뉘던 이전 방식은 폐기됐습니다~~ — 이제 표준 데이터가 전체 고유 요리명(60,282개)을 커버하기 때문에, "아직 준비 안 됨" 안내는 예외적인 경우에만 나옵니다.

---

## 6. 개발 환경 세팅 (중요 — 반드시 순서대로) ⚠️ 환경 분리 폐지

### 6.1 왜 이제 작업 공간을 하나만 쓰는가
~~Piper(TTS) 학습이 STT 학습과 완전히 다른 버전을 요구해서 환경을 분리했었습니다.~~ Piper를 더 이상 쓰지 않고, Qwen3-TTS와 Whisper 둘 다 HuggingFace transformers 계열 파인튜닝(LoRA/전체)이라 **환경을 하나로 통합**합니다.

```bash
# 오케스트레이션·STT 파인튜닝·TTS 파인튜닝·서비스 전부 이 환경 하나로
python3.12 -m venv env-main
source env-main/bin/activate
pip install -r requirements-main.txt --break-system-packages
```

⚠️ **주의**: Qwen3-TTS 1.7B 파인튜닝은 노트북(RTX 4060 8GB)에서는 사실상 어렵습니다. 데스크탑(RTX 5070 12GB)에서도 배치사이즈를 최소화해야 하며, 실제로 OOM 없이 완주 가능한지 아직 실측 중입니다. 착수 초반에 먼저 확인하세요.

### 6.2 기술 스택 버전 (고정, 임의로 바꾸지 말 것)

| 구분 | 패키지 | 버전 |
|---|---|---|
| 언어 | Python | 3.12 (env-main) |
| 실행 | streamlit | 1.61.1 |
| 임베딩(의도분류 겸용) | sentence-transformers | 5.6.1 (모델: jhgan/ko-sroberta-multitask) |
| STT 학습 | transformers / peft / accelerate / bitsandbytes | 버전 재검증 필요(착수 후) |
| STT 추론 | faster-whisper | 1.2.1 |
| TTS 학습 | Qwen3-TTS 커뮤니티 LoRA 저장소(instavar/qwen3-tts-lora-finetuning 등) | 버전 미정, **비공식 실험적 저장소**라 디버깅 시간 여유 두기 |
| TTS 추론 | Qwen3-TTS 공식 저장소 기반 | 버전 미정 |
| STT·TTS 평가 | jiwer | 4.0.0 (파인튜닝 전/후 실제 비교 대상) |
| 벡터DB | supabase | 2.31.0 (SQL 절대 안 씀, 잠정) |

**주의**: `groq`, `piper-tts` 패키지는 requirements에서 완전히 제외했습니다. Qwen3-TTS 학습 시 **24kHz 리샘플링은 필수**(코덱이 다른 샘플레이트를 거부함)입니다.

---

## 7. 음성 학습 데이터 ⚠️ 녹음 절차 전면 폐지

### 7.1 팀원·지인 녹음, 하지 않습니다
~~파인튜닝된 Whisper가 진짜 사람 목소리로도 잘 알아듣는지 확인하려면 실제 녹음이 필요합니다~~ — **이 계획은 폐기됐습니다.** TTS·STT 파인튜닝 모두 **KSS(공개 한국어 음성 데이터셋)**를 사용합니다. TTS는 KSS 원문 음성으로 직접 학습하고, STT는 KSS 원문 음성 + 파인튜닝된 Qwen3-TTS가 생성한 합성 음성을 함께 학습 데이터로 씁니다.

KSS 라이선스는 CC BY-NC-SA 4.0(비상업)으로, 본 프로젝트(수업 과제)는 조건을 충족합니다. 팀원 동의서도 필요 없습니다(본인 목소리를 쓰지 않으므로).

### 7.2 그래도 사람이 필요한 부분 — MOS 청취평가
강사 가이드 8장에 **TTS MOS(평균 의견 점수) 평가 — 5명 이상 청취 평가**가 필수 정량 지표로 명시돼 있습니다. 이건 "학습용 녹음"이 아니라 **"완성된 TTS 음성을 듣고 점수 매기는" 평가 참여**라 훨씬 부담이 적습니다. `data/mos_participants/`에 참여자·점수를 기록합니다.

### 7.3 STT 학습데이터 관련 유의사항
자기가 만든 합성음(Qwen3-TTS 출력)으로만 STT를 학습시키면 특정 목소리·패턴에 치우칠 수 있습니다(model collapse 위험). KSS 원문 음성과 합성음을 함께 섞어 쓰고, 검증 단계에서 팀원 실제 음성으로도 별도 테스트하는 것을 권장합니다.

---

## 8. 전체 일정 (2주) ⚠️ 녹음 일정 삭제, 파인튜닝 일정 갱신

### 1주차 — 개발
| 기간 | 내용 |
|---|---|
| Day1 | 인수인계(이 문서 공유), 인터페이스 확정, env-main 세팅, 임베딩 의도분류 기준예문 정리, STT 학습데이터 구성 착수, Qwen3-TTS 학습 환경 구성, HF Spaces 저장소 초기화 |
| Day2~3 | KSS 기반 Qwen3-TTS 1차 파인튜닝, TTS 결과물로 STT 학습데이터 생성 및 Whisper 1차 파인튜닝, Supabase 시드 적재(60,282건) |
| Day4 | 조회/등록 흐름 통합, HF Spaces 배포 1차 시도 — **CPU 환경에서 Qwen3-TTS 추론 속도 반드시 실측**(6.1 참고) |
| **Day5~7** | **1주차 통합테스트** — TTS·STT 파인튜닝 1차 모델 포함 전체 파이프라인 동작 확인 |

### 2주차 — 정확도 개선 + 발표 준비
| 기간 | 내용 |
|---|---|
| Day8~9 | 하이퍼파라미터 튜닝(LR, epoch 등) 반복 테스트, MOS 청취평가 참여자 섭외·진행 |
| Day10 | 결과 안 좋으면 한 번 더 반복 |
| Day11~14 | Before/After 비교자료 정리, 발표 준비·리허설 |

---

## 9. 배포 ⚠️ 리스크 추가

**Hugging Face Spaces (CPU Basic, 완전 무료)**를 사용합니다. GPU는 학습(파인튜닝) 때만 필요하고, 배포된 서비스의 추론은 CPU로 처리하는 게 목표입니다.

⚠️ **미해결 리스크**: 이 계획은 원래 Piper(경량)를 전제로 세웠습니다. Qwen3-TTS(1.7B 파라미터)로 바뀌면서, **GPU 없는 무료 CPU 환경에서 목표 응답시간(5초 이내) 안에 동작하는지 아직 실측하지 못했습니다.** 안 되면 대안: ① GPU 지원 플랫폼(Modal 등)으로 전환 ② 데스크탑을 Tailscale로 상시 노출해 추론 서버로 활용 ③ Qwen3-TTS 0.6B 경량 모델로 축소. 착수 초반 실측 필수입니다.

---

## 10. 발표 시 반드시 챙길 것 ⚠️ 항목 변경

1. **STT/TTS 둘 다 Before/After 비교** (WER, 청취 비교) — 이제 STT도 파인튜닝하므로 둘 다 필요합니다
2. **"왜 LLM을 런타임에서 뺐는지"를 먼저 설명** — 지도 강사 가이드를 따른 것임을 명확히
3. **조리순서 데이터 구성을 있는 그대로 설명** — 요리명·재료 등 메타데이터(60,282건)는 실데이터로 확보했지만 조리순서(`COOKING_STEPS`) 원문 실데이터는 못 구해 LLM(ChatGPT)으로 채웠다는 점,
(2026-08-16)을 숨기지 말고 그대로 설명(원칙 4: 절대 임의로 지어내지 않음 — 발표에서도 동일 원칙 적용)
4. **경쟁앱(레시피오·레시핏·만개의레시피) 실사용 비교 결과** — 우리 차별점이 근거와 어떻게 맞아떨어지는지
5. **KSS 라이선스 확인했다는 것** 한 줄 명시(동의서는 불필요 — 팀원 녹음 안 함)

---

## 11. 질문 있으면

`docs/ChefEar_PRD_SDD_v0.8.md`에 지금까지 정리된 모든 기술 결정과 근거가 다 있습니다(v0.2~v0.8 변경 요약도 포함). 여기 없는 애매한 상황이 생기면, 임의로 판단하지 말고 팀 채팅방에 먼저 물어봐 주세요.
