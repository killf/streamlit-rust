"""Emit widget creation-wire parameter variants for the M3 differential."""
import streamlit as st

if st.query_params.get("probe") == "select-policy":
    phase = st.query_params.get("phase", "load")
    creation = phase not in ("load", "edit", "restore", "observe")
    limit = 3 if phase in ("limit", "limit-edit") else 2 if creation else None
    options = {"width": 320} if phase == "width" else {}
    selected = st.selectbox("Choice", ["Alpha", "Beta", "Charlie"], key="choice", accept_new_options=creation, **options)
    selections = st.multiselect("Choices", ["Alpha", "Beta", "Charlie"], default=["Alpha"], key="choices", max_selections=limit, **options)
    st.json({"phase": phase, "values": [selected, selections]})
elif st.query_params.get("probe") == "bool-width":
    phase = st.query_params.get("phase", "load")
    options = {"width": 320} if phase in ("width", "width-edit") else {}
    values = [st.checkbox("Unkeyed check", **options), st.toggle("Unkeyed toggle", **options),
              st.checkbox("Keyed check", key="keyed-check", **options), st.toggle("Keyed toggle", key="keyed-toggle", **options)]
    st.json({"phase": phase, "values": values})
elif st.query_params.get("probe") == "color-unkeyed":
    phase = st.query_params.get("phase", "load")
    implicit = phase in ("load", "edit", "implicit-return", "observe")
    options = {} if implicit else {"value": "#000000"}
    width = {"width-zero": 0, "width-edit": 0, "width-neg": -5, "width-one": 1, "width39": 39,
             "width40": 40, "width41": 41, "width41-edit": 41, "width40-return": 40}.get(phase)
    if width is not None:
        options["width"] = width
    value = st.color_picker("Unkeyed accent", **options)
    st.json({"phase": phase, "value": value})
elif st.query_params.get("probe") == "color":
    phase = st.query_params.get("phase", "load")
    if phase == "defaults":
        reports = []
        for name, value in [
            ("short-upper", "#ABC"), ("short-lower", "#abc"), ("long-mixed", "#aBcDeF"), ("black", "#000000"),
            ("missing-hash", "ABCDEF"), ("short-unprefixed", "abc"), ("alpha", "#12345678"), ("bad-digit", "#12G"),
            ("too-short", "#12"), ("leading-space", " #123"), ("trailing-space", "#123 "), ("lf", "#ABC\n"),
            ("crlf", "#ABC\r\n"), ("double-lf", "#ABC\n\n"), ("empty", ""), ("plain-default", None),
        ]:
            try:
                value = st.color_picker(name, value=value, key=name)
                reports.append({"case": name, "accepted": True, "value": value})
            except Exception as error:
                reports.append({"case": name, "accepted": False, "error_type": type(error).__name__, "error": str(error)})
        for width in (-5, 0, 1, 39, 40, 41):
            name = "width-" + str(width)
            value = st.color_picker(name, "#123456", key=name, width=width)
            reports.append({"case": name, "accepted": True, "value": value})
        st.json(reports)
    else:
        if phase == "assign":
            st.session_state.accent = "#135"
        if phase == "native-invalid":
            st.session_state.accent = "nothex"

        def color_changed():
            st.session_state.setdefault("color_calls", []).append(st.session_state.accent)

        alternate = phase in ("default-change", "changed-invalid", "width", "assign", "native-invalid", "observe", "recover")
        value = st.color_picker("Accent", "#FED" if alternate else "#123456", key="accent", on_change=color_changed,
                                width=-5 if phase == "width" else "content")
        st.json({"phase": phase, "accepted": True, "value": value, "native": st.session_state.accent,
                 "events": st.session_state.get("color_calls", [])})
elif st.query_params.get("probe") == "form-identity":
    if st.query_params.get("ui") == "on":
        phase = st.selectbox("Location", ("root", "form-a", "form-b"), key="identity_location")
    else:
        phase = st.query_params.get("phase", "load")

    def draw_identity():
        number = st.number_input("Number " + phase, value=4, key="number", help=phase)
        note = st.text_input("Note " + phase, value="base", key="note", max_chars=5, help=phase)
        unkeyed = st.number_input("Unkeyed", value=4)
        return number, note, unkeyed

    submitted = None
    if phase.startswith("form-"):
        with st.form("alpha" if phase in ("form-a", "form-a-return") else "beta"):
            number, note, unkeyed = draw_identity()
            submitted = st.form_submit_button("Apply", key="apply")
    else:
        number, note, unkeyed = draw_identity()
    st.json({"phase": phase, "number": number, "note": note, "unkeyed": unkeyed,
             "submitted": submitted, "native": [st.session_state["number"], st.session_state["note"]]})

elif st.query_params.get("probe") == "number-permissive":
    for label, default, low, high, step in (
        ("Int equal", 2, 2, 2, 1), ("Int zero step", 4, None, None, 0),
        ("Int negative step", 4, None, None, -2),
        ("Float equal", 2.5, 2.5, 2.5, 0.25), ("Float zero step", 1.5, None, None, 0.0),
        ("Float negative step", 1.5, None, None, -0.25),
        ("Int inverted", 2, 3, 2, 1), ("Int below", 1, 2, 8, 1), ("Int above", 9, 2, 8, 1),
        ("Float inverted", 2.0, 3.0, 2.0, 0.25),
        ("Float below", 1.0, 2.0, 8.0, 0.25), ("Float above", 9.0, 2.0, 8.0, 0.25),
    ):
        try:
            value = st.number_input(label, value=default, min_value=low, max_value=high, step=step, key=label)
        except Exception:
            st.json({"case": label, "accepted": False})
        else:
            st.json({"case": label, "accepted": True, "value": value, "state": st.session_state[label]})

elif st.query_params.get("probe") == "stop-lifecycle":
    phase = st.query_params.get("phase", "load")

    def changed_lifecycle(key):
        st.session_state["lifecycle_calls"] = st.session_state.get("lifecycle_calls", []) + [{"key": key, "value": st.session_state.get(key)}]

    def lifecycle_report(stage, returns=None):
        st.json({"phase": phase, "stage": stage, "fire": st.session_state.get("fire"),
                 "plain": st.session_state.get("plain"), "bound": st.session_state.get("bound"),
                 "callbacks": st.session_state.get("lifecycle_calls", []), "pairs": list(st.query_params.to_dict().items()),
                 "returns": returns})

    lifecycle_report("before")
    if phase in ("submit", "peek"):
        st.stop()
    if phase in ("load", "resume", "restore"):
        fire = st.button("Fire", key="fire", on_click=changed_lifecycle, args=("fire",))
        plain = st.text_input("Plain", value="base", key="plain", on_change=changed_lifecycle, args=("plain",))
        bound = st.text_input("Bound", value="base", key="bound", bind="query-params", on_change=changed_lifecycle, args=("bound",))
        lifecycle_report("values", {"fire": fire, "plain": plain, "bound": bound})
        if phase == "resume":
            st.stop()

elif st.query_params.get("probe") == "number-unkeyed":
    phase = st.query_params.get("phase", "load")

    def changed_unkeyed():
        st.session_state["unkeyed_calls"] = st.session_state.get("unkeyed_calls", []) + ["changed"]

    low = 0 if phase in ("minzero", "min-edit") else None
    high = 0 if phase in ("maxzero", "negative-edit") else None
    default = -4 if phase in ("maxzero", "negative-edit", "maxnone") else 5 if phase == "default" else 4
    step = 1 if phase in ("explicit-step", "explicit-edit") else 2 if phase == "step2" else None
    callback = "ignore" if phase == "ignore" else None if phase == "none" else changed_unkeyed
    value = st.number_input("Unkeyed", value=default, min_value=low, max_value=high, step=step,
                            width=360 if phase in ("width", "width-edit") else "stretch",
                            help="hint" if phase == "help" else "", disabled=phase == "disabled",
                            label_visibility="hidden" if phase == "hidden" else "visible", on_change=callback)
    st.json({"phase": phase, "value": value, "callbacks": st.session_state.get("unkeyed_calls", [])})
    if st.query_params.get("stop") == "on":
        st.stop()

elif st.query_params.get("probe") == "number-float":
    phase = st.query_params.get("phase", "load")
    if phase == "assign":
        st.session_state["number"] = 8.25

    def changed_float():
        st.session_state["number_calls"] = st.session_state.get("number_calls", []) + [st.session_state["number"]]

    low = 3.0 if phase == "raise-min" else 0.0 if phase not in ("load", "edit") else None
    high = 6.0 if phase == "narrow-max" else 10.0 if phase not in ("load", "edit", "zero-min") else None
    value = st.number_input("Dynamic float", value=5.5 if phase == "default" else 4.25,
                            min_value=low, max_value=high, step=0.5 if phase == "step" else 0.25,
                            key="number", on_change=changed_float, disabled=phase == "disabled")
    st.json({"phase": phase, "value": value, "state": st.session_state["number"],
             "callbacks": st.session_state.get("number_calls", [])})

elif st.query_params.get("probe") == "number-sequence":
    phase = st.query_params.get("phase", "load")
    if phase == "assign":
        st.session_state["number"] = 8

    def changed():
        st.session_state["number_calls"] = st.session_state.get("number_calls", []) + [st.session_state["number"]]

    low = 3 if phase == "raise-min" else 0 if phase != "load" and phase != "edit" else None
    high = 6 if phase == "narrow-max" else 10 if phase not in ("load", "edit", "zero-min") else None
    value = st.number_input("Dynamic", value=5 if phase == "default" else 4, min_value=low, max_value=high,
                            step=2 if phase == "step" else 1, key="number", on_change=changed,
                            disabled=phase == "disabled")
    st.json({"phase": phase, "value": value, "state": st.session_state["number"],
             "callbacks": st.session_state.get("number_calls", [])})

else:
    st.title("Widget parameter edges")

    # number_input: the float path (FLOAT enum, unset format) plus min/max/step.
    st.number_input("Float free", value=1.5)
    st.number_input("Float bounded", min_value=0.25, max_value=9.75, value=2.5, step=0.25)
    st.number_input("Int bounded", min_value=2, max_value=8, value=4, step=2)

    # radio: index=None (no default), horizontal, captions.
    st.radio("Plain", ["a", "b"], index=None, key="r1")
    st.radio("Horizontal", ["x", "y"], horizontal=True, captions=["first", "second"], key="r2")

    # text_area: max_chars, placeholder, height.
    st.text_area("Bounded", value="hello", max_chars=10, placeholder="type here", height=200, key="t1")

    # multiselect: max_selections rides the creation wire.
    st.multiselect("Capped", ["p", "q", "r"], max_selections=2, key="m1")


    # Opt-in boundary probe leaves the original eight-element reference intact.
    if st.query_params.get("probe") == "integer-bounds":
        st.number_input("Int free", value=4)
        st.number_input("Int min only", value=4, min_value=2)
        st.number_input("Int max only", value=4, max_value=8)
        st.number_input("Int zero min", value=4, min_value=0)
        st.number_input("Int zero max", value=-4, max_value=0)
        st.number_input("Int safe high", value=9007199254740991)
        st.number_input("Int safe low", value=-9007199254740991)
