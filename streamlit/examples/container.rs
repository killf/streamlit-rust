// use ::streamlit::*;

// #[main]
// fn main(st: &Streamlit) {
//     st.title("Container and Columns Test");

//     st.write("This is a test outside any container");

//     // Test container functionality
//     let container = st.container();
//     container.write("This is inside a container");
//     container.button("Container Button", Some("container_btn"));

//     // Test columns functionality
//     let [col1, col2] = st.columns();
//     col1.write("Column 1 content");
//     col1.button("Col1 Button", Some("col1_btn"));
//     col2.write("Column 2 content");
//     col2.button("Col2 Button", Some("col2_btn"));
// }