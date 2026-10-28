"""Echo the size-limited uploader surface onto the wire for capture."""
import json

import streamlit as st

st.title("Size-limited upload")
files = st.file_uploader("Upload one small file", max_upload_size=1, key="limit-upload")

report = {
    "count": len(files) if isinstance(files, list) else (1 if files else 0),
    "files": [
        {"name": file.name, "size": file.size}
        for file in (files if isinstance(files, list) else ([files] if files else []))
    ],
}
st.code(json.dumps(report, ensure_ascii=False, sort_keys=True), language="json")
