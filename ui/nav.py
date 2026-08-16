"""화면 전환 헬퍼. st.session_state.screen을 바꾸고 즉시 rerun한다."""
import streamlit as st


def goto(screen: str) -> None:
    st.session_state.screen = screen
    st.rerun()
