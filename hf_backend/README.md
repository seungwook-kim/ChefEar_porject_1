---
title: ChefEar Backend
emoji: 🧠
colorFrom: purple
colorTo: blue
sdk: gradio
# ⚠️ 6.25.0으로 시작했다가 실제 빌드에서 huggingface-hub 버전 충돌로 두 번 실패함
# (2026-08-24 실측) — gradio가 이 sdk_version 값 그대로 강제로 같이 깔리는데(레포
# requirements.txt와 별개로), gradio>=6.0은 huggingface-hub>=1.16.0을 요구해서
# transformers==4.57.3(huggingface-hub<1.0 요구, qwen-tts==0.1.1이 이 버전을 강제)과
# 근본적으로 양립 불가. gradio 5.49.0은 huggingface-hub<2.0,>=0.33.5라 두 요구사항
# 교집합([0.34.0, 1.0))에 들어가서 고름 — transformers 버전(팀 검증 완료 조합)은
# 안 건드리는 쪽으로 해결.
sdk_version: "5.49.0"
app_file: app.py
pinned: false
---

# ChefEar 추론 백엔드 (내부용)

`src/stt/infer.py`·`src/tts/infer.py`·`src/llm/infer.py`를 Gradio API로 감싼 것.
사람이 쓰는 화면이 아니라, Streamlit Cloud 프론트(`src/app.py`)가
`src/orchestration/inference_backend.py`를 통해 원격 호출하는 대상이다.

이 폴더(`hf_backend/`)가 이 Space 저장소의 루트가 되도록 push해야 한다 — 단,
`app.py`가 `sys.path`에 `<레포 루트>/src`를 추가하므로, `src/` 폴더도 이 Space
저장소에 형제 폴더로 같이 올라가야 한다(레포 루트 전체를 이 Space로 push하는 게
가장 간단함, `hf_backend/app.py`의 상단 docstring 배포 방법 참고).

로컬에서 이 백엔드만 켜서 API 계약을 확인하려면(GPU 있는 로컬 환경 필요):

```
pip install -r hf_backend/requirements.txt
python hf_backend/app.py
```

자세한 배경/결정 근거는 `docs/decisions.md` #2, `hf_backend/app.py` 상단 docstring 참고.
