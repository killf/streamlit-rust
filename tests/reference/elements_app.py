"""Elements differential fixture: one page exercising the fifteen display,
layout, form and data APIs this chain promotes (title, header, caption, badge,
divider, code, markdown, write, columns, container, form, text_input,
form_submit_button, table, bar_chart)."""
import pandas as pd
import streamlit as st

st.title("Elements parity title")
st.header("Header level")
st.caption("A caption line")
st.badge("BETA")
st.divider()
st.code("print('hello')", language="python")
st.markdown("**bold** and `inline`")
st.write("plain write")

left, right = st.columns(2)
left.write("left column")
right.write("right column")

with st.container():
    st.write("inside container")

with st.form("note_form"):
    note = st.text_input("Note", value="hello")
    submitted = st.form_submit_button("Apply")
st.write(f"form: note={note!r} submitted={submitted}")

frame = pd.DataFrame({"kind": ["a", "b"], "count": [1, 2]})
st.table(frame)
st.bar_chart(frame, x="kind", y="count")
