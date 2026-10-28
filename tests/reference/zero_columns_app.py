"""Public zero-column protocol cases and a separate interactive UI fixture."""
import argparse
import base64
import json
from pathlib import Path
import traceback

import pandas as pd
import pyarrow as pa
import streamlit as st


def schema_details(schema):
    return {
        "fields": [{"name": field.name, "type": str(field.type), "nullable": field.nullable} for field in schema],
        "metadata": [{"key_base64": base64.b64encode(key).decode(), "value_base64": base64.b64encode(value).decode()} for key, value in (schema.metadata or {}).items()],
    }


def describe(value):
    result = {"type": type(value).__module__ + "." + type(value).__qualname__}
    if isinstance(value, pa.Table):
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, value.schema) as writer:
            writer.write_table(value)
        result.update(num_rows=value.num_rows, num_columns=value.num_columns, column_names=value.column_names,
                      rows=value.to_pylist(), schema=schema_details(value.schema), serialized_ipc_base64=base64.b64encode(sink.getvalue().to_pybytes()).decode())
    elif isinstance(value, pd.DataFrame):
        result.update(num_rows=len(value), num_columns=len(value.columns), column_names=value.columns.tolist(),
                      index=value.index.tolist(), index_type=type(value.index).__name__, index_name=value.index.name,
                      rows=value.to_dict(orient="records"), dtypes={str(name): str(dtype) for name, dtype in value.dtypes.items()})
    return result


def ui():
    st.title("Zero-column data")
    two = st.checkbox("Two rows", value=False, key="zero-two")
    data = pa.table({"drop": [1, 2] if two else []}).drop(["drop"])
    st.caption(f"zero-input rows={data.num_rows} columns={data.num_columns}")
    st.caption("zero-case=dataframe")
    st.dataframe(data)
    st.caption("zero-case=editor-disabled-fixed")
    disabled = st.data_editor(data, disabled=True, num_rows="fixed", key="zero-disabled")
    st.caption(f"zero-return=disabled rows={disabled.num_rows} columns={disabled.num_columns}")
    st.caption("zero-case=editor-fixed")
    enabled = st.data_editor(data, num_rows="fixed", key="zero-editor")
    st.caption(f"zero-return=enabled rows={enabled.num_rows} columns={enabled.num_columns}")
    st.caption("zero-case=table-index")
    st.table(data, hide_index=False)
    st.button("Ordinary rerun", key="zero-rerun")


def protocol(path):
    inputs = json.loads(path.read_text(encoding="utf-8"))
    for case in inputs["cases"]:
        if case["input"] == "arrow-zero0":
            data = pa.table({})
        elif case["input"] == "arrow-zero2":
            data = pa.table({"drop": [1, 2]}).drop(["drop"])
        elif case["input"] == "pandas-index2":
            data = pd.DataFrame(index=range(2))
        else:
            raise ValueError(f"unknown input: {case['input']}")
        report = {"label": case["label"], "input": case["input"], "operation": case["operation"], "input_before": describe(data)}
        st.caption("zero-case=" + case["label"])
        try:
            if case["operation"] == "dataframe":
                returned = st.dataframe(data)
            elif case["operation"] == "table-index":
                returned = st.table(data, hide_index=False)
            else:
                returned = st.data_editor(data, key=case["label"], **inputs["operations"][case["operation"]])
            report.update(outcome="returned", returned=describe(returned))
        except Exception as error:
            report.update(outcome="exception", exception_type=type(error).__module__ + "." + type(error).__name__, exception_message=str(error), traceback=traceback.format_exc())
        report["input_after"] = describe(data)
        report["caller_input_unchanged"] = report["input_before"] == report["input_after"]
        st.code(json.dumps(report, ensure_ascii=False, sort_keys=True), language="json")


parser = argparse.ArgumentParser()
parser.add_argument("--ui", action="store_true")
parser.add_argument("--inputs", type=Path, default=Path(__file__).parent / "reference-browser/zero-columns/primary/inputs.json")
args = parser.parse_args()
if args.ui:
    ui()
else:
    protocol(args.inputs)
