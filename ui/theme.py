"""ui/html/assets/style.css와 같은 디자인 토큰을 Streamlit용으로 옮긴 공통 스타일/컴포넌트.

Streamlit 기본 위젯(st.button 등)은 그대로 쓰고, 배지·카드·재료칩·대화 로그처럼
Streamlit 기본 컴포넌트로 표현하기 어려운 조각만 st.markdown(unsafe_allow_html=True)로
그린다. docs/ChefEar_PRD_SDD_v0.8.md 3.3의 화면 구성(①~⑥)을 그대로 따른다.
"""
import streamlit as st

CSS = """
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
  --positive-icon-bg: #dcebc9;
  --danger-bg: #f6e4de;
  --danger-text: #a24a34;
}

/* Streamlit 기본 크롬(헤더 툴바·메뉴·푸터)을 최소화해서 ui/html 버전처럼 화면 자체만
   보이게 한다. 사이드바 열기 화살표는 남겨둔다(개발용 "화면 바로가기" 접근용). */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; box-shadow: none; }

/* ui/html/assets/style.css의 body(#e9e2d3 바깥 배경) + .screen(카드 자체) 2단 구조를 그대로 옮김 */
.stApp { background: #e9e2d3; }
.block-container {
  max-width: 430px; background: var(--bg);
  padding: 20px 22px 44px;
  box-shadow: 0 20px 46px rgba(36, 28, 21, 0.14);
  min-height: 100vh;
  display: flex; flex-direction: column;
  /* block-container(stMainBlockContainer) 자신이 stMain(overflow:auto인 진짜 스크롤
     컨테이너)의 flex 자식이라, 기본값인 flex-shrink:1 때문에 콘텐츠가 길어지면(예: 대화
     구역이 항상 보이도록 바뀌며 화면이 길어진 경우) 실제 콘텐츠 높이(예: 1041px)를
     무시하고 min-height 한계선(예: 뷰포트 900px)까지 찌그러들어서, 넘친 부분이 바깥
     stApp의 overflow:hidden에 잘려 보이는 버그가 있었다(DevTools 실측으로 확인).
     flex-shrink:0으로 고정해 절대 안 찌그러들게 한다. */
  flex-shrink: 0;
}
/* block-container 바로 밑의 큰 stVerticalBlock 하나가 전체 화면 내용을 담는데, 기본값으로는
   내용물 높이만큼만 차지해서(auto) block-container의 min-height:100vh가 남겨준 여유 공간을
   실제로 갖지 못했다(그래서 render_spacer()의 flex:1 방식이 예전에 안 먹혔던 진짜 원인 -
   부모가 flex가 아니어서 자식이 늘어날 공간 자체가 없었음). block-container를 flex column으로
   만들고 이 자식을 flex:1로 늘려서, 그 안의 .ce-spacer(flex:1)들이 진짜 남는 공간을 나눠
   가지며 화면 크기가 바뀌어도(창 크기 조절·브라우저 확대/축소) 반응형으로 중앙 정렬되게 한다. */
/* flex-shrink을 0으로 고정한다 - flex:1 1 auto(shrink:1)였을 때, 콘텐츠 실제 높이가
   min-height:100vh보다 커지면(예: 대화 구역이 항상 보이게 바뀌면서 콘텐츠가 길어짐)
   브라우저가 이 블록을 부모 높이에 맞춰 억지로 찌그러뜨리려 하면서, 넘친 부분이
   화면에 잘려 보이는(ghost/cut) 렌더링 버그가 있었다(DevTools로 stMainBlockContainer/
   stVerticalBlock에서 실측 확인함). shrink:0으로 고정하면 콘텐츠가 짧을 때 grow:1로
   남는 공간을 채우는 동작은 그대로 유지하면서, 콘텐츠가 길어져도 절대 안 찌그러진다. */
.block-container > [data-testid="stVerticalBlock"] { flex: 1 0 auto !important; }
/* .ce-spacer 자체에 flex:1을 줘도 소용없다 - 실제로 stVerticalBlock의 flex 아이템인 건
   .ce-spacer의 4단계 위 조상인 stElementContainer이고, .ce-spacer는 그 안에 block으로
   납작하게 들어있는 손자뻘이라 flex:1이 그 자리에서 먹히지 않는다(DOM 구조를 실제로
   찍어봐서 확인함). 그래서 .ce-spacer를 담은 stElementContainer 쪽에 직접 flex:1을 준다.
   Streamlit 자체 CSS(Emotion)가 .element-container에 flex:0 1 auto를 이미 주고 있어서
   단순 규칙으로는 안 먹혀 !important로 덮어썼다. */
[data-testid="stElementContainer"]:has(.ce-spacer) { flex: 1 1 auto !important; }
/* 재료 칩 그리드(.ce-chip-grid)와 바로 아래 "응, 시작할게요" 버튼 사이 간격을 다른 구역보다
   더 띄우고 싶을 때, 칩 자체에 margin-bottom을 주면 위 문단에서 설명한 바로 그 겹침 버그가
   재현된다(margin은 stElementContainer 높이 측정에 반영 안 됨). 대신 padding은 박스 모델상
   항상 높이에 포함되므로, 칩을 담은 stElementContainer 쪽에 padding-bottom을 준다. */
[data-testid="stElementContainer"]:has(.ce-chip-grid) { padding-bottom: 14px; }
/* cooking_step의 "나:/ChefEar:" 대화 카드(.ce-transcript)와 바로 아래 "듣는 중" 마이크바
   사이 간격을 다른 구역보다 더 띄운다. 같은 이유로 margin이 아니라 padding-bottom을 쓴다. */
[data-testid="stElementContainer"]:has(.ce-transcript) { padding-bottom: 14px; }
/* cooking_step의 "듣는 중" 마이크바(.ce-mic-bar)와 바로 아래 이전/다시/다음 버튼 줄
   사이 간격을 더 띄운다. 같은 이유로 margin이 아니라 padding-bottom을 쓴다. */
[data-testid="stElementContainer"]:has(.ce-mic-bar) { padding-bottom: 14px; }
/* complete 화면의 "원본 레시피 보존됨"/"나만의 레시피로 저장됨" 상태 배지 줄과 바로 아래
   설명 카드 사이 간격을 더 띄운다. 같은 이유로 margin이 아니라 padding-bottom을 쓴다. */
[data-testid="stElementContainer"]:has(.ce-status-badge) { padding-top: 14px; padding-bottom: 14px; }
/* substitution_confirm의 레시피 교체 비교 카드(된장찌개 → 바지락된장찌개)와 바로 아래
   "네, 바꿔주세요"/"아니요, 원래대로" 버튼 줄 사이 간격을 더 띄운다. */
[data-testid="stLayoutWrapper"]:has([class*="st-key-sc_swap_card"]) { padding-bottom: 14px; }
html, body, [class*="css"] { font-family: "Pretendard", -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif; }

/* 시작·매칭실패·등록제안·완료·인식실패 화면(01/05/06/10/11)은 ui/html에서
   .screen을 flex column으로 두고 중간 콘텐츠에 flex:1 + justify-content:center를 줘서
   로고 밑 남는 공간에 내용을 수직 중앙 정렬한다. Streamlit은 네이티브 위젯(st.button 등)을
   그렇게 감쌀 수 없어서(각 위젯이 별도 컨테이너로 렌더링됨), 대신 중앙에 둘 콘텐츠
   앞뒤에 flex:1짜리 빈 블록을 넣어 위아래가 남는 공간을 똑같이 나눠 갖게 한다(위
   .block-container > stVerticalBlock 규칙과 짝을 이뤄야 실제로 늘어난다). 뷰포트/창
   크기가 바뀌면 남는 공간도 같이 바뀌므로 브라우저 확대·축소나 창 크기 조절에도
   반응형으로 중앙 정렬이 유지된다. */
.ce-spacer { width: 100%; flex: 1 1 auto; }

/* 커스텀 컴포넌트(.ce-*)는 각각 별도의 st.markdown() 호출로 그려지는데, Streamlit이
   그 감싸는 컨테이너(stElementContainer) 높이를 CSS margin을 반영하지 않고 먼저
   측정해버려서, 그 컴포넌트 자체에 위/아래 margin을 주면 다음 요소와 실제로 겹치는
   문제가 있었다("이전/다시/다음" 버튼 줄이 마이크 상태줄과 겹쳐 보인 원인).
   그래서 요소 사이 간격은 개별 margin이 아니라 부모의 flex gap 하나로만 통일한다. */
[data-testid="stVerticalBlock"] { gap: 1.35rem; }
.block-container hr { border-color: var(--border); margin: 10px 0; }
.block-container small, [data-testid="stCaptionContainer"] { color: var(--text-secondary) !important; font-size: 12.5px !important; }
[data-testid="stAlert"] { border-radius: 16px; }
div.stTextInput input {
  border-radius: 14px; border: 1.5px solid var(--border); background: var(--surface-alt);
  color: var(--text); font-family: inherit;
}

.ce-back-link { display:inline-flex; align-items:center; gap:4px; font-size:13px; color: var(--text-secondary); font-weight:700; margin-bottom: 4px; }

.ce-brand { display:flex; align-items:center; gap:8px; font-size:22px; font-weight:800; color:var(--text); }
.ce-brand .icon { color: var(--accent); display:inline-flex; }

.ce-section-title { display:flex; align-items:center; gap:7px; font-size:15px; font-weight:800; color:var(--text); margin-top: 18px; }
.ce-section-title .icon { color: var(--text-secondary); display:inline-flex; }

.ce-badge {
  display:inline-flex; align-items:center; gap:6px;
  background: var(--accent-soft); color: var(--accent-soft-text);
  font-size:13px; font-weight:700; padding:7px 15px; border-radius:999px;
}

.ce-card {
  background: var(--surface); border-radius: 22px; padding: 22px 20px;
  box-shadow: 0 10px 24px rgba(36,28,21,0.07);
}

.ce-dots { display:flex; justify-content:center; gap:9px; }
.ce-dots .d { width:9px; height:9px; border-radius:50%; background: var(--border); }
.ce-dots .d.active { background: var(--accent); transform: scale(1.25); }
.ce-dots .d.done { background: var(--accent-soft-text); opacity:.45; }

.ce-step-title { font-size:22px; font-weight:800; text-align:center; line-height:1.45; margin: 32px 0 14px !important; }

.ce-chip-grid { display:flex; flex-wrap:wrap; column-gap:9px; row-gap:16px; }
.ce-chip { display:inline-flex; align-items:center; gap:6px; background: var(--surface-alt); border:1px solid var(--border);
  border-radius:999px; padding:9px 14px; font-size:14px; font-weight:600; color: var(--text); }
.ce-chip.substituted { background: var(--positive-bg); border-color: var(--positive-bg); color: var(--positive-text); }

.ce-transcript { background: var(--surface); border-radius:16px; box-shadow: 0 2px 8px rgba(36,28,21,0.05); overflow:hidden; }
.ce-row { display:flex; gap:12px; padding:18px 18px; }
.ce-row + .ce-row { border-top:1px solid var(--border); }
.ce-avatar { width:30px; height:30px; min-width:30px; border-radius:50%; display:grid; place-items:center; font-size:14px; }
.ce-avatar.user { background: var(--accent); color: #fff; }
.ce-avatar.ai { background: var(--positive-icon-bg); color: var(--positive-text); }
.ce-row .who { font-weight:800; margin-right:3px; }
.ce-row .who.user { color: var(--accent-dark); }
.ce-row .who.ai { color: var(--positive-text); }
.ce-row p { margin:4px 0 0; font-size:14.5px; line-height:1.65; }

.ce-center { text-align:center; }
.ce-center h1 { font-size:22px; font-weight:800; margin:6px 0 8px; }
.ce-center p { font-size:14.5px; color: var(--text-secondary); line-height:1.6; margin:0; }

.ce-lead-icon { width:56px; height:56px; border-radius:50%; display:grid; place-items:center; margin: 0 auto; }
.ce-lead-icon.positive { background: var(--positive-bg); color: var(--positive-text); }
.ce-lead-icon.warn { background: var(--danger-bg); color: var(--danger-text); }
.ce-lead-icon.neutral { background: var(--accent-soft); color: var(--accent-soft-text); }

.ce-checkpoint { background: var(--accent-soft); border-radius:16px; padding:14px 16px; }
.ce-checkpoint .title { font-weight:800; color: var(--accent-soft-text); font-size:13.5px; margin-bottom:4px; }
.ce-checkpoint p { margin:0; font-size:13.5px; color: var(--accent-soft-text); line-height:1.5; }

.ce-status-badge { display:inline-flex; align-items:center; gap:6px; background: var(--positive-bg); color: var(--positive-text);
  font-size:12.5px; font-weight:700; padding:7px 13px; border-radius:999px; margin: 0 4px 0 0; }

.ce-hint { text-align:center; font-size:12.5px; color: var(--text-secondary); }

/* Streamlit은 좁은 화면에서 st.columns()를 자동으로 세로로 쌓는다(반응형 기본 동작).
   이 앱은 일부러 폰 너비(430px)로 좁게 만들어서 그 반응형 기준을 항상 넘겨버리기
   때문에, 이전/다시/다음 같은 가로 버튼 줄이 항상 세로로 쌓이고 그 위 요소와
   겹쳐 보였다. 컬럼이 항상 가로로 나란히 있도록 강제로 되돌린다. */
div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 10px !important; }
div[data-testid="stColumn"] { width: unset !important; flex: 1 1 0 !important; min-width: 0 !important; }

div.stButton > button {
  border-radius: 18px; font-weight: 700; padding: 0.65rem 1rem; border: 1.5px solid var(--border);
  background: var(--surface); color: var(--text); box-shadow: 0 2px 8px rgba(36,28,21,0.05);
  cursor: pointer;
}
div.stButton > button[kind="primary"] {
  background: var(--accent); border-color: var(--accent); color: #fff;
  box-shadow: 0 10px 22px rgba(238,123,54,0.32); font-weight: 800;
}
div.stButton > button[kind="primary"]:hover { background: var(--accent-dark); border-color: var(--accent-dark); }

.ce-player {
  display:flex; align-items:center; gap:14px; background: var(--surface-alt);
  border-radius:999px; padding:10px 14px; margin-top: 6px;
}
.ce-play-btn {
  width:38px; height:38px; min-width:38px; border-radius:50%;
  background: var(--accent-soft); color: var(--accent); display:grid; place-items:center;
}
.ce-wave { flex:1; display:flex; align-items:center; gap:3px; height:26px; overflow:hidden; }
.ce-wave span { width:3px; border-radius:2px; background: var(--accent); opacity:.85; display:inline-block; }

.ce-mic-bar {
  display:flex; align-items:center; gap:14px; background: var(--surface);
  border-radius:999px; padding:8px 18px 8px 8px; box-shadow: 0 10px 24px rgba(36,28,21,0.07);
  /* 브라우저 줌이 100%가 아니거나 Windows 디스플레이 배율이 걸려있을 때, 둥근 모서리 +
     box-shadow 조합이 정수 픽셀에 안 맞으면 가장자리가 이중으로 겹쳐 보이는(고스팅)
     크로미움 렌더링 버그가 있다. 이 요소를 별도 GPU 레이어로 승격시켜 서브픽셀
     반올림 오차를 줄인다. */
  transform: translateZ(0);
}
.ce-mic-icon { width:50px; height:50px; min-width:50px; border-radius:50%; display:grid; place-items:center; }
.ce-mic-icon.listening { background: var(--accent); color:#fff; box-shadow: 0 0 0 7px rgba(238,123,54,0.16); }
.ce-mic-icon.idle { background: var(--surface-alt); color: var(--accent); border:2px solid var(--border); }
.ce-mic-status .state { font-weight:800; color: var(--accent-dark); font-size:14.5px; display:block; }
.ce-mic-status .hint { font-size:12px; color: var(--text-secondary); display:block; }

.ce-big-mic-wrap { display:flex; justify-content:center; margin: 34px 0 8px; cursor: pointer; }
.ce-big-mic { width:84px; height:84px; border-radius:50%; display:grid; place-items:center;
  background: var(--surface-alt); color: var(--accent); border: 2px solid var(--border); cursor: pointer; }

/* start 화면의 실제 녹음 위젯(st.audio_input) - 장식용 원형 마이크 바로 아래 놓고, 앱
   색감에 맞춰 폭을 카드 안쪽으로 좁히고 둥글게 다듬는다. */
[data-testid="stAudioInput"] {
  max-width: 320px; margin: 4px auto 0; border-radius: 999px !important;
  border-color: var(--border) !important; background: var(--surface) !important;
}
/* 녹음/재생 버튼 아이콘은 fill="currentColor"라서 color만 바꾸면 앱 강조색으로 물든다.
   실시간 파형 자체는 wavesurfer.js가 그리는 라이브 렌더링이라(캔버스 기반) CSS로
   색을 못 바꾼다 - 재생 버튼·테두리·배경만 앱 색감에 맞춘다. */
[data-testid="stAudioInput"] [data-testid="stAudioInputActionButton"] { color: var(--accent) !important; }

/* 큰 원형 마이크(장식용 그림 + 안내 문구) 전체를 클릭 영역으로 만들어, 눌렀을 때만
   실제 녹음 위젯(st.audio_input)이 나타나게 한다 - hint_chip과 같은 방식으로 투명
   버튼을 그 위에 겹친다. */
[class*="st-key-ce_big_mic"] { position: relative; }
[class*="st-key-ce_big_mic"] [data-testid="stElementContainer"]:has(div.stButton) {
  position: absolute; inset: 0; z-index: 2;
}
[class*="st-key-ce_big_mic"] div.stButton > button {
  width: 100%; height: 100%; padding: 0; border: none; background: transparent;
  box-shadow: none; color: transparent; cursor: pointer;
}

/* ui/html의 .hint-chip은 <a> 안에 <span class="quote">로 일부만 굵게+주황색을 준다.
   st.button 라벨은 순수 텍스트만 지원해서 그 안에서 글자색을 섞어 쓸 수 없다 - 그래서
   "글씨는 서식 있는 st.markdown으로 진짜처럼 그리고, 그 위에 완전히 투명한 st.button을
   똑같은 크기로 겹쳐서 클릭만 받는" 방식으로 우회한다. st.container(key=...)로 감싼
   두 자식(markdown, button) 중 markdown이 정상 흐름으로 박스 크기를 결정하고, button은
   position:absolute로 그 위에 정확히 덮인다. */
[class*="st-key-hint_chip"] { position: relative; margin-bottom: 10px; }
[class*="st-key-hint_chip"] [data-testid="stElementContainer"]:has(div.stButton) {
  position: absolute; inset: 0; z-index: 2;
}
[class*="st-key-hint_chip"] div.stButton > button {
  width: 100%; height: 100%; padding: 0; border: none; background: transparent;
  box-shadow: none; color: transparent; cursor: pointer;
}

.ce-hint-chip {
  display: block; background: var(--surface); border: 1px solid var(--border);
  border-radius: 18px; padding: 14px 18px; font-size: 14.5px; font-weight: 600;
  color: var(--text); box-shadow: 0 2px 8px rgba(36,28,21,0.05); line-height: 1.5;
}
.ce-hint-chip .quote { color: var(--accent-dark); font-weight: 800; }

/* "처음으로" 뒤로가기 링크. render_brand()가 app.py에서 화면 공통으로 먼저 그려지기
   때문에 recipe_confirm 화면에서만 이 링크를 브랜드보다 "위"에 두려면 DOM 순서가 아니라
   CSS로 되돌려야 한다. st.container(key=...)는 stLayoutWrapper > stVerticalBlock 두
   겹으로 감싸는데, [class*="st-key-..."]가 잡는 건 안쪽 stVerticalBlock이라 거기에
   order를 줘도 진짜 형제(render_brand의 markdown)와 순서가 안 바뀐다 - 바깥쪽
   stLayoutWrapper가 진짜 flex 형제라 그쪽에 order:-1을 줘야 한다(DOM 직접 확인함). */
/* 부모 stVerticalBlock의 gap(1.35rem)이 모든 형제 사이에 균일하게 적용되는데, 처음으로↔
   ChefEar 사이만 더 붙이고 싶어서 이 항목에만 음수 margin-bottom을 줘서 gap을 상쇄한다.
   flex 아이템 자체(stLayoutWrapper)에 준 margin이라 콘텐츠 내부 margin 미반영 버그와는
   무관하게 정상적으로 다음 형제와의 간격을 줄인다. */
[data-testid="stLayoutWrapper"]:has([class*="st-key-ce_back_link"]) { order: -1; margin-bottom: -14px; }
[class*="st-key-ce_back_link"] { position: relative; margin-bottom: 4px; display: inline-block; }
[class*="st-key-ce_back_link"] [data-testid="stElementContainer"]:has(div.stButton) {
  position: absolute; inset: 0; z-index: 2;
}
[class*="st-key-ce_back_link"] div.stButton > button {
  width: 100%; height: 100%; padding: 0; border: none; background: transparent;
  box-shadow: none; color: transparent; cursor: pointer;
}

/* 화면 하단 버튼 줄을 화면 밑에 고정한다(recipe_confirm의 응/시작·다른 레시피,
   substitution_confirm의 네/아니요 등 - 컨테이너 key가 "_footer_buttons"로 끝나는
   화면마다 재사용). position:fixed는 뷰포트 기준이라 스크롤은 물론 Ctrl+휠 브라우저
   확대/축소로 뷰포트 배율이 바뀌어도 항상 화면 맨 아래에 붙어있다(별도 JS 없이 CSS
   표준 동작). block-container 자체는 안 건드리고 이 컨테이너만 흐름에서 빼내는
   것이라, 그 자리에는 각 화면에서 같은 높이만큼 빈 여백(spacer)을 넣어 마지막
   콘텐츠가 고정 버튼에 가려지지 않게 한다. */
[data-testid="stLayoutWrapper"]:has([class*="_footer_buttons"]) {
  position: fixed; left: 50%; bottom: 0; transform: translateX(-50%);
  width: 100%; max-width: 430px;
  background: transparent;
  padding: 14px 22px calc(20px + env(safe-area-inset-bottom, 0px));
  z-index: 50;
}
[data-testid="stVerticalBlock"][class*="_footer_buttons"] { gap: 10px; }

/* cooking_step 하단의 데모용 예시 버튼들 - ui/html의 .footer-nav 알약 버튼처럼 작게,
   가운데 정렬로 줄바꿈되게 만든다. 이 컨테이너의 내부 stVerticalBlock은 기본이
   flex-direction:column(세로 쌓기)인데, row+wrap으로 바꿔서 가로로 흐르다 넘치면
   다음 줄로 줄바꿈되게 한다. 각 버튼은 use_container_width=False로 둬서 텍스트
   길이만큼만 폭을 차지하게 한다(cooking_step.py에서 이미 그렇게 호출함). */
[data-testid="stVerticalBlock"][class*="st-key-cs_demo_buttons"] {
  flex-direction: row; flex-wrap: wrap; justify-content: center; gap: 8px;
}
[class*="st-key-cs_demo_buttons"] [data-testid="stElementContainer"] { width: auto !important; }
[class*="st-key-cs_demo_buttons"] div.stButton > button {
  background: rgba(36,28,21,0.82); color: #fff; border: none; border-radius: 999px;
  padding: 9px 16px; font-size: 12.5px; font-weight: 600; box-shadow: none; white-space: normal;
}
[class*="st-key-cs_demo_buttons"] div.stButton > button:hover { background: rgba(36,28,21,0.95); }
</style>
"""


# ui/html/assets/style.css의 인라인 SVG 아이콘을 그대로 재사용한다(HTML 버전과 아이콘을
# 통일하기 위함 - 이전에는 이모지를 썼는데 OS/브라우저마다 이모지 렌더링이 달라 HTML과
# 어긋나 보였다). st.button 라벨은 순수 텍스트만 지원해서 HTML을 못 그리므로, 버튼 위의
# 마이크 표시만은 이모지(🎙️)를 그대로 둔다.
_SVG = '<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'

ICON_POT = _SVG.format(
    size=28,
    body='<path d="M4 3c0 1.5 1 2 1 3M8 3c0 1.5 1 2 1 3M12 3c0 1.5 1 2 1 3"/>'
    '<path d="M3 9h18v2a8 8 0 0 1-8 8h-2a8 8 0 0 1-8-8V9Z"/>'
    '<line x1="1" y1="9" x2="3" y2="9"/><line x1="21" y1="9" x2="23" y2="9"/>',
)
ICON_MIC = _SVG.format(
    size=15,
    body='<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z"/>'
    '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>',
)
ICON_SPEAKER = _SVG.format(
    size=14,
    body='<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/>',
)
ICON_CHECK_CIRCLE = _SVG.format(size=26, body='<circle cx="12" cy="12" r="10"/><polyline points="8 12.5 11 15.5 16 9"/>')
ICON_CHECK_SMALL = _SVG.format(size=12, body='<path d="M20 6 9 17l-5-5"/>')
ICON_X_CIRCLE = _SVG.format(
    size=26, body='<circle cx="12" cy="12" r="10"/><line x1="9" y1="9" x2="15" y2="15"/><line x1="15" y1="9" x2="9" y2="15"/>'
)
ICON_QUESTION_CIRCLE = _SVG.format(
    size=26,
    body='<circle cx="12" cy="12" r="10"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.8.4-1.3 1-1.3 1.9"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
)
ICON_SPARKLE = _SVG.format(size=26, body='<path d="M12 3v6M12 15v6M3 12h6M15 12h6"/>')
ICON_BASKET = _SVG.format(
    size=21,
    body='<path d="M3 11h18M12 3v3M7 5v1M17 5v1"/><path d="M4 11l1.2 8.4A2 2 0 0 0 7.2 21h9.6a2 2 0 0 0 2-1.6L20 11"/>',
)
_MIC_BODY = (
    '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3Z"/>'
    '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>'
)
ICON_MIC_MD = _SVG.format(size=22, body=_MIC_BODY)
ICON_MIC_LG = _SVG.format(size=34, body=_MIC_BODY)
ICON_PLAY = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>'
ICON_CHEVRON_LEFT = _SVG.format(size=12, body='<polyline points="15 18 9 12 15 6"/>')


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def render_spacer() -> None:
    """ui/html의 flex:1(수직 중앙 정렬용 빈 공간)에 대응하는 여백.

    HTML은 콘텐츠를 `<div style="flex:1;justify-content:center">` 하나로 감싸면 되지만,
    Streamlit은 st.button 같은 네이티브 위젯을 그렇게 감쌀 수 없다(각 위젯이 별도
    컨테이너로 렌더링됨). 대신 중앙에 두고 싶은 콘텐츠 앞뒤에 flex:1짜리 빈 블록을
    넣어 남는 공간을 위아래로 똑같이 나눠 갖게 한다(CSS의 .ce-spacer 및
    .block-container > stVerticalBlock 규칙 참고). 창 크기나 브라우저 확대/축소가
    바뀌어도 남는 공간 자체가 다시 계산되므로 항상 반응형으로 중앙 정렬된다.
    """
    st.markdown('<div class="ce-spacer"></div>', unsafe_allow_html=True)


def render_brand() -> None:
    st.markdown(f'<div class="ce-brand"><span class="icon">{ICON_POT}</span> ChefEar</div>', unsafe_allow_html=True)


def render_back_link(label: str = "처음으로", key: str = "ce_back_link") -> bool:
    """ui/html의 .top-nav-back(뒤로가기 링크). 클릭되면 True를 반환한다."""
    with st.container(key=key):
        st.markdown(f'<div class="ce-back-link">{ICON_CHEVRON_LEFT}{label}</div>', unsafe_allow_html=True)
        return st.button(label, key=f"{key}_btn")


def render_section_title(text: str) -> None:
    st.markdown(f'<div class="ce-section-title"><span class="icon">{ICON_BASKET}</span>{text}</div>', unsafe_allow_html=True)


def render_badge(text: str) -> None:
    st.markdown(f'<span class="ce-badge">{text}</span>', unsafe_allow_html=True)


def render_chat(rows: list[tuple[str, str]]) -> None:
    """rows: [(role, text), ...], role은 'user' 또는 'ai'."""
    parts = ['<div class="ce-transcript">']
    for role, text in rows:
        if not text:
            continue
        who = "나" if role == "user" else "ChefEar"
        icon = ICON_MIC if role == "user" else ICON_SPEAKER
        parts.append(
            f'<div class="ce-row"><span class="ce-avatar {role}">{icon}</span>'
            f'<p><span class="who {role}">{who}:</span>{text}</p></div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_chips(ingredients: list[dict], substituted_name: str | None = None, show_qty: bool = True) -> None:
    parts = ['<div class="ce-chip-grid">']
    for ing in ingredients:
        is_sub = ing["name"] == substituted_name
        cls = "ce-chip substituted" if is_sub else "ce-chip"
        suffix = " (대체)" if is_sub else ""
        qty_part = f' {ing["qty"]}' if show_qty and "qty" in ing else ""
        parts.append(f'<span class="{cls}">{ing["emoji"]} {ing["name"]}{qty_part}{suffix}</span>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _dots_html(total: int, current: int) -> str:
    parts = ['<div class="ce-dots">']
    for i in range(1, total + 1):
        cls = "active" if i == current else ("done" if i < current else "")
        parts.append(f'<span class="d {cls}"></span>')
    parts.append("</div>")
    return "".join(parts)


def render_dots(total: int, current: int) -> None:
    st.markdown(_dots_html(total, current), unsafe_allow_html=True)


_WAVE_HEIGHTS = [6, 10, 16, 24, 14, 22, 28, 18, 26, 12, 20, 9, 16, 24, 14, 8, 12, 6, 10, 6]


def _player_html() -> str:
    bars = "".join(f'<span style="height:{h}px"></span>' for h in _WAVE_HEIGHTS)
    return f'<div class="ce-player"><span class="ce-play-btn">{ICON_PLAY}</span><span class="ce-wave">{bars}</span></div>'


def render_player() -> None:
    """ui/html의 .player(재생 버튼 + 파형) - 카드 밖에서 단독으로 쓸 때만 이 함수를 쓴다.
    카드 안에 넣을 땐 render_step_card()를 써야 한다(아래 설명 참고)."""
    st.markdown(_player_html(), unsafe_allow_html=True)


def render_step_card(total: int, current_step: int, step_text: str) -> None:
    """조리 화면의 .ce-card(점 표시 + 단계 텍스트 + 재생 파형) 전체를 통째로 그린다.

    st.markdown()은 호출마다 완전히 분리된 HTML 조각으로 렌더링돼서, 카드를 열고
    (`<div class="ce-card">`) 다른 st.markdown 호출들을 거쳐 나중에 닫으면(`</div>`) 그
    안에 있어야 할 내용이 카드 밖으로 빠져나가고 빈 카드만 남는다(실제로 이 버그가
    발생해서 빈 흰색 알약 모양 박스로 보였다). 그래서 카드 내용 전체를 반드시 하나의
    st.markdown 호출로 합쳐서 그린다.
    """
    st.markdown(
        '<div class="ce-card">'
        + _dots_html(total, current_step)
        + f'<p class="ce-step-title">{step_text}</p>'
        + _player_html()
        + "</div>",
        unsafe_allow_html=True,
    )


def render_mic_bar(state: str, hint: str, listening: bool = True) -> None:
    """ui/html의 .mic-bar - 조리 화면(듣는 중)·등록 화면·인식 실패 화면(idle)에서 쓴다."""
    cls = "listening" if listening else "idle"
    st.markdown(
        f'<div class="ce-mic-bar"><span class="ce-mic-icon {cls}">{ICON_MIC_MD}</span>'
        f'<div class="ce-mic-status"><span class="state">{state}</span><span class="hint">{hint}</span></div></div>',
        unsafe_allow_html=True,
    )


def render_big_mic():
    """ui/html 01_start.html의 큰 원형 마이크 버튼(대기 상태) + 실제 브라우저 마이크 녹음.

    원형 아이콘 자체는 눌러도 녹음을 시작/정지할 수 없다(st.audio_input은 여러 단계
    상호작용이 필요한 위젯이라 hint_chip처럼 투명 버튼만 얹어 흉내낼 수 없음). 대신
    아이콘을 처음 누르면 실제 녹음 위젯이 그 아래에 나타나고, 이후 녹음/정지는 그
    위젯으로 직접 조작한다. 녹음된 오디오(UploadedFile) 또는 아직 없으면 None을 반환한다.
    """
    st.session_state.setdefault("show_mic_recorder", False)

    with st.container(key="ce_big_mic"):
        st.markdown(
            f'<div class="ce-big-mic-wrap"><span class="ce-big-mic">{ICON_MIC_LG}</span></div>'
            '<p class="ce-hint">눌러서 말씀해주세요</p>',
            unsafe_allow_html=True,
        )
        if st.button("마이크 켜기", key="ce_big_mic_btn", use_container_width=True):
            st.session_state.show_mic_recorder = True

    if not st.session_state.show_mic_recorder:
        return None
    return st.audio_input("음성으로 말씀해주세요", label_visibility="collapsed")
