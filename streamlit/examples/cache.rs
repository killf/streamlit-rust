//! Cache demo: memoized computation and shared resources on the measured
//! 1.66.1 wire. Mirrors tests/reference/cache_app.py.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) {
    let runs = st.session_state().get::<i64>("runs").ok().flatten().unwrap_or(0) + 1;
    st.session_state().set("runs", runs).expect("valid state write");

    st.write(format!("runs={runs}"));

    let cached = st.cache_data("double").call(21, |n: i64| n * 2);
    st.write(format!("cached={cached}"));

    let other = st.cache_data("double").call(7, |n: i64| n * 2);
    st.write(format!("cached_other={other}"));

    let side = st.cache_data("side").call((), |()| {
        st.write("inside cached fn");
        1
    });
    st.write(format!("side={side}"));

    st.button("Again");

    if runs == 2 {
        st.cache_clear();
        st.write("cleared");
        let again = st.cache_data("double").call(21, |n: i64| n * 2);
        st.write(format!("cached_after_clear={again}"));
    }
}

#[main(host = "127.0.0.1", port = 8516)]
async fn main(st: &Streamlit) {
    render(st);
}
