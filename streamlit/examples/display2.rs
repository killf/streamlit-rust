//! Presentation-leftover demo: the logo message, the help viewer, a
//! skeleton placeholder and st.pdf's measured no-component path. Mirrors
//! tests/reference/display2_app.py.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) {
    st.logo(LogoOptions::new("🏠").small());

    // The fields mirror what Python's st.help(len) reports.
    st.help(HelpOptions::new("Return the number of items in a container.", "builtin_function_or_method").name("len").value("builtins.len(obj, /)"));

    let _placeholder = st.skeleton(SkeletonOptions::new().height(100));

    st.pdf("https://example.com/sample.pdf");
}

#[main(host = "127.0.0.1", port = 8525)]
async fn main(st: &Streamlit) {
    render(st);
}
