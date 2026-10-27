"""data_editor interaction reference fixture: a dynamic editor over a typed
two-column frame; each stage's rerun re-renders the table with the edits
applied server-side (st.write of the returned, edited dataframe)."""
import pandas as pd
import streamlit as st

df = pd.DataFrame({"qty": [1, 2], "label": ["a", "b"]})
edits = st.data_editor(df, num_rows="dynamic", key="editor")
st.write(edits)
st.write(f"rows={len(edits)}")
