//! Charts demo: native line, area and scatter charts plus one map on the
//! measured 1.66.1 wire. Mirrors tests/reference/charts_app.py so the browser
//! differential compares identical pages.
use ::streamlit::*;
use std::sync::Arc;

use streamlit::data::{DataType, Field, Float64Array, Int64Array, RecordBatch, Schema};

fn int64_batch(columns: &[(&str, Vec<i64>)]) -> anyhow::Result<RecordBatch> {
    let fields: Vec<_> = columns.iter().map(|(name, _)| Field::new(*name, DataType::Int64, true)).collect();
    let arrays = columns.iter().map(|(_, values)| Arc::new(Int64Array::from(values.clone())) as _).collect();
    Ok(RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)?)
}

fn float64_batch(columns: &[(&str, Vec<f64>)]) -> anyhow::Result<RecordBatch> {
    let fields: Vec<_> = columns.iter().map(|(name, _)| Field::new(*name, DataType::Float64, true)).collect();
    let arrays = columns.iter().map(|(_, values)| Arc::new(Float64Array::from(values.clone())) as _).collect();
    Ok(RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)?)
}

fn render(st: &Streamlit) -> anyhow::Result<()> {
    st.line_chart(&int64_batch(&[("value", vec![2, 1, 3])])?)?;
    st.area_chart(&int64_batch(&[("alpha", vec![1, 2, 3]), ("beta", vec![3, 2, 1])])?)?;
    st.scatter_chart(ScatterChartOptions::new(&int64_batch(&[("x", vec![1, 2, 3]), ("y", vec![3, 1, 2])])?, "x", "y"))?;
    st.map(&float64_batch(&[("lat", vec![40.7, 41.0]), ("lon", vec![-74.0, -73.9])])?)?;
    Ok(())
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                if let Err(error) = render(st) {
                    st.write(format!("Example error: {error}"));
                }
            })
        },
        "127.0.0.1".into(),
        8512,
    )
    .start()
    .await
}
