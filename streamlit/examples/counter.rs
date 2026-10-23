use ::streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    st.title("Streamlit Rust session counter");
    let state = st.session_state();
    let mut pulses = state.get::<u64>("pulses").expect("counter must be an integer").unwrap_or(0);
    if st.button("Pulse") {
        pulses += 1;
    }
    state.set("pulses", pulses).expect("counter is JSON-serializable");
    let runs = state.get::<u64>("runs").expect("runs must be an integer").unwrap_or(0) + 1;
    state.set("runs", runs).expect("runs is JSON-serializable");
    st.write(format!("Pulses: {pulses}"));
    st.write(format!("Script runs: {runs}"));
}
