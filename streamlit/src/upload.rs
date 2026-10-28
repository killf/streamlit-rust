//! Uploaded bytes belong to one session, independently of a render tree.
use futures_util::StreamExt;
use std::collections::HashMap;
use std::fmt;
use std::io::{self, Cursor, Read, Seek, SeekFrom};
use std::sync::Arc;
use subtle::ConstantTimeEq;

pub(crate) const XSRF_COOKIE: &str = "_streamlit_xsrf";

fn unhex(text: &str) -> Option<Vec<u8>> {
    if !text.len().is_multiple_of(2) {
        return None;
    }
    let (pairs, _) = text.as_bytes().as_chunks::<2>();

    pairs.iter().map(|pair| Some((pair[0] as char).to_digit(16)? as u8 * 16 + (pair[1] as char).to_digit(16)? as u8)).collect()
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn timestamp_decimal(text: &str) -> Option<String> {
    // The actual upstream accepts surrounding whitespace and digit separators
    // (" 1", "1_0"), including integers beyond fixed-width machine ranges.
    let text = text.trim();
    let negative = text.starts_with('-');
    let digits = text.strip_prefix(['+', '-']).unwrap_or(text).as_bytes();
    if digits.is_empty() {
        return None;
    }
    for (i, &byte) in digits.iter().enumerate() {
        if byte.is_ascii_digit() {
            continue;
        }
        if byte != b'_' || i == 0 || i + 1 == digits.len() || !digits[i - 1].is_ascii_digit() || !digits[i + 1].is_ascii_digit() {
            return None;
        }
    }
    let canonical: String = digits.iter().filter(|&&byte| byte != b'_').map(|&byte| byte as char).collect();
    let canonical = canonical.trim_start_matches('0');
    Some(if canonical.is_empty() {
        "0".into()
    } else if negative {
        format!("-{canonical}")
    } else {
        canonical.into()
    })
}

fn xsrf_cookie_value(req: &actix_web::HttpRequest) -> Option<String> {
    // Actix's single-cookie accessor chooses the first occurrence. The actual
    // reference chooses the last, across semicolon pairs AND multiple headers.
    let cookies = req.cookies().ok()?;
    cookies.iter().rev().find(|cookie| cookie.name() == XSRF_COOKIE).map(|cookie| cookie.value().to_owned())
}

/// Decode the observed legacy hex / masked-v2 wire forms, not an identity or
/// signed cookie. Timestamp is syntax, not a locally invented expiry policy.
fn xsrf_payload(value: &str) -> Option<Vec<u8>> {
    if !value.contains('|') {
        return unhex(value).filter(|bytes| !bytes.is_empty());
    }
    let parts: Vec<_> = value.split('|').collect();
    if parts.len() != 4 || parts[0] != "2" {
        return None;
    }
    timestamp_decimal(parts[3])?;
    let mask = unhex(parts[1])?;
    if mask.len() != 4 {
        return None;
    }
    let mut payload = unhex(parts[2])?;
    if payload.is_empty() {
        return None;
    }
    for (i, byte) in payload.iter_mut().enumerate() {
        *byte ^= mask[i % 4];
    }
    Some(payload)
}

pub(crate) fn check_xsrf(req: &actix_web::HttpRequest) -> Result<(), UploadHttpError> {
    let cookie = xsrf_cookie_value(req).ok_or(UploadHttpError::Xsrf)?;
    let header = req.headers().get("x-xsrftoken").and_then(|value| value.to_str().ok()).ok_or(UploadHttpError::Xsrf)?;
    let cookie = xsrf_payload(&cookie).ok_or(UploadHttpError::Xsrf)?;
    let header = xsrf_payload(header).ok_or(UploadHttpError::Xsrf)?;
    // Length is public wire syntax; equality work is independent of contents.
    if bool::from(cookie.ct_eq(&header)) { Ok(()) } else { Err(UploadHttpError::Xsrf) }
}

pub(crate) fn health_cookie(req: &actix_web::HttpRequest) -> actix_web::cookie::Cookie<'static> {
    // v4 uses the OS RNG via the existing uuid/getrandom path: 122 random bits
    // plus UUID version/variant bits, not a full-entropy 128-bit secret/signature.
    let existing = xsrf_cookie_value(req);
    let token = existing.as_deref().and_then(xsrf_payload).unwrap_or_else(|| uuid::Uuid::new_v4().as_bytes().to_vec());
    let random_mask = uuid::Uuid::new_v4();
    let mask = &random_mask.as_bytes()[..4];
    let masked: Vec<u8> = token.iter().enumerate().map(|(i, byte)| byte ^ mask[i % 4]).collect();
    let timestamp = existing
        .as_deref()
        .filter(|value| xsrf_payload(value).is_some())
        .and_then(|value| value.split('|').nth(3))
        .and_then(timestamp_decimal)
        .unwrap_or_else(|| std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_secs().to_string());
    let value = format!("2|{}|{}|{timestamp}", hex(mask), hex(&masked));
    actix_web::cookie::Cookie::build(XSRF_COOKIE, value).path("/").same_site(actix_web::cookie::SameSite::Lax).finish()
}

/// Native transport failures. Only independently observed upstream error
/// responses are mapped; multipart/limit status parity remains unverified.
#[derive(Debug, thiserror::Error)]
pub(crate) enum UploadHttpError {
    #[error("XSRF token missing or invalid")]
    Xsrf,
    #[error("Invalid session_id. This is likely caused by a multi-replica deployment without sticky sessions / session affinity. See https://docs.streamlit.io/develop/concepts/architecture/architecture#websockets-and-session-management")]
    SessionUnavailable,
    #[error("multipart upload could not be parsed")]
    Multipart,
    #[error("upload must contain one file")]
    FileCount,
    #[error("upload exceeds the local byte limit")]
    TooLarge,
}
impl actix_web::ResponseError for UploadHttpError {
    fn status_code(&self) -> actix_web::http::StatusCode {
        match self {
            Self::Xsrf => actix_web::http::StatusCode::FORBIDDEN,
            // Official 8601: valid XSRF plus unknown-session PUT.
            Self::SessionUnavailable => actix_web::http::StatusCode::BAD_REQUEST,
            // Measured on the pinned 1.66.1 server (server.maxUploadSize):
            // an oversized PUT is rejected with 413 before any storage.
            Self::TooLarge => actix_web::http::StatusCode::PAYLOAD_TOO_LARGE,
            _ => actix_web::http::StatusCode::INTERNAL_SERVER_ERROR,
        }
    }

    fn error_response(&self) -> actix_web::HttpResponse {
        actix_web::HttpResponse::build(self.status_code()).content_type("text/plain; charset=utf-8").body(self.to_string())
    }
}

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

    /// Release the store's ownership. Already returned handles keep their own
    /// immutable bytes; future lookups cannot recover a removed file.
    pub(crate) fn remove(&mut self, id: &str) -> bool {
        self.files.remove(id).is_some()
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
    fn xsrf_decodes_the_official_masked_and_short_legacy_matrix() {
        use actix_web::test::TestRequest;
        // Independently measured 8601 token matrix, not Streamlit implementation.
        let issued = "2|f65b844a|be87e919eefd1a85bb0153c1f211778e|1792824916";
        let legacy = "48dc6d5318a69ecf4d5ad78b044af3c4";
        let remasked = "2|12345678|5ae83b2b0a92c8b75f6e81f3167ea5bc|1792824916";
        for (cookie, header) in [
            (issued, issued),
            (issued, remasked),
            (issued, legacy),
            (legacy, issued),
            (legacy, legacy),
            ("48dc", "48dc"),
            (issued, "2|12345678|5ae83b2b0a92c8b75f6e81f3167ea5bc|1"),
        ] {
            let req = TestRequest::default().insert_header(("Cookie", format!("{XSRF_COOKIE}={cookie}"))).insert_header(("X-Xsrftoken", header)).to_http_request();
            assert!(check_xsrf(&req).is_ok());
        }
        for (cookie, header) in [
            (issued, "2|12345678|5be83b2b0a92c8b75f6e81f3167ea5bc|1792824916"),
            ("invalid-token", "invalid-token"),
            (issued, "2%7Cf65b844a%7Cbe87e919eefd1a85bb0153c1f211778e%7C1792824916"),
        ] {
            let req = TestRequest::default().insert_header(("Cookie", format!("{XSRF_COOKIE}={cookie}"))).insert_header(("X-Xsrftoken", header)).to_http_request();
            assert!(matches!(check_xsrf(&req), Err(UploadHttpError::Xsrf)));
        }
        for req in [
            TestRequest::default().to_http_request(),
            TestRequest::default().insert_header(("X-Xsrftoken", issued)).to_http_request(),
            TestRequest::default().insert_header(("Cookie", format!("{XSRF_COOKIE}={issued}"))).to_http_request(),
        ] {
            assert!(check_xsrf(&req).is_err());
        }
        // Additional native parser robustness, not exhaustive upstream parity.
        for value in ["", "0", "zz", "3|12345678|0011|1", "2||00|1", "2|12345678|xx|1", "2|12345678|0011|x", "2|12345678|0011|1|extra"] {
            assert!(xsrf_payload(value).is_none());
        }
    }

    #[test]
    fn fresh_health_cookie_has_observed_flags_and_independent_random_values() {
        use actix_web::test::TestRequest;
        let req = TestRequest::get().to_http_request();
        let a = health_cookie(&req);
        let b = health_cookie(&req);
        assert_eq!((a.name(), a.path(), a.same_site()), (XSRF_COOKIE, Some("/"), Some(actix_web::cookie::SameSite::Lax)));
        assert_eq!((a.secure(), a.http_only(), a.domain(), a.max_age(), a.expires()), (None, None, None, None, None));
        let parts: Vec<_> = a.value().split('|').collect();
        assert_eq!(parts.len(), 4);
        assert_eq!((parts[0], parts[1].len(), parts[2].len()), ("2", 8, 32));
        assert_ne!(xsrf_payload(a.value()), xsrf_payload(b.value()));
        let original_payload = xsrf_payload(a.value());
        let original_value = a.value().to_owned();
        let existing = TestRequest::get().cookie(a).to_http_request();
        let refreshed = health_cookie(&existing);
        assert_ne!(refreshed.value(), original_value);
        assert_eq!(xsrf_payload(refreshed.value()), original_payload);
    }

    #[test]
    fn health_upgrades_legacy_and_preserves_v2_payload_and_timestamp() {
        use actix_web::test::TestRequest;
        for value in ["48dc", "2|12345678|0011|1", "2|12345678|0011| 1", "2|12345678|0011|1_0"] {
            let req = TestRequest::get().insert_header(("Cookie", format!("{XSRF_COOKIE}={value}"))).to_http_request();
            let updated = health_cookie(&req);
            assert!(updated.value().starts_with("2|"));
            assert_ne!(updated.value(), value);
            assert_eq!(xsrf_payload(updated.value()), xsrf_payload(value));
            if let Some(stamp) = value.split('|').nth(3) {
                let expected_stamp = timestamp_decimal(stamp);
                assert!(expected_stamp.is_some(), "fixture timestamp must be accepted: {stamp:?}");
                assert_eq!(updated.value().split('|').nth(3), expected_stamp.as_deref());
            }
        }
        for accepted in [" 1", "1_0", "+1", "-1", "01", "0", "9999999999999999999999999999999999999999"] {
            assert!(xsrf_payload(&format!("2|12345678|0011|{accepted}")).is_some());
        }
        for rejected in ["", "--1", "1.0", "x"] {
            assert!(xsrf_payload(&format!("2|12345678|0011|{rejected}")).is_none());
        }
    }

    #[actix_web::test]
    async fn upload_byte_limit_accepts_exact_boundary_and_rejects_next_byte() -> anyhow::Result<()> {
        use actix_web::http::header::{HeaderMap, HeaderName, HeaderValue};
        for (bytes, limit, accepted) in [(b"abc".as_slice(), 3, true), (b"abcd".as_slice(), 3, false), (b"".as_slice(), 0, true)] {
            let mut headers = HeaderMap::new();
            headers.insert(HeaderName::from_static("content-type"), HeaderValue::from_static("multipart/form-data; boundary=boundary"));
            let mut body = b"--boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.csv\"\r\n\r\n".to_vec();
            body.extend_from_slice(bytes);
            body.extend_from_slice(b"\r\n--boundary--\r\n");
            let stream = futures_util::stream::iter(vec![Ok::<_, actix_web::error::PayloadError>(bytes::Bytes::from(body))]);
            let result = read_upload(actix_multipart::Multipart::new(&headers, stream), limit).await;
            if accepted {
                assert_eq!(result?.bytes, bytes);
            } else {
                assert!(matches!(result, Err(UploadHttpError::TooLarge)));
            }
        }

        Ok(())
    }

    #[test]
    fn unknown_session_matches_observed_error_status_and_body() {
        use actix_web::ResponseError;
        let error = UploadHttpError::SessionUnavailable;
        assert_eq!(error.status_code(), actix_web::http::StatusCode::BAD_REQUEST);
        assert_eq!(
            error.to_string(),
            "Invalid session_id. This is likely caused by a multi-replica deployment without sticky sessions / session affinity. See https://docs.streamlit.io/develop/concepts/architecture/architecture#websockets-and-session-management"
        );
    }

    #[test]
    fn bytes_metadata_and_read_cursors_are_preserved() -> anyhow::Result<()> {
        let mut store = UploadStore::default();
        let bytes = include_bytes!("../../tests/fixtures/csv/sales_basic.csv");
        store.insert("id".into(), "sales_basic.csv".into(), Some("text/csv".into()), bytes.to_vec());
        let mut file = store.get("id").ok_or_else(|| anyhow::anyhow!("inserted sales CSV must be available as id"))?;
        assert_eq!((file.id(), file.name(), file.content_type(), file.size()), ("id", "sales_basic.csv", Some("text/csv"), bytes.len() as u64));
        let mut prefix = [0_u8; 7];
        file.read_exact(&mut prefix)?;
        assert_eq!(&prefix, &bytes[..7]);
        assert_eq!(file.position(), 7);
        assert_eq!(file.as_bytes(), bytes);
        let fresh = store.get("id").ok_or_else(|| anyhow::anyhow!("reading sales CSV must retain its store entry"))?;
        assert_eq!(fresh.position(), 0);
        assert!(Arc::ptr_eq(file.cursor.get_ref(), fresh.cursor.get_ref()));
        file.seek(SeekFrom::End(-3))?;
        let mut tail = Vec::new();
        file.read_to_end(&mut tail)?;
        assert_eq!(&tail, &bytes[bytes.len() - 3..]);
        assert!(!format!("{file:?}").contains(std::str::from_utf8(&bytes[..7])?));

        Ok(())
    }

    #[test]
    fn stores_do_not_share_ids_or_overwrite_existing_handles() -> anyhow::Result<()> {
        let mut a = UploadStore::default();
        let mut b = UploadStore::default();
        a.insert("same".into(), "folder/a.csv".into(), None, vec![1, 2]);
        b.insert("same".into(), "b.csv".into(), None, vec![3]);
        let retained = a.get("same").ok_or_else(|| anyhow::anyhow!("first store must contain folder/a.csv"))?;
        assert_eq!(retained.name(), "folder/a.csv");
        assert_eq!(b.get("same").ok_or_else(|| anyhow::anyhow!("second store must contain b.csv"))?.as_bytes(), &[3]);
        a.insert("same".into(), "empty.csv".into(), None, vec![]);
        assert_eq!(retained.as_bytes(), &[1, 2]);
        assert_eq!(a.get("same").ok_or_else(|| anyhow::anyhow!("replacement empty CSV must remain in first store"))?.size(), 0);
        assert!(a.remove("same"));
        assert!(!a.remove("same"));
        assert!(a.get("same").is_none());
        assert_eq!(retained.as_bytes(), &[1, 2]);
        assert_eq!(b.get("same").ok_or_else(|| anyhow::anyhow!("removing first store entry must retain second store b.csv"))?.as_bytes(), &[3]);

        Ok(())
    }
}
