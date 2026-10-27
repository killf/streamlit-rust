"""Synthetic pinned dataframe-selection reference; output reports observed state."""

import json

import pandas as pd
import streamlit as st


case = st.query_params.get("case", "ignore")
allowed = {"ignore", "multi", "single-combo", "multi-combo", "required", "multi-shrink"}
if case not in allowed:
    raise ValueError("unknown synthetic selection case")
key = "selection-" + case
st.session_state.setdefault("events", [])
st.session_state["run"] = st.session_state.get("run", 0) + 1
run = st.session_state["run"]
st.session_state["events"].append({"kind": "main", "run": run})
st.session_state.setdefault("version", 1)
st.session_state.setdefault("visible", True)
before = st.session_state.get(key)
trigger = None

st.caption("Synthetic case: " + case)
controls = st.columns(3)
if controls[0].button("Probe"):
    trigger = "Probe"
if controls[1].button("Replace data"):
    st.session_state["version"] = 3 - st.session_state["version"]
    trigger = "Replace data"
if controls[2].button("Toggle visible"):
    st.session_state["visible"] = not st.session_state["visible"]
    trigger = "Toggle visible"

if case == "single-combo":
    program = st.columns(3)
    for column, label, selection in zip(program, ("Program rows", "Program columns", "Program cells"),
                                         ({"rows": [0]}, {"columns": ["id"]}, {"cells": [[0, "qty"]]}), strict=True):
        if column.button(label):
            st.session_state[key] = {"selection": selection}
            trigger = label

version = st.session_state["version"]
data = pd.DataFrame({"id": ["rC", "rA", "rB"], "qty": [30, 10, 20] if version == 1 else [300, 100, 200],
                     "label": ["C", "A", "B"] if version == 1 else ["CX", "AX", "BX"]})
if case == "multi-shrink" and version == 2:
    data = data.iloc[:1].copy()


def selection_changed():
    st.session_state["events"].append({"kind": "callback", "run_seen": st.session_state["run"],
                                       "state": json.loads(json.dumps(st.session_state.get(key)))})


options = {"key": key, "hide_index": True, "height": 190, "width": 700, "row_height": 32,
           "column_config": {name: st.column_config.Column(width=160) for name in data.columns}}
if case in {"multi", "multi-shrink"}:
    options["on_select"] = "rerun"
elif case == "single-combo":
    options.update(on_select=selection_changed, selection_mode=["single-row", "single-column", "single-cell"],
                   selection_default={"selection": {"rows": [1], "columns": ["qty"], "cells": [[2, "label"]]}})
elif case == "multi-combo":
    options.update(on_select="rerun", selection_mode=["multi-row", "multi-column", "multi-cell"])
elif case == "required":
    options.update(on_select="rerun", selection_mode="single-row-required")

event = st.dataframe(data, **options) if st.session_state["visible"] else None
output = {"case": case, "run": run, "version": version, "visible": st.session_state["visible"], "trigger": trigger,
          "input_rows": data.to_dict(orient="records"), "before": before,
          "returned_type": type(event).__name__, "returned": event if case != "ignore" else None,
          "key_present": key in st.session_state, "keyed": st.session_state.get(key),
          "events": st.session_state["events"][-18:]}
st.code(json.dumps(output, sort_keys=True), language="json")
