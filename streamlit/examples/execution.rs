//! Execution semantics: `st.rerun()` and `st.stop()`.
//!
//! Run with `cargo run --example execution --locked` (port 8501) and switch
//! the selector: `rerun` performs exactly one guarded rerun — the aborted run
//! disappears, the counters advance by one and the next run starts without a
//! browser request; `stop` keeps the prefix and drops the epilogue. Mirrors
//! the reference fixture `tests/reference/execution_app.py`.
use ::streamlit::*;

#[streamlit::main]
async fn main(st: &Streamlit) {
    let runs: i64 = st.session_state().get("runs").ok().flatten().unwrap_or(0) + 1;
    let reruns: i64 = st.session_state().get("reruns").ok().flatten().unwrap_or(0);
    st.session_state().set("runs", runs).unwrap();

    let mode = st.selectbox(("mode", ["plain", "rerun", "stop"])).ok().flatten().unwrap_or("plain");

    st.markdown(format!("mode={mode} runs={runs} reruns={reruns}"));

    if mode == "rerun" && reruns == 0 {
        st.session_state().set("reruns", 1_i64).unwrap();
        st.rerun();
        st.markdown("unreachable-after-rerun");
    }

    if mode == "stop" {
        st.markdown("before-stop");
        st.stop();
    }

    st.markdown("epilogue");
}
