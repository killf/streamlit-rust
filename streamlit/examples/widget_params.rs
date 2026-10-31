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

    // 仅显式探针追加整数边界，保留原有参数示例的默认输出。
    if st.query_params().get("probe").as_deref() == Some("integer-bounds") {
        st.number_input(("Int free", 4_i64))?;
        st.number_input(NumberInputOptions::new("Int min only", 4_i64).min(2))?;
        st.number_input(NumberInputOptions::new("Int max only", 4_i64).max(8))?;
        st.number_input(NumberInputOptions::new("Int zero min", 4_i64).min(0))?;
        st.number_input(NumberInputOptions::new("Int zero max", -4_i64).max(0))?;
        st.number_input(("Int safe high", 9_007_199_254_740_991_i64))?;
        st.number_input(("Int safe low", -9_007_199_254_740_991_i64))?;
    }

    Ok(())
}

#[main(host = "127.0.0.1", port = 8599)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Widget params error: {error}"));
    }
}
