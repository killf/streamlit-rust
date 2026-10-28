"""Emit button/image creation-wire parameter variants."""
import io

from PIL import Image
import streamlit as st

st.title("Button and image parameter edges")

# st.button: disabled, type primary, and an icon ride the creation wire.
st.button("Primary", type="primary", icon=":material/star:", key="b1")
st.button("Disabled", disabled=True, key="b2")

# st.download_button: explicit file_name/mime, and a bytes body with defaults.
st.download_button("Save named", b"named payload", file_name="report.txt", mime="text/plain", key="d1")
st.download_button("Save default name", b"plain bytes", key="d2")


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (4, 3), (255, 0, 0, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


# st.image: two images in one call (a list input), plus a caption each.
st.image([png(), png()], caption=["first", "second"], width=120)
