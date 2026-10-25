//! Python wire string formats the reference serializes with its defaults:
//! `json.dumps` separators and ASCII escapes, and the `str()` of a bytes
//! object, which names the measured vega datasets.

use blake2::digest::consts::U16;
use blake2::{Blake2b, Digest};
use serde_json::Value;

/// Render one value exactly as `json.dumps(value)` with the defaults the
/// reference uses: `", "`/`": "` separators and ensure_ascii escapes. The
/// crate's serde maps keep insertion order (preserve_order), so the values
/// must be built in the reference's construction order.
pub fn py_dumps(value: &Value) -> String {
    let mut out = String::new();
    write_value(&mut out, value);
    out
}

fn write_value(out: &mut String, value: &Value) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(number) => out.push_str(&number.to_string()),
        Value::String(text) => write_string(out, text),
        Value::Array(items) => {
            out.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    out.push_str(", ");
                }
                write_value(out, item);
            }
            out.push(']');
        }
        Value::Object(map) => {
            out.push('{');
            for (index, (key, item)) in map.iter().enumerate() {
                if index > 0 {
                    out.push_str(", ");
                }
                write_string(out, key);
                out.push_str(": ");
                write_value(out, item);
            }
            out.push('}');
        }
    }
}

/// An object whose key order is the reference's construction order rather
/// than sorted order (the chart specs, the pandas metadata).
pub fn py_dumps_pairs(pairs: &[(&str, Value)]) -> String {
    let mut out = String::from("{");
    for (index, (key, value)) in pairs.iter().enumerate() {
        if index > 0 {
            out.push_str(", ");
        }
        write_string(&mut out, key);
        out.push_str(": ");
        write_value(&mut out, value);
    }
    out.push('}');
    out
}

fn write_string(out: &mut String, text: &str) {
    out.push('"');
    for character in text.chars() {
        match character {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            character if (character as u32) < 0x20 || (character as u32) > 0x7e => {
                out.push_str(&format!("\\u{:04x}", character as u32));
            }
            character => out.push(character),
        }
    }
    out.push('"');
}

/// The `str()` of a Python bytes object: `b'...'` with `\\xHH` escapes.
pub fn py_bytes_repr(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len() + 3);
    out.push_str("b'");
    for &byte in bytes {
        match byte {
            b'\'' => out.push_str("\\'"),
            b'\\' => out.push_str("\\\\"),
            b'\n' => out.push_str("\\n"),
            b'\r' => out.push_str("\\r"),
            b'\t' => out.push_str("\\t"),
            0x20..=0x7e => out.push(byte as char),
            byte => out.push_str(&format!("\\x{byte:02x}")),
        }
    }
    out.push('\'');
    out
}

/// The reference names each chart dataset `calc_hash(str(arrow_bytes))`
/// with the fast hasher pinned in 1.66.1: BLAKE2b with a 16-byte digest.
pub fn dataset_name(ipc: &[u8]) -> String {
    let mut hasher = Blake2b::<U16>::new();
    hasher.update(py_bytes_repr(ipc).as_bytes());
    format!("{:x}", hasher.finalize())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn py_dumps_uses_python_separators_and_escapes() {
        assert_eq!(py_dumps(&serde_json::json!({"a": 1, "b": [true, null]})), r#"{"a": 1, "b": [true, null]}"#);
        assert_eq!(py_dumps(&serde_json::json!("\u{2705}")), r#""\u2705""#);
        assert_eq!(py_dumps(&serde_json::json!(0.7)), "0.7");
        assert_eq!(py_dumps(&serde_json::json!(-74.0)), "-74.0");
    }

    #[test]
    fn py_dumps_pairs_keeps_construction_order() {
        assert_eq!(py_dumps_pairs(&[("layer", serde_json::json!(1)), ("$schema", serde_json::json!(2))]), r#"{"layer": 1, "$schema": 2}"#);
    }

    #[test]
    fn py_bytes_repr_matches_the_python_str_of_bytes() {
        assert_eq!(py_bytes_repr(b"ab'\\\n"), "b'ab\\'\\\\\\n'");
        assert_eq!(py_bytes_repr(&[0x00, 0xff, 0x7f]), "b'\\x00\\xff\\x7f'");
        assert_eq!(py_bytes_repr(b"\""), "b'\"'");
    }
}
