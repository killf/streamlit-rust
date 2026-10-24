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
