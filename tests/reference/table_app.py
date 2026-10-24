"""Development-only public-API oracle for Streamlit 1.66.1 tables and bars.

Select one isolated case with ?case=table-default (the default). Each browser
session has its own update counter. This fixture is never used by production.
"""

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Table and native bar reference", layout="wide")
case = st.query_params.get("case", "table-default")
st.title(case)
if st.button("Update data", key="update"):
    st.session_state["revision"] = st.session_state.get("revision", 0) + 1
revision = st.session_state.get("revision", 0)
st.caption(f"revision={revision}; streamlit={st.__version__}")

table_data = pd.DataFrame({
    "group.name": ["图书", "Café", "**Music**", None],
    "amount[0]": pd.Series([12 + revision, None, -3, 0], dtype="Int64"),
    "path\\label": ["普通", "naïve", None, "fin"],
})
bar_data = pd.DataFrame({
    "sales": [12 + revision, 24, -3, 0],
    "cost": [4, 8 + revision, None, 2],
})
named_bar = pd.DataFrame({
    "group.name": ["图书", "Café", "Music", "Toys"],
    "amount[0]": [12 + revision, 24, -3, None],
    "other": [4, 8 + revision, 1, 2],
})

try:
    if case == "table-default":
        result = st.table(table_data)
    elif case == "table-explicit":
        result = st.table(table_data, border="horizontal", hide_header=False,
                          hide_index=False, width=480, height=220, alt="UTF8 table")
    elif case == "table-hidden":
        result = st.table(table_data, border=False, hide_header=True,
                          hide_index=True, width="content", height="content")
    elif case == "table-custom-index":
        table_data.index = ["甲", "乙", "丙", "丁"]
        result = st.table(table_data)
    elif case == "bar-default":
        result = st.bar_chart(bar_data)
    elif case == "bar-single":
        result = st.bar_chart(bar_data[["sales"]])
    elif case == "bar-large-mixed":
        large = [9007199254740991 + revision, 9007199254740993, 9223372036854775807]
        st.json({"input_large_int64": large, "input_fraction": [0.5, 1.5, 2.5]})
        result = st.bar_chart(pd.DataFrame({"large": pd.Series(large, dtype="int64"),
                                           "fraction": [0.5, 1.5, 2.5]}))
    elif case == "bar-xy":
        result = st.bar_chart(named_bar, x="group.name", y="amount[0]",
                              width=480, height=260)
    elif case == "bar-horizontal":
        result = st.bar_chart(named_bar, x="group.name", y="amount[0]",
                              horizontal=True, sort=False, height=260)
    elif case == "bar-multiple":
        result = st.bar_chart(named_bar, x="group.name", y=["amount[0]", "other"],
                              stack=False, height=260)
    elif case == "table-invalid-border":
        result = st.table(table_data, border="vertical")
    elif case == "table-invalid-width":
        result = st.table(table_data, width=0)
    elif case == "bar-missing-column":
        result = st.bar_chart(named_bar, x="missing", y="amount[0]")
    elif case == "bar-invalid-width":
        result = st.bar_chart(bar_data, width=0)
    else:
        raise ValueError(f"Unknown isolated case: {case}")
except Exception as exc:
    st.json({"case": case, "exception": type(exc).__name__, "message": str(exc)})
else:
    st.json({"case": case, "return_is_none": result is None,
             "return_type": type(result).__name__, "revision": revision})
