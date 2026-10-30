"""Reference app for the four Streamlit status elements.

DEVELOPMENT ONLY -- an oracle for the C-P0-04 style/icon/width capture.  It is
never shipped and the Rust server must not start it.

Every case is a separate script run, selected with ``?case=...``.  That matters
for the invalid-parameter cases: a bad argument raises inside the script, which
aborts the whole run, so it must not sit in the same run as the default
messages -- otherwise the default messages after it would never be rendered.

    /?case=defaults     the four kinds with default icon, width and title
    /?case=variants      icon extraction, icon="", a Material icon, int width, title
    /?case=leading_emoji       a LEADING emoji in the body, icon left at None
    /?case=leading_emoji_noicon  the same leading emoji with icon=""
    /?case=leading_material   a LEADING Material icon shortcode in the body
    /?case=icon_zwj        explicit icon="👩‍💻" (ZWJ sequence, 3 code points)
    /?case=icon_skin_tone  explicit icon="👍🏽" (emoji + skin tone, 2 code points)
    /?case=icon_flag       explicit icon="🇨🇳" (regional indicators, 2 code points)
    /?case=icon_two_emoji  explicit icon="🔥💡" (two independent emoji)
    /?case=leading_composite  a LEADING ZWJ sequence in the body
    /?case=invalid_width width="bogus"  -> the error semantics
    /?case=invalid_icon  icon=123       -> the error semantics
"""

from __future__ import annotations

import streamlit as st

def run_error_contract():
    from streamlit.errors import StreamlitInvalidWidthError
    cases = [
        {'icon': '🔥💡', 'width': 0},
        {'icon': '👩\u200dx', 'width': 'bogus'},
        {'icon': 'bad', 'width': -1},
        {'icon': ' :material/not_a_real_icon: ', 'width': 'bogus'},
        {'icon': ':material/Thumb_UP:', 'width': 0},
        {'icon': ':material/thumb_up', 'width': 0},
        {'icon': ':smile:', 'width': 0},
        {'icon': 'http://example.invalid/icon.png', 'width': 0},
        {'icon': ' spinner ', 'width': 240},
        {'icon': '', 'width': 0},
        {'icon': '🧊', 'width': 'bogus'},
        {'icon': '  ', 'width': 'content'},
        {'icon': '🧊', 'width': 1},
        {'icon': 'spinner', 'width': 1},
        {'icon': ':material/thumb_up:', 'width': 1},
        {'icon': ':material/not_a_real_icon:', 'width': 1},
        {'icon': 'not-an-icon', 'width': 1},
        {'icon': ':+1:', 'width': 1},
        {'icon': 'https://example.invalid/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'width': 1},
        {'icon': '🧊', 'width': "'quoted"},
    ]
    cases.extend({'icon': '🧊', 'width': width} for width in (
        'plain', "'quoted", '"quoted', "'both\"", 'slash\\end', 'line\nnext', '\t\r\0', '\x1f\x7f',
        '中文🧊', 'e\u0301', '\u00a0', '\u2003', '\u200d', '\ue000', '\u0378', '\U000e0000', '\u2028', '\u0085',
    ))
    st.json({"error_cases": cases})
    for index, kwargs in enumerate(cases):
        for kind in ("info", "success", "warning", "error"):
            try:
                getattr(st, kind)("error boundary", **kwargs)
                result = {"index": index, "kind": kind, "returned": True}
            except Exception as error:
                result = {"index": index, "kind": kind, "category": "width" if isinstance(error, StreamlitInvalidWidthError) else "icon", "message": str(error)}
            st.json(result)


if st.query_params.get("case") == "error-contract":
    run_error_contract()
    st.stop()


def run_normalization():
    cases = [
        {'body': '\n    alpha\n      beta\n', 'kwargs': {'title': '\n  Title\n    detail\n'}},
        {'body': '\n    💡 alpha\n      beta\n', 'kwargs': {'width': 240}},
        {'body': '\n    :material/thumb_up: alpha\n      beta\n', 'kwargs': {'title': '\tTitle\n    detail'}},
        {'body': ' \t💡 keep \n', 'kwargs': {'icon': '', 'width': 240}},
        {'body': ' \t💡 keep \n', 'kwargs': {'icon': ' \t\n'}},
        {'body': '  body\r\n    next  ', 'kwargs': {'icon': ' 🧊 ', 'width': 240}},
        {'body': ' \x1cbody\x1f ', 'kwargs': {'icon': '\x1c👩\u200d💻\x1f', 'title': '\x1cTitle\x1f'}},
        {'body': '\u2003alpha\n\u2003beta', 'kwargs': {'width': 240}},
        {'body': '💡\x1cafter', 'kwargs': {}},
        {'body': ' \t\n ', 'kwargs': {'title': ' \t\n ', 'width': 240}},
        {'body': 'plain [x] **bold**', 'kwargs': {'icon': ' :material/warning: '}},
        {'body': '\tfirst\n    second', 'kwargs': {'title': '\n    **Title**\n', 'width': 240}},
    ]
    st.json({"alert_cases": cases})
    results = []
    for index, case in enumerate(cases):
        for kind in ("info", "success", "warning", "error"):
            getattr(st, kind)(case["body"], **case["kwargs"])
            results.append({"index": index, "kind": kind, "returned": True})
    st.json({"results": results})


if st.query_params.get("case") == "normalization":
    run_normalization()
    st.stop()


st.set_page_config(page_title="streamlit-rust status reference", layout="wide")

CASE = st.query_params.get("case", "defaults")

st.title("Status element reference")

if CASE == "defaults":
    st.info("INFO-BODY plain information")
    st.success("SUCCESS-BODY the operation succeeded")
    st.warning("WARNING-BODY something needs attention")
    st.error("ERROR-BODY something failed")

elif CASE == "variants":
    # A leading emoji in the body is extracted and shown as the icon.
    st.info("INFO-EMOJI-BODY \U0001f4a1 this body starts with an emoji")
    # icon="" skips the extraction and shows no icon at all.
    st.info("INFO-NOICON-BODY \U0001f4a1 body keeps its emoji", icon="")
    # A Material Symbols icon by name.
    st.success("SUCCESS-MATERIAL-BODY material icon", icon=":material/thumb_up:")
    # An integer width is a fixed pixel width.
    st.warning("WARNING-WIDTH-BODY fixed width", width=240)
    # A title is rendered above the body.
    st.error("ERROR-TITLE-BODY with a title", title="ERROR-TITLE")

elif CASE == "leading_emoji":
    # A LEADING emoji is extracted, shown as the icon and removed from the body.
    st.info("💡 INFO-LEADING-EMOJI this body starts with an emoji")

elif CASE == "leading_emoji_noicon":
    # icon="" suppresses the extraction: no icon is shown and the emoji stays in
    # the body.
    st.info("💡 INFO-LEADING-NOICON body keeps its emoji", icon="")

elif CASE == "leading_material":
    # A LEADING Material icon shortcode is extracted the same way.
    st.info(":material/thumb_up: INFO-LEADING-MATERIAL body starts with a shortcode")

elif CASE == "invalid_width":
    st.info("INFO-BODY before the invalid call")
    st.info("INFO-BODY invalid width follows", width="bogus")

elif CASE == "invalid_icon":
    st.info("INFO-BODY before the invalid call")
    st.info("INFO-BODY invalid icon follows", icon=123)

elif CASE == "icon_zwj":
    # An explicit ZWJ sequence: woman technologist, three code points.
    st.info("INFO-ICON-ZWJ body", icon="\U0001f469\u200d\U0001f4bb")

elif CASE == "icon_skin_tone":
    # An explicit emoji plus a skin-tone modifier: two code points.
    st.info("INFO-ICON-SKIN body", icon="\U0001f44d\U0001f3fd")

elif CASE == "icon_flag":
    # An explicit regional-indicator flag: two code points.
    st.info("INFO-ICON-FLAG body", icon="\U0001f1e8\U0001f1f3")

elif CASE == "icon_two_emoji":
    # Two independent emoji in one icon string: the counter-example.
    st.info("INFO-ICON-TWO body", icon="\U0001f525\U0001f4a1")

elif CASE == "leading_composite":
    # A LEADING ZWJ sequence: is the whole grapheme extracted, or only the
    # first code point of it?
    st.info("\U0001f469\u200d\U0001f4bb INFO-LEADING-COMPOSITE body starts with a composite emoji")

else:
    st.error(f"unknown case {CASE!r}")
