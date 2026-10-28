//! st.columns parameter variants — the frozen columns-params reference's
//! calls: the default baseline, gap sizes, borders, vertical alignments, and
//! a weighted spec with everything combined.
use ::streamlit::*;
use streamlit::StreamlitApi;
use streamlit::{ColumnsOptions, Gap, VerticalAlignment};

fn render(st: &Streamlit) {
    st.title("Columns parameters");
    let cols = st.columns(2);
    cols[0].write("default left");
    cols[1].write("default right");
    let medium = st.columns(ColumnsOptions::new(vec![1.0, 1.0]).gap(Gap::Medium));
    medium[0].write("medium");
    let large = st.columns(ColumnsOptions::new(vec![1.0, 1.0, 1.0]).gap(Gap::Large));
    large[0].write("large");
    let bordered = st.columns(ColumnsOptions::new(vec![1.0, 1.0]).border(true));
    bordered[0].write("bordered");
    bordered[1].write("bordered");
    let centered = st.columns(ColumnsOptions::new(vec![1.0, 1.0]).vertical_alignment(VerticalAlignment::Center));
    centered[0].write("centered");
    let bottom = st.columns(ColumnsOptions::new(vec![1.0, 1.0]).vertical_alignment(VerticalAlignment::Bottom));
    bottom[0].write("bottom");
    let weighted = st.columns(ColumnsOptions::new(vec![3.0, 1.0]).gap(Gap::Large).border(true).vertical_alignment(VerticalAlignment::Center));
    weighted[0].write("weighted");
    weighted[1].write("weighted");
}

#[main(host = "127.0.0.1", port = 8595)]
async fn main(st: &Streamlit) {
    render(st);
}
