pub fn hash(txt: &str) -> String {
    let md5 = md5::compute(txt.as_bytes());
    format!("{:x}", md5)
}

/// The reference's calc_hash: a 16-byte BLAKE2b digest as hex (the MD5
/// fallback never applies on this platform).
pub fn blake2b16(txt: &str) -> String {
    use blake2::digest::consts::U16;
    use blake2::{Blake2b, Digest};
    let mut hasher = Blake2b::<U16>::new();
    hasher.update(txt.as_bytes());
    format!("{:x}", hasher.finalize())
}
