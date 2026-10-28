"""Echo the multiple-file uploader surface onto the wire for capture."""
import json

import streamlit as st

st.title("Multiple uploads")
files = st.file_uploader("Upload files", accept_multiple_files=True, key="multi-upload")

report = {
    "count": len(files),
    "files": [
        {
            "name": file.name,
            "size": file.size,
            "type": file.type,
            "bytes_head": list(file.getvalue()[:8]),
        }
        for file in files
    ],
}
st.code(json.dumps(report, ensure_ascii=False, sort_keys=True), language="json")
