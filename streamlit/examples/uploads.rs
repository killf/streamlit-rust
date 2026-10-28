//! Uploaders: one single-file picker and one multiple-file picker. The
//! multiple mode returns UploadedFiles::Multiple; removing one file in the
//! browser keeps the rest, exactly like the reference.
use ::streamlit::*;

fn render(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    st.title("Uploads");
    st.sub_header("Single file");
    match st.file_uploader(FileUploaderOptions::new("Upload one file").key("single-upload"))? {
        UploadedFiles::Single(None) => st.caption("No file selected."),
        UploadedFiles::Single(Some(file)) => {
            st.caption(format!("{} ({} bytes)", file.name(), file.size()));
            st.code(String::from_utf8_lossy(&file.as_bytes()[..file.as_bytes().len().min(60)]).into_owned(), "text");
        }
        UploadedFiles::Multiple(files) => st.caption(format!("Unexpected multiple result: {} files", files.len())),
    }
    st.sub_header("Multiple files");
    match st.file_uploader(FileUploaderOptions::new("Upload files").multiple_files().key("multi-upload"))? {
        UploadedFiles::Multiple(files) => st.code(
            serde_json::json!({
                "count": files.len(),
                "files": files.iter().map(|file| serde_json::json!({
                    "name": file.name(),
                    "size": file.size(),
                    "bytes_head": file.as_bytes().iter().take(8).copied().collect::<Vec<_>>(),
                })).collect::<Vec<_>>(),
            })
            .to_string(),
            "json",
        ),
        UploadedFiles::Single(_) => st.caption("Unexpected single result"),
    }
    st.sub_header("Directory");
    // A Rust extension beyond the pinned Python API (1.66.1 has no directory
    // parameter); the wire flag asks the official frontend for a directory
    // picker. Returned files ride the same Multiple flow.
    match st.file_uploader(FileUploaderOptions::new("Upload a folder").directory().key("dir-upload"))? {
        UploadedFiles::Multiple(files) => st.caption(format!("{} files from the folder", files.len())),
        UploadedFiles::Single(_) => st.caption("Unexpected single result"),
    }
    st.sub_header("Size-limited (1 MiB)");
    match st.file_uploader(FileUploaderOptions::new("Upload one small file").max_upload_size_mb(1).key("limit-upload"))? {
        UploadedFiles::Single(None) => st.caption("No file selected."),
        UploadedFiles::Single(Some(file)) => st.code(
            serde_json::json!({
                "count": 1,
                "files": [{"name": file.name(), "size": file.size()}],
            })
            .to_string(),
            "json",
        ),
        UploadedFiles::Multiple(files) => st.caption(format!("Unexpected multiple result: {} files", files.len())),
    }
    Ok(())
}

#[main(host = "127.0.0.1", port = 8591)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Uploads example error: {error}"));
    }
}
