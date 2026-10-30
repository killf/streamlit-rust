"""Emit text-family and misc element creation-wire parameter variants."""
import streamlit as st

def run_identity():
    st.title("Element identity controls")
    alternate = st.checkbox("Alternate attributes", key="identity-alternate")
    help_text = "help B" if alternate else "help A"
    st.header("Stable heading", anchor="anchor-b" if alternate else "anchor-a", help=help_text,
              divider="red" if alternate else "blue")
    st.markdown("Stable markdown", help=help_text)
    st.badge("Stable badge", help=help_text)
    if alternate:
        st.caption("Same style text")
    else:
        st.markdown("Same style text")
    st.button("Action", key="identity-action", disabled=alternate, help=help_text,
              icon="✅" if alternate else "🧊", width="content")
    st.caption(f"alternate={str(alternate).lower()}")


if st.query_params.get("case") == "identity":
    run_identity()
    st.stop()


st.title("Text misc parameter edges")

# text: the plain pre-formatted body.
st.text("plain body")

# latex: a display formula.
st.latex(r"\int_0^1 x^2 dx")

# help: the inline popover helper.
st.help(st.dataframe)

# divider: small and default stretch forms.
st.divider()
