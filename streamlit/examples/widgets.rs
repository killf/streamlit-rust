use ::streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    st.title("Streamlit Rust input widgets");
    let changed = |st: &Streamlit| {
        let state = st.session_state();
        let count = state.get::<u64>("changes").unwrap().unwrap_or(0);
        state.set("changes", count + 1).unwrap();
    };
    let group = st.selectbox(SelectboxOptions::new("Group by", ["category", "region", "channel"]).key("group_by").on_change(changed)).unwrap();
    let amount = st.slider(SliderOptions::new("Minimum amount", 0_i64).max(200).step(10).key("min_amount").on_change(changed)).unwrap();
    let unknown = st.checkbox(CheckboxOptions::new("Include unknown region").value(true).key("include_unknown").on_change(changed)).unwrap();
    let ratio = st.slider(SliderOptions::new("Ratio", 0.25_f64).step(0.05).key("ratio").on_change(changed)).unwrap();
    let amount_range = st.slider(SliderOptions::new("Amount range", (20_i64, 80_i64)).max(200).step(10).key("amount_range").on_change(changed)).unwrap();
    let ratio_range = st.slider(SliderOptions::new("Ratio range", [0.2_f64, 0.8_f64]).step(0.1).key("ratio_range").on_change(changed)).unwrap();
    st.write(format!("Group by: {}", group.unwrap_or("none")));
    st.write(format!("Minimum amount: {amount}"));
    st.write(format!("Include unknown region: {unknown}"));
    st.write(format!("Ratio: {ratio:.2}"));
    st.write(format!("Amount range: {}..{}", amount_range.0, amount_range.1));
    st.write(format!("Ratio range: {:.2}..{:.2}", ratio_range[0], ratio_range[1]));
    st.write(format!("Changes: {}", st.session_state().get::<u64>("changes").unwrap().unwrap_or(0)));
    // This is a values/callback demo. A data view is not implemented here.
    st.button(ButtonOptions::new("Disabled button").disabled(true));
    st.button("Rerun");
}
