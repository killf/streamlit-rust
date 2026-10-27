//! Navigation demo: st.navigation pages and st.switch_page on the measured
//! 1.66.1 wire. Mirrors tests/reference/navigation_app.py.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render_main(st: &Streamlit) {
    let hits = st.session_state().get::<i64>("hits").ok().flatten().unwrap_or(0) + 1;
    st.session_state().set("hits", hits).expect("valid state write");

    st.write(format!("page=main hits={hits}"));

    if st.button("Switch") {
        st.switch_page("two").expect("registered page");
    }
}

fn render_two(st: &Streamlit) {
    st.write("page=two");
}

#[main(host = "127.0.0.1", port = 8517)]
async fn main(st: &Streamlit) {
    let nav = st.navigation([Page::new("Main", render_main).icon(":material/home:").default(true).url_path("render_main"), Page::new("Two", render_two).url_path("two")]);
    nav.run();
}
