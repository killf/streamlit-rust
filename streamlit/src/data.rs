//! Native columnar data and Arrow IPC streaming. No Python runtime is involved.
pub use arrow_array::{Array, ArrayRef, BooleanArray, Float64Array, Int64Array, LargeStringArray, RecordBatch, StringArray, record_batch};
use arrow_ipc::{reader::StreamReader, writer::StreamWriter};
pub use arrow_schema::{DataType, Field, Schema};

#[derive(Debug, thiserror::Error)]
pub enum DataError {
    #[error(transparent)]
    Arrow(#[from] arrow_schema::ArrowError),
    #[error("invalid data view option: {0}")]
    InvalidOption(String),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
}

/// Encode one batch as an uncompressed IPC stream, preserving schema metadata.
pub fn to_ipc_stream(batch: &RecordBatch) -> Result<Vec<u8>, DataError> {
    let mut bytes = Vec::new();
    {
        let mut writer = StreamWriter::try_new(&mut bytes, batch.schema_ref())?;
        writer.write(batch)?;
        writer.finish()?;
    }
    Ok(bytes)
}

/// Decode all batches in an IPC stream. IPC files are a different format.
pub fn from_ipc_stream(bytes: &[u8]) -> Result<Vec<RecordBatch>, DataError> {
    StreamReader::try_new(bytes, None)?.collect::<Result<Vec<_>, _>>().map_err(Into::into)
}

/// Build a batch from a vega-lite inline `values` list (objects with the
/// same keys, like pandas.DataFrame(records)): keys in first-appearance
/// order, int64 for all-integer columns, utf8 otherwise.
pub fn values_to_batch(values: &[serde_json::Value]) -> Result<RecordBatch, DataError> {
    use std::sync::Arc;

    let mut names: Vec<String> = Vec::new();
    for value in values {
        if let Some(fields) = value.as_object() {
            for key in fields.keys() {
                if !names.iter().any(|name| name == key) {
                    names.push(key.clone());
                }
            }
        }
    }
    let mut fields = Vec::with_capacity(names.len());
    let mut arrays: Vec<ArrayRef> = Vec::with_capacity(names.len());
    for name in &names {
        let column: Vec<&serde_json::Value> = values.iter().map(|row| &row[name]).collect();
        let all_integers = column.iter().all(|value| value.is_i64() || value.is_u64());
        if all_integers && !column.is_empty() {
            let numbers: Vec<i64> = column.iter().map(|value| value.as_i64().unwrap_or_default()).collect();
            fields.push(Field::new(name, DataType::Int64, true));
            arrays.push(Arc::new(Int64Array::from(numbers)));
        } else {
            let texts: Vec<String> = column
                .iter()
                .map(|value| match value {
                    serde_json::Value::String(text) => text.clone(),
                    serde_json::Value::Null => String::new(),
                    other => other.to_string(),
                })
                .collect();
            fields.push(Field::new(name, DataType::Utf8, true));
            arrays.push(Arc::new(StringArray::from(texts)));
        }
    }
    RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays).map_err(Into::into)
}
