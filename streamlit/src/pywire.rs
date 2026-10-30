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

/// The compact variant some reference call sites use:
/// `json.dumps(..., separators=(",", ":"))` (the echarts spec).
pub fn py_dumps_compact(value: &Value) -> String {
    let mut out = String::new();
    write_value_compact(&mut out, value);
    out
}

fn write_value_compact(out: &mut String, value: &Value) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(number) => write_number(out, number),
        Value::String(text) => write_string(out, text),
        Value::Array(items) => {
            out.push('[');
            for item in items {
                write_value_compact(out, item);
                out.push(',');
            }
            if out.ends_with(',') {
                out.pop();
            }
            out.push(']');
        }
        Value::Object(map) => {
            out.push('{');
            for (key, item) in map {
                write_string(out, key);
                out.push(':');
                write_value_compact(out, item);
                out.push(',');
            }
            if out.ends_with(',') {
                out.pop();
            }
            out.push('}');
        }
    }
}

fn write_value(out: &mut String, value: &Value) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(number) => write_number(out, number),
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

fn write_number(out: &mut String, number: &serde_json::Number) {
    let text = number.to_string();
    if !number.is_f64() {
        out.push_str(&text);
        return;
    }

    // 1. Python 指数带显式正号，绝对值小于十时补齐两位。
    if let Some((mantissa, exponent)) = text.split_once('e') {
        out.push_str(mantissa);
        out.push('e');
        let digits = if let Some(digits) = exponent.strip_prefix('-') {
            out.push('-');
            digits
        } else {
            out.push('+');
            exponent.strip_prefix('+').unwrap_or(exponent)
        };
        if digits.len() == 1 {
            out.push('0');
        }
        out.push_str(digits);
        return;
    }

    // 2. Python 从 1e-5 开始用指数，serde 的最短小数形式仍可能是 0.00001。
    let unsigned = text.strip_prefix('-').unwrap_or(&text);
    if let Some(fraction) = unsigned.strip_prefix("0.")
        && let Some(first) = fraction.bytes().position(|digit| digit != b'0').filter(|first| *first >= 4)
    {
        if text.starts_with('-') {
            out.push('-');
        }
        out.push(char::from(fraction.as_bytes()[first]));
        let rest = &fraction[first + 1..];
        if !rest.is_empty() {
            out.push('.');
            out.push_str(rest);
        }
        out.push_str(&format!("e-{:02}", first + 1));
        return;
    }
    out.push_str(&text);
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
                // JSON 的 ASCII 转义按 UTF-16 码元输出，非 BMP 字符必须使用代理对。
                let mut units = [0; 2];
                for unit in character.encode_utf16(&mut units) {
                    out.push_str(&format!("\\u{unit:04x}"));
                }
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
    fn finite_json_numbers_follow_python_exponent_formatting() -> Result<(), serde_json::Error> {
        let cases = [
            ("0.0", "0.0"),
            ("-0.0", "-0.0"),
            ("1.0", "1.0"),
            ("0.0001", "0.0001"),
            ("0.00001", "1e-05"),
            ("-0.0000123", "-1.23e-05"),
            ("1e-6", "1e-06"),
            ("-1e-7", "-1e-07"),
            ("1e15", "1000000000000000.0"),
            ("1e16", "1e+16"),
            ("-1e20", "-1e+20"),
            ("1.23e-7", "1.23e-07"),
            ("5e-324", "5e-324"),
            ("2.2250738585072014e-308", "2.2250738585072014e-308"),
            ("1.7976931348623157e308", "1.7976931348623157e+308"),
        ];
        for (input, expected) in cases {
            let value: Value = serde_json::from_str(input)?;
            assert_eq!(py_dumps(&value), expected, "input {input}");
            assert_eq!(py_dumps_compact(&value), expected, "compact input {input}");
            assert_eq!(py_dumps_pairs(&[("value", value)]), format!("{{\"value\": {expected}}}"), "pairs input {input}");
        }
        let integers: Value = serde_json::from_str("[0, -1, 10000000000000000, 18446744073709551615]")?;
        assert_eq!(py_dumps(&integers), "[0, -1, 10000000000000000, 18446744073709551615]");
        Ok(())
    }

    #[test]
    fn non_bmp_json_values_and_keys_use_surrogate_pairs() -> Result<(), serde_json::Error> {
        let text = "🤖👩‍💻🛠️\u{10000}\u{10ffff}";
        let expected = r#""\ud83e\udd16\ud83d\udc69\u200d\ud83d\udcbb\ud83d\udee0\ufe0f\ud800\udc00\udbff\udfff""#;
        let encoded = py_dumps(&Value::String(text.into()));
        assert_eq!(encoded, expected, "Python json.dumps ensure_ascii reference");
        assert_eq!(serde_json::from_str::<String>(&encoded)?, text);

        let value = serde_json::json!({"🤖": [text]});
        let compact = py_dumps_compact(&value);
        assert_eq!(compact, format!(r#"{{"\ud83e\udd16":[{expected}]}}"#));
        assert_eq!(serde_json::from_str::<Value>(&compact)?, value);
        let pairs = py_dumps_pairs(&[("🤖", Value::String(text.into()))]);
        assert_eq!(pairs, format!(r#"{{"\ud83e\udd16": {expected}}}"#));
        assert_eq!(serde_json::from_str::<Value>(&pairs)?, serde_json::json!({"🤖": text}));
        Ok(())
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
