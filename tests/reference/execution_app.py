"""Execution-semantics reference fixture: st.rerun and st.stop wire behavior.

Driven by the mode selector: ``plain`` renders everything; ``rerun`` performs
exactly one guarded st.rerun on entry (the line after it is unreachable);
``stop`` renders the prefix, calls st.stop and must not render the epilogue.
Session counters make each server-side run observable in the DOM and wire.
"""
import time

import streamlit as st

if "runs" not in st.session_state:
    st.session_state.runs = 0
    st.session_state.reruns = 0
st.session_state.runs += 1

mode = st.selectbox("mode", ["plain", "rerun", "rerun-slow", "stop"])

st.markdown(f"mode={mode} runs={st.session_state.runs} reruns={st.session_state.reruns}")

if mode == "rerun" and st.session_state.reruns == 0:
    st.session_state.reruns = 1
    st.rerun()
    st.markdown("unreachable-after-rerun")

if mode == "rerun-slow" and st.session_state.reruns < 2:
    st.session_state.reruns += 1
    st.markdown("slow-before-rerun")
    time.sleep(1.5)
    st.rerun()

if mode == "stop":
    st.markdown("before-stop")
    st.stop()

st.markdown("epilogue")
