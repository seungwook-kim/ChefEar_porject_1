"""ChefEar 마이 레시피(로그인 -> 내가 등록한 레시피 목록 -> 수정/삭제) 화면 —
src/app.py에서 분리(2026-08-22, 화면 컴포넌트화).

목업 로그인이다 — 실제 회원가입/비밀번호 저장 없이 .env의 TEST_LOGIN_ID/
TEST_LOGIN_PASSWORD 계정 하나만으로 확인한다(2026-08-21, 소스 하드코딩 제거).
이 로그인은 FR-08의 쿠키 owner_id(누가 어떤 user_custom을 등록했는지 익명 식별)와는
별개 개념이라, 로그인 성공 후 보여주는 "내가 등록한 레시피"는 계정별로 걸러내지 않고
source="user_custom"인 레시피 전체를 보여준다 — 목업 계정이 하나뿐이라 계정별
소유권을 구분할 방법 자체가 없어서다.
"""
from __future__ import annotations

import os

import streamlit as st

from theme import ICON_BASKET_SM, render_back_link, render_badge, render_spacer
from orchestration.db import get_client
from orchestration.registration import delete_recipe, update_recipe
from ui.session import goto

# 2026-08-21: 로그인 화면의 목업 계정 아이디/비밀번호가 소스에 리터럴로 박혀 있어서
# (CWE-798, 하드코딩된 자격증명) PR 리뷰에서 거부됐다 — .env의 TEST_LOGIN_ID/
# TEST_LOGIN_PASSWORD로 옮기고, 소스에는 값 자체를 남기지 않는다(다른 자격증명과
# 같은 방식 — orchestration/db.py의 SUPABASE_URL/KEY, orchestration/identity.py의
# COOKIE_SECRET 참고). .env에 없으면 로그인 화면 자체를 막는다(fallback으로 다시
# 하드코딩된 기본값을 두면 같은 문제가 재발함).
TEST_LOGIN_ID = os.environ.get("TEST_LOGIN_ID")
TEST_LOGIN_PASSWORD = os.environ.get("TEST_LOGIN_PASSWORD")


def screen_login() -> None:
    if render_back_link("첫화면으로 가기"):
        goto("start")

    render_spacer()
    st.markdown(
        '<div class="ce-center"><h1>로그인</h1>'
        "<p>등록한 레시피를 관리하려면 로그인해주세요.</p></div>",
        unsafe_allow_html=True,
    )
    render_spacer()

    if not TEST_LOGIN_ID or not TEST_LOGIN_PASSWORD:
        st.error("로그인이 아직 설정되지 않았어요 — .env에 TEST_LOGIN_ID/TEST_LOGIN_PASSWORD를 채워주세요.")
        return

    user_id = st.text_input("아이디", key="login_id_input")
    password = st.text_input("비밀번호", type="password", key="login_pw_input")
    if st.button("로그인", type="primary", use_container_width=True):
        if user_id == TEST_LOGIN_ID and password == TEST_LOGIN_PASSWORD:
            st.session_state.logged_in = True
            goto("my_recipes")
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않아요.")


def screen_my_recipes() -> None:
    if not st.session_state.logged_in:
        goto("login")
        return
    if render_back_link("첫화면으로 가기"):
        goto("start")

    client = get_client()
    rows = (
        client.table("recipes")
        .select("id,dish_name,created_at")
        .eq("source", "user_custom")
        .order("created_at", desc=True)
        .execute()
        .data
    )

    render_badge(f"내가 등록한 레시피 · {len(rows)}개")

    if not rows:
        st.info("아직 등록한 레시피가 없어요.")
        return

    confirm_id = st.session_state.confirm_delete_id
    # 2026-08-22 요청 - 레시피가 많아지면 목록이 화면 밖으로 길게 늘어나던 걸, 일정
    # 높이가 넘으면 그 안에서만 스크롤되게 감싼다(CSS는 theme.py의 st-key-my_recipes_list
    # 선택자 참고).
    with st.container(key="my_recipes_list"):
        for row in rows:
            with st.container(key=f"my_recipe_card_{row['id']}"):
                c1, c_actions = st.columns([5, 2])
                with c1:
                    st.markdown(
                        f'<div class="ce-recipe-name"><span class="icon">{ICON_BASKET_SM}</span>{row["dish_name"]}</div>',
                        unsafe_allow_html=True,
                    )
                with c_actions:
                    # st.columns([1,1])는 c_actions 칸 자체가 넓어지면 두 버튼도 같이
                    # 벌어진다(각 컬럼이 그 절반씩을 차지) - 화면이 넓을수록 간격이
                    # 커지는 문제가 실측으로 확인됐다(2026-08-21). 컬럼 대신 세로
                    # 블록 하나에 버튼 둘을 넣고 CSS로 가로 정렬 + 오른쪽 붙임
                    # 처리해서, 화면 폭과 무관하게 항상 붙어있게 한다.
                    with st.container(key=f"my_recipe_actions_{row['id']}"):
                        if st.button(":material/edit:", key=f"edit_{row['id']}", help="수정"):
                            st.session_state.editing_recipe_id = row["id"]
                            goto("edit_recipe")
                        if st.button(":material/delete:", key=f"delete_{row['id']}", help="삭제"):
                            st.session_state.confirm_delete_id = row["id"]
                            st.rerun()

                if confirm_id == row["id"]:
                    st.warning(f'"{row["dish_name"]}"를 정말 삭제할까요? 되돌릴 수 없어요.')
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button(
                            "네, 삭제할게요", key=f"confirm_delete_{row['id']}", type="primary", use_container_width=True
                        ):
                            delete_recipe(row["id"], client=client)
                            st.session_state.confirm_delete_id = None
                            st.rerun()
                    with cc2:
                        if st.button("취소", key=f"cancel_delete_{row['id']}", use_container_width=True):
                            st.session_state.confirm_delete_id = None
                            st.rerun()


def screen_edit_recipe() -> None:
    recipe_id = st.session_state.editing_recipe_id
    if not recipe_id:
        goto("my_recipes")
        return

    client = get_client()
    recipe = client.table("recipes").select("*").eq("id", recipe_id).single().execute().data
    steps = (
        client.table("recipe_steps")
        .select("step_number,step_text")
        .eq("recipe_id", recipe_id)
        .order("step_number")
        .execute()
        .data
    )

    if render_back_link("첫화면으로 가기"):
        st.session_state.editing_recipe_id = None
        goto("start")

    st.markdown(f'**{recipe["dish_name"]} 수정**')

    dish_name = st.text_input("요리명", value=recipe["dish_name"], key="edit_dish_name")
    ingredients_text = st.text_area(
        "재료 (쉼표로 구분)", value=recipe.get("ingredients") or "", key="edit_ingredients"
    )
    instructions_text = st.text_area(
        "조리 순서 (한 줄에 한 단계씩)",
        value="\n".join(s["step_text"] for s in steps),
        key="edit_instructions",
        height=200,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("저장", type="primary", use_container_width=True):
            ingredients = [x.strip() for x in ingredients_text.split(",") if x.strip()]
            instructions = [x.strip() for x in instructions_text.split("\n") if x.strip()]
            update_recipe(recipe_id, dish_name.strip(), ingredients, instructions, client=client)
            st.session_state.editing_recipe_id = None
            goto("my_recipes")
    with c2:
        if st.button("취소", use_container_width=True):
            st.session_state.editing_recipe_id = None
            goto("my_recipes")
