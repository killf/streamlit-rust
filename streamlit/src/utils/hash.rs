pub fn hash(txt: &str) -> String {
    let md5 = md5::compute(txt.as_bytes());
    format!("{:x}", md5)
}
