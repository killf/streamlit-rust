"""Emit date_input/select_slider creation-wire parameter variants."""
import datetime

import streamlit as st

if st.query_params.get("probe") in ("identity", "unkeyed"):
    unkeyed = st.query_params["probe"] == "unkeyed"
    phase = st.query_params.get("phase", "load")
    phases = (("load", "edit", "format", "width", "restore", "edit-bounds", "bounds", "observe") if unkeyed else
              ("load", "edit", "policy", "step", "edit-step", "format", "edit-format", "defaults", "bounds", "restore", "observe"))
    index = phases.index(phase)
    step = 1800 if not unkeyed and 3 <= index <= 8 else 900
    date_format = "DD/MM/YYYY" if not unkeyed and 5 <= index <= 8 else "YYYY/MM/DD"
    defaults = not unkeyed and phase in ("defaults", "bounds")
    date_default = datetime.date(2024, 4, 20) if defaults else datetime.date(2024, 3, 15)
    time_default = datetime.time(10, 0) if defaults else datetime.time(12, 30)
    options = dict(disabled=phase == "policy", label_visibility="hidden" if phase == "policy" else "visible",
                   width=360 if phase == "policy" or (unkeyed and phase == "width") else "stretch", help=None if unkeyed else phase)
    clock = st.time_input("Clock", value=time_default, step=step,
                          format="12h" if (unkeyed and phase == "format") or (not unkeyed and 5 <= index <= 8) else "24h",
                          key=None if unkeyed else "clock", **options)
    moment = st.datetime_input("Moment", value=datetime.datetime.combine(date_default, time_default), step=step,
                              format=date_format, key=None if unkeyed else "moment", **options,
                              min_value=datetime.datetime(2024, 1, 1) if phase == "bounds" else None,
                              max_value=datetime.datetime(2024, 12, 31, 23, 59) if phase == "bounds" else None)
    date = st.date_input("Date", value=date_default, format=date_format, key=None if unkeyed else "date", **options,
                         min_value=datetime.date(2024, 1, 1) if not unkeyed and phase == "bounds" else None,
                         max_value=datetime.date(2024, 12, 31) if not unkeyed and phase == "bounds" else None)

    def iso(value):
        return value.isoformat() if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime) else value.isoformat(timespec="minutes")

    st.json({"phase": phase, "values": [iso(clock), iso(moment), iso(date)],
             "native": [] if unkeyed else [iso(st.session_state[key]) for key in ("clock", "moment", "date")]})
else:
    st.title("Temporal parameter edges")

    # date_input: explicit value, min/max window, a custom display format.
    st.date_input("Bounded", value=datetime.date(2024, 3, 15),
                  min_value=datetime.date(2024, 1, 1), max_value=datetime.date(2024, 12, 31), key="d1")
    st.date_input("Formatted", value=datetime.date(2024, 6, 1), format="DD/MM/YYYY", key="d2")

    # select_slider: a range default (two endpoints) with custom labels.
    st.select_slider("Range", options=["low", "mid", "high"], value=("low", "high"), key="s1")

    # time_input: step rides the creation wire.
    st.time_input("Stepped", value=datetime.time(12, 30), step=900, key="t1")
