//! The content-addressed media store and the `/media/{file_id}.{ext}` wire
//! shapes, measured on the Python 1.66.1 reference (see
//! .codex/compatibility.md, Media route): a full GET answers 200 with
//! `accept-ranges: bytes`, and a `bytes=a-b` Range request answers 206 with
//! `content-range: bytes a-b/total`. The file id is the reference's
//! MemoryMediaFileStorage address: a 16-byte BLAKE2b of
//! `"{len}:" + data + mimetype (+ filename)`, with files above 1 MiB hashed
//! as length + head/middle/tail 64 KiB samples.

use blake2::digest::consts::U16;
use blake2::{Blake2b, Digest};
use dashmap::DashMap;
use std::sync::LazyLock;

static FILES: LazyLock<DashMap<String, Vec<u8>>> = LazyLock::new(DashMap::new);

// The reference's measured partial-hash constants: above 1 MiB only the
// length plus head, middle and tail samples are hashed.
const PARTIAL_HASH_THRESHOLD: usize = 1_048_576;
const PARTIAL_HASH_SAMPLE_SIZE: usize = 65_536;

/// The reference's stable file id for stored media.
pub fn file_id(data: &[u8], mime: &str, filename: Option<&str>) -> String {
    let mut hasher = Blake2b::<U16>::new();
    hasher.update(format!("{}:", data.len()).as_bytes());
    if data.len() > PARTIAL_HASH_THRESHOLD {
        hasher.update(&data[..PARTIAL_HASH_SAMPLE_SIZE]);
        let middle = (data.len() - PARTIAL_HASH_SAMPLE_SIZE) / 2;
        hasher.update(&data[middle..middle + PARTIAL_HASH_SAMPLE_SIZE]);
        hasher.update(&data[data.len() - PARTIAL_HASH_SAMPLE_SIZE..]);
    } else {
        hasher.update(data);
    }
    hasher.update(mime.as_bytes());
    if let Some(filename) = filename {
        hasher.update(filename.as_bytes());
    }
    format!("{:x}", hasher.finalize())
}

/// Registers bytes under the reference's content address and returns the id.
pub fn put(data: &[u8], mime: &str) -> String {
    let id = file_id(data, mime, None);
    FILES.entry(id.clone()).or_insert_with(|| data.to_vec());
    id
}

/// The stored bytes of a content address, if this process ever registered it.
pub fn get(id: &str) -> Option<Vec<u8>> {
    FILES.get(id).map(|entry| entry.value().clone())
}

#[cfg(test)]
pub(crate) fn clear() {
    FILES.clear();
}

/// The extension of the measured media content types. The URL extension is
/// how the reference names stored media files.
pub fn extension(mime: &str) -> Option<&'static str> {
    Some(match mime {
        "image/png" => "png",
        "image/jpeg" => "jpg",
        "image/webp" => "webp",
        "image/gif" => "gif",
        "audio/wav" | "audio/x-wav" | "audio/wave" => "wav",
        "audio/mpeg" => "mp3",
        "audio/ogg" => "ogg",
        "audio/flac" => "flac",
        "audio/aac" => "aac",
        "video/mp4" => "mp4",
        "video/webm" => "webm",
        "video/ogg" => "ogv",
        _ => return None,
    })
}

/// A parsed `Range: bytes=...` request. `bytes=a-` (open end) and `bytes=a-b`
/// are the measured forms; anything else is served as a full 200 response.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ByteRange {
    pub start: u64,
    pub end: u64,
}

impl ByteRange {
    pub fn parse(header: &str, total: u64) -> Option<Self> {
        let spec = header.strip_prefix("bytes=")?;
        let (start, end) = spec.split_once('-')?;
        if start.is_empty() {
            // A suffix range (`bytes=-n`) was never measured; serve the
            // full body rather than guessing upstream's shape.
            return None;
        }
        let start: u64 = start.parse().ok()?;
        if start >= total {
            return None;
        }
        let end = match end {
            "" => total - 1,
            text => text.parse::<u64>().ok()?.min(total - 1),
        };
        (start <= end).then_some(Self { start, end })
    }
}

/// A minimal RGBA PNG encoder: stored (uncompressed) deflate blocks in a
/// valid zlib stream, which every browser decodes. The reference encodes
/// with PIL's deflate, so PNG bytes differ per side; pixels do not.
pub fn png_encode(rgba: &RgbaImage) -> Vec<u8> {
    let mut raw = Vec::with_capacity(rgba.height as usize * (1 + rgba.width as usize * 4));
    for row in 0..rgba.height as usize {
        raw.push(0u8); // filter type None
        let offset = row * rgba.width as usize * 4;
        raw.extend_from_slice(&rgba.pixels[offset..offset + rgba.width as usize * 4]);
    }
    let mut out = Vec::with_capacity(raw.len() + 128);
    out.extend_from_slice(b"\x89PNG\r\n\x1a\n");
    let mut ihdr = Vec::with_capacity(13);
    ihdr.extend_from_slice(&rgba.width.to_be_bytes());
    ihdr.extend_from_slice(&rgba.height.to_be_bytes());
    ihdr.extend_from_slice(&[8, 6, 0, 0, 0]); // 8-bit RGBA, deflate, adaptive, no interlace
    chunk(&mut out, b"IHDR", &ihdr);
    chunk(&mut out, b"IDAT", &zlib_stored(&raw));
    chunk(&mut out, b"IEND", &[]);
    out
}

fn chunk(out: &mut Vec<u8>, kind: &[u8; 4], body: &[u8]) {
    out.extend_from_slice(&(body.len() as u32).to_be_bytes());
    let mut crc_input = Vec::with_capacity(4 + body.len());
    crc_input.extend_from_slice(kind);
    crc_input.extend_from_slice(body);
    out.extend_from_slice(kind);
    out.extend_from_slice(body);
    out.extend_from_slice(&crc32(&crc_input).to_be_bytes());
}

fn crc32(data: &[u8]) -> u32 {
    let mut crc = u32::MAX;
    for &byte in data {
        crc ^= byte as u32;
        for _ in 0..8 {
            crc = if crc & 1 != 0 { (crc >> 1) ^ 0xEDB8_8320 } else { crc >> 1 };
        }
    }
    !crc
}

fn zlib_stored(data: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(data.len() + data.len() / 65535 * 5 + 6);
    out.extend_from_slice(&[0x78, 0x01]);
    let mut offset = 0;
    while offset < data.len() {
        let len = (data.len() - offset).min(65535);
        let last = offset + len == data.len();
        out.extend_from_slice(&[u8::from(last), 0x00]);
        out.extend_from_slice(&(len as u16).to_le_bytes());
        out.extend_from_slice(&(!(len as u16)).to_le_bytes());
        out.extend_from_slice(&data[offset..offset + len]);
        offset += len;
    }
    if data.is_empty() {
        out.extend_from_slice(&[1, 0, 0, 0, 0]);
    }
    out.extend_from_slice(&adler32(data).to_be_bytes());
    out
}

fn adler32(data: &[u8]) -> u32 {
    let (mut a, mut b) = (1u32, 0u32);
    for &byte in data {
        a = (a + byte as u32) % 65521;
        b = (b + a) % 65521;
    }
    (b << 16) | a
}

/// In-memory RGBA8 pixels, the measured `st.image` input shape.
#[derive(Debug, Clone)]
pub struct RgbaImage {
    pub width: u32,
    pub height: u32,
    pub pixels: Vec<u8>,
}

impl RgbaImage {
    pub fn new(width: u32, height: u32, pixels: Vec<u8>) -> Self {
        Self { width, height, pixels }
    }

    pub fn valid(&self) -> bool {
        self.width > 0 && self.height > 0 && self.pixels.len() == self.width as usize * self.height as usize * 4
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn put_is_content_addressed_and_get_round_trips() {
        clear();
        let id = put(b"deterministic", "image/png");
        assert_eq!(id.len(), 32);
        assert!(id.chars().all(|c| c.is_ascii_hexdigit()));
        assert_eq!(put(b"deterministic", "image/png"), id);
        assert_ne!(put(b"deterministic", "audio/wav"), id, "the mime is part of the address");
        assert_eq!(get(&id).as_deref(), Some(b"deterministic".as_slice()));
        assert_eq!(get("0".repeat(32).as_str()), None);
        assert_eq!(file_id(b"", "image/png", None), file_id(b"", "image/png", None),);
        assert_ne!(file_id(b"", "image/png", None), file_id(b"", "image/png", Some("name.png")));
    }

    #[test]
    fn the_file_id_matches_the_reference_blake2b_address() {
        // The reference's address is BLAKE2b-128 over "{len}:<bytes><mimetype>"
        // (plus a filename when one is given); these vectors come from the
        // pinned 1.66.1 implementation, and the runtime media regression
        // additionally pins the full fixture WAV's exact measured URL.
        assert_eq!(file_id(b"hello world", "image/png", None), "711f0cba1e3108dbe04e81c18464a64c");
        assert_eq!(file_id(b"", "audio/wav", None), "97f81d2d1f3da9445303cc7cbc74f550");
    }

    #[test]
    fn byte_ranges_follow_the_measured_forms() {
        assert_eq!(ByteRange::parse("bytes=0-", 22094), Some(ByteRange { start: 0, end: 22093 }));
        assert_eq!(ByteRange::parse("bytes=10-20", 100), Some(ByteRange { start: 10, end: 20 }));
        assert_eq!(ByteRange::parse("bytes=90-500", 100), Some(ByteRange { start: 90, end: 99 }));
        assert_eq!(ByteRange::parse("bytes=100-", 100), None);
        assert_eq!(ByteRange::parse("bytes=5-2", 100), None);
        assert_eq!(ByteRange::parse("bytes=-500", 100), None);
        assert_eq!(ByteRange::parse("items=0-", 100), None);
    }

    #[test]
    fn png_bytes_carry_the_signature_and_decode_dimensions() {
        let mut pixels = Vec::new();
        for index in 0..64u32 {
            let channel = (4u32.wrapping_mul(index) % 256) as u8;
            pixels.extend_from_slice(&[channel, channel, channel, 255]);
        }
        let png = png_encode(&RgbaImage::new(8, 8, pixels));
        assert!(png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert_eq!(&png[12..16], b"IHDR");
        assert_eq!(u32::from_be_bytes(png[16..20].try_into().unwrap()), 8);
        assert_eq!(u32::from_be_bytes(png[20..24].try_into().unwrap()), 8);
        assert!(png.windows(4).any(|window| window == b"IDAT"));
        assert!(png.windows(4).any(|window| window == b"IEND"));
    }
}
