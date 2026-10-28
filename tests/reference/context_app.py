"""Echo the pinned 1.66.1 st.context surface onto the wire for capture."""
import json

import streamlit as st

report = {
    "headers": dict(st.context.headers),
    "ip_address": st.context.ip_address,
    "is_embedded": st.context.is_embedded,
    "locale": st.context.locale,
    "timezone": st.context.timezone,
    "timezone_offset": st.context.timezone_offset,
    "url": st.context.url,
    "theme": dict(st.context.theme) if st.context.theme is not None else None,
}
st.code(json.dumps(report, ensure_ascii=False, sort_keys=True), language="json")
