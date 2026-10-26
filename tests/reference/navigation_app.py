"""Reference fixture: st.navigation multipage behavior on 1.66.1.

Driven by the m5 navigation probe (target/checks/m5-navigation-pyref):
a default function page with session state and a switch button, plus a
second page with a custom url_path, navigated both through the sidebar
and through st.switch_page.
"""
import streamlit as st


def render_main():
    st.session_state["hits"] = st.session_state.get("hits", 0) + 1
    st.write(f"page=main hits={st.session_state['hits']}")
    if st.button("Switch"):
        st.switch_page(two_page)


def render_two():
    st.write("page=two")


main_page = st.Page(render_main, title="Main", icon=":material/home:", default=True)
two_page = st.Page(render_two, title="Two", url_path="two")

pg = st.navigation([main_page, two_page])
pg.run()
