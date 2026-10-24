use std::sync::Arc;
use streamlit::data::{ArrayRef, Float64Array, Int64Array, LargeStringArray, RecordBatch, to_ipc_stream};
use streamlit::{BarChartOptions, DataApi, DataframeOptions, Streamlit, StreamlitApi, StreamlitServer};

fn sales(revision: i64) -> Result<RecordBatch, streamlit::data::DataError> {
    let change = revision as f64;
    Ok(RecordBatch::try_from_iter(vec![
        ("group_key", Arc::new(LargeStringArray::from(vec!["Books", "Games", "Music", "Toys"])) as ArrayRef),
        ("row_count", Arc::new(Int64Array::from(vec![3, 3, 3, 3])) as ArrayRef),
        ("total_amount", Arc::new(Float64Array::from(vec![245.75 + change, 409.48 + change, 139.0 + change, 104.49 + change])) as ArrayRef),
        ("avg_amount", Arc::new(Float64Array::from(vec![81.92 + change / 3.0, 136.49 + change / 3.0, 46.33 + change / 3.0, 34.83 + change / 3.0])) as ArrayRef),
    ])?)
}

fn page(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    st.title("Native Rust columnar data");
    let state = st.session_state();
    let revision = state.get::<i64>("revision")?.unwrap_or(0) + i64::from(st.button("Update data"));
    state.set("revision", revision)?;
    let data = sales(revision)?;
    st.dataframe(DataframeOptions::new(&data).hide_index(true).column_order(["group_key", "row_count", "total_amount", "avg_amount"]))?;
    st.bar_chart(
        BarChartOptions::new(&data, "group_key", "total_amount")
            .x_order(["Books", "Games", "Music", "Toys"])
            .tooltip("group_key", "group")
            .tooltip("row_count", "rows")
            .tooltip("total_amount", "total")
            .tooltip("avg_amount", "avg")
            .plot_height(260),
    )?;
    st.write(format!("Data revision: {revision}"));
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Also permits a Python/JS decoder to inspect bytes produced by Rust.
    let mut args = std::env::args().skip(1);
    if args.next().as_deref() == Some("--ipc-out") {
        let path = args.next().ok_or("--ipc-out requires a path")?;
        std::fs::write(path, to_ipc_stream(&sales(0)?)?)?;
        return Ok(());
    }
    env_logger::Builder::from_default_env().init();
    StreamlitServer::new(|st| Box::pin(async move { page(st).expect("the example uses valid typed data") }), "127.0.0.1".into(), 8503).start().await?;
    Ok(())
}
