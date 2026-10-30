"""Emit code/skeleton/logo creation-wire parameter variants."""
import streamlit as st


def run_logo_strings():
    values = ["🧊", "🛠️", "🛠", "👩‍💻", "👨‍👩‍👧‍👦", "🏳️‍🌈", "🇨🇳", "1️⃣", "👍🏽", "👩🏽‍💻", "☕", "☕️",
              ":material/home:", ":material/rocket_launch:", "https://example.invalid/logo.png", "HTTPS://example.invalid/logo.png",
              "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jk1sAAAAASUVORK5CYII=", "/app/static/logo.png"]
    cases = []
    for index, image in enumerate(values):
        case = {"image": image, "icon_image": values[(index + 3) % len(values)], "size": ("small", "medium", "large")[index % 3]}
        if index % 2:
            case["link"] = f"https://example.invalid/logo/{index}"
        cases.append(case)
    st.json({"logo_cases": cases})
    for case in cases:
        st.logo(**case)


if st.query_params.get("case") == "logo-strings":
    run_logo_strings()
    st.stop()

st.title("Code skeleton logo edges")

# st.code: an exotic language tag and line numbers.
st.code("print('hi')", language="rust", line_numbers=True)

# st.skeleton: the default placeholder shape.
st.skeleton()

# st.logo: an emoji image with the default medium size.
st.logo("🧊")
