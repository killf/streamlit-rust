extern crate core;

use ::streamlit::*;

#[main]
fn main(st: &Streamlit) {
    st.title("Container and Columns Test");

    st.write("This is a test outside any container");

    // let [col1, col2] = st.columns();

    if let [col1, col2] = st.columns(2).as_slice() {
        println!("1111")
    }
}
