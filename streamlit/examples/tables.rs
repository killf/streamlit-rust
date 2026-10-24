use std::sync::Arc;
use streamlit::data::{ArrayRef, Float64Array, Int64Array, LargeStringArray, RecordBatch, to_ipc_stream};
use streamlit::{BarChartOptions, DataApi, DataframeOptions, Streamlit, StreamlitApi, StreamlitServer, TableBorder, TableOptions};

fn sales(revision: i64) -> Result<RecordBatch, streamlit::data::DataError> {
    let change = revision as f64;
    Ok(RecordBatch::try_from_iter(vec![
        ("group_key", Arc::new(LargeStringArray::from(vec!["Books", "Games", "Music", "Toys"])) as ArrayRef),
        ("row_count", Arc::new(Int64Array::from(vec![3, 3, 3, 3])) as ArrayRef),
        ("total_amount", Arc::new(Float64Array::from(vec![245.75 + change, 409.48 + change, 139.0 + change, 104.49 + change])) as ArrayRef),
        ("avg_amount", Arc::new(Float64Array::from(vec![81.92 + change / 3.0, 136.49 + change / 3.0, 46.33 + change / 3.0, 34.83 + change / 3.0])) as ArrayRef),
    ])?)
}

fn native_page(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    st.title("Native table and bar chart");
    let state = st.session_state();
    let revision = state.get::<i64>("revision")?.unwrap_or(0) + i64::from(st.button("Update data"));
    state.set("revision", revision)?;
    let table = RecordBatch::try_from_iter(vec![
        ("group.name", Arc::new(LargeStringArray::from(vec![Some("图书"), Some("Café"), Some("**Music**"), None])) as ArrayRef),
        ("amount[0]", Arc::new(Int64Array::from(vec![Some(12 + revision), None, Some(-3), Some(0)])) as ArrayRef),
        ("path\\label", Arc::new(LargeStringArray::from(vec![Some("普通"), Some("naïve"), None, Some("fin")])) as ArrayRef),
    ])?;
    st.table(&table)?;
    st.table(TableOptions::new(&table).border(TableBorder::Horizontal).hide_index(false).width(480).height(220).alt("UTF8 table"))?;
    let numeric = RecordBatch::try_from_iter(vec![
        ("sales", Arc::new(Int64Array::from(vec![12 + revision, 24, -3, 0])) as ArrayRef),
        ("cost", Arc::new(Float64Array::from(vec![Some(4.0), Some(8.0 + revision as f64), None, Some(2.0)])) as ArrayRef),
    ])?;
    st.bar_chart(&numeric)?;
    let named = RecordBatch::try_from_iter(vec![
        ("group.name", Arc::new(LargeStringArray::from(vec!["图书", "Café", "Music", "Toys"])) as ArrayRef),
        ("amount[0]", Arc::new(Float64Array::from(vec![Some(12.0 + revision as f64), Some(24.0), Some(-3.0), None])) as ArrayRef),
    ])?;
    st.bar_chart(BarChartOptions::native(&named).x("group.name").y("amount[0]").horizontal(true).sort(false).height(260))?;
    st.write(format!("Data revision: {revision}"));
    Ok(())
}

fn page(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    if std::env::args().any(|arg| arg == "--native") {
        return native_page(st);
    }
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
    let args = std::env::args().collect::<Vec<_>>();
    let port = match args.iter().position(|arg| arg == "--port") {
        Some(index) => args.get(index + 1).ok_or("--port requires a number")?.parse()?,
        None => 8503,
    };
    StreamlitServer::new(|st| Box::pin(async move { page(st).expect("the example uses valid typed data") }), "127.0.0.1".into(), port).start().await?;
    Ok(())
}
