use ::streamlit::*;

#[main]
fn main(st: &Streamlit) {
    st.write("Hello world!").unsafe_allow_html(true);
}
