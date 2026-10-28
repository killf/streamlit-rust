//! Widget creation-parameter edges — the frozen widget-params reference's
//! calls: the number-input float path with bounds, radio index=None and
//! horizontal+captions, text_area max_chars/placeholder/height, and
//! multiselect max_selections.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) -> Result<(), WidgetError> {
    st.title("Widget parameter edges");
    st.number_input(("Float free", 1.5_f64))?;
    st.number_input(NumberInputOptions::<f64>::new("Float bounded", 2.5).min(0.25).max(9.75).step(0.25))?;
    st.number_input(NumberInputOptions::<i64>::new("Int bounded", 4).min(2).max(8).step(2.0))?;
    st.radio(RadioOptions::new("Plain", ["a", "b"]).index(None).key("r1"))?;
    st.radio(RadioOptions::new("Horizontal", ["x", "y"]).horizontal(true).captions(["first", "second"]).key("r2"))?;
    st.text_area(TextAreaOptions::new("Bounded", "hello").max_chars(10).placeholder("type here").height(200).key("t1"))?;
    st.multiselect(MultiselectOptions::new("Capped", ["p", "q", "r"]).max_selections(2).key("m1"))?;
    Ok(())
}

#[main(host = "127.0.0.1", port = 8599)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Widget params error: {error}"));
    }
}
