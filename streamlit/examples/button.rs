use ::streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    st.title("Streamlit Rust button");
    let triggered = st.button("Pulse");
    st.write(if triggered { "Pulse received" } else { "Ready" });
}
