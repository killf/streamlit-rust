"""Emit st.json/st.badge/st.feedback creation-wire parameter variants."""
import streamlit as st


def run_strings():
    strings = ['{"a":1}', ' \n { "a": 1 } \t', '[1, true, null]', '"a string"', '42', 'true', 'null',
               '""', '', 'not json', '{"unfinished":', '{"emoji":"🤖","中文":"值"}', 'NaN', 'Infinity', '{"a":1}\n{"b":2}']
    controls = [{"nested": '{"a": 1}', "🤖": "工具", "control": "\n\t"}, ["raw string", "🤖", {"a": 1}], None, False, 42]
    sample = st.query_params.get("sample")
    if sample is not None:
        index = int(sample)
        st.title(f"JSON string {index}")
        st.json(strings[index], expanded=st.query_params.get("collapsed") != "true")
        return
    st.json({"string_cases": strings, "controls": controls})
    for text in strings:
        st.json(text)
        st.json(text, expanded=False)
    for value in controls:
        st.json(value)


def run_numbers():
    texts = ['0.0', '-0.0', '1.0', '1e-4', '1e-5', '1e-6', '1e-7', '1e15', '1e16', '1e20', '1e21', '1.23e-7', '1.2345678901234567', '5e-324', '2.2250738585072014e-308', '1.7976931348623157e308', 'NaN', 'Infinity', '-Infinity']
    st.json({"number_cases": texts})
    for text in texts:
        value = float(text)
        st.json(value)
        st.json([value])


def run_serialization():
    repr_calls = {"type_error": 0, "value_error": 0}

    class StableRepr:
        def __repr__(self):
            return "StableRepr(value=7)"

    class TypeFailure:
        def __repr__(self):
            repr_calls["type_error"] += 1
            raise TypeError("synthetic repr type failure")

    class ValueFailure:
        def __repr__(self):
            repr_calls["value_error"] += 1
            raise ValueError("synthetic repr value failure")

    circular_list = []
    circular_list.append(circular_list)
    circular_dict = {}
    circular_dict["self"] = circular_dict
    cases = [
        ("primitive-values", {"plain": 1, "false": False, "nil": None}),
        ("primitive-keys", {None: "nil", False: "no", 2: "two"}),
        ("float-keys", {1.5: "fraction", -0.0: "negative-zero", 1e16: "large", 1e-5: "small"}),
        ("nonfinite-keys", {float("nan"): "nan", float("inf"): "positive", float("-inf"): "negative"}),
        ("key-text-collisions", {1: "integer", "1": "string", None: "none", "null": "string-null"}),
        ("tuple-key", {("x",): "drop", "kept": 1}),
        ("nested-tuple-key", {"outer": {("x",): "drop", "kept": 1}}),
        ("complex-key", {1 + 2j: "drop", "kept": 2}),
        ("all-invalid-keys", {(1,): "drop", 1 + 2j: "drop"}),
        ("set-value", {"set": {1, 2}}),
        ("bytes-value", {"bytes": b"hi\n\xff"}),
        ("stable-object", {"object": StableRepr()}),
        ("repr-type-error", {"value": TypeFailure()}),
        ("repr-value-error", {"value": ValueFailure()}),
        ("circular-list", circular_list),
        ("circular-dict", circular_dict),
        ("recovery", {"recovered": True}),
    ]
    st.json({"serialization_cases": [label for label, _ in cases]})
    for index, (label, value) in enumerate(cases):
        try:
            st.json(value)
        except Exception as error:
            st.json({"index": index, "label": label, "ok": False, "error_type": type(error).__name__, "message": str(error)})
        else:
            st.json({"index": index, "label": label, "ok": True})
    st.json({"repr_calls": repr_calls})


def run_expansion():
    cases = [
        {"label": "default", "kwargs": {}},
        {"label": "false", "kwargs": {"expanded": False}},
        {"label": "depth-0", "kwargs": {"expanded": 0}},
        {"label": "depth-1", "kwargs": {"expanded": 1}},
        {"label": "depth-2-width-240", "kwargs": {"expanded": 2, "width": 240}},
        {"label": "depth-3-width-480", "kwargs": {"expanded": 3, "width": 480}},
        {"label": "depth-negative", "kwargs": {"expanded": -1}},
        {"label": "depth-max", "kwargs": {"expanded": 2147483647}},
        {"label": "depth-overflow", "kwargs": {"expanded": 2147483648}},
        {"label": "depth-float", "kwargs": {"expanded": 1.5}},
        {"label": "depth-text", "kwargs": {"expanded": "2"}},
        {"label": "width-zero", "kwargs": {"expanded": 2, "width": 0}},
        {"label": "width-negative", "kwargs": {"expanded": 2, "width": -1}},
        {"label": "width-content", "kwargs": {"expanded": 2, "width": "content"}},
        {"label": "width-invalid", "kwargs": {"expanded": 2, "width": "bad"}},
        {"label": "width-float", "kwargs": {"expanded": 2, "width": 240.5}},
        {"label": "width-bool", "kwargs": {"expanded": 2, "width": True}},
        {"label": "width-none", "kwargs": {"expanded": 2, "width": None}},
    ]
    st.json({"expansion_cases": cases})
    for index, case in enumerate(cases):
        try:
            st.json({"nested": {"items": [1, 2]}}, **case["kwargs"])
        except Exception as error:
            st.json({"index": index, "label": case["label"], "ok": False, "error_type": type(error).__name__, "message": str(error)})
        else:
            st.json({"index": index, "label": case["label"], "ok": True})


if st.query_params.get("case") == "serialization":
    run_serialization()
    st.stop()

if st.query_params.get("case") == "numbers":
    run_numbers()
    st.stop()

if st.query_params.get("case") == "expansion":
    run_expansion()
    st.stop()

if st.query_params.get("case") == "strings":
    run_strings()
    st.stop()

st.title("Json badge feedback edges")

# st.json: explicit expanded/collapsed values. The separate depth= keyword
# is not accepted; integer expanded depth has its own reference scenario.
st.json({"outer": {"inner": [1, 2]}}, expanded=True)
st.json({"deep": {"a": {"b": {"c": 1}}}}, expanded=False)

# st.badge: the icon/color variants ride the message.
st.badge("New", icon=":material/rocket_launch:", color="green")
st.badge("Plain")

# st.feedback: the positional kind plus disabled riding the wire.
st.feedback("thumbs", key="f1", disabled=True)
