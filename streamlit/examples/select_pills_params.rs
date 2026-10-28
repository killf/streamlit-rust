//! selectbox/checkbox/pills parameter edges — the frozen select-pills-params
//! reference's calls: placeholder/help/disabled selectboxes, a chatty disabled
//! checkbox, and multi pills with defaults and help.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    st.title("Select pills edges");
    st.selectbox(SelectboxOptions::new("Placeholder", ["a", "b"]).index(None).placeholder("pick one").help("sb help").key("s1"))?;
    st.selectbox(SelectboxOptions::new("Disabled", ["a", "b"]).disabled(true).key("s2"))?;
    st.checkbox(CheckboxOptions::new("Chatty").value(true).help("cb help").disabled(true).key("c1"))?;
    st.pills(ButtonGroupOptions::new("Multi", ["x", "y", "z"]).selection_mode(SelectionMode::Multi).default(["x", "z"]).help("p help").key("p1"))?;
    Ok(())
}

#[main(host = "127.0.0.1", port = 8608)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Select/pills error: {error}"));
    }
}
