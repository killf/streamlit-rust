"""Echo the unauthenticated st.user and st.context.cookies surface for capture."""
import json

import streamlit as st

report = {
    "user": st.user.to_dict(),
    "user_keys": list(st.user.keys()),
    "cookies": dict(st.context.cookies.items()),
    "cookie_missing": st.context.cookies.get("missing"),
}
st.code(json.dumps(report, ensure_ascii=False, sort_keys=True), language="json")
