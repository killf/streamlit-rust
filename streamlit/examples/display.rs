//! Display-container demo: json, status, empty, space and bottom on the
//! measured 1.66.1 wire. Mirrors tests/reference/display_app.py.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) {
    st.json_expanded(serde_json::json!({"a": 1, "b": [true, null]}), true);

    let status = st.status(StatusContainerOptions::new("Working...").expanded(true));
    status.write("step one");
    status.write("step two");
    status.update(Some("Done".into()), Some(StatusState::Complete), Some(false));

    let slot = st.empty();
    slot.write("replaced");

    st.space(3);

    let bottom = st.bottom();
    bottom.write("bottom line");
}

#[main(host = "127.0.0.1", port = 8521)]
async fn main(st: &Streamlit) {
    render(st);
}
