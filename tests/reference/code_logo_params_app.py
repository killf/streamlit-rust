"""Emit code/skeleton/logo creation-wire parameter variants."""
import streamlit as st


def run_code_text():
    bodies = ["", "\n", "\n\n", "\n\n\n", "\nprint('hi')\n", "\n\n  indented\n\n", "  leading\n    nested  \n", "\r\nwindows\r\n", "\rreturn\r", "\n spaced \r\n", "\talpha\n\t\tbeta\n", "\u0085line\u2028end\u2029", "Unicode 🤖 中文\n"]
    languages = ["python", "", "RuSt", "made-up", " "]
    cases = []
    for index in range(len(bodies) * 2):
        cases.append({"body": bodies[index // 2], "language": languages[index % len(languages)],
                      "line_numbers": index % 2 == 1, "wrap_lines": index % 3 == 0,
                      "width": ["stretch", "content", 240][index % 3],
                      "height": ["content", "stretch", 120][index // 3 % 3]})
    cases.append({"body": "\nplain None language\n", "language": None, "line_numbers": True,
                  "wrap_lines": True, "width": "content", "height": 120})
    st.json({"code_cases": cases})
    for case in cases:
        st.code(**case)


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


if st.query_params.get("case") == "code-text":
    run_code_text()
    st.stop()

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
