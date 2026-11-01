"""Emit widget creation-wire parameter variants for the M3 differential."""
import streamlit as st

if st.query_params.get("probe") in ("date-bounds", "date-range"):
    from datetime import date
    range_probe = st.query_params.get("probe") == "date-range"
    phase = st.query_params.get("phase", "load")
    parse = date.fromisoformat
    def wire(value):
        return [v.isoformat() for v in value] if isinstance(value, tuple) else value.isoformat()
    if "date_bound_calls" not in st.session_state:
        st.session_state.date_bound_calls = []
    def changed(source):
        st.session_state.date_bound_calls.append([source, wire(st.session_state.date_bound_single), wire(st.session_state.date_bound_range), st.session_state.date_bound_peer])
    assignments = {"assign": ("2026-02-01", "2026-03-01"), "implicit": ("2050-02-01", "2050-03-01"), "minimum": ("2025-02-01", "2025-03-20"), "maximum": ("2025-04-20", "2025-05-20"), "lower": ("2025-02-28", "2025-03-20")}
    if phase in assignments:
        start, end = assignments[phase]
        st.session_state.date_bound_single = parse(start)
        st.session_state.date_bound_range = (parse(start), parse(end))
    def bounds(range_mode):
        if phase in ("implicit", "implicit-observe"):
            return {}
        low = "2025-02-01" if phase == "minimum" else "2025-03-01" if phase in ("lower", "final") else "2025-01-01"
        high = "2025-04-10" if phase in ("narrow", "observe", "joint", "assign") else ("2025-05-20" if range_mode else "2025-04-20") if phase == "maximum" else "2025-12-31"
        return dict(min_value=parse(low), max_value=parse(high))
    single = st.date_input("Single", value=parse("2025-03-15"), key="date_bound_single", on_change=changed, args=("single",), **bounds(False))
    range_default = (parse("2025-06-10"), parse("2025-06-20")) if range_probe and phase in ("range-defaults", "range-fallback", "range-observe", "range-recover", "range-invalid-final") else (parse("2025-03-15"), parse("2025-03-20"))
    selected_range = st.date_input("Range", value=range_default, key="date_bound_range", on_change=changed, args=("range",), **bounds(True))
    peer = st.checkbox("Peer", key="date_bound_peer", on_change=changed, args=("peer",))
    st.json({"phase": phase, "values": [wire(single), wire(selected_range), peer], "native": [wire(st.session_state.date_bound_single), wire(st.session_state.date_bound_range), st.session_state.date_bound_peer], "calls": st.session_state.date_bound_calls})
elif st.query_params.get("probe") in ("date-single", "date-mode", "date-implicit"):
    from datetime import date
    mode_probe = st.query_params.get("probe") in ("date-mode", "date-implicit")
    implicit_bounds = st.query_params.get("probe") == "date-implicit"
    phase = st.query_params.get("phase", "load")
    if "date_single_calls" not in st.session_state:
        st.session_state.date_single_calls = []
    def wire(value):return [v.isoformat() for v in value] if isinstance(value, tuple) else value.isoformat()
    def changed(source):
        st.session_state.date_single_calls.append([source, wire(st.session_state.date_single_day), st.session_state.date_single_peer])
    default = date(2025, 6, 10) if phase in ("defaults", "fallback", "observe", "recover", "invalid") else date(2025, 3, 15)
    range_mode = mode_probe and phase in ("range", "range-edit", "range-narrow", "range-observe", "range-recover")
    high = date(2025, 3, 31) if mode_probe and phase in ("range-narrow", "range-observe", "range-recover") else date(2025, 3, 15) if mode_probe and phase in ("single-narrow", "single-recover", "single-observe") else date(2025, 12, 31)
    bounds = {} if implicit_bounds else dict(min_value=date(2025, 1, 1), max_value=high)
    day = st.date_input("Day", value=(date(2025, 3, 15), date(2025, 3, 20)) if range_mode else default, key="date_single_day", on_change=changed, args=("day",), **bounds)
    peer = st.checkbox("Peer", key="date_single_peer", on_change=changed, args=("peer",))
    st.json({"phase": phase, "values": [wire(day), peer], "native": [wire(st.session_state.date_single_day), st.session_state.date_single_peer], "calls": st.session_state.date_single_calls})
elif st.query_params.get("probe") in ("datetime-empty", "datetime-bounds"):
    from datetime import datetime
    bounds_probe = st.query_params.get("probe") == "datetime-bounds"
    phase = st.query_params.get("phase", "load")
    if "datetime_empty_calls" not in st.session_state:
        st.session_state.datetime_empty_calls = []
    def clock(value):
        return None if value is None else value.strftime("%Y-%m-%dT%H:%M")
    def changed(source):
        st.session_state.datetime_empty_calls.append([source, clock(st.session_state.datetime_empty_moment), clock(st.session_state.datetime_empty_optional), st.session_state.datetime_empty_peer])
    changed_default = not bounds_probe and phase in ("defaults", "fallback", "bad-first", "seconds", "recover", "observe", "reset")
    value = datetime(2025, 3, 15, 16, 20) if changed_default else datetime(2025, 3, 15, 12, 30)
    if bounds_probe and phase in ("assign", "implicit"):
        assigned = datetime(2025, 3, 15, 19) if phase == "assign" else datetime(2050, 3, 15, 19)
        st.session_state.datetime_empty_moment = assigned
        st.session_state.datetime_empty_optional = assigned
    hour = 15 if bounds_probe and phase in ("reset", "final") else 16 if bounds_probe and phase in ("narrow", "observe", "joint", "assign", "explicit-none", "none-observe", "recover") else 18
    kwargs = {} if bounds_probe and phase in ("implicit", "implicit-observe") else dict(min_value=datetime(2025, 3, 15, 8), max_value=datetime(2025, 3, 15, hour))
    moment = st.datetime_input("Moment", value=None if bounds_probe and phase == "explicit-none" else value, key="datetime_empty_moment", on_change=changed, args=("moment",), **kwargs)
    optional_default = value if changed_default else None
    if bounds_probe and phase in ("implicit", "implicit-observe", "none-observe", "recover", "reset", "final"):
        optional_default = datetime(2025, 3, 15, 12, 30)
    optional = st.datetime_input("Optional", value=optional_default, key="datetime_empty_optional", on_change=changed, args=("optional",), **kwargs)
    peer = st.checkbox("Peer", key="datetime_empty_peer", on_change=changed, args=("peer",))
    report = {"phase": phase, "values": [clock(moment), clock(optional), peer], "calls": st.session_state.datetime_empty_calls}
    if bounds_probe:
        report["native"] = [clock(st.session_state.datetime_empty_moment), clock(st.session_state.datetime_empty_optional), st.session_state.datetime_empty_peer]
    st.json(report)
elif st.query_params.get("probe") == "time-empty":
    from datetime import time
    phase = st.query_params.get("phase", "load")
    if "time_empty_calls" not in st.session_state:
        st.session_state.time_empty_calls = []
    def clock(value, seconds=False):
        return None if value is None else value.strftime("%H:%M:%S" if seconds else "%H:%M")
    def changed(source):
        st.session_state.time_empty_calls.append([source, clock(st.session_state.time_empty_minute), clock(st.session_state.time_empty_seconds, True), st.session_state.time_empty_peer])
    changed_default = phase in ("defaults", "fallback", "leap", "recover", "observe", "reset")
    minute = st.time_input("Minute", value=time(16, 20) if changed_default else time(12, 30), step=900, key="time_empty_minute", on_change=changed, args=("minute",))
    seconds = st.time_input("Seconds", value=time(6, 7, 8) if changed_default else None, step=1, key="time_empty_seconds", on_change=changed, args=("seconds",))
    peer = st.checkbox("Peer", key="time_empty_peer", on_change=changed, args=("peer",))
    st.json({"phase": phase, "values": [clock(minute), clock(seconds, True), peer], "calls": st.session_state.time_empty_calls})
elif st.query_params.get("probe") == "number-empty":
    phase = st.query_params.get("phase", "load")
    if "number_empty_calls" not in st.session_state:
        st.session_state.number_empty_calls = []
    def changed(source):
        st.session_state.number_empty_calls.append([source, st.session_state.number_empty_int, st.session_state.number_empty_float, st.session_state.number_empty_peer])
    changed_default = phase in ("default", "fallback", "limits", "unbounded", "high", "recover", "observe")
    unbounded = phase in ("unbounded", "high")
    integer = st.number_input("Integer", min_value=None if unbounded else 0, max_value=None if unbounded else 10,
                              value=6 if changed_default else 4, key="number_empty_int", on_change=changed, args=("integer",))
    floating = st.number_input("Float", min_value=None if unbounded else -5.0, max_value=None if unbounded else 5.0,
                               value=1.25 if changed_default else 2.5, key="number_empty_float", on_change=changed, args=("float",))
    peer = st.checkbox("Peer", key="number_empty_peer", on_change=changed, args=("peer",))
    st.json({"phase": phase, "values": [integer, floating, peer], "calls": st.session_state.number_empty_calls})
elif st.query_params.get("probe") == "text-empty":
    phase = st.query_params.get("phase", "load")
    if "text_empty_calls" not in st.session_state:
        st.session_state.text_empty_calls = []
    def changed(source):
        st.session_state.text_empty_calls.append([source, st.session_state.text_empty_input, st.session_state.text_empty_area, st.session_state.text_empty_peer])
    default = "Next" if phase in ("default", "fallback", "observe", "recover") else "Base🙂X"
    value = st.text_input("Input", value=default, max_chars=5, key="text_empty_input", on_change=changed, args=("input",))
    area = st.text_area("Area", value=None, max_chars=6, key="text_empty_area", on_change=changed, args=("area",))
    peer = st.checkbox("Peer", key="text_empty_peer", on_change=changed, args=("peer",))
    st.json({"phase": phase, "values": [value, area, peer], "calls": st.session_state.text_empty_calls})
elif st.query_params.get("probe") == "feedback-empty":
    phase = st.query_params.get("phase", "load")
    if "feedback_calls" not in st.session_state:
        st.session_state.feedback_calls = []
    if phase == "assign":
        st.session_state.feedback_primary = None
        st.session_state.feedback_peer = 4
    def changed(source):
        st.session_state.feedback_calls.append([source, st.session_state.feedback_primary, st.session_state.feedback_peer])
    default = 0 if phase in ("default", "fallback", "assign", "observe", "clear-both", "recover") else 2
    primary = st.feedback("stars", default=default, key="feedback_primary", on_change=changed, args=("primary",))
    peer = st.feedback("faces", key="feedback_peer", on_change=changed, args=("peer",))
    st.json({"phase": phase, "values": [primary, peer], "calls": st.session_state.feedback_calls})
elif st.query_params.get("probe") == "feedback-identity":
    phase = st.query_params.get("phase", "load")
    kind = "faces" if phase in ("faces", "faces-edit") else "thumbs" if phase in ("thumbs", "thumbs-edit") else "stars"
    default = 0 if phase in ("zero", "zero-edit", "width", "width-edit") else None
    width = 300 if phase in ("width", "width-edit") else "content"
    values = [st.feedback(kind, default=default, width=width),
              st.feedback(kind, default=default, width=width, key="feedback_choice")]
    st.json({"phase": phase, "values": values, "native": st.session_state.feedback_choice})
elif st.query_params.get("probe") == "group-defaults":
    phase = st.query_params.get("phase", "load")
    choices = [] if phase == "empty" else ["Alpha", "Beta"]
    defaults = [] if phase == "empty" else ["Alpha"] * 3 if phase in ("default", "default-edit") else ["Beta", "Beta", "Alpha", "Beta"]
    values = []
    for position, label in enumerate(["Plain pills", "Keyed pills", "Plain segments", "Keyed segments"]):
        widget = st.pills if position < 2 else st.segmented_control
        values.append(widget(label, choices, default=defaults, key=label if position % 2 else None, selection_mode="multi"))
    st.json({"phase": phase, "values": values})
elif st.query_params.get("probe") == "group-state":
    phase = st.query_params.get("phase", "load")
    labels = ["Single pills", "Multi pills", "Single segments", "Multi segments"]
    for position, label in enumerate(labels):
        if phase == "assign":
            st.session_state[label] = "Gone" if position % 2 == 0 else ["Gone", "Beta", "Beta", "Alpha"]
        elif phase == "clear":
            st.session_state[label] = None if position % 2 == 0 else []
    choices = [] if phase == "empty" else ["Beta"] if phase == "subset" else ["Alpha", "Beta"]
    values = []
    for position, label in enumerate(labels):
        multi = position % 2 == 1
        widget = st.pills if position < 2 else st.segmented_control
        values.append(widget(label, choices, key=label, selection_mode="multi" if multi else "single",
                             default=(["Beta"] if multi else "Beta") if choices else ([] if multi else None)))
    st.json({"phase": phase, "values": values, "native": [st.session_state[label] for label in labels]})
elif st.query_params.get("probe") == "group-policy":
    phase = st.query_params.get("phase", "load")
    mode = "multi" if phase in ("multi", "multi-edit") else "single"
    required = phase in ("required", "required-edit")
    values = [st.pills("Plain pills", ["Alpha", "Beta"], selection_mode=mode, required=required),
              st.pills("Keyed pills", ["Alpha", "Beta"], key="Keyed pills", selection_mode=mode, required=required),
              st.segmented_control("Plain segments", ["Alpha", "Beta"], selection_mode=mode, required=required),
              st.segmented_control("Keyed segments", ["Alpha", "Beta"], key="Keyed segments", selection_mode=mode, required=required)]
    st.json({"phase": phase, "values": values})
elif st.query_params.get("probe") == "group-width":
    phase = st.query_params.get("phase", "load")
    width = 300 if phase in ("width", "width-edit") else "content"
    values = [st.pills("Plain pills", ["Alpha", "Beta"], width=width),
              st.pills("Keyed pills", ["Alpha", "Beta"], key="Keyed pills", width=width),
              st.segmented_control("Plain segments", ["Alpha", "Beta"], selection_mode="multi", width=width),
              st.segmented_control("Keyed segments", ["Alpha", "Beta"], selection_mode="multi", key="Keyed segments", width=width)]
    st.json({"phase": phase, "values": values})
elif st.query_params.get("probe") == "radio-duplicates":
    phase = st.query_params.get("phase", "load")
    if "radio_duplicate_calls" not in st.session_state:
        st.session_state.radio_duplicate_calls = []
    def changed(source):
        st.session_state.radio_duplicate_calls.append([source, st.session_state.choice, st.session_state.peer])
    choice = st.radio("Choice", ["Same", "Same", "Other"], index=1, key="choice", on_change=changed, args=("choice",))
    peer = st.radio("Peer", ["Idle", "Ready"], key="peer", on_change=changed, args=("peer",))
    st.json({"phase": phase, "values": [choice, peer], "calls": st.session_state.radio_duplicate_calls})
elif st.query_params.get("probe") == "format-collisions":
    phase = st.query_params.get("phase", "load")
    if phase == "assign":
        st.session_state["choice"] = 2
        st.session_state["choices"] = [2]
    values = [2, 1, 3] if phase in ("reorder", "reorder-edit", "assign", "observe") else [1, 2, 3]
    formatter = lambda value: "Other" if value == 3 else "Same"
    plain = st.selectbox("Choice", values, format_func=formatter)
    keyed = st.selectbox("Keyed choice", values, format_func=formatter, key="choice")
    multiple = st.multiselect("Choices", values, default=[values[1]], format_func=formatter, key="choices")
    st.json({"phase": phase, "values": [plain, keyed, multiple]})
elif st.query_params.get("probe") == "multi-limits":
    phase = st.query_params.get("phase", "load")
    if phase in ("repair", "repair-final"):
        st.session_state["limited"] = [2]
    elif phase == "partial":
        st.session_state["limited"] = [99, 2, 99]
    cases = []
    if phase == "load":
        cases.extend([
            ("Repeat", [2, 2], None), ("Repeat long", [2, 2, 2, 2], None),
            ("Repeat capped", [2, 2], 2), ("Default over", [1, 2], 1),
            ("Zero", [], 0), ("Outside", [4], None),
        ])
    cases.append(("State", [2], 2))
    for label, defaults, limit in cases:
        try:
            value = st.multiselect(label, [1, 2, 3], default=defaults, max_selections=limit,
                                   key="limited" if label == "State" else None)
            report = {"case": label, "phase": phase, "accepted": True, "value": value}
        except Exception as error:
            report = {"case": label, "phase": phase, "accepted": False,
                      "error_type": type(error).__name__, "error": str(error)}
        st.json(report)
elif st.query_params.get("probe") == "multi-empty":
    phase = st.query_params.get("phase", "load")
    if phase == "assign-partial":
        st.session_state["choice"] = ["Missing", "Beta", "Missing", "Charlie"]
        st.session_state["number"] = [99, 2, 99, 3]
    elif phase == "assign-repeat":
        st.session_state["choice"] = ["Beta", "Beta"]
        st.session_state["number"] = [2, 2]
    labels, numbers = {
        "subset": (["Beta", "Charlie"], [2, 3]),
        "reorder": (["Charlie", "Beta", "Alpha"], [3, 2, 1]),
        "empty": ([], []), "empty-observe": ([], []),
    }.get(phase, (["Alpha", "Beta", "Charlie"], [1, 2, 3]))
    plain = st.multiselect("Choice", labels)
    keyed = st.multiselect("Keyed choice", labels, key="choice")
    number = st.multiselect("Number", numbers, key="number")
    st.json({"phase": phase, "values": [plain, keyed, number]})
elif st.query_params.get("probe") == "select-empty":
    phase = st.query_params.get("phase", "load")
    if phase == "assign-none":
        st.session_state["choice"] = None
        st.session_state["number"] = None
    elif phase == "assign-missing":
        st.session_state["choice"] = "Missing"
        st.session_state["number"] = 99
    labels = [] if phase.startswith("empty") else ["Alpha", "Beta", "Charlie"]
    numbers = [] if phase.startswith("empty") else [1, 2, 3]
    index = None if phase in ("none", "none-edit", "none-observe", "empty-none") else 0
    plain = st.selectbox("Choice", labels, index=index)
    keyed = st.selectbox("Keyed choice", labels, index=index, key="choice")
    number = st.selectbox("Number", numbers, index=index, key="number")
    st.json({"phase": phase, "values": [plain, keyed, number]})
elif st.query_params.get("probe") == "radio-empty":
    phase = st.query_params.get("phase", "load")
    if phase == "assign-none":
        st.session_state["choice"] = None
    elif phase == "assign-missing":
        st.session_state["choice"] = "Missing"
    labels = [] if phase.startswith("empty") else ["Alpha", "Beta", "Charlie"]
    index = None if phase in ("none", "none-edit", "none-observe", "empty-none") else 0
    values = [st.radio("Choice", labels, index=index), st.radio("Keyed choice", labels, index=index, key="choice")]
    st.json({"phase": phase, "values": values})
elif st.query_params.get("probe") == "radio-identity":
    phase = st.query_params.get("phase", "load")
    options = {}
    if phase in ("width", "width-edit"):
        options["width"] = 320
    if phase in ("horizontal", "horizontal-edit"):
        options["horizontal"] = True
    if phase in ("captions", "captions-edit"):
        options["captions"] = ["First", "Second", "Third"]
    if phase in ("empty", "empty-edit"):
        options["captions"] = []
    values = [st.radio("Choice", ["Alpha", "Beta", "Charlie"], **options),
              st.radio("Keyed choice", ["Alpha", "Beta", "Charlie"], key="choice", **options)]
    st.json({"phase": phase, "values": values})
elif st.query_params.get("probe") in ("select-policy", "select-policy-unkeyed"):
    unkeyed = st.query_params.get("probe") == "select-policy-unkeyed"
    phase = st.query_params.get("phase", "load")
    creation = phase not in ("load", "edit", "restore", "observe")
    limit = (2 if phase in ("mode", "mode-edit", "width") else 3) if creation else None
    options = {"width": 320} if phase == "width" else {}
    placeholder = "Pick one" if phase.startswith(("placeholder", "filter")) else "" if phase.startswith("empty") else " " if phase == "space-placeholder" else None
    selected = st.selectbox("Choice", ["Alpha", "Beta", "Charlie"], key=None if unkeyed else "choice", accept_new_options=creation,
                            placeholder=placeholder, filter_mode="prefix" if phase in ("filter", "filter-edit") else "fuzzy", **options)
    selections = st.multiselect("Choices", ["Alpha", "Beta", "Charlie"], default=["Alpha"], key=None if unkeyed else "choices", max_selections=limit, **options)
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
