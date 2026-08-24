---
title: ChefEar Backend
emoji: 🧠
colorFrom: purple
colorTo: blue
sdk: gradio
sdk_version: "6.25.0"
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
