"""ChefEar 소개(랜딩) 페이지 — 메인 서비스(src/app.py)와 완전히 분리된 정적 소개용 페이지.

메인 서비스와 코드/의존성을 공유하지 않는다 — 이 폴더 하나만으로 실행된다(로컬 전용,
HF Spaces 등 별도 배포 없음). 내용은 루트 README.md의 팀 소개/Product Goal/Core Scenario/
Core Features/Differentiation/Data & Models를 소개 페이지 톤으로 다시 정리한 것이다.

실행: streamlit run landing/app.py
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="ChefEar", page_icon="🍳", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
:root {
  --bg: #f7f1e6;
  --surface: #ffffff;
  --surface-alt: #fbf6ec;
  --border: #ece1cc;
  --text: #241c15;
  --text-secondary: #8b7e6c;
  --text-faint: #b3a690;
  --accent: #ee7b36;
  --accent-dark: #d9631f;
  --accent-soft: #fbebd3;
  --accent-soft-text: #ac6a28;
  --positive-bg: #e3efd3;
  --positive-text: #4b7a34;
}

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stAppViewContainer"] { background: var(--bg); }
.block-container { max-width: 980px; padding-top: 2.5rem; padding-bottom: 4rem; }
html, body, [class*="css"] {
  font-family: "Pretendard", -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  color: var(--text);
}

/* 히어로 */
.hero { text-align: center; padding: 20px 0 8px; }
.hero .logo { font-size: 52px; line-height: 1; margin-bottom: 10px; }
.hero h1 {
  font-size: 40px; font-weight: 800; letter-spacing: -0.5px; margin: 0 0 12px;
  color: var(--text);
}
.hero p.tagline {
  font-size: 18px; font-weight: 600; color: var(--accent-dark); margin: 0 0 14px;
}
.hero p.desc {
  font-size: 15.5px; color: var(--text-secondary); line-height: 1.7; max-width: 620px;
  margin: 0 auto;
}
.badge-row { display:flex; justify-content:center; gap:8px; margin-top: 22px; flex-wrap: wrap; }
.badge {
  display:inline-flex; align-items:center; gap:6px; background: var(--accent-soft);
  color: var(--accent-soft-text); border-radius: 999px; padding: 7px 16px;
  font-size: 13px; font-weight: 700;
}

/* 섹션 공통 */
.section { margin-top: 64px; }
.section-label {
  text-align:center; font-size: 13px; font-weight: 800; letter-spacing: 1.5px;
  color: var(--accent); text-transform: uppercase; margin-bottom: 8px;
}
.section-title {
  text-align:center; font-size: 26px; font-weight: 800; margin: 0 0 12px; color: var(--text);
}
.section-sub {
  text-align:center; font-size: 14.5px; color: var(--text-secondary); max-width: 560px;
  margin: 0 auto 32px; line-height: 1.65;
}

/* 카드 그리드 */
.card-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; }
.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 18px;
  padding: 22px 20px; box-shadow: 0 6px 18px rgba(36,28,21,0.05);
}
.card .icon { font-size: 26px; margin-bottom: 10px; display:block; }
.card h4 { font-size: 15.5px; font-weight: 800; margin: 0 0 6px; }
.card p { font-size: 13.5px; color: var(--text-secondary); line-height: 1.6; margin: 0; }

/* 시나리오 대화 */
.scenario {
  background: var(--surface); border-radius: 22px; padding: 26px 28px;
  box-shadow: 0 10px 24px rgba(36,28,21,0.06); max-width: 560px; margin: 0 auto;
}
.bubble { display:flex; margin-bottom: 14px; }
.bubble:last-child { margin-bottom: 0; }
.bubble .msg {
  border-radius: 16px; padding: 10px 15px; font-size: 14px; line-height: 1.55; max-width: 82%;
}
.bubble.user { justify-content: flex-end; }
.bubble.user .msg { background: var(--accent); color: #fff; border-bottom-right-radius: 4px; }
.bubble.ai .msg { background: var(--surface-alt); color: var(--text); border-bottom-left-radius: 4px; }

/* 플로우 */
.flow { display:flex; align-items:center; justify-content:center; flex-wrap: wrap; gap: 6px; }
.flow .step {
  background: var(--surface); border: 1px solid var(--border); border-radius: 999px;
  padding: 9px 16px; font-size: 13px; font-weight: 700; color: var(--text);
  box-shadow: 0 4px 10px rgba(36,28,21,0.04);
}
.flow .arrow { color: var(--text-faint); font-size: 15px; }

/* 통계 */
.stat-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }
.stat {
  background: var(--surface-alt); border-radius: 18px; padding: 20px; text-align:center;
}
.stat .num { font-size: 26px; font-weight: 800; color: var(--accent-dark); }
.stat .label { font-size: 12.5px; color: var(--text-secondary); margin-top: 4px; }

/* 차별점 테이블 느낌 카드 */
.diff-row {
  display:grid; grid-template-columns: 1fr 1fr; gap: 12px; background: var(--surface);
  border-radius: 16px; padding: 16px 18px; margin-bottom: 10px; box-shadow: 0 4px 12px rgba(36,28,21,0.04);
}
.diff-row .old { color: var(--text-faint); font-size: 13.5px; }
.diff-row .old::before { content: "기존 "; font-weight: 700; color: var(--text-secondary); }
.diff-row .new { color: var(--positive-text); font-size: 13.5px; font-weight: 600; }
.diff-row .new::before { content: "ChefEar "; font-weight: 700; }

/* 팀 카드 */
.team-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
.team-card {
  background: var(--surface); border-radius: 20px; padding: 24px 20px; text-align:center;
  box-shadow: 0 6px 18px rgba(36,28,21,0.05);
}
.team-card .avatar {
  width: 56px; height: 56px; border-radius: 50%; background: var(--accent-soft);
  display:flex; align-items:center; justify-content:center; font-size: 24px; margin: 0 auto 12px;
}
.team-card h4 { margin: 0 0 4px; font-size: 15.5px; font-weight: 800; }
.team-card .role { font-size: 12.5px; color: var(--accent-dark); font-weight: 700; margin-bottom: 10px; }
.team-card .task { font-size: 13px; color: var(--text-secondary); line-height: 1.6; }

/* 원칙 배너 */
.principle {
  background: var(--positive-bg); color: var(--positive-text); border-radius: 18px;
  padding: 18px 22px; text-align:center; font-size: 14px; font-weight: 600; line-height: 1.6;
  max-width: 640px; margin: 0 auto;
}

.footer-note {
  text-align:center; color: var(--text-faint); font-size: 12.5px; margin-top: 60px;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── 히어로 ──────────────────────────────────────────────────────────
st.markdown(
    """
<div class="hero">
  <div class="logo">🍳</div>
  <h1>ChefEar</h1>
  <p class="tagline">화면 대신, 목소리로 완성하는 요리</p>
  <p class="desc">
    요리 경험이 거의 없는 사용자가 칼질·반죽 등으로 손을 쓰기 어려운 상황에서도,
    화면을 보지 않고 음성만으로 레시피를 한 단계씩 진행하고 재료 대체까지
    그 자리에서 반영받는 음성 레시피 에이전트입니다.
  </p>
  <div class="badge-row">
    <span class="badge">🎙️ Whisper STT 파인튜닝</span>
    <span class="badge">🔊 Qwen3-TTS 파인튜닝</span>
    <span class="badge">🥘 표준 레시피 60,282종</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Target User ─────────────────────────────────────────────────────
st.markdown(
    """
<div class="section">
  <div class="section-label">Who it's for</div>
  <div class="section-title">이런 순간, ChefEar가 필요해요</div>
  <div class="section-sub">
    주요 사용자는 부모님과 따로 살기 시작한 직후이거나, 요리를 거의 해본 적 없는 완전 초보입니다.
  </div>
  <div class="card-grid">
    <div class="card"><span class="icon">🧂</span><h4>재료·계량 낯섦</h4><p>재료명과 계량 단위에 익숙하지 않아 레시피를 봐도 막막해요.</p></div>
    <div class="card"><span class="icon">🤲</span><h4>손을 쓰기 어려움</h4><p>칼질·반죽으로 손이 젖거나 더러워지면 화면 조작이 번거로워요.</p></div>
    <div class="card"><span class="icon">🥕</span><h4>재료가 없을 때</h4><p>조리 도중 재료가 없어서 다른 걸로 바꿔야 하는 상황이 자주 생겨요.</p></div>
    <div class="card"><span class="icon">👂</span><h4>필요한 순간만</h4><p>긴 레시피를 한 번에 듣기보다, 지금 필요한 단계만 안내받고 싶어요.</p></div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Core Scenario ───────────────────────────────────────────────────
st.markdown(
    """
<div class="section">
  <div class="section-label">How it works</div>
  <div class="section-title">이렇게 대화하듯 요리해요</div>
  <div class="scenario">
    <div class="bubble user"><div class="msg">된장찌개 만드는 법 알려줘</div></div>
    <div class="bubble ai"><div class="msg">된장찌개, 조회수 1위 표준 레시피예요. 이걸로 시작할까요?</div></div>
    <div class="bubble user"><div class="msg">응</div></div>
    <div class="bubble ai"><div class="msg">1단계, 물을 넣고 끓여주세요.</div></div>
    <div class="bubble user"><div class="msg">애호박 없는데 바지락 넣어도 돼?</div></div>
    <div class="bubble ai"><div class="msg">네, 바지락 된장찌개로 바꿔드렸어요. 계속 진행할게요.</div></div>
    <div class="bubble user"><div class="msg">다시 알려줘</div></div>
    <div class="bubble ai"><div class="msg">현재 단계를 다시 읽어드릴게요.</div></div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Service Flow ────────────────────────────────────────────────────
st.markdown(
    """
<div class="section">
  <div class="section-title" style="margin-top:0;">서비스 흐름</div>
  <div class="flow">
    <span class="step">🎙️ 사용자 음성</span><span class="arrow">→</span>
    <span class="step">Whisper STT</span><span class="arrow">→</span>
    <span class="step">의도 분류</span><span class="arrow">→</span>
    <span class="step">레시피 검색·진행·재료대체</span><span class="arrow">→</span>
    <span class="step">Qwen3-TTS</span><span class="arrow">→</span>
    <span class="step">🔊 음성 안내</span>
  </div>
  <div class="principle" style="margin-top:26px;">
    ✅ 의도분류는 문장 임베딩 유사도 매칭으로, 재료 대체·조리순서는 실데이터 검색으로만 처리해요.
    서비스가 실행되는 동안에는 외부 LLM API를 호출하지 않습니다.
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Core Features ───────────────────────────────────────────────────
st.markdown(
    """
<div class="section">
  <div class="section-label">Core Features</div>
  <div class="section-title">무엇을 할 수 있나요</div>
  <div class="card-grid">
    <div class="card"><span class="icon">🗣️</span><h4>음성 레시피 조회</h4><p>자유발화를 STT로 바꾸고 의도를 분석해 원하는 요리를 바로 찾아요.</p></div>
    <div class="card"><span class="icon">📶</span><h4>단계별 조리 안내</h4><p>전체 레시피를 한 번에 읽지 않고, 한 단계씩 필요한 만큼만 안내해요.</p></div>
    <div class="card"><span class="icon">🔁</span><h4>진행 / 재청취</h4><p>"다음", "다시", "한 번 더" 등 다양한 표현을 인식해요.</p></div>
    <div class="card"><span class="icon">🔄</span><h4>재료 대체</h4><p>조리 중 다른 재료를 쓰고 싶을 때, 실제 레시피 데이터에서 대체 가능한 레시피를 찾아줘요.</p></div>
    <div class="card"><span class="icon">💾</span><h4>사용자 레시피 저장</h4><p>변경한 레시피를 나만의 버전으로 별도 저장해요.</p></div>
    <div class="card"><span class="icon">🖥️</span><h4>화면 보조 UI</h4><p>현재 단계, 재료, 최근 대화를 화면으로도 함께 보여줘요.</p></div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Differentiation ─────────────────────────────────────────────────
st.markdown(
    """
<div class="section">
  <div class="section-label">Differentiation</div>
  <div class="section-title">기존 AI 스피커 요리 서비스와 다른 점</div>
  <div style="max-width:640px; margin:0 auto;">
    <div class="diff-row"><span class="old">정해진 레시피를 그대로 읽어줌</span><span class="new">사용자 진행 속도에 맞춰 단계별 안내</span></div>
    <div class="diff-row"><span class="old">주방 소음에 음성 인식 성능 저하</span><span class="new">요리 용어·잡음 환경 반영한 STT 파인튜닝</span></div>
    <div class="diff-row"><span class="old">재료 없을 때 대응 제한적</span><span class="new">실제 레시피 DB 기반 재료 대체 검색</span></div>
    <div class="diff-row"><span class="old">개인 변경사항 유지 어려움</span><span class="new">변경된 레시피를 개인 버전으로 저장</span></div>
    <div class="diff-row"><span class="old">음성만으로 이전 내용 확인 어려움</span><span class="new">음성 중심 + 화면 보조 방식</span></div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Data & Models ───────────────────────────────────────────────────
st.markdown(
    """
<div class="section">
  <div class="section-label">Data &amp; Models</div>
  <div class="section-title">숫자로 보는 ChefEar</div>
  <div class="stat-grid">
    <div class="stat"><div class="num">60,282</div><div class="label">고유 요리명</div></div>
    <div class="stat"><div class="num">234,538</div><div class="label">고유 레시피</div></div>
    <div class="stat"><div class="num">0.0000</div><div class="label">TTS→STT 재인식 CER</div></div>
    <div class="stat"><div class="num">90%+</div><div class="label">목표 재료 대체 완료율</div></div>
  </div>
  <div class="section-sub" style="margin-top:24px; margin-bottom:0;">
    STT는 <code>openai/whisper-large-v3-turbo</code>를 요리 도메인(재료명·계량단위·진행표현)으로
    QLoRA 파인튜닝했고, TTS는 <code>Qwen3-TTS-1.7B-VoiceDesign</code>을 KSS 데이터셋으로
    파인튜닝했습니다. 레시피 데이터는 만개의레시피 실데이터를 기준으로 씁니다.
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Team ─────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="section">
  <div class="section-label">Team</div>
  <div class="section-title">AI Human 7기 · A조</div>
  <div class="team-grid">
    <div class="team-card">
      <div class="avatar">👨‍🍳</div>
      <h4>김승욱 · 조장</h4>
      <div class="role">오케스트레이션 · 통합</div>
      <div class="task">의도분류, 단계 진행·재료대체 로직, Supabase 검색, HF Spaces 배포 및 통합테스트</div>
    </div>
    <div class="team-card">
      <div class="avatar">🔊</div>
      <h4>홍민하</h4>
      <div class="role">TTS 파인튜닝 · UI</div>
      <div class="task">Qwen3-TTS-1.7B-VoiceDesign + KSS 학습 환경 구성 및 파인튜닝, Streamlit UI 구현</div>
    </div>
    <div class="team-card">
      <div class="avatar">🎙️</div>
      <h4>하주성</h4>
      <div class="role">STT 파인튜닝</div>
      <div class="task">Whisper Small·wav2vec2 비교 실험, Whisper Large-v3-turbo QLoRA 파인튜닝, WER·CER 평가</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="footer-note">
  🍳 AI Human 7기 · Chef Ear — 기존 음성비서가 레시피를 읽어주는 서비스라면,<br/>
  ChefEar는 사용자의 조리 진행과 재료 변경에 맞춰 레시피가 함께 변하는 음성 요리 에이전트입니다.
</div>
""",
    unsafe_allow_html=True,
)
