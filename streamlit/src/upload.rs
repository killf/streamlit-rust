//! Uploaded bytes belong to one session, independently of a render tree.
use futures_util::StreamExt;
use std::collections::HashMap;
use std::fmt;
use std::io::{self, Cursor, Read, Seek, SeekFrom};
use std::sync::Arc;

/// Native transport failures. Error-specific upstream status/body parity is
/// deliberately not implemented until the negative browser probes are captured.
#[derive(Debug, thiserror::Error)]
pub(crate) enum UploadHttpError {
    #[error("upload session is unavailable")]
    SessionUnavailable,
    #[error("multipart upload could not be parsed")]
    Multipart,
    #[error("upload must contain one file")]
    FileCount,
    #[error("upload exceeds the local byte limit")]
    TooLarge,
}
// Use the framework's generic failure response for now, not invented upstream
// 400/403/404/413 mappings. Only the measured successful PUT response is accepted.
impl actix_web::ResponseError for UploadHttpError {}

pub(crate) struct ParsedUpload {
    pub(crate) name: String,
    pub(crate) content_type: Option<String>,
    pub(crate) bytes: Vec<u8>,
}

pub(crate) async fn read_upload(mut payload: actix_multipart::Multipart, max_bytes: usize) -> Result<ParsedUpload, UploadHttpError> {
    let mut result = None;
    while let Some(field) = payload.next().await {
        let mut field = field.map_err(|_| UploadHttpError::Multipart)?;
        let name = field.content_disposition().and_then(|header| header.get_filename()).map(str::to_owned);
        let content_type = field.content_type().map(ToString::to_string);
        let mut bytes = Vec::new();
        while let Some(chunk) = field.next().await {
            let chunk = chunk.map_err(|_| UploadHttpError::Multipart)?;
            if bytes.len().checked_add(chunk.len()).is_none_or(|size| size > max_bytes) {
                return Err(UploadHttpError::TooLarge);
            }
            bytes.extend_from_slice(&chunk);
        }
        if let Some(name) = name {
            if result.is_some() {
                return Err(UploadHttpError::FileCount);
            }
            result = Some(ParsedUpload { name, content_type, bytes });
        }
    }
    result.ok_or(UploadHttpError::FileCount)
}

/// An immutable uploaded file with an independent read cursor.
/// Reading/ seeking changes this handle's position, not the retained bytes.
/// A new handle obtained on a rerun starts at position zero.
#[derive(Clone)]
pub struct UploadedFile {
    id: String,
    name: String,
    content_type: Option<String>,
    cursor: Cursor<Arc<[u8]>>,
}

impl UploadedFile {
    pub fn id(&self) -> &str {
        &self.id
    }
    pub fn name(&self) -> &str {
        &self.name
    }
    /// The MIME type supplied with the upload, if one was provided.
    pub fn content_type(&self) -> Option<&str> {
        self.content_type.as_deref()
    }
    pub fn size(&self) -> u64 {
        self.cursor.get_ref().len() as u64
    }
    /// The original bytes, regardless of the current read position.
    pub fn as_bytes(&self) -> &[u8] {
        self.cursor.get_ref()
    }
    pub fn position(&self) -> u64 {
        self.cursor.position()
    }
}

impl fmt::Debug for UploadedFile {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("UploadedFile")
            .field("id", &self.id)
            .field("name", &self.name)
            .field("content_type", &self.content_type)
            .field("size", &self.size())
            .field("position", &self.position())
            .finish()
    }
}
impl AsRef<[u8]> for UploadedFile {
    fn as_ref(&self) -> &[u8] {
        self.as_bytes()
    }
}
impl Read for UploadedFile {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        self.cursor.read(buf)
    }
}
impl Seek for UploadedFile {
    fn seek(&mut self, position: SeekFrom) -> io::Result<u64> {
        self.cursor.seek(position)
    }
}

struct StoredFile {
    name: String,
    content_type: Option<String>,
    bytes: Arc<[u8]>,
}

/// One instance is owned by one SessionState, never by a process-global map.
#[derive(Default)]
pub(crate) struct UploadStore {
    files: HashMap<String, StoredFile>,
}

impl UploadStore {
    // Transport validation/status semantics belong to the HTTP boundary. This
    // storage primitive makes no assumptions about unobserved error responses.
    pub(crate) fn insert(&mut self, id: String, name: String, content_type: Option<String>, bytes: Vec<u8>) {
        self.files.insert(id, StoredFile { name, content_type, bytes: bytes.into() });
    }

    pub(crate) fn get(&self, id: &str) -> Option<UploadedFile> {
        self.files.get(id).map(|file| UploadedFile {
            id: id.into(),
            name: file.name.clone(),
            content_type: file.content_type.clone(),
            cursor: Cursor::new(file.bytes.clone()),
        })
    }
}

pub(crate) fn file_urls(session_id: &str, request: crate::proto::FileUrLsRequest) -> crate::proto::FileUrLsResponse {
    crate::proto::FileUrLsResponse {
        response_id: request.request_id,
        file_urls: request
            .file_names
            .iter()
            .map(|_| {
                let file_id = uuid::Uuid::new_v4().to_string();
                let url = format!("/_stcore/upload_file/{session_id}/{file_id}");
                crate::proto::FileUrLs {
                    file_id,
                    upload_url: url.clone(),
                    delete_url: url,
                }
            })
            .collect(),
        error_msg: String::new(),
    }
}

/// The mode is explicit in Rust: single has an optional file; multiple and
/// directory modes have a vector, including an empty vector before selection.
#[derive(Debug)]
pub enum UploadedFiles {
    Single(Option<UploadedFile>),
    Multiple(Vec<UploadedFile>),
}

impl UploadedFiles {
    pub fn as_slice(&self) -> &[UploadedFile] {
        match self {
            Self::Single(file) => file.as_slice(),
            Self::Multiple(files) => files.as_slice(),
        }
    }
}

impl crate::SessionState {
    /// Resolve a read-only uploader key into retained native file handles. Each
    /// call starts new read cursors; missing/deleted files are not resurrected.
    pub fn uploaded_files(&self, key: &str) -> serde_json::Result<Vec<UploadedFile>> {
        let ids = self.get::<Vec<String>>(key)?.unwrap_or_default();
        let store = self.uploads.lock();
        Ok(ids.iter().filter_map(|id| store.get(id)).collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bytes_metadata_and_read_cursors_are_preserved() {
        let mut store = UploadStore::default();
        let bytes = include_bytes!("../../tests/fixtures/csv/sales_basic.csv");
        store.insert("id".into(), "sales_basic.csv".into(), Some("text/csv".into()), bytes.to_vec());
        let mut file = store.get("id").unwrap();
        assert_eq!((file.id(), file.name(), file.content_type(), file.size()), ("id", "sales_basic.csv", Some("text/csv"), bytes.len() as u64));
        let mut prefix = [0_u8; 7];
        file.read_exact(&mut prefix).unwrap();
        assert_eq!(&prefix, &bytes[..7]);
        assert_eq!(file.position(), 7);
        assert_eq!(file.as_bytes(), bytes);
        let fresh = store.get("id").unwrap();
        assert_eq!(fresh.position(), 0);
        assert!(Arc::ptr_eq(file.cursor.get_ref(), fresh.cursor.get_ref()));
        file.seek(SeekFrom::End(-3)).unwrap();
        let mut tail = Vec::new();
        file.read_to_end(&mut tail).unwrap();
        assert_eq!(&tail, &bytes[bytes.len() - 3..]);
        assert!(!format!("{file:?}").contains(std::str::from_utf8(&bytes[..7]).unwrap()));
    }

    #[test]
    fn stores_do_not_share_ids_or_overwrite_existing_handles() {
        let mut a = UploadStore::default();
        let mut b = UploadStore::default();
        a.insert("same".into(), "folder/a.csv".into(), None, vec![1, 2]);
        b.insert("same".into(), "b.csv".into(), None, vec![3]);
        let retained = a.get("same").unwrap();
        assert_eq!(retained.name(), "folder/a.csv");
        assert_eq!(b.get("same").unwrap().as_bytes(), &[3]);
        a.insert("same".into(), "empty.csv".into(), None, vec![]);
        assert_eq!(retained.as_bytes(), &[1, 2]);
        assert_eq!(a.get("same").unwrap().size(), 0);
        assert!(a.files.remove("same").is_some());
        assert!(a.files.remove("same").is_none());
        assert!(a.get("same").is_none());
        assert_eq!(retained.as_bytes(), &[1, 2]);
        assert_eq!(b.get("same").unwrap().as_bytes(), &[3]);
    }
}
