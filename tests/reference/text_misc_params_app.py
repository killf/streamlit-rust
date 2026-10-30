"""Emit text-family and misc element creation-wire parameter variants."""
import streamlit as st


def run_badge_content():
    cases = [
        {'label': 'plain', 'kwargs': {'help': '\n    Tip [0]\n      detail\n', 'color': 'blue'}},
        {'label': '[ready]', 'kwargs': {'help': '\n    Tip [1]\n      detail\n', 'color': 'green', 'icon': ' 🧊 ', 'width': 'stretch'}},
        {'label': 'x] :red-badge[other', 'kwargs': {'help': '\n    Tip [2]\n      detail\n', 'color': 'orange', 'icon': '\t \n', 'width': 240}},
        {'label': '\\[ready\\]', 'kwargs': {'help': '\n    Tip [3]\n      detail\n', 'color': 'blue', 'icon': ' :material/check: '}},
        {'label': 'nested [[x]]', 'kwargs': {'help': '\n    Tip [4]\n      detail\n', 'color': 'green', 'icon': '\x1c🧊\x1f', 'width': 'stretch'}},
        {'label': '**bold**', 'kwargs': {'help': '\n    Tip [5]\n      detail\n', 'color': 'orange', 'width': 240}},
        {'label': '`code`', 'kwargs': {'help': '\n    Tip [6]\n      detail\n', 'color': 'blue', 'icon': ' 🧊 '}},
        {'label': '', 'kwargs': {'help': '\n    Tip [7]\n      detail\n', 'color': 'green', 'icon': '\t \n', 'width': 'stretch'}},
        {'label': '  padded  ', 'kwargs': {'help': '\n    Tip [8]\n      detail\n', 'color': 'orange', 'icon': ' :material/check: ', 'width': 240}},
        {'label': '\n  first\n    second\n', 'kwargs': {'help': '\n    Tip [9]\n      detail\n', 'color': 'blue', 'icon': '\x1c🧊\x1f'}},
        {'label': '中文 [🧊]', 'kwargs': {'help': '\n    Tip [10]\n      detail\n', 'color': 'green', 'width': 'stretch'}},
        {'label': 'line1\r\n[line2]', 'kwargs': {'help': '\n    Tip [11]\n      detail\n', 'color': 'orange', 'icon': ' 🧊 ', 'width': 240}},
    ]
    common_help = '\n    Common **help**\n      detail\n'
    st.json({"badge_cases": cases, "common_help": common_help})
    for case in cases:
        st.badge(case["label"], **case["kwargs"])
    for kind in ("markdown", "caption", "title", "header", "subheader"):
        getattr(st, kind)("Help control", help=common_help)


if st.query_params.get("case") == "badge-content":
    run_badge_content()
    st.stop()


def run_divider_errors():
    phase = st.query_params.get("phase", "zero")
    runs = st.session_state.get("divider_error_runs", 0) + 1
    st.session_state["divider_error_runs"] = runs
    st.json({"phase": phase, "runs": runs, "stage": "before"})
    if phase == "caught":
        results = []
        for width in (0, -1, -2147483648, 1):
            try:
                st.divider(width=width)
                results.append({"width": width, "returned": True})
            except Exception as error:
                results.append({"width": width, "type": type(error).__name__, "message": str(error)})
        st.json({"caught_results": results})
    else:
        width = {"zero": 0, "negative": -1, "recovered": 240}[phase]
        st.divider(width=width)
    st.json({"phase": phase, "runs": runs, "stage": "after"})


if st.query_params.get("case") == "divider-errors":
    run_divider_errors()
    st.stop()


def run_dividers():
    widths = ["default", "stretch", 1, 240, 2147483647]
    st.json({"divider_widths": widths})
    for width in widths:
        if width == "default":
            st.divider()
        else:
            st.divider(width=width)
    st.markdown("---")
    st.caption("---")
    st.latex("x")


if st.query_params.get("case") == "dividers":
    run_dividers()
    st.stop()


def run_normalization():
    cases = [
        "\n    alpha\n      beta\n    gamma\n",
        "\talpha\n    beta",
        " \talpha\n \tbeta",
        "  alpha\n \tbeta",
        "  alpha\n \t \n    beta",
        "\n  alpha\r\n    beta\r\n",
        "  alpha\r    beta",
        "\u2003alpha\n\u2003beta",
        "\u001calpha\u001f",
        "  alpha\n\u00a0\n    beta",
        " \t\n\t  ",
        "\n  中文\n    🧊\n",
    ]
    st.json({'normalization_cases': cases})
    for body in cases:
        for kind in ('markdown', 'caption', 'text', 'title', 'header', 'subheader', 'latex'):
            getattr(st, kind)(body)


if st.query_params.get("case") == "normalization":
    run_normalization()
    st.stop()


def run_layouts():
    cases = [
        {'kind': 'markdown', 'body': 'Markdown default', 'kwargs': {}},
        {'kind': 'markdown', 'body': 'Markdown auto', 'kwargs': {'width': 'auto'}},
        {'kind': 'markdown', 'body': 'Markdown stretch', 'kwargs': {'width': 'stretch'}},
        {'kind': 'markdown', 'body': 'Markdown content', 'kwargs': {'width': 'content'}},
        {'kind': 'markdown', 'body': 'Markdown pixels', 'kwargs': {'width': 240}},
        {'kind': 'markdown', 'body': 'Markdown help', 'kwargs': {'help': 'layout help'}},
        {'kind': 'markdown', 'body': 'Markdown center', 'kwargs': {'text_alignment': 'center'}},
        {'kind': 'markdown', 'body': 'Markdown right', 'kwargs': {'text_alignment': 'right', 'width': 'stretch'}},
        {'kind': 'markdown', 'body': 'Markdown justify', 'kwargs': {'text_alignment': 'justify', 'width': 240}},
        {'kind': 'caption', 'body': 'Caption default', 'kwargs': {}},
        {'kind': 'caption', 'body': 'Caption content', 'kwargs': {'width': 'content'}},
        {'kind': 'caption', 'body': 'Caption pixels', 'kwargs': {'width': 240}},
        {'kind': 'caption', 'body': 'Caption right help', 'kwargs': {'text_alignment': 'right', 'help': 'caption help'}},
        {'kind': 'badge', 'body': 'Badge default', 'kwargs': {}},
        {'kind': 'badge', 'body': 'Badge stretch', 'kwargs': {'width': 'stretch'}},
        {'kind': 'badge', 'body': 'Badge pixels', 'kwargs': {'width': 240}},
        {'kind': 'badge', 'body': 'Badge help icon', 'kwargs': {'help': 'badge help', 'icon': '🧊'}},
    ]
    if st.query_params.get("only_widths") == "true":
        cases = [case for case in cases if "text_alignment" not in case["kwargs"]]
    st.json({"layout_cases": cases})
    for case in cases:
        getattr(st, case["kind"])(case["body"], **case["kwargs"])


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


if st.query_params.get("case") == "layouts":
    run_layouts()
    st.stop()

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
