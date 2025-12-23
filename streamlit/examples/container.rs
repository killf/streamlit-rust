extern crate core;

use ::streamlit::*;

#[main]
fn main(st: &Streamlit) {
    st.title("Container and Columns Test");

    st.write("This is a test outside any container");

    if let [col1, col2] = st.columns(2) {
        col1.write("left");
        col2.write("right");
    }

    st.write("This is a test outside any container");
}
