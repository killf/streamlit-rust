use ::streamlit::*;

#[main(host = "127.0.0.1", port = 8543)]
async fn main(st: &Streamlit) {
    st.title("Nested cache replay");

    let data = st.cache_data("nested-data-outer").call(21, |n: i64| {
        st.write("Data outer: before");
        let inner = st.cache_data("nested-data-inner").call(n, |value: i64| {
            st.write("Data inner");
            value * 2
        });
        st.write("Data outer: after");
        inner + 1
    });
    st.write(format!("Data result: {data}"));

    let resource = st.cache_resource("nested-resource-outer").call(21, |n: i64| {
        st.write("Resource outer: before");
        let inner = st.cache_resource("nested-resource-inner").call(n, |value: i64| {
            st.write("Resource inner");
            value * 2
        });
        st.write("Resource outer: after");
        *inner + 1
    });
    st.write(format!("Resource result: {resource}"));

    st.button("Again");
}
