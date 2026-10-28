//! Slider/multiselect parameter edges — the frozen slider-multi-params
//! reference's calls: a datetime slider with an explicit 30-minute step, a
//! date window, and multiselect default selections.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    st.title("Slider multiselect edges");
    let center = chrono::NaiveDateTime::parse_from_str("2024-03-15 12:00", "%Y-%m-%d %H:%M")?;
    let lo = chrono::NaiveDateTime::parse_from_str("2024-03-01 00:00", "%Y-%m-%d %H:%M")?;
    let hi = chrono::NaiveDateTime::parse_from_str("2024-03-31 00:00", "%Y-%m-%d %H:%M")?;
    st.slider(SliderOptions::new("Datetime stepped", center).min(lo).max(hi).step(1_800_000_000.0).key("s1"))?;
    let mid = chrono::NaiveDate::from_ymd_opt(2024, 6, 15).ok_or("bad date")?;
    let dlo = chrono::NaiveDate::from_ymd_opt(2024, 6, 1).ok_or("bad date")?;
    let dhi = chrono::NaiveDate::from_ymd_opt(2024, 6, 30).ok_or("bad date")?;
    st.slider(SliderOptions::new("Date window", mid).min(dlo).max(dhi).key("s2"))?;
    st.multiselect(MultiselectOptions::new("Defaults", ["p", "q", "r"]).default_indices([1, 2]).key("m1"))?;
    Ok(())
}

#[main(host = "127.0.0.1", port = 8603)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Slider/multiselect error: {error}"));
    }
}
