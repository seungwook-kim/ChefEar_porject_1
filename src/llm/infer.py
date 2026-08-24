"""ChefEar 로컬 LLM - 발화에서 요리명을 뽑기 위한 EXAONE 추론.

[모델]
LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct — LG AI Research, 온디바이스/경량 배포용으로 설계된
한국어 네이티브 모델. 동급 경량 모델 중 한국어 벤치마크가 가장 높아서 채택했다
(`docs/specs/llm_dish_name_extract.md` 참고).

[배포 방식]
이 파일 자체는 `transformers.AutoModelForCausalLM`으로 가중치를 직접 로드하는 코드다 —
별도 상용 API 서버(Ollama/OpenAI 호환 서버 등)를 두지 않는다. 이 파일이 실제로 어느
프로세스에서 도는지는 배포 구조에 따라 다르다(2026-08-24, 같은 날 두 번 바뀜—
`docs/decisions.md` #2 참고):
- **로컬 개발/검증**: 팀 GPU 데스크탑(RTX 5070)에서 Streamlit 프로세스 안에 직접 로드.
- **배포(현재 확정)**: 프론트(Streamlit Community Cloud, GPU 없음)/백엔드(HF Spaces
  유료 GPU T4) 분리 — 이 파일은 프론트가 아니라 `hf_backend/app.py`(Gradio API 서버)
  프로세스 안에서 로드되고, 프론트는 `src/orchestration/inference_backend.py`를 통해
  네트워크로 그 결과만 받는다. 이 파일의 로직 자체는 어느 경우든 동일 — 호출 위치만
  달라진다.

AGENTS.md의 "외부 LLM API 호출 금지"(1.5 원칙)는 OpenAI/Anthropic/Gemini/Groq/
OpenRouter처럼 인터넷 건너 남의(제3자) 서버로 텍스트를 보내는 걸 막는 규칙이다 —
오픈라우터도 API 키로 호출하는 이상 실제 추론이 오픈라우터 서버에서 일어나므로 이
원칙에 걸린다(그래서 배제함). 여기서는 팀이 직접 만든 HF Space(`hf_backend/`)나 팀
GPU 데스크탑에 이 파일이 가중치를 직접 올려서 돌리는 것이라, 프론트-백엔드 사이에
네트워크 호출이 있어도 제3자 LLM API가 아니라 팀 소유 인프라의 원격 호출이라 이
원칙에 걸리지 않는다(같은 논리가 `docs/decisions.md` #2에도 남아있음).

이 저장소에 이미 고정된 `transformers==4.57.3`(requirements-main.txt/requirements-stt.txt,
Whisper 학습용으로 확정된 버전)을 그대로 재사용한다 — 새 의존성 추가 없음.

`trust_remote_code=True`가 필요하다(EXAONE 공식 모델카드 기준 — LG가 배포한 커스텀
모델링 코드를 그대로 실행한다는 뜻). 다른 소스의 체크포인트로 바꿀 땐 이 코드를
신뢰할 수 있는지 다시 확인할 것.

[호출 예시]
from llm.infer import generate_json
result = generate_json('아래 발화에서 요리명만 JSON으로 답해: "된장찌개 어떻게 만들어?"')
# {"dish_name": "된장찌개"} 또는 None(실패/형식 오류)
"""
from __future__ import annotations

import json
import os
import re

import torch

from orchestration.db import load_env

load_env()

MODEL_ID = os.environ.get("LLM_MODEL_REPO") or "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"

# 2026-08-20 실측: 이 리포의 최신 커밋(ccce25bd39, "Update ... for Transformers v5")이
# configuration_exaone.py에서 transformers.modeling_rope_utils.RopeParameters를 import하는데,
# 이 프로젝트에 고정된 transformers==4.57.3(STT/TTS와 공유하는 버전, requirements-main.txt)엔
# 그 심볼이 없어서 ImportError로 로드 자체가 실패했다(`AutoModelForCausalLM.from_pretrained`).
# v5 마이그레이션 이전 커밋(2024-12-11, transformers v4.x 시절 코드)으로 고정하면 로드된다 —
# transformers==4.57.3을 올리는 대신(공유 pin이라 STT/TTS 회귀 위험, docs/decisions.md 4번과
# 같은 유형의 문제) 이 리포 쪽을 과거 커밋에 고정하는 쪽을 선택했다.
MODEL_REVISION = os.environ.get("LLM_MODEL_REVISION") or "e949c91dec92095908d34e6b560af77dd0c993f8"

# 요리명 JSON 한 줄({"dish_name": "..."})만 생성하면 되므로 짧게 잡는다 — tts_synthesize()의
# DEFAULT_MAX_NEW_TOKENS(600, 문장 전체 음성 합성용)보다 훨씬 짧아도 충분한 태스크다.
DEFAULT_MAX_NEW_TOKENS = 64

_model = None
_tokenizer = None


def load_llm():
    """EXAONE 모델/토크나이저를 최초 1번만 로드하고 이후 호출에서 재사용한다.

    tts/infer.py의 load_tts_model()과 같은 지연 로드 + 전역 캐시 패턴 — 앱이 뜰 때마다
    매번 몇 GB짜리 가중치를 다시 읽지 않게 한다.
    """
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer

    from transformers import AutoModelForCausalLM, AutoTokenizer

    # 2026-08-19 팀 결정(docs/decisions.md #2, TTS 배포 결정을 서비스 전체에 동일 적용): 배포를
    # GPU 데스크탑 상시 노출로 확정해서 CPU 폴백을 없애고 GPU를 필수로 요구한다.
    if not torch.cuda.is_available():
        raise RuntimeError(
            "GPU(CUDA)가 필요합니다 — 배포 방향이 GPU 전용으로 확정됨(docs/decisions.md #2)."
        )
    device_map, dtype = "cuda:0", torch.bfloat16

    _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=True)
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        trust_remote_code=True,
        device_map=device_map,
        dtype=dtype,
    )
    print(f"[LLM] 모델 로드 완료: {MODEL_ID} (device={device_map})")
    return _model, _tokenizer


def generate_response(prompt: str, *, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS) -> str:
    """프롬프트 하나를 EXAONE에 넣고, 새로 생성된 부분만(입력 프롬프트 제외) 텍스트로 돌려준다."""
    model, tokenizer = load_llm()

    input_ids = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=False,  # 요리명 추출은 매번 같은 답이 나와야 하는 태스크라 그리디 디코딩
        )

    generated = output_ids[0][input_ids.shape[-1]:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    """EXAONE이 JSON을 마크다운 코드펜스(```json ... ```)로 감싸서 답하는 경우가 실측으로
    확인됐다(2026-08-20, 프롬프트에 "다른 말은 절대 덧붙이지 않는다"고 명시해도 발생) —
    json.loads() 전에 펜스를 벗겨낸다. 코드펜스가 없는 순수 JSON 응답도 그대로 통과시킨다.
    """
    text = text.strip()
    match = _CODE_FENCE_RE.match(text)
    return match.group(1).strip() if match else text


def generate_json(prompt: str, *, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS) -> dict | None:
    """generate_response()의 결과를 JSON dict로 파싱한다.

    모델 로드/추론 자체가 실패하면(GPU 메모리 부족, 모델 파일 없음 등) 예외를 그대로
    올린다 — 이건 설정 문제라 개발 중엔 바로 보이는 게 낫다. 반면 모델이 응답은 했는데
    JSON 형식을 안 지켰을 때는 예외 없이 None을 돌려준다 — 호출부(entity_extract_llm.py)가
    "요리명 없음"과 똑같이 처리해서 서비스가 죽지 않게 하기 위해서다(EC-03).
    """
    raw_text = generate_response(prompt, max_new_tokens=max_new_tokens)
    try:
        return json.loads(_strip_code_fence(raw_text))
    except json.JSONDecodeError:
        print(f"[LLM] 모델 응답이 JSON 형식이 아님: {raw_text!r}")
        return None
