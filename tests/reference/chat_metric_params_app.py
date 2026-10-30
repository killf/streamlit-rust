"""Emit chat/metric/progress creation-wire parameter variants."""
import streamlit as st


def run_avatars():
    names = ["user", "human", "assistant", "ai", "USER", "HuMaN", "ASSISTANT", "AI", "Helper", "文字", "🤖", "👩‍💻", "🛠️", "🛠", ""]
    avatars = ["user", "human", "assistant", "ai", "🤖", "👩‍💻", ":material/robot:",
               "https://example.invalid/avatar.png", "HTTPS://example.invalid/avatar.png",
               "http://127.0.0.1:9/avatar.png", "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jk1sAAAAASUVORK5CYII=",
               "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciLz4=", "/app/static/avatar.png"]
    cases = [{"name": name, "avatar": None} for name in names] + [{"name": "Helper", "avatar": avatar} for avatar in avatars]
    st.json({"avatar_cases": cases})
    for index, case in enumerate(cases):
        with st.chat_message(case["name"], avatar=case["avatar"]):
            st.write(f"avatar-case:{index}")


if st.query_params.get("case") == "avatars":
    run_avatars()
    st.stop()

st.title("Chat metric progress edges")

# chat_message: emoji-type avatar and a nested element.
with st.chat_message("Helper", avatar="🛠️"):
    st.write("inside")

# metric: no-delta, zero delta, off/gray, and negative normal.
st.metric("No delta", value=42)
st.metric("Zero delta", value=5, delta=0)
st.metric("Gray", value=7, delta="3", delta_color="off")
st.metric("Negative", value=9, delta="-2")

# String deltas are text: numeric-looking strings must not be parsed as floats.
for mode in ("normal", "inverse", "off"):
    for index, delta in enumerate(("", "0", "0.0", "0%", "-0", "up", "-down", "NaN", " 0", "  -down", "\n  up\n  next\n", " \t\n")):
        st.metric(f"{mode}:{index}", value="1", delta=delta, delta_color=mode)

# progress: text label and a float value.
st.progress(50, text="Halfway there")
st.progress(25.5)
