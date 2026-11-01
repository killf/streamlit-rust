//! Session-local input values and callback ordering. No process-global widget state.
use crate::proto::{WidgetState, widget_state};
use crate::{SessionState, Streamlit};
use chrono::{NaiveDate, NaiveDateTime, NaiveTime, Timelike};
use serde::{Deserialize, Deserializer};
use serde_json::Value;
use std::collections::{HashMap, HashSet};
use std::sync::Arc;

/// A synchronous callback runs after all incoming values are applied and before main.
/// Captured Rust values replace Python's args/kwargs; the callback must be thread safe.
pub type WidgetCallback = Arc<dyn Fn(&Streamlit) + Send + Sync>;

/// The largest integer every f64 carries exactly. Both the numeric and the
/// temporal slider wires are f64 arrays; temporal values are integer epoch
/// microseconds, which stay inside this bound for roughly 1677..2262.
pub(crate) const JS_SAFE_INTEGER: f64 = 9_007_199_254_740_991.0;

/// 2000-01-01T00:00:00Z in microseconds: the anchor of time-of-day sliders,
/// measured on the pinned 1.66.1 reference wire.
pub(crate) const TIME_ANCHOR_MICROS: i64 = 946_684_800_000_000;

fn parse_date_input(text: &str) -> Option<NaiveDate> {
    let mut fields = text.split(if text.contains('/') { '/' } else { '-' });
    let year = fields.next()?;
    if year.len() != 4 || !year.bytes().all(|byte| byte.is_ascii_digit()) {
        return None;
    }
    let year: i32 = year.parse().ok()?;
    let month = parse_temporal_number(fields.next()?, false)?;
    let day = parse_temporal_number(fields.next()?, true)?;
    if year == 0 || fields.next().is_some() {
        return None;
    }

    NaiveDate::from_ymd_opt(year, month, day)
}

/// Python strptime 仅在日/小时允许一个空格加一位数字，不修剪其他字段。
fn parse_temporal_number(text: &str, space_padded: bool) -> Option<u32> {
    let digits = if space_padded && text.len() == 2 { text.strip_prefix(' ').unwrap_or(text) } else { text };
    if !(1..=2).contains(&digits.len()) || !digits.bytes().all(|byte| byte.is_ascii_digit()) {
        return None;
    }

    digits.parse().ok()
}

fn parse_time_input(text: &str, seconds_allowed: bool) -> Option<NaiveTime> {
    let mut fields = text.split(':');
    let hour = parse_temporal_number(fields.next()?, true)?;
    let minute = parse_temporal_number(fields.next()?, false)?;
    let second = match fields.next() {
        Some(value) if seconds_allowed => parse_temporal_number(value, false)?,
        Some(_) => return None,
        None => 0,
    };
    if fields.next().is_some() {
        return None;
    }

    NaiveTime::from_hms_opt(hour, minute, second)
}

fn parse_datetime_input(text: &str) -> Option<NaiveDateTime> {
    // 1. SDK 的 ISO 分隔 T 不区分大小写，时间仍只接受小时/分钟。
    if let Some((date, time)) = text.split_once(['T', 't']) {
        if date.contains('/') {
            return None;
        }
        return Some(parse_date_input(date)?.and_time(parse_time_input(time, false)?));
    }

    // 2. legacy 逗号后必须有 Python 空白；其他字段的空白不能被吞掉。
    let (date, time) = text.split_once(',')?;
    let trimmed = time.trim_start_matches(crate::utils::python_whitespace);
    if !date.contains('/') || trimmed.len() == time.len() {
        return None;
    }

    Some(parse_date_input(date)?.and_time(parse_time_input(trimmed, false)?))
}

// JSON 语法状态显式入栈，避免深层容器消耗 Rust 调用栈。
enum JsonFrame {
    Value,

    RootEnd,

    ArrayValue(Option<usize>),

    ArrayTail,

    ObjectKey(Option<usize>),

    ObjectColon,

    ObjectTail,
}

fn json_string_end(input: &[u8], start: usize) -> Result<usize, (&'static str, usize)> {
    let mut index = start + 1;
    while let Some(&byte) = input.get(index) {
        match byte {
            b'"' => return Ok(index + 1),
            0..=0x1f => return Err(("Invalid control character at", index)),
            b'\\' => match input.get(index + 1) {
                None => break,
                Some(b'"' | b'\\' | b'/' | b'b' | b'f' | b'n' | b'r' | b't') => index += 2,
                Some(b'u') => {
                    if !input.get(index + 2..index + 6).is_some_and(|hex| hex.iter().all(u8::is_ascii_hexdigit)) {
                        return Err((r"Invalid \uXXXX escape", index + 1));
                    }
                    index += 6;
                }
                Some(_) => return Err((r"Invalid \escape", index)),
            },
            _ => index += 1,
        }
    }

    Err(("Unterminated string starting at", start))
}

fn json_number_end(input: &[u8], start: usize) -> Option<usize> {
    // 1. 整数只匹配一个前导零，保留后续非法字符的位置。
    let mut index = start + usize::from(input.get(start) == Some(&b'-'));
    match input.get(index)? {
        b'0' => index += 1,
        b'1'..=b'9' => {
            index += 1;
            while input.get(index).is_some_and(u8::is_ascii_digit) {
                index += 1;
            }
        }
        _ => return None,
    }

    // 2. 小数点后必须有数字，否则它属于后续额外数据。
    if input.get(index) == Some(&b'.') && input.get(index + 1).is_some_and(u8::is_ascii_digit) {
        index += 2;
        while input.get(index).is_some_and(u8::is_ascii_digit) {
            index += 1;
        }
    }

    // 3. 不完整指数也留给容器/根值的分隔检查。
    if matches!(input.get(index), Some(b'e' | b'E')) {
        let mut end = index + 1;
        if matches!(input.get(end), Some(b'+' | b'-')) {
            end += 1;
        }
        let digits = end;
        while input.get(end).is_some_and(u8::is_ascii_digit) {
            end += 1;
        }
        if end > digits {
            index = end;
        }
    }

    Some(index)
}

fn widget_json_error(text: &str) -> Option<WidgetInputError> {
    // 1. SDK 使用字符偏移，行号只按 LF 计算；不把 UTF-8 字节数当作位置。
    let error = |message: &str, offset: usize| {
        let prefix = &text[..offset];
        let position = prefix.chars().count();
        let line = prefix.bytes().filter(|byte| *byte == b'\n').count() + 1;
        let column = prefix.rsplit('\n').next().unwrap_or("").chars().count() + 1;
        WidgetInputError {
            kind: "json.decoder.JSONDecodeError",
            message: format!("{message}: line {line} column {column} (char {position})"),
        }
    };
    if text.starts_with('\u{feff}') {
        return Some(error("Unexpected UTF-8 BOM (decode using utf-8-sig)", 0));
    }
    let input = text.as_bytes();
    let mut index = 0;
    let mut frames = vec![JsonFrame::RootEnd, JsonFrame::Value];

    // 2. 只检查语法，不构造 JSON 值；常量和数值前缀按 SDK 的扫描顺序匹配。
    while let Some(frame) = frames.pop() {
        while matches!(input.get(index), Some(b' ' | b'\t' | b'\r' | b'\n')) {
            index += 1;
        }
        match frame {
            JsonFrame::Value => match input.get(index) {
                Some(b'"') => match json_string_end(input, index) {
                    Ok(end) => index = end,
                    Err((message, offset)) => return Some(error(message, offset)),
                },
                Some(b'[') => {
                    index += 1;
                    frames.push(JsonFrame::ArrayValue(None));
                }
                Some(b'{') => {
                    index += 1;
                    frames.push(JsonFrame::ObjectKey(None));
                }
                Some(b'n') if input[index..].starts_with(b"null") => index += 4,
                Some(b't') if input[index..].starts_with(b"true") => index += 4,
                Some(b'f') if input[index..].starts_with(b"false") => index += 5,
                Some(b'N') if input[index..].starts_with(b"NaN") => index += 3,
                Some(b'I') if input[index..].starts_with(b"Infinity") => index += 8,
                Some(b'-') if input[index..].starts_with(b"-Infinity") => index += 9,
                Some(b'-' | b'0'..=b'9') => match json_number_end(input, index) {
                    Some(end) => index = end,
                    None => return Some(error("Expecting value", index)),
                },
                _ => return Some(error("Expecting value", index)),
            },
            JsonFrame::ArrayValue(comma) => {
                if input.get(index) == Some(&b']') {
                    if let Some(comma) = comma {
                        return Some(error("Illegal trailing comma before end of array", comma));
                    }
                    index += 1;
                } else {
                    frames.push(JsonFrame::ArrayTail);
                    frames.push(JsonFrame::Value);
                }
            }
            JsonFrame::ArrayTail => match input.get(index) {
                Some(b']') => index += 1,
                Some(b',') => {
                    frames.push(JsonFrame::ArrayValue(Some(index)));
                    index += 1;
                }
                _ => return Some(error("Expecting ',' delimiter", index)),
            },
            JsonFrame::ObjectKey(comma) => {
                if input.get(index) == Some(&b'}') {
                    if let Some(comma) = comma {
                        return Some(error("Illegal trailing comma before end of object", comma));
                    }
                    index += 1;
                } else if input.get(index) != Some(&b'"') {
                    return Some(error("Expecting property name enclosed in double quotes", index));
                } else {
                    match json_string_end(input, index) {
                        Ok(end) => index = end,
                        Err((message, offset)) => return Some(error(message, offset)),
                    }
                    frames.push(JsonFrame::ObjectColon);
                }
            }
            JsonFrame::ObjectColon => {
                if input.get(index) != Some(&b':') {
                    return Some(error("Expecting ':' delimiter", index));
                }
                index += 1;
                frames.push(JsonFrame::ObjectTail);
                frames.push(JsonFrame::Value);
            }
            JsonFrame::ObjectTail => match input.get(index) {
                Some(b'}') => index += 1,
                Some(b',') => {
                    frames.push(JsonFrame::ObjectKey(Some(index)));
                    index += 1;
                }
                _ => return Some(error("Expecting ',' delimiter", index)),
            },
            // 3. 根值完成后只允许 JSON 空白，多余数据的位置保留为首个字符。
            JsonFrame::RootEnd if index != input.len() => return Some(error("Extra data", index)),
            JsonFrame::RootEnd => (),
        }
    }
    None
}

/// Bool serde 只需要真值，不构造受数值范围和字符串表示限制的 JSON 树。
fn decode_bool_json(text: &str) -> Option<Value> {
    if widget_json_error(text).is_some() {
        return None;
    }
    let text = text.trim_matches(|character: char| matches!(character, ' ' | '\t' | '\r' | '\n'));
    if text == "null" {
        return Some(Value::Null);
    }
    let value = match text.as_bytes().first()? {
        b't' => true,
        b'f' => false,
        b'"' => text.len() > 2,
        b'[' | b'{' => !text[1..text.len() - 1].trim_matches(|character: char| matches!(character, ' ' | '\t' | '\r' | '\n')).is_empty(),
        _ if matches!(text, "NaN" | "Infinity" | "-Infinity") => true,
        _ => text.parse::<f64>().ok()? != 0.0,
    };
    Some(Value::Bool(value))
}

/// One temporal day/step in microseconds, as measured on the reference.
pub(crate) const DAY_MICROS: i64 = 86_400_000_000;

/// SDK 颜色默认值要求 #RGB/#RRGGBB；其正则 $ 还接受一个末尾 LF。
pub(crate) fn valid_color_hex(value: &str) -> bool {
    let value = value.strip_suffix('\n').unwrap_or(value);
    value.strip_prefix('#').is_some_and(|digits| matches!(digits.len(), 3 | 6) && digits.bytes().all(|byte| byte.is_ascii_hexdigit()))
}

pub(crate) fn date_micros(date: NaiveDate) -> i64 {
    date.and_hms_opt(0, 0, 0).expect("midnight is valid for every date").and_utc().timestamp_micros()
}

pub(crate) fn time_micros(time: NaiveTime) -> i64 {
    let sub_second = (time.nanosecond() % 1_000_000_000) as i64 / 1_000;
    TIME_ANCHOR_MICROS + time.num_seconds_from_midnight() as i64 * 1_000_000 + sub_second
}

pub(crate) fn datetime_micros(value: NaiveDateTime) -> i64 {
    value.and_utc().timestamp_micros()
}

fn date_from_micros(micros: i64) -> Option<NaiveDate> {
    chrono::DateTime::from_timestamp_micros(micros).map(|value| value.date_naive())
}

fn time_from_micros(micros: i64) -> Option<NaiveTime> {
    let day = micros.checked_sub(TIME_ANCHOR_MICROS)?;
    if !(0..DAY_MICROS).contains(&day) {
        return None;
    }
    let seconds = (day / 1_000_000) as u32;
    let nanos = (day % 1_000_000 * 1_000) as u32;
    NaiveTime::from_num_seconds_from_midnight_opt(seconds, nanos)
}

fn datetime_from_micros(micros: i64) -> Option<NaiveDateTime> {
    chrono::DateTime::from_timestamp_micros(micros).map(|value| value.naive_utc())
}

/// The temporal slider kinds, measured on the pinned 1.66.1 wire: every value
/// is an integer number of epoch microseconds carried as a double. Naive
/// date-times encode as if UTC; a time-of-day encodes against the 2000-01-01
/// anchor above.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum TemporalKind {
    Datetime,
    Date,
    Time,
}

impl TemporalKind {
    /// The `Slider.DataType` enum value: DATETIME = 2, DATE = 3, TIME = 4.
    pub(crate) fn data_type(self) -> i32 {
        match self {
            Self::Datetime => 2,
            Self::Date => 3,
            Self::Time => 4,
        }
    }

    /// The typed JSON form (chrono serde strings) of one wire value.
    pub(crate) fn typed_value(self, micros: i64) -> Option<Value> {
        let value = match self {
            Self::Datetime => serde_json::to_value(datetime_from_micros(micros)?).ok()?,
            Self::Date => serde_json::to_value(date_from_micros(micros)?).ok()?,
            Self::Time => serde_json::to_value(time_from_micros(micros)?).ok()?,
        };
        Some(value)
    }

    /// The microseconds of one typed JSON value.
    pub(crate) fn micros(self, value: &Value) -> Option<i64> {
        match self {
            Self::Datetime => NaiveDateTime::deserialize(value).ok().map(datetime_micros),
            Self::Date => NaiveDate::deserialize(value).ok().map(date_micros),
            Self::Time => NaiveTime::deserialize(value).ok().map(time_micros),
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum WidgetError {
    #[error("widget key is already used in this run: {0}")]
    DuplicateKey(String),
    #[error("identical widgets need distinct explicit keys: {0}")]
    DuplicateId(String),
    #[error("invalid widget value: {0}")]
    InvalidValue(String),
    #[error(transparent)]
    Serialization(#[from] serde_json::Error),
}

#[derive(Clone)]
pub(crate) enum Codec {
    Trigger,
    Bool,
    Text {
        max_chars: Option<usize>,
    },

    /// 前端颜色字符串在 callback 前补 #；空/非法字符串恢复注册时的默认值。
    Color {
        default: String,
    },

    Select(Vec<(String, Value)>),
    /// Creation-mode selectbox: a known label decodes to its index, an
    /// unknown label passes through as its string (accept_new_options).
    SelectCreation(Vec<(String, Value)>),
    /// Radio option labels; the wire state is the selected option's text.
    Radio(Vec<String>),
    /// Multiselect options paired with their native values; the wire state is
    /// the selected option texts, in selection order.
    MultiSelect(Vec<(String, Value)>),
    /// Number bounds in wire units; the state is int_value or double_value
    /// according to the measured integer/float split.
    NumberInput {
        min: Option<f64>,
        max: Option<f64>,
        integer: bool,
    },
    Slider {
        min: f64,
        max: f64,
        count: usize,
        integer: bool,
    },
    TemporalSlider {
        min: f64,
        max: f64,
        count: usize,
        kind: TemporalKind,
    },
    Files {
        store: Arc<parking_lot::Mutex<crate::upload::UploadStore>>,
        multiple: bool,
    },
    /// The chat input's submitted value: the data string of the
    /// chat_input_value state, absent data meaning None (the trigger
    /// resets after the run, like the reference).
    ChatInput,
    /// The feedback string state: "" (the user cleared, so None) or the
    /// decimal index of the picked icon, within the style's icon count.
    Feedback {
        count: usize,
    },
    /// The pagination page, 1-indexed within `num_pages`.
    Pagination {
        num_pages: u32,
    },
    /// pills/segmented_control: option labels paired with their native
    /// values; the wire is the selected label strings (one at most in
    /// single-select mode, in selection order in multi-select).
    ButtonGroup {
        options: Vec<(String, Value)>,
        multi: bool,

        /// Pills/segmented controls filter stale strings; select-slider endpoints retain strict validation.
        filter_invalid: bool,
    },
    /// The menu button's one-shot string trigger: the selected option's
    /// label, resetting to None after the run like button triggers.
    StringTrigger(Vec<String>),
    /// A dataframe button column's one-shot string trigger: the click state
    /// as one JSON object ({"row": index, "label": text}), resetting to None
    /// after the run like the reference's ButtonClickSerde.
    ButtonColumn,

    /// Browser selections are decoded before callbacks using the previous run's
    /// mode and row count. Application writes keep their original partial JSON.
    DataframeSelection {
        required_row: bool,
        num_rows: usize,
    },

    /// A bidi component's persistent state: the whole state object as one
    /// JSON string (json_value). Missing top-level keys retain their defaults.
    JsonValue {
        defaults: Value,
    },

    /// A bidi component's trigger aggregator: json_trigger_value carries the
    /// fired events as one JSON array string of {"event", "value"} payloads
    /// (the frontend accumulates them), resetting to null after the run like
    /// every reference trigger.
    JsonTrigger,
    /// date_input: ISO "YYYY-MM-DD" strings, one for a single date or two
    /// for a range; the value stays a string and the emitter parses it.
    DateInput {
        range: bool,
        min: chrono::NaiveDate,
        max: chrono::NaiveDate,

        /// 仅显式提供边界时，在登记阶段校验已有原生值。
        reset_native: bool,

        /// 前端解析失败/越界时的声明默认，也用于登记后的原生边界重置。
        default: Value,
    },
    /// time_input: "HH:MM" for whole-minute steps, "HH:MM:SS" otherwise.
    TimeInput {
        step: i64,
    },
    /// datetime_input: ISO "YYYY-MM-DDTHH:MM" strings (the reference also
    /// accepts the legacy "YYYY/MM/DD, HH:MM" spelling on input).
    DateTimeInput {
        min: chrono::NaiveDateTime,
        max: chrono::NaiveDateTime,

        /// 显式边界越界时恢复的本轮声明默认；省略边界则不重置原生值。
        reset_default: Option<Value>,
    },
}

impl Codec {
    fn query_value(&self, text: &str, clearable: bool) -> Option<Value> {
        if text.is_empty() {
            if !clearable {
                return None;
            }
            if matches!(self, Self::Select(_) | Self::SelectCreation(_)) {
                return Some(Value::Null);
            }
        }
        self.decode(&widget_state::Value::StringValue(text.into())).filter(|value| self.valid(value))
    }

    fn query_text(&self, value: &Value) -> Option<String> {
        match self {
            Self::Text { .. } => value.as_str().map(str::to_owned),
            Self::Select(options) | Self::SelectCreation(options) => value.as_u64().and_then(|index| options.get(index as usize)).map(|(label, _)| label.clone()).or_else(|| value.as_str().map(str::to_owned)),
            _ => None,
        }
    }

    fn dataframe_selection_shape(value: &Value) -> bool {
        value.as_object().and_then(|state| state.get("selection")).is_some_and(Value::is_object)
    }

    /// The reference's ButtonColumnClickState shape: a non-negative row
    /// index and a text label.
    fn button_click_shape(value: &Value) -> bool {
        value.as_object().is_some_and(|click| click.get("row").is_some_and(Value::is_u64) && click.get("label").is_some_and(Value::is_string))
    }

    fn input_error(&self, wire: Option<&widget_state::Value>) -> Option<WidgetInputError> {
        if let Some(widget_state::Value::JsonValue(text)) = wire
            && let Some(error) = widget_json_error(text)
        {
            return Some(error);
        }

        self.date_input_error(wire).map(WidgetInputError::type_error)
    }

    fn date_input_error(&self, wire: Option<&widget_state::Value>) -> Option<&'static str> {
        if !matches!(self, Self::DateInput { .. }) {
            return None;
        }
        match wire {
            Some(widget_state::Value::BoolValue(_) | widget_state::Value::TriggerValue(_)) => Some("'bool' object is not iterable"),
            Some(widget_state::Value::IntValue(_)) => Some("'int' object is not iterable"),
            Some(widget_state::Value::DoubleValue(_)) => Some("'float' object is not iterable"),
            Some(widget_state::Value::IntArrayValue(array)) if !array.data.is_empty() => Some("strptime() argument 1 must be str, not int"),
            Some(widget_state::Value::DoubleArrayValue(array)) if !array.data.is_empty() => Some("strptime() argument 1 must be str, not float"),
            Some(widget_state::Value::BytesValue(bytes)) if !bytes.is_empty() => Some("strptime() argument 1 must be str, not int"),
            Some(widget_state::Value::JsonValue(text)) => serde_json::from_str::<Value>(text).ok().and_then(|value| match value {
                Value::Bool(_) => Some("'bool' object is not iterable"),
                Value::Number(number) if number.is_i64() || number.is_u64() => Some("'int' object is not iterable"),
                Value::Number(_) => Some("'float' object is not iterable"),

                Value::Array(items) => {
                    // 逐项解析：前面的非法日期先回默认，后项类型错误不再发生。
                    for item in items {
                        let error = match item {
                            Value::String(text) => {
                                if parse_date_input(&text).is_none() {
                                    break;
                                }
                                continue;
                            }

                            Value::Bool(_) => "strptime() argument 1 must be str, not bool",
                            Value::Number(number) if number.is_i64() || number.is_u64() => "strptime() argument 1 must be str, not int",
                            Value::Number(_) => "strptime() argument 1 must be str, not float",
                            Value::Null => "strptime() argument 1 must be str, not None",
                            Value::Array(_) => "strptime() argument 1 must be str, not list",
                            Value::Object(_) => "strptime() argument 1 must be str, not dict",
                        };
                        return Some(error);
                    }
                    None
                }

                _ => None,
            }),
            _ => None,
        }
    }

    fn decode_date_json(&self, text: &str) -> Option<Value> {
        let Self::DateInput { default, .. } = self else { return None };
        let items = match serde_json::from_str::<Value>(text).ok()? {
            Value::Null => return Some(default.clone()),

            Value::String(text) => text.chars().map(|ch| Value::String(ch.to_string())).collect(),

            Value::Array(items) => items,

            Value::Object(_) => {
                // 1. Python 迭代对象键，重复键保留首次位置；不依赖 Map 的排序配置。
                struct Keys;
                impl<'de> serde::de::Visitor<'de> for Keys {
                    type Value = Vec<String>;

                    fn expecting(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                        formatter.write_str("a JSON object")
                    }

                    fn visit_map<M: serde::de::MapAccess<'de>>(self, mut map: M) -> Result<Self::Value, M::Error> {
                        let mut keys = Vec::new();
                        let mut seen = HashSet::new();
                        while let Some(key) = map.next_key::<String>()? {
                            map.next_value::<serde::de::IgnoredAny>()?;
                            if seen.insert(key.clone()) {
                                keys.push(key);
                            }
                        }
                        Ok(keys)
                    }
                }
                serde_json::Deserializer::from_str(text).deserialize_map(Keys).ok()?.into_iter().map(Value::String).collect()
            }

            _ => return None,
        };
        // 2. 非法日期先回默认；后续类型错误不再发生。空/部分范围仍待公共模型。
        let mut dates = Vec::new();
        for item in items {
            let Value::String(text) = item else { return None };
            if parse_date_input(&text).is_none() {
                return Some(default.clone());
            }
            dates.push(text);
        }
        if dates.is_empty() {
            return None;
        }
        self.decode(&widget_state::Value::StringArrayValue(crate::proto::StringArray { data: dates }))
    }

    fn decode_state(&self, state: &WidgetState, empty_input: Option<&Value>) -> Option<Value> {
        let value = match state.value.as_ref() {
            Some(widget_state::Value::JsonValue(text)) if matches!(self, Self::DateInput { .. }) => self.decode_date_json(text),

            Some(widget_state::Value::StringValue(text)) if matches!(self, Self::DateInput { .. }) && !text.is_empty() => empty_input.cloned(),

            Some(wire) => self.decode(wire),

            // 支持的 ID-only 包按上一轮 serde 的有效默认值反序列化。
            None => empty_input.cloned(),
        }?;

        // 布尔 null 和时间空/无效/越界输入恢复上轮 serde 默认，不强制清空。
        if matches!(self, Self::Bool | Self::TimeInput { .. } | Self::DateTimeInput { .. }) && value.is_null() {
            return empty_input.cloned();
        }

        // 数字前端输入先按上轮显式/隐式边界回默认，callback 只读取归一化后的值。
        if let Self::NumberInput { min, max, integer } = self {
            let lower = min.unwrap_or(if *integer { -JS_SAFE_INTEGER } else { f64::MIN });
            let upper = max.unwrap_or(if *integer { JS_SAFE_INTEGER } else { f64::MAX });
            if value.as_f64().is_none_or(|number| !number.is_finite() || number < lower || number > upper) {
                return empty_input.cloned();
            }
        }

        Some(value)
    }

    pub(crate) fn decode(&self, wire: &widget_state::Value) -> Option<Value> {
        match (self, wire) {
            (Self::Trigger, widget_state::Value::TriggerValue(value)) => Some((*value).into()),
            (Self::Bool, wire) => {
                // 1. SDK 先解包状态，再按 Python bool 转换；None 回声明默认。
                let value = match wire {
                    widget_state::Value::BoolValue(value) | widget_state::Value::TriggerValue(value) => *value,
                    widget_state::Value::IntValue(value) => *value != 0,
                    widget_state::Value::DoubleValue(value) => *value != 0.0,
                    widget_state::Value::StringValue(value) | widget_state::Value::JsonTriggerValue(value) => !value.is_empty(),

                    widget_state::Value::StringArrayValue(value) => !value.data.is_empty(),
                    widget_state::Value::IntArrayValue(value) => !value.data.is_empty(),
                    widget_state::Value::DoubleArrayValue(value) => !value.data.is_empty(),
                    widget_state::Value::BytesValue(value) => !value.is_empty(),
                    widget_state::Value::StringTriggerValue(value) => value.data.as_ref().is_some_and(|value| !value.is_empty()),

                    // 2. 普通 JSON 先解码；消息对象自身始终为真，不能看其 data 是否为空。
                    widget_state::Value::JsonValue(text) => return decode_bool_json(text),
                    widget_state::Value::ArrowValue(_) | widget_state::Value::FileUploaderStateValue(_) | widget_state::Value::ChatInputValue(_) => true,
                };

                Some(Value::Bool(value))
            }
            (Self::Text { max_chars }, widget_state::Value::StringValue(value)) => Some(Value::String(max_chars.map_or_else(|| value.clone(), |limit| value.chars().take(limit).collect()))),

            (Self::Color { default }, widget_state::Value::StringValue(value)) => {
                let normalized = if value.starts_with('#') { value.clone() } else { format!("#{value}") };
                Some(Value::String(if valid_color_hex(&normalized) { normalized } else { default.clone() }))
            }

            (Self::Select(options), widget_state::Value::StringValue(label)) => options.iter().rposition(|(text, _)| text == label).map(Value::from),
            (Self::SelectCreation(options), widget_state::Value::StringValue(label)) => Some(match options.iter().position(|(text, _)| text == label) {
                Some(index) => Value::from(index),
                // A freshly typed value keeps its label as the native value.
                None => Value::String(label.clone()),
            }),
            (Self::Radio(options), widget_state::Value::StringValue(label)) => options.iter().position(|text| text == label).map(Value::from),
            (Self::MultiSelect(options), widget_state::Value::StringArrayValue(array)) => {
                let indices: Option<Vec<Value>> = array.data.iter().map(|label| options.iter().position(|(text, _)| text == label).map(Value::from)).collect();
                indices.map(Value::Array)
            }
            (Self::NumberInput { integer, .. }, widget_state::Value::IntValue(value)) if *integer => Some(Value::from(*value)),
            (Self::NumberInput { integer, .. }, widget_state::Value::DoubleValue(value)) if !*integer => Some(Value::from(*value)),
            (Self::Files { store, multiple }, widget_state::Value::FileUploaderStateValue(state)) => {
                let store = store.lock();
                let ids: Vec<Value> = state.uploaded_file_info.iter().filter(|file| store.get(&file.file_id).is_some()).map(|file| Value::String(file.file_id.clone())).collect();
                if !multiple && ids.len() > 1 {
                    return None;
                }
                Some(Value::Array(ids))
            }
            (Self::ChatInput, widget_state::Value::ChatInputValue(value)) => Some(match value.data.as_deref() {
                Some("") | None => Value::Null,
                Some(data) => Value::String(data.to_owned()),
            }),
            (Self::Feedback { .. }, widget_state::Value::StringValue(value)) => Some(if value.is_empty() { Value::Null } else { value.parse::<u64>().ok().map(Value::from)? }),
            (Self::Pagination { num_pages }, widget_state::Value::IntValue(value)) => {
                let num_pages = *num_pages as u64;
                (*value >= 1 && *value as u64 <= num_pages).then(|| (*value as u64).into())
            }
            (Self::ButtonGroup { options, multi, .. }, widget_state::Value::StringArrayValue(array)) => {
                let indices: Option<Vec<Value>> = array.data.iter().map(|label| options.iter().position(|(text, _)| text == label).map(Value::from)).collect();
                let indices = indices?;
                if *multi {
                    Some(Value::Array(indices))
                } else if indices.len() <= 1 {
                    Some(indices.into_iter().next().unwrap_or(Value::Null))
                } else {
                    None
                }
            }
            (Self::StringTrigger(options), widget_state::Value::StringTriggerValue(trigger)) => trigger.data.as_deref().and_then(|label| options.iter().position(|option| option == label).map(Value::from)),
            (Self::ButtonColumn, widget_state::Value::StringTriggerValue(trigger)) => Some(match trigger.data.as_deref() {
                None | Some("") => Value::Null,
                Some(data) => serde_json::from_str::<Value>(data).ok().filter(Self::button_click_shape)?,
            }),
            (Self::DataframeSelection { required_row, num_rows }, widget_state::Value::StringValue(text)) => {
                let mut value = serde_json::from_str::<Value>(text).ok()?;
                if !Self::dataframe_selection_shape(&value) {
                    return None;
                }
                let state = serde_json::from_value::<crate::DataframeState>(value.clone()).ok()?;
                let selection = value.get_mut("selection")?.as_object_mut()?;
                // 先正规化协议值再比较变更和安排回调；不能到 main 末尾只修返回值。
                for field in ["rows", "columns", "cells"] {
                    if !selection.contains_key(field) {
                        selection.insert(field.into(), Value::Array(Vec::new()));
                    }
                }
                if *required_row && *num_rows > 0 && state.selection.rows.is_empty() {
                    selection.insert("rows".into(), serde_json::json!([0]));
                }
                Some(value)
            }
            (Self::JsonValue { defaults }, widget_state::Value::JsonValue(text)) => {
                let mut value = serde_json::from_str::<Value>(text).ok()?;
                if let (Value::Object(state), Value::Object(defaults)) = (&mut value, defaults) {
                    for (key, default) in defaults {
                        state.entry(key.clone()).or_insert_with(|| default.clone());
                    }
                }
                Some(value)
            }
            (Self::JsonTrigger, widget_state::Value::JsonTriggerValue(text)) => Some(match serde_json::from_str::<Value>(text) {
                Ok(Value::Array(list)) => Value::Array(list),
                Ok(Value::Null) => Value::Null,
                Ok(single) => Value::Array(vec![single]),
                // The reference's handle_deserialize keeps an unparsable
                // payload as its raw string, list-normalized.
                Err(_) => Value::Array(vec![Value::String(text.clone())]),
            }),
            (Self::DateInput { range, min, max, default, .. }, widget_state::Value::StringArrayValue(array)) => {
                // 1. 先检查全部日期；任意非法/越界条目都恢复上轮登记默认。
                let dates: Option<Vec<_>> = array.data.iter().map(|text| parse_date_input(text)).collect();
                match dates {
                    Some(dates) if dates.iter().all(|date| date >= min && date <= max) => {
                        let iso = |date: &chrono::NaiveDate| Value::String(date.format("%Y-%m-%d").to_string());
                        // 2. 保持现有返回模型：范围仍需两项，单值取首项；空单值是 None。
                        if *range {
                            (dates.len() == 2).then(|| Value::Array(dates.iter().map(iso).collect()))
                        } else {
                            Some(dates.first().map_or(Value::Null, iso))
                        }
                    }

                    _ => Some(default.clone()),
                }
            }
            (Self::TimeInput { step }, widget_state::Value::StringValue(text)) => {
                let format = if step % 60 != 0 { "%H:%M:%S" } else { "%H:%M" };
                let parsed = parse_time_input(text, true);
                Some(parsed.map_or(Value::Null, |time| Value::String(time.format(format).to_string())))
            }
            (Self::DateTimeInput { min, max, .. }, widget_state::Value::StringArrayValue(array)) => {
                // 只解析首项；空、无效和越界产生回默认标记，不把私有 Null 当成清空。
                let parsed = array.data.first().and_then(|text| parse_datetime_input(text).filter(|moment| moment >= min && moment <= max));
                Some(parsed.map_or(Value::Null, |moment| Value::String(moment.format("%Y-%m-%dT%H:%M").to_string())))
            }
            (Codec::Slider { count, integer, .. }, widget_state::Value::DoubleArrayValue(array)) if array.data.len() == *count => {
                let values: Vec<Value> = array.data.iter().map(|value| if *integer { Value::from(*value as i64) } else { Value::from(*value) }).collect();
                let result = if *count == 1 { values[0].clone() } else { Value::Array(values) };
                // Validate the wire numbers before converting them to integers.
                if array.data.iter().any(|value| !value.is_finite() || (*integer && value.fract() != 0.0)) {
                    return None;
                }
                self.valid(&result).then_some(result)
            }
            (Codec::TemporalSlider { count, kind, .. }, widget_state::Value::DoubleArrayValue(array)) if array.data.len() == *count => {
                // Temporal wires carry integer epoch microseconds as doubles.
                if array.data.iter().any(|value| !value.is_finite() || value.fract() != 0.0 || value.abs() > JS_SAFE_INTEGER) {
                    return None;
                }
                let mut values = Vec::with_capacity(*count);
                for value in &array.data {
                    values.push(kind.typed_value(*value as i64)?);
                }
                let result = if *count == 1 { values[0].clone() } else { Value::Array(values) };
                self.valid(&result).then_some(result)
            }
            _ => None,
        }
    }

    pub(crate) fn valid(&self, value: &Value) -> bool {
        match self {
            Self::Trigger | Self::Bool => value.is_boolean(),
            Self::ChatInput => value.is_null() || value.is_string(),
            Self::Feedback { count } => value.is_null() || value.as_u64().is_some_and(|index| index < *count as u64),
            Self::Pagination { num_pages } => value.as_u64().is_some_and(|page| (1..=*num_pages as u64).contains(&page)),
            Self::ButtonGroup { options, multi, .. } => {
                let within = |index: &Value| index.as_u64().is_some_and(|index| index < options.len() as u64);
                if *multi { value.as_array().is_some_and(|indices| indices.iter().all(within)) } else { value.is_null() || within(value) }
            }
            Self::StringTrigger(options) => value.is_null() || value.as_u64().is_some_and(|index| index < options.len() as u64),
            Self::ButtonColumn => value.is_null() || Self::button_click_shape(value),
            Self::DataframeSelection { .. } => Self::dataframe_selection_shape(value),
            Self::JsonValue { .. } => true,
            Self::JsonTrigger => value.is_null() || value.is_array(),
            Self::DateInput { range, .. } => {
                let iso = |item: &Value| item.as_str().is_some_and(|text| chrono::NaiveDate::parse_from_str(text, "%Y-%m-%d").is_ok());
                // 原生状态可保留上轮单值/完整范围；前端解码仍按当前模式约束。
                (!*range && value.is_null()) || iso(value) || value.as_array().is_some_and(|dates| dates.len() == 2 && dates.iter().all(iso))
            }
            Self::TimeInput { step } => {
                let format = if step % 60 != 0 { "%H:%M:%S" } else { "%H:%M" };
                value.is_null() || value.as_str().is_some_and(|text| chrono::NaiveTime::parse_from_str(text, format).is_ok())
            }
            Self::DateTimeInput { .. } => {
                let iso = |text: &str| chrono::NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M").is_ok();
                value.is_null() || value.as_str().is_some_and(iso)
            }

            // 长度只限制反序列化输入，已由应用赋值的原生字符串不截断。
            Self::Text { .. } => value.is_null() || value.is_string(),

            // 代码赋值的字符串不走前端颜色校验，与 SDK 的原生状态路径一致。
            Self::Color { .. } => value.is_string(),

            Self::Select(options) => value.is_null() || value.as_u64().is_some_and(|index| index < options.len() as u64),
            Self::SelectCreation(options) => value.is_null() || value.is_string() || value.as_u64().is_some_and(|index| index < options.len() as u64),
            Self::Radio(options) => value.is_null() || value.as_u64().is_some_and(|index| index < options.len() as u64),
            Self::MultiSelect(options) => value.as_array().is_some_and(|indices| indices.iter().all(|index| index.as_u64().is_some_and(|i| i < options.len() as u64))),
            Self::NumberInput { min, max, integer } => value
                .as_f64()
                .is_some_and(|number| number.is_finite() && (!*integer || number.fract() == 0.0) && min.is_none_or(|bound| number >= bound) && max.is_none_or(|bound| number <= bound)),
            Self::Files { multiple, .. } => value.as_array().is_some_and(|ids| (*multiple || ids.len() <= 1) && ids.iter().all(Value::is_string)),
            Codec::Slider { min, max, count, integer } => {
                let values = match value {
                    Value::Array(values) if *count == 2 => values.clone(),
                    _ if *count == 1 => vec![value.clone()],
                    _ => return false,
                };
                values.len() == *count && values.iter().all(|value| value.as_f64().is_some_and(|v| v.is_finite() && v >= *min && v <= *max && (!*integer || v.fract() == 0.0))) && (*count == 1 || values[0].as_f64() <= values[1].as_f64())
            }
            Codec::TemporalSlider { min, max, count, kind } => {
                let values = match value {
                    Value::Array(values) if *count == 2 => values.clone(),
                    _ if *count == 1 => vec![value.clone()],
                    _ => return false,
                };
                let Some(micros) = values.iter().map(|value| kind.micros(value)).collect::<Option<Vec<i64>>>() else {
                    return false;
                };
                micros.len() == *count && micros.iter().all(|value| (*value as f64) >= *min && (*value as f64) <= *max) && (*count == 1 || micros[0] <= micros[1])
            }
        }
    }

    // Selection presence is internal state, distinct from the selected native
    // value: Some(index) may legitimately project to JSON null in session state.
    fn session_value(&self, value: &Value) -> Value {
        match self {
            Self::Select(options) => value.as_u64().and_then(|index| options.get(index as usize)).map(|(_, native)| native.clone()).unwrap_or(Value::Null),
            Self::SelectCreation(options) => match value.as_u64().and_then(|index| options.get(index as usize)).map(|(_, native)| native.clone()) {
                Some(native) => native,
                // A freshly typed label already is the native value.
                None => value.clone(),
            },
            Self::Radio(options) => value.as_u64().and_then(|index| options.get(index as usize)).cloned().map(Value::String).unwrap_or(Value::Null),
            Self::MultiSelect(options) => Value::Array(
                value
                    .as_array()
                    .map(|indices| indices.iter().filter_map(|index| index.as_u64().and_then(|i| options.get(i as usize)).map(|(_, native)| native.clone())).collect())
                    .unwrap_or_default(),
            ),
            Self::ButtonGroup { options, multi, .. } if *multi => Value::Array(
                value
                    .as_array()
                    .map(|indices| indices.iter().filter_map(|index| index.as_u64().and_then(|i| options.get(i as usize)).map(|(_, native)| native.clone())).collect())
                    .unwrap_or_default(),
            ),
            Self::ButtonGroup { options, multi, .. } => {
                debug_assert!(!*multi);
                value.as_u64().and_then(|index| options.get(index as usize)).map(|(_, native)| native.clone()).unwrap_or(Value::Null)
            }
            Self::StringTrigger(options) => value.as_u64().and_then(|index| options.get(index as usize)).cloned().map(Value::String).unwrap_or(Value::Null),
            _ => value.clone(),
        }
    }

    fn read_session_value(&self, native: &Value, previous: Option<&Record>) -> Result<Value, WidgetError> {
        if let Self::Select(options) = self {
            if let Some(previous) = previous
                && previous.codec.session_value(&previous.value) == *native
            {
                if previous.value.is_null() {
                    return Ok(Value::Null);
                }
                // Preserve the selected occurrence if its native value is
                // unchanged; otherwise remap after keyed options are reordered.
                if let Some(index) = previous.value.as_u64()
                    && options.get(index as usize).is_some_and(|(_, value)| value == native)
                {
                    return Ok(index.into());
                }
            }
            return options
                .iter()
                .position(|(_, value)| value == native)
                .map(Value::from)
                .or_else(|| native.is_null().then_some(Value::Null))
                .ok_or_else(|| WidgetError::InvalidValue("session value is absent from selectbox options".into()));
        }
        if let Self::Radio(options) = self {
            return native
                .as_str()
                .and_then(|text| options.iter().position(|option| option == text))
                .map(Value::from)
                .or_else(|| native.is_null().then_some(Value::Null))
                .ok_or_else(|| WidgetError::InvalidValue("session value is absent from radio options".into()));
        }
        if let Self::MultiSelect(options) = self {
            let Some(items) = native.as_array() else {
                return Err(WidgetError::InvalidValue("multiselect session value must be an array".into()));
            };
            let mut indices = Vec::with_capacity(items.len());
            for item in items {
                if let Some(index) = options.iter().position(|(_, value)| value == item) {
                    indices.push(Value::from(index));
                } else if item.as_str().is_some_and(|text| options.iter().any(|(label, _)| label == text)) {
                    // SDK 可返回异类型标签；typed Vec<T> 尚不能表达，保留错误而非静默过滤。
                    return Err(WidgetError::InvalidValue("session value is absent from multiselect options".into()));
                }
            }
            return Ok(Value::Array(indices));
        }
        if let Self::ButtonGroup { options, multi, filter_invalid } = self {
            if *multi {
                let Some(items) = native.as_array() else {
                    return Err(WidgetError::InvalidValue("multi-select session value must be an array".into()));
                };
                let mut indices = Vec::with_capacity(items.len());
                for item in items {
                    if let Some(index) = options.iter().position(|(_, value)| value == item) {
                        indices.push(Value::from(index));
                    } else if !filter_invalid || !item.is_string() {
                        return Err(WidgetError::InvalidValue("session value is absent from options".into()));
                    }
                }
                return Ok(Value::Array(indices));
            }
            return native
                .as_str()
                .and_then(|text| options.iter().position(|(label, _)| label == text))
                .map(Value::from)
                .or_else(|| native.is_null().then_some(Value::Null))
                .ok_or_else(|| WidgetError::InvalidValue("session value is absent from options".into()));
        }
        if let Self::StringTrigger(options) = self {
            return native
                .as_str()
                .and_then(|text| options.iter().position(|option| option == text))
                .map(Value::from)
                .or_else(|| native.is_null().then_some(Value::Null))
                .ok_or_else(|| WidgetError::InvalidValue("session value is absent from options".into()));
        }
        Ok(native.clone())
    }
}

/// The value a one-shot widget resets to between runs, or None for widgets
/// that keep their state: buttons and link/download triggers to false, the
/// chat input to its empty value, the menu button to no selection.
fn one_shot_reset(codec: &Codec) -> Option<Value> {
    match codec {
        Codec::Trigger => Some(Value::Bool(false)),
        Codec::ChatInput | Codec::StringTrigger(_) | Codec::ButtonColumn | Codec::JsonTrigger => Some(Value::Null),
        _ => None,
    }
}

#[derive(Clone)]
struct Record {
    key: Option<String>,
    value: Value,
    codec: Codec,
    callback: Option<WidgetCallback>,

    /// Query binding follows this record's lifetime, including hidden widgets
    /// until run-end cleanup. The parameter name is the explicit widget key.
    query_bound: bool,

    /// Previous render policy used when accepting the next frontend batch.
    disabled: bool,

    /// Value before this run's input, restored if registration now disables it.
    before_input: Option<Value>,

    /// Effective defaults for supported ID-only widgets and numeric/time fallback.
    /// Other codecs retain the existing missing-value rejection.
    empty_input: Option<Value>,
}

#[derive(Clone, Default)]
pub(crate) struct WidgetRegistry {
    records: HashMap<String, Record>,
    seen: HashSet<String>,
    keys: HashSet<String>,
    active: bool,
    dirty_keys: HashSet<String>,
    /// Incoming states for unknown or previously disabled widgets;
    /// the reference applies the browser's state at widget creation, so
    /// these land when the widget registers (for example after another
    /// page left it unrendered).
    pending: Vec<crate::proto::WidgetState>,
    /// Submitted IDs determine frontend/URL priority independently of decoding.
    received: HashSet<String>,

    /// 无 metadata 的普通 ID 在 SDK filtered_state 中仍作为用户 key 读取。
    /// 保留跨请求错误；生成控件 ID 和内部 key 不进入该视图。
    unknown_keys: Vec<String>,

    /// Registration failure stops rendering without pruning unseen widgets.
    registration_error: Option<RegistrationError>,

    /// Deserialization failed before callback dispatch. Keep the first error
    /// latched across requests, as in the pinned Python session.
    input_error: Option<WidgetInputError>,
}

#[derive(Clone)]
pub(crate) struct WidgetInputError {
    // 错误元素所用的 Python 类型名。
    pub(crate) kind: &'static str,

    // 保留解析位置的完整 SDK 文案。
    pub(crate) message: String,
}

impl WidgetInputError {
    fn type_error(message: impl Into<String>) -> Self {
        Self { kind: "TypeError", message: message.into() }
    }
}

#[derive(Clone)]
struct RegistrationError {
    error: WidgetInputError,

    rendered: bool,
}

/// Registration-time URL policy for the existing bound text/select controls.
#[derive(Clone, Copy)]
pub(crate) struct QueryBinding {
    /// An empty URL value can represent this widget's empty state.
    pub(crate) clearable: bool,
}

pub(crate) struct WidgetSpec<'a> {
    /// Disabled state of this run; callbacks use the previous record.
    pub(crate) disabled: bool,

    /// Only the supported URL-bound text/select emitters opt into seeding.
    pub(crate) query: Option<QueryBinding>,

    pub(crate) kind: &'a str,
    pub(crate) key: Option<&'a str>,
    pub(crate) identity: &'a str,
    pub(crate) default: Value,
    pub(crate) codec: Codec,
    pub(crate) callback: Option<WidgetCallback>,
}

impl WidgetRegistry {
    pub(crate) fn query_bound(&self, key: &str) -> bool {
        self.records.values().any(|record| record.query_bound && record.key.as_deref() == Some(key))
    }

    pub(crate) fn bound_query_keys(&self) -> Vec<String> {
        self.records.values().filter(|record| record.query_bound).filter_map(|record| record.key.clone()).collect()
    }

    pub(crate) fn mark_write(&mut self, key: &str) {
        self.dirty_keys.insert(key.into());
    }
    pub(crate) fn check_write(&self, key: &str) -> serde_json::Result<()> {
        use serde::ser::Error;
        if self.records.values().any(|record| record.key.as_deref() == Some(key) && matches!(record.codec, Codec::Trigger | Codec::Files { .. })) {
            return Err(serde_json::Error::custom("button and uploader keys are read-only"));
        }
        if self.active && self.keys.contains(key) {
            return Err(serde_json::Error::custom("cannot modify a widget key after instantiation in this run"));
        }
        Ok(())
    }
}

impl SessionState {
    /// 历史导航跳过已注册绑定控件的旧输入，未知与未绑定输入继续保留。
    pub(crate) fn omit_query_bound_inputs(&self, incoming: &mut Vec<WidgetState>) {
        let registry = self.widgets.lock();
        incoming.retain(|widget| !registry.records.get(&widget.id).is_some_and(|record| record.query_bound));
    }

    pub(crate) fn form_checkpoint(&self) -> (WidgetRegistry, HashMap<String, Value>) {
        let registry = self.widgets.lock();
        (registry.clone(), self.values.lock().clone())
    }

    pub(crate) fn rollback_form(&self, checkpoint: (WidgetRegistry, HashMap<String, Value>)) {
        let mut registry = self.widgets.lock();
        let mut values = self.values.lock();
        // Only restore widget-associated values; unrelated application writes
        // in the user's fallible closure retain their ordinary semantics.
        for key in registry.records.values().filter_map(|record| record.key.as_ref()) {
            if let Some(value) = checkpoint.1.get(key) {
                values.insert(key.clone(), value.clone());
            } else {
                values.remove(key);
            }
        }
        *registry = checkpoint.0;
    }

    pub(crate) fn begin_widgets(&self, incoming: Vec<WidgetState>) -> Vec<WidgetCallback> {
        // 1. 初始化本轮；持续的解码错误在接收新输入前中止。
        let mut registry = self.widgets.lock();
        registry.active = true;
        registry.seen.clear();
        registry.keys.clear();
        registry.registration_error = None;
        if registry.input_error.is_some() {
            return Vec::new();
        }

        registry.pending.clear();
        registry.received.clear();

        // 2. 同批重复 ID 使用最后一个完整包，保留首次位置决定 callback/首错顺序。
        let mut positions = HashMap::new();
        let mut merged = Vec::with_capacity(incoming.len());
        for widget in incoming {
            if let Some(&position) = positions.get(&widget.id) {
                merged[position] = widget;
            } else {
                positions.insert(widget.id.clone(), merged.len());
                merged.push(widget);
            }
        }
        let incoming = merged;

        let mut values = self.values.lock();
        for record in registry.records.values_mut() {
            record.before_input = None;
            // Trigger widgets are one-shot: buttons reset to false, the chat
            // input to its empty (null) value, the menu button to null.
            if let Some(reset) = one_shot_reset(&record.codec) {
                record.value = reset.clone();
                if let Some(key) = &record.key {
                    values.insert(key.clone(), reset);
                }
            }
        }
        let mut callbacks = Vec::new();
        // 3. 已知解析错误交由有序应用阶段锁存；其他非法输入沿用原校验。
        let errors: Vec<_> = incoming.iter().map(|widget| registry.records.get(&widget.id).and_then(|record| record.codec.input_error(widget.value.as_ref()))).collect();
        if incoming.iter().zip(&errors).any(|(widget, error)| {
            registry
                .records
                .get(&widget.id)
                .is_some_and(|record| !record.disabled && error.is_none() && record.codec.decode_state(widget, record.empty_input.as_ref()).is_none_or(|value| !record.codec.valid(&value)))
        }) {
            return callbacks;
        }

        // 4. 应用输入并收集 callback，完成全部变化判断后再交给调用方执行。
        for (widget, error) in incoming.into_iter().zip(errors) {
            registry.received.insert(widget.id.clone());
            // 已知解析错误按输入顺序锁存；仍接收正常同批值，统一阻止 callback。
            if let Some(error) = error {
                registry.input_error.get_or_insert(error);
                continue;
            }

            // 禁用日期/布尔先暴露解码值；登记恢复旧值，不分派自身 callback。
            if let Some(record) = registry.records.get_mut(&widget.id)
                && record.disabled
                && matches!(record.codec, Codec::DateInput { .. } | Codec::Bool)
                && let Some(value) = record.codec.decode_state(&widget, record.empty_input.as_ref()).filter(|value| record.codec.valid(value))
            {
                record.before_input = Some(record.value.clone());
                record.value = value.clone();
                if let Some(key) = &record.key {
                    values.insert(key.clone(), value);
                }
                if matches!(record.codec, Codec::Bool) || !matches!(widget.value.as_ref(), Some(widget_state::Value::StringValue(_))) {
                    continue;
                }
            }

            if registry.records.get(&widget.id).is_none_or(|record| record.disabled) {
                if !registry.records.contains_key(&widget.id) && !widget.id.starts_with("$$ID") && !widget.id.starts_with("$$STREAMLIT_INTERNAL_KEY") && !registry.unknown_keys.contains(&widget.id) {
                    registry.unknown_keys.push(widget.id.clone());
                }

                if registry.records.get(&widget.id).is_some_and(|record| record.disabled && matches!(record.codec, Codec::Select(_))) {
                    let unhashable_type = match widget.value.as_ref() {
                        Some(widget_state::Value::StringArrayValue(_) | widget_state::Value::IntArrayValue(_) | widget_state::Value::DoubleArrayValue(_)) => Some("google._upb._message.RepeatedScalarContainer"),
                        Some(widget_state::Value::JsonValue(value)) => match serde_json::from_str::<Value>(value) {
                            Ok(Value::Array(_)) => Some("list"),
                            Ok(Value::Object(_)) => Some("dict"),
                            _ => None,
                        },
                        _ => None,
                    };
                    if let Some(kind) = unhashable_type {
                        registry.input_error.get_or_insert_with(|| WidgetInputError::type_error(format!("cannot use '{kind}' as a dict key (unhashable type: '{kind}')")));
                    }
                }
                // Applied at registration, like the reference's lazy
                // widget-state application.
                registry.pending.push(widget);
                continue;
            }
            let Some(record) = registry.records.get_mut(&widget.id) else { continue };
            let Some(value) = record.codec.decode_state(&widget, record.empty_input.as_ref()) else { continue };
            record.before_input = Some(record.value.clone());
            // 仅在有 callback 时比较原生返回值，重复选项的索引可不同。
            let changed = record.callback.is_some()
                && if matches!(&record.codec, Codec::Select(_) | Codec::MultiSelect(_) | Codec::Radio(_)) {
                    record.codec.session_value(&record.value) != record.codec.session_value(&value)
                } else {
                    record.value != value
                };
            record.value = value.clone();
            if let Some(key) = &record.key {
                values.insert(key.clone(), record.codec.session_value(&value));
            }
            if changed && let Some(callback) = &record.callback {
                callbacks.push(callback.clone());
            }

            // 启用日期也保留原字符串包，callback 后由登记触发重新序列化错误。
            if matches!(record.codec, Codec::DateInput { .. }) && matches!(widget.value.as_ref(), Some(widget_state::Value::StringValue(text)) if !text.is_empty()) {
                registry.pending.push(widget);
            }
        }

        if registry.input_error.is_some() {
            // 5. 解码失败使变化判断中止，本轮 callback 尚未分派。
            callbacks.clear();
        }

        callbacks
    }

    pub(crate) fn widget_input_error(&self) -> Option<WidgetInputError> {
        self.widgets.lock().input_error.clone()
    }

    /// An internal rerun has no fresh frontend batch or callback dispatch.
    pub(crate) fn continue_widgets(&self) {
        let mut registry = self.widgets.lock();
        registry.active = true;
        registry.seen.clear();
        registry.keys.clear();
        registry.registration_error = None;
    }

    pub(crate) fn register_widget<T>(&self, spec: WidgetSpec<'_>, resolve: impl Fn(&Value) -> Result<T, WidgetError>) -> Result<(String, T, bool), WidgetError> {
        let WidgetSpec { kind, key, .. } = spec;
        let identity_fields = serde_json::to_string(&(kind, spec.identity, key))?;
        let id = format!("$$ID-{}-{}", crate::utils::hash::hash(&identity_fields), key.unwrap_or("None"));
        self.register_widget_with_id(spec, &id, resolve)
    }

    /// Registration under an externally derived id — the bidi component's
    /// trigger aggregator ($$STREAMLIT_INTERNAL_KEY_<widget-id>__events),
    /// whose id the frontend recomputes from the state widget's id.
    pub(crate) fn register_widget_with_id<T>(&self, spec: WidgetSpec<'_>, id: &str, resolve: impl Fn(&Value) -> Result<T, WidgetError>) -> Result<(String, T, bool), WidgetError> {
        let WidgetSpec {
            disabled,
            query,
            kind,
            key,
            identity: _,
            default,
            codec,
            callback,
        } = spec;
        let id = id.to_owned();
        // Text codec 也供 data_editor 使用；文本缺省解码仅限这两类输入控件。
        let empty_input = (matches!(
            codec,
            Codec::Bool | Codec::Select(_) | Codec::SelectCreation(_) | Codec::Radio(_) | Codec::Feedback { .. } | Codec::NumberInput { .. } | Codec::TimeInput { .. } | Codec::DateTimeInput { .. } | Codec::DateInput { .. }
        ) || (matches!(kind, "text_input" | "text_area") && matches!(codec, Codec::Text { .. })))
        .then(|| default.clone());
        let mut registry = self.widgets.lock();
        if registry.registration_error.is_some() {
            return Ok((String::new(), resolve(&default)?, false));
        }

        // 文本控件读取 filtered_state 时，未知普通 ID 缺 metadata，callback 已执行。
        if matches!(kind, "text_input" | "text_area")
            && let Some(key) = registry.unknown_keys.iter().find(|key| !registry.records.contains_key(*key) && !self.values.lock().contains_key(*key))
        {
            let message = crate::utils::python_error_value(&format!(
                "st.session_state has no key \"{key}\". Did you forget to initialize it? More info: https://docs.streamlit.io/develop/concepts/architecture/session-state#initialization"
            ));
            registry.registration_error = Some(RegistrationError {
                error: WidgetInputError { kind: "KeyError", message: message.clone() },
                rendered: false,
            });
            return Err(WidgetError::InvalidValue(message));
        }

        // 禁用选择控件的错误包和日期字符串包在 URL 初始化前重新序列化；不同 wire 类型
        // 产生各自的 Python TypeError，此时其他控件 callback 已执行。
        let scalar_error = if registry.records.get(&id).is_some_and(|record| record.disabled || matches!(codec, Codec::DateInput { .. })) {
            registry.pending.iter().find(|state| state.id == id).and_then(|state| match (&codec, state.value.as_ref()) {
                (Codec::Select(_), Some(widget_state::Value::BoolValue(_) | widget_state::Value::IntValue(_) | widget_state::Value::TriggerValue(_))) => Some("'str' object cannot be interpreted as an integer"),
                (Codec::Select(_), Some(widget_state::Value::DoubleValue(_))) => Some("must be real number, not str"),
                (Codec::Select(_), Some(widget_state::Value::BytesValue(_))) => Some("expected bytes, str found"),
                (Codec::DateInput { .. }, Some(widget_state::Value::StringValue(text))) if !text.is_empty() => Some("bad argument type for built-in operation"),
                _ => None,
            })
        } else {
            None
        };
        if let Some(message) = scalar_error {
            let message = message.to_owned();
            registry.registration_error = Some(RegistrationError {
                error: WidgetInputError::type_error(message.clone()),
                rendered: false,
            });
            return Err(WidgetError::InvalidValue(message));
        }

        if let Some(key) = key
            && registry.keys.contains(key)
        {
            return Err(WidgetError::DuplicateKey(key.into()));
        }
        if registry.seen.contains(&id) {
            return Err(WidgetError::DuplicateId(id));
        }
        let mut values = self.values.lock();
        // 1. URL 初值、前端提交和代码赋值在注册时统一决定，不覆盖其他控件。
        let query_default = query.map(|_| default.clone());
        let had_record = registry.records.contains_key(&id);
        let code_assigned = key.is_some_and(|key| registry.dirty_keys.contains(key));
        let query_seed = if let (Some(binding), Some(key)) = (query, key) {
            let mut params = self.query_params.lock();
            let history = params.history_navigation;
            let can_seed = history || ((!registry.received.contains(&id) || disabled) && (!had_record || !code_assigned));
            if can_seed {
                let parsed = params.initial_value(key).and_then(|text| codec.query_value(text, binding.clearable));
                match parsed {
                    Some(value) if value != default => {
                        if let Some(text) = codec.query_text(&value)
                            && params.initial_value(key) != Some(text.as_str())
                        {
                            params.set_binding_value(key, text);
                        }

                        Some(value)
                    }
                    _ => {
                        if params.initial_value(key).is_some() {
                            params.remove_binding(key);
                        }
                        history.then(|| default.clone())
                    }
                }
            } else {
                None
            }
        } else {
            None
        };
        if matches!(codec, Codec::Trigger | Codec::Files { .. } | Codec::ChatInput | Codec::StringTrigger(_) | Codec::ButtonColumn) && key.is_some_and(|key| values.contains_key(key)) && !registry.records.contains_key(&id) {
            return Err(WidgetError::InvalidValue("button, chat input, menu button and uploader state cannot be preseeded".into()));
        }
        // A constraint-dependent identity change resets the old widget binding.
        let changed_identity = key.is_some_and(|key| registry.records.iter().any(|(old_id, record)| old_id != &id && record.key.as_deref() == Some(key)));

        // 旧控件已清理但用户键仍有值：重新挂载时恢复原生值，而非新代码赋值。
        let restored_native = !had_record && !changed_identity && !code_assigned && key.is_some_and(|key| values.contains_key(key));
        let restored_default = restored_native.then(|| default.clone());

        // A state the browser sent while this widget was not registered
        // (for example on a run that rendered another page) applies here,
        // exactly like begin_widgets would have applied it to the record.
        // on_change callbacks of these late applications do not run.
        let pending_value = registry
            .pending
            .iter()
            .position(|state| state.id == id)
            .map(|position| registry.pending.remove(position))
            .filter(|_| !disabled)
            .and_then(|state| codec.decode_state(&state, empty_input.as_ref()))
            .filter(|applied| codec.valid(applied));

        // 数字控件的范围重置保留本轮默认值，不改变其他 codec 的错误路径。
        let number_default = matches!(codec, Codec::NumberInput { .. }).then(|| default.clone());
        let selection_default = matches!(codec, Codec::Radio(_) | Codec::Select(_) | Codec::ButtonGroup { multi: false, filter_invalid: true, .. }).then(|| default.clone());
        let mut selection_reset = false;
        let url_resolved = query_seed.is_some();
        let value = if let Some(value) = query_seed {
            value
        } else {
            let base_value = if disabled && registry.received.contains(&id) && !code_assigned {
                registry.records.get(&id).map(|record| record.before_input.as_ref().unwrap_or(&record.value).clone()).unwrap_or(default)
            } else if changed_identity && !code_assigned {
                default
            } else if one_shot_reset(&codec).is_some() {
                registry.records.get(&id).map(|record| record.value.clone()).unwrap_or(default)
            } else {
                if let Some(key) = key
                    && let Some(native) = values.get(key)
                {
                    // 普通选择控件的失效原生值恢复有效默认；创建模式和其他 codec 保持各自规则。
                    let reset_default = match (&codec, native, &selection_default) {
                        (Codec::Radio(options), Value::String(label), Some(default)) if !options.contains(label) => Some(default),

                        (Codec::Select(options), native, Some(default)) if !native.is_null() && !options.iter().any(|(label, value)| value == native || native.as_str() == Some(label)) => Some(default),

                        (Codec::ButtonGroup { options, multi: false, filter_invalid: true }, Value::String(label), Some(default)) if !options.iter().any(|(text, _)| text == label) => Some(default),

                        _ => None,
                    };
                    if let Some(default) = reset_default {
                        selection_reset = true;
                        default.clone()
                    } else {
                        let value = codec.read_session_value(native, if registry.dirty_keys.contains(key) { None } else { registry.records.get(&id) })?;
                        // 多选逐项移除失效原生值，并将过滤后的标签同步给前端。
                        if matches!(codec, Codec::MultiSelect(_) | Codec::ButtonGroup { multi: true, filter_invalid: true, .. }) && codec.session_value(&value) != *native {
                            selection_reset = true;
                        }
                        value
                    }
                } else if key.is_none()
                    && let Codec::Select(options) = &codec
                    && let Some(record) = registry.records.get(&id)
                {
                    // 标签保持身份时，仍存在的旧原生值按本轮选项顺序重映射。
                    let native = record.codec.session_value(&record.value);
                    if native.is_null() || options.iter().any(|(_, value)| value == &native) {
                        codec.read_session_value(&native, Some(record))?
                    } else {
                        record.value.clone()
                    }
                } else {
                    registry.records.get(&id).map(|record| record.value.clone()).unwrap_or(default)
                }
            };
            pending_value.unwrap_or(base_value)
        };
        let (value, range_reset) = match (&codec, number_default) {
            (Codec::NumberInput { min, max, integer }, Some(default))
                if value
                    .as_f64()
                    .is_some_and(|number| number.is_finite() && (!*integer || value.as_i64().is_some()) && (min.is_some_and(|low| number < low) || max.is_some_and(|high| number > high))) =>
            {
                (default, true)
            }

            (Codec::DateTimeInput { min, max, reset_default: Some(default) }, _) if value.as_str().and_then(|text| chrono::NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M").ok()).is_some_and(|moment| moment < *min || moment > *max) => {
                (default.clone(), true)
            }

            // 显式边界同时校验单值/范围模式；先回本轮默认，再检查返回类型。
            (Codec::DateInput { range, default, reset_native: true, .. }, _) if !value.is_null() && (if *range { !value.is_array() || value.as_array().is_some_and(Vec::is_empty) } else { !value.is_string() }) => (default.clone(), true),

            (
                Codec::DateInput {
                    range: false,
                    min,
                    max,
                    default,
                    reset_native: true,
                },
                _,
            ) if value.as_str().and_then(|text| chrono::NaiveDate::parse_from_str(text, "%Y-%m-%d").ok()).is_some_and(|date| date < *min || date > *max) => (default.clone(), true),

            (
                Codec::DateInput {
                    range: true,
                    min,
                    max,
                    default,
                    reset_native: true,
                },
                _,
            ) if value.as_array().is_some_and(|dates| {
                let parse = |value: &Value| value.as_str().and_then(|text| chrono::NaiveDate::parse_from_str(text, "%Y-%m-%d").ok());
                dates.first().and_then(parse).is_some_and(|date| date < *min) || dates.last().and_then(parse).is_some_and(|date| date > *max)
            }) =>
            {
                (default.clone(), true)
            }

            _ => (value, false),
        };

        if !codec.valid(&value) {
            return Err(WidgetError::InvalidValue(format!("value does not match {kind}")));
        }
        // Resolve every fallible native conversion before committing a key,
        // record or value. Resolvers here only convert built-in scalar/index
        // types; user callbacks and option cloning never run under these locks.
        let resolved = resolve(&value)?;
        let restored_value = restored_default.as_ref().is_some_and(|default| &value != default);
        let set_value = restored_value || range_reset || selection_reset || url_resolved || code_assigned || (disabled && registry.received.contains(&id));
        // 2. 默认值折叠不重复广播前端已经清空的 URL；代码改值则显式同步。
        if query.is_some()
            && let Some(key) = key
        {
            let mut params = self.query_params.lock();
            if query_default.as_ref() == Some(&value) {
                if code_assigned && !url_resolved && had_record {
                    params.remove_binding(key);
                } else {
                    params.remove(key);
                }
            } else if !url_resolved
                && (restored_value || (code_assigned && had_record))
                && let Some(text) = codec.query_text(&value)
            {
                params.set_binding_value(key, text);
            }
        }
        if let Some(key) = key {
            values.insert(key.into(), codec.session_value(&value));
            registry.keys.insert(key.into());
        }
        registry.seen.insert(id.clone());
        registry.active = true;
        let query_bound = registry.records.get(&id).is_some_and(|record| record.query_bound);
        registry.records.insert(
            id.clone(),
            Record {
                key: key.map(str::to_owned),
                value: value.clone(),
                codec,
                callback,
                query_bound,

                disabled,
                before_input: None,
                empty_input,
            },
        );
        Ok((id, resolved, set_value))
    }

    pub(crate) fn take_registration_error(&self) -> Option<WidgetInputError> {
        let mut registry = self.widgets.lock();
        let error = registry.registration_error.as_mut()?;
        if error.rendered {
            return None;
        }
        error.rendered = true;
        Some(error.error.clone())
    }

    pub(crate) fn set_query_binding(&self, id: &str, bound: bool) {
        let removed_key = {
            let mut registry = self.widgets.lock();
            let Some(record) = registry.records.get_mut(id) else { return };
            let removed_key = (record.query_bound && !bound).then(|| record.key.clone()).flatten();
            record.query_bound = bound;
            removed_key
        };
        if let Some(key) = removed_key {
            self.query_params.lock().remove_binding(&key);
        }
    }

    pub(crate) fn finish_widgets(&self) {
        // 1. 快照本轮仍存活的键与绑定，避免旧身份删除新控件的 URL。
        let mut registry = self.widgets.lock();
        let mut values = self.values.lock();
        let rerun = self.run_control() == Some(crate::session::RunControl::Rerun);
        let stopped = self.run_control() == Some(crate::session::RunControl::Stop);
        let preserve_unseen = rerun || stopped || registry.registration_error.is_some() || registry.input_error.is_some();

        let seen = registry.seen.clone();
        let live_keys = registry.keys.clone();
        let live_bound: HashSet<String> = registry.records.iter().filter(|(id, record)| seen.contains(*id) && record.query_bound).filter_map(|(_, record)| record.key.clone()).collect();
        let mut removed_bindings = Vec::new();

        // 2. 删除失效记录，重置一次性触发状态。
        registry.records.retain(|id, record| {
            record.before_input = None;
            if !preserve_unseen && !seen.contains(id) {
                if record.query_bound
                    && let Some(key) = &record.key
                    && !live_bound.contains(key)
                {
                    removed_bindings.push(key.clone());
                }
                if let Some(key) = &record.key
                    && !live_keys.contains(key)
                    && !record.query_bound
                {
                    values.remove(key);
                }
                return false;
            }
            // stop 跳过轮末触发器重置；下一次真实输入开始时仍正常重置。
            if !stopped && let Some(reset) = one_shot_reset(&record.codec) {
                record.value = reset.clone();
                if let Some(key) = &record.key {
                    values.insert(key.clone(), reset);
                }
            }
            true
        });
        registry.active = false;
        if !rerun {
            registry.dirty_keys.clear();
        }

        // 3. 释放控件锁后清理失效 URL，由调用方在结束帧前统一发送。
        drop(values);
        drop(registry);
        let mut query = self.query_params.lock();
        for key in removed_bindings {
            query.remove_binding(&key);
        }
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn repeated_widget_ids_use_last_payload_before_validation() -> anyhow::Result<()> {
        let state = SessionState::default();
        let callback: WidgetCallback = Arc::new(|_| {});
        let register = |key: &'static str, callback: WidgetCallback| {
            state.register_widget(
                WidgetSpec {
                    kind: "checkbox",
                    key: Some(key),
                    disabled: false,
                    query: None,
                    identity: "stable",
                    default: Value::Bool(false),
                    codec: Codec::Bool,
                    callback: Some(callback),
                },
                |value| Ok(value.clone()),
            )
        };
        let first = register("first", callback.clone())?.0;
        let peer_callback: WidgetCallback = Arc::new(|_| {});
        let peer = register("peer", peer_callback.clone())?.0;
        state.finish_widgets();

        // 首次 ID 位置决定顺序；最终完整包覆盖此前坏 JSON。
        let callbacks = state.begin_widgets(vec![
            WidgetState {
                id: first.clone(),
                value: Some(widget_state::Value::JsonValue("{".into())),
            },
            WidgetState {
                id: peer,
                value: Some(widget_state::Value::BoolValue(true)),
            },
            WidgetState {
                id: first.clone(),
                value: Some(widget_state::Value::BoolValue(true)),
            },
        ]);
        assert!(state.widget_input_error().is_none());
        assert_eq!(state.get::<bool>("first")?, Some(true));
        assert_eq!(callbacks.len(), 2);
        assert!(Arc::ptr_eq(&callbacks[0], &callback));
        assert!(Arc::ptr_eq(&callbacks[1], &peer_callback));
        register("first", callback)?;
        register("peer", peer_callback)?;
        state.finish_widgets();

        // ID-only 也覆盖整个包，按已有缺省解码回默认值。
        let callbacks = state.begin_widgets(vec![
            WidgetState {
                id: first.clone(),
                value: Some(widget_state::Value::BoolValue(true)),
            },
            WidgetState { id: first, value: None },
        ]);
        assert_eq!(state.get::<bool>("first")?, Some(false));
        assert_eq!(callbacks.len(), 1);
        Ok(())
    }

    #[test]
    fn first_json_or_select_error_matches_sdk_input_order() -> anyhow::Result<()> {
        let reference: Value = serde_json::from_str(include_str!("../../tests/reference/reference-browser/widget-params/trace.json"))?;
        let cases = reference["json_input_errors_reference"]["priority_cases"].as_array().ok_or_else(|| anyhow::anyhow!("priority cases"))?;
        assert_eq!(cases.len(), 2);
        for case in cases {
            let state = SessionState::default();
            let flag = state
                .register_widget(
                    WidgetSpec {
                        kind: "checkbox",
                        key: Some("flag"),
                        disabled: false,
                        query: None,
                        identity: "stable",
                        default: Value::Bool(false),
                        codec: Codec::Bool,
                        callback: None,
                    },
                    |value| Ok(value.clone()),
                )?
                .0;
            let frozen = state
                .register_widget(
                    WidgetSpec {
                        kind: "selectbox",
                        key: Some("frozen"),
                        disabled: true,
                        query: None,
                        identity: "stable",
                        default: Value::from(0),
                        codec: Codec::Select(vec![("a".into(), Value::String("a".into())), ("b".into(), Value::String("b".into()))]),
                        callback: None,
                    },
                    |value| Ok(value.clone()),
                )?
                .0;
            state.finish_widgets();
            let json = WidgetState {
                id: flag,
                value: Some(widget_state::Value::JsonValue("{".into())),
            };
            let select = WidgetState {
                id: frozen,
                value: Some(widget_state::Value::StringArrayValue(crate::proto::StringArray { data: vec!["a".into()] })),
            };
            assert!(state.begin_widgets(if case["json_first"] == true { vec![json, select] } else { vec![select, json] }).is_empty());
            let error = state.widget_input_error().ok_or_else(|| anyhow::anyhow!("missing first error"))?;
            assert_eq!(error.kind, case["error_type"]);
            assert_eq!(error.message, case["error"]);
            state.finish_widgets();
        }
        Ok(())
    }

    #[test]
    fn json_input_syntax_and_character_positions_match_sdk() -> anyhow::Result<()> {
        let reference: Value = serde_json::from_str(include_str!("../../tests/reference/reference-browser/widget-params/trace.json"))?;
        let cases = reference["json_input_errors_reference"]["syntax_cases"].as_array().ok_or_else(|| anyhow::anyhow!("syntax cases"))?;
        assert_eq!(cases.len(), 293);
        for case in cases {
            let text = case["input"].as_str().ok_or_else(|| anyhow::anyhow!("syntax input"))?;
            let error = widget_json_error(text);
            if case["accepted"] == true {
                assert!(error.is_none(), "{}: {text:?}", case["name"]);
            } else {
                let error = error.ok_or_else(|| anyhow::anyhow!("{} must be rejected", case["name"]))?;
                assert_eq!(error.kind, case["error_type"], "{}: {text:?}", case["name"]);
                assert_eq!(error.message, case["error"], "{}: {text:?}", case["name"]);
            }
        }
        Ok(())
    }

    #[test]
    fn malformed_json_latches_before_callbacks_and_before_repair_input() -> anyhow::Result<()> {
        let reference: Value = serde_json::from_str(include_str!("../../tests/reference/reference-browser/widget-params/trace.json"))?;
        let cases = reference["json_input_errors_reference"]["cases"].as_array().ok_or_else(|| anyhow::anyhow!("JSON error cases"))?;
        assert_eq!(cases.len(), 96);

        for case in cases {
            let state = SessionState::default();
            let target = case["key"].as_str().ok_or_else(|| anyhow::anyhow!("target"))?;
            let partner = case["partner"].as_str().ok_or_else(|| anyhow::anyhow!("partner"))?;
            let register = |key: &str| {
                state.register_widget(
                    WidgetSpec {
                        kind: if key == "peer" {
                            "text_input"
                        } else if key.starts_with("cb") {
                            "checkbox"
                        } else {
                            "toggle"
                        },
                        key: Some(key),
                        disabled: key != "peer" && case["disabled"] == true,
                        query: None,
                        identity: "stable",
                        default: if key == "peer" { Value::String("base".into()) } else { Value::Bool(key.ends_with('1')) },
                        codec: if key == "peer" { Codec::Text { max_chars: None } } else { Codec::Bool },
                        callback: Some(Arc::new(|_| {})),
                    },
                    |value| Ok(value.clone()),
                )
            };
            let target_id = register(target)?.0;
            let partner_id = register(partner)?.0;
            state.finish_widgets();
            let submitted = WidgetState {
                id: target_id.clone(),
                value: Some(widget_state::Value::JsonValue(case["input"].as_str().ok_or_else(|| anyhow::anyhow!("input"))?.into())),
            };
            let expected_partner = &case["errors"][0]["partner"];
            let peer = WidgetState {
                id: partner_id,
                value: Some(if let Some(text) = expected_partner.as_str() {
                    widget_state::Value::StringValue(text.into())
                } else {
                    widget_state::Value::BoolValue(expected_partner.as_bool().ok_or_else(|| anyhow::anyhow!("bool partner"))?)
                }),
            };
            assert!(state.begin_widgets(if case["peer_first"] == true { vec![peer, submitted] } else { vec![submitted, peer] }).is_empty());
            assert!(state.widget_input_error().is_some(), "{}", case["name"]);
            assert_eq!(state.get::<Value>(partner)?.as_ref(), Some(expected_partner), "{}", case["name"]);
            state.finish_widgets();

            assert!(
                state
                    .begin_widgets(vec![WidgetState {
                        id: target_id,
                        value: Some(widget_state::Value::BoolValue(true))
                    }])
                    .is_empty()
            );
            assert!(state.widget_input_error().is_some());
            state.finish_widgets();
        }
        Ok(())
    }

    #[test]
    fn bool_json_values_and_rejections_match_frozen_sdk() -> anyhow::Result<()> {
        let reference: Value = serde_json::from_str(include_str!("../../tests/reference/reference-browser/widget-params/trace.json"))?;
        let reference = &reference["bool_json_reference"];
        let cases = reference["cases"].as_array().ok_or_else(|| anyhow::anyhow!("JSON cases"))?;
        assert_eq!(cases.len(), 172);

        for case in cases {
            let key = case["key"].as_str().ok_or_else(|| anyhow::anyhow!("key"))?;
            let index = ["cb0", "cb1", "tg0", "tg1"].iter().position(|candidate| *candidate == key).ok_or_else(|| anyhow::anyhow!("target"))?;
            let wire = WidgetState {
                id: "json".into(),
                value: Some(widget_state::Value::JsonValue(case["input"].as_str().ok_or_else(|| anyhow::anyhow!("input"))?.into())),
            };
            assert_eq!(Codec::Bool.decode_state(&wire, Some(&Value::Bool(key.ends_with('1')))).as_ref(), Some(&case["expected"][0]["values"][index]), "{}", case["name"]);
        }

        let rejected = reference["rejections"].as_array().ok_or_else(|| anyhow::anyhow!("rejections"))?;
        assert_eq!(rejected.len(), 32);
        for case in rejected {
            let text = case["input"].as_str().ok_or_else(|| anyhow::anyhow!("rejected input"))?;
            assert!(Codec::Bool.decode(&widget_state::Value::JsonValue(text.into())).is_none(), "{text:?}");
        }

        Ok(())
    }

    #[test]
    fn disabled_bool_exposes_transient_value_then_restores_at_registration() -> anyhow::Result<()> {
        use prost::Message;
        let reference: Value = serde_json::from_str(include_str!("../../tests/reference/reference-browser/widget-params/trace.json"))?;
        let cases = reference["bool_disabled_reference"]["cases"].as_array().ok_or_else(|| anyhow::anyhow!("missing disabled bool cases"))?;
        assert_eq!(cases.len(), 176);

        for case in cases {
            let key = case["key"].as_str().ok_or_else(|| anyhow::anyhow!("key"))?;
            let index = ["cb0", "cb1", "tg0", "tg1"].iter().position(|candidate| *candidate == key).ok_or_else(|| anyhow::anyhow!("target"))?;
            let state = SessionState::default();
            let default = Value::Bool(key.ends_with('1'));
            let register = || {
                state.register_widget(
                    WidgetSpec {
                        kind: if key.starts_with("cb") { "checkbox" } else { "toggle" },
                        key: Some(key),
                        disabled: true,
                        query: None,
                        identity: "stable",
                        default: default.clone(),
                        codec: Codec::Bool,
                        callback: Some(Arc::new(|_| {})),
                    },
                    |value| Ok(value.clone()),
                )
            };
            let target_id = register()?.0;
            let peer_id = state
                .register_widget(
                    WidgetSpec {
                        kind: "text_input",
                        key: Some("peer"),
                        disabled: false,
                        query: None,
                        identity: "stable",
                        default: Value::String("base".into()),
                        codec: Codec::Text { max_chars: None },
                        callback: Some(Arc::new(|_| {})),
                    },
                    |value| Ok(value.clone()),
                )?
                .0;
            state.finish_widgets();
            let bytes = serde_json::from_value::<Vec<u8>>(case["input_bytes"].clone())?;
            let mut target = WidgetState::decode(bytes.as_slice())?;
            target.id = target_id;
            let callbacks = state.begin_widgets(vec![
                target,
                WidgetState {
                    id: peer_id,
                    value: Some(widget_state::Value::StringValue("submit".into())),
                },
            ]);
            assert_eq!(callbacks.len(), 1, "{}", case["name"]);
            assert_eq!(state.get::<Value>(key)?.as_ref(), Some(&case["expected"][0]["calls"][0][index + 1]), "{}: before peer callback", case["name"]);
            assert_eq!(register()?.1, default, "{}: returned value", case["name"]);
            assert_eq!(state.get::<Value>(key)?, Some(default), "{}: restored native value", case["name"]);
            state.finish_widgets();
        }
        Ok(())
    }

    #[test]
    fn checkbox_and_toggle_coercion_matches_frozen_sdk() -> anyhow::Result<()> {
        use prost::Message;
        let reference: Value = serde_json::from_str(include_str!("../../tests/reference/reference-browser/widget-params/trace.json"))?;
        let cases = reference["bool_coercion_reference"]["cases"].as_array().ok_or_else(|| anyhow::anyhow!("missing bool cases"))?;
        assert_eq!(cases.len(), 176);

        for case in cases {
            let key = case["key"].as_str().ok_or_else(|| anyhow::anyhow!("key"))?;
            let index = ["cb0", "cb1", "tg0", "tg1"].iter().position(|candidate| *candidate == key).ok_or_else(|| anyhow::anyhow!("target"))?;
            let bytes = serde_json::from_value::<Vec<u8>>(case["input_bytes"].clone())?;
            let wire = WidgetState::decode(bytes.as_slice())?;
            let expected = &case["expected"][0]["values"][index];
            assert_eq!(Codec::Bool.decode_state(&wire, Some(&Value::Bool(key.ends_with('1')))).as_ref(), Some(expected), "{}", case["name"]);
        }

        Ok(())
    }

    #[test]
    fn temporal_lexical_inputs_match_frozen_sdk_defaults() -> anyhow::Result<()> {
        let reference: Value = serde_json::from_str(include_str!("../../tests/reference/reference-browser/temporal-params/trace.json"))?;
        let cases = reference["lexical_reference"]["cases"].as_array().ok_or_else(|| anyhow::anyhow!("missing lexical cases"))?;
        assert_eq!(cases.len(), 75);

        for case in cases {
            let kind = case["kind"].as_str().ok_or_else(|| anyhow::anyhow!("kind"))?;
            let text = case["input"].as_str().ok_or_else(|| anyhow::anyhow!("input"))?;
            let (codec, default, wire) = match kind {
                "date" => (
                    Codec::DateInput {
                        range: false,
                        min: NaiveDate::from_ymd_opt(2024, 1, 1).expect("valid reference minimum"),
                        max: NaiveDate::from_ymd_opt(2026, 12, 31).expect("valid reference maximum"),
                        reset_native: false,
                        default: Value::String("2025-03-15".into()),
                    },
                    Value::String("2025-03-15".into()),
                    widget_state::Value::StringArrayValue(crate::proto::StringArray { data: vec![text.into()] }),
                ),
                "datetime" => (
                    Codec::DateTimeInput {
                        min: NaiveDate::from_ymd_opt(2024, 1, 1).expect("valid reference minimum").and_hms_opt(0, 0, 0).expect("valid midnight"),
                        max: NaiveDate::from_ymd_opt(2026, 12, 31).expect("valid reference maximum").and_hms_opt(23, 59, 0).expect("valid final minute"),
                        reset_default: None,
                    },
                    Value::String("2025-03-15T12:30".into()),
                    widget_state::Value::StringArrayValue(crate::proto::StringArray { data: vec![text.into()] }),
                ),
                _ => (
                    Codec::TimeInput { step: if kind == "minute" { 900 } else { 1 } },
                    Value::String(if kind == "minute" { "12:30" } else { "12:30:45" }.into()),
                    widget_state::Value::StringValue(text.into()),
                ),
            };
            let actual = codec.decode_state(&WidgetState { id: "lexical".into(), value: Some(wire) }, Some(&default));
            let expected = if matches!(kind, "date" | "datetime") { &case["expected"][0] } else { &case["expected"] };
            assert_eq!(actual.as_ref(), Some(expected), "{}: {text:?}", case["name"]);
        }

        Ok(())
    }

    use super::*;

    #[test]
    fn date_nonempty_strings_run_callbacks_before_registration_error_and_recover() -> anyhow::Result<()> {
        let min = NaiveDate::from_ymd_opt(2025, 1, 1).expect("fixture date");
        let max = NaiveDate::from_ymd_opt(2025, 12, 31).expect("fixture date");
        for disabled in [false, true] {
            for range in [false, true] {
                for text in ["bad", "2025-04-10", "日期🧊"] {
                    for peer_first in [false, true] {
                        let state = SessionState::default();
                        state.begin_widgets(Vec::new());
                        let native = |start: &str, end: &str| if range { serde_json::json!([start, end]) } else { serde_json::json!(start) };
                        let default = native("2025-03-15", "2025-03-20");
                        let register_date = |disabled| {
                            state.register_widget(
                                WidgetSpec {
                                    kind: "date_input",
                                    key: Some("day"),
                                    disabled,
                                    query: None,
                                    identity: "stable",
                                    default: default.clone(),
                                    codec: Codec::DateInput {
                                        range,
                                        min,
                                        max,
                                        reset_native: true,
                                        default: default.clone(),
                                    },
                                    callback: Some(Arc::new(|_| {})),
                                },
                                |value| Ok(value.clone()),
                            )
                        };
                        let register_peer = || {
                            state.register_widget(
                                WidgetSpec {
                                    kind: "checkbox",
                                    key: Some("peer"),
                                    disabled: false,
                                    query: None,
                                    identity: "stable",
                                    default: Value::Bool(false),
                                    codec: Codec::Bool,
                                    callback: Some(Arc::new(|_| {})),
                                },
                                |value| Ok(value.clone()),
                            )
                        };
                        state.set("day", native("2025-10-01", "2025-10-20"))?;
                        let date_id = register_date(disabled)?.0;
                        let peer_id = register_peer()?.0;
                        state.finish_widgets();
                        let mut incoming = vec![
                            WidgetState {
                                id: date_id.clone(),
                                value: Some(widget_state::Value::StringValue(text.into())),
                            },
                            WidgetState {
                                id: peer_id.clone(),
                                value: Some(widget_state::Value::BoolValue(true)),
                            },
                        ];
                        if peer_first {
                            incoming.reverse();
                        }

                        // 1. 错误字符串逐字符解析失败，Peer callback 先看到声明默认。
                        assert_eq!(state.begin_widgets(incoming).len(), if disabled { 1 } else { 2 });
                        assert!(state.widget_input_error().is_none());
                        assert_eq!(state.get::<Value>("day")?, Some(default.clone()));
                        assert!(register_date(disabled).is_err());
                        assert_eq!(state.take_registration_error().as_ref().map(|error| error.message.as_str()), Some("bad argument type for built-in operation"));
                        state.finish_widgets();

                        // 2. 登记错误可恢复，临时默认成为保存值，不复活旧 October 值。
                        assert_eq!(
                            state
                                .begin_widgets(vec![WidgetState {
                                    id: peer_id.clone(),
                                    value: Some(widget_state::Value::BoolValue(false))
                                }])
                                .len(),
                            1
                        );
                        let (_, value, sync) = register_date(disabled)?;
                        assert_eq!(value, default);
                        assert!(!sync && state.take_registration_error().is_none());
                        register_peer()?;
                        state.finish_widgets();

                        // 3. 再次声明为启用时沿用上轮策略，下一次正常日期输入继续回调。
                        for (start, end, peer, callbacks) in [("2025-08-01", "2025-08-20", true, if disabled { 1 } else { 2 }), ("2025-11-01", "2025-11-20", false, 2)] {
                            let dates = if range { vec![start.into(), end.into()] } else { vec![start.into()] };
                            assert_eq!(
                                state
                                    .begin_widgets(vec![
                                        WidgetState {
                                            id: date_id.clone(),
                                            value: Some(widget_state::Value::StringArrayValue(crate::proto::StringArray { data: dates }))
                                        },
                                        WidgetState {
                                            id: peer_id.clone(),
                                            value: Some(widget_state::Value::BoolValue(peer))
                                        }
                                    ])
                                    .len(),
                                callbacks
                            );
                            let (_, value, sync) = register_date(false)?;
                            assert_eq!(value, native(start, end), "initial disabled={disabled}");
                            assert!(!sync);
                            register_peer()?;
                            state.finish_widgets();
                        }
                    }
                }
            }
        }
        Ok(())
    }

    #[test]
    fn date_json_exposes_decoded_value_and_respects_registered_disabled_policy() -> anyhow::Result<()> {
        for disabled in [false, true] {
            for range in [false, true] {
                for (text, expected) in [
                    ("null", None),
                    ("\"bad\"", None),
                    ("\"2025-04-10\"", None),
                    ("[\"bad\",7]", None),
                    ("[\"2025-04-10\",\"bad\",{}]", None),
                    ("[\"2025-04-10\",\"2025-04-20\"]", Some(["2025-04-10", "2025-04-20"])),
                    ("[\"2025/04/10\",\"2025/04/20\"]", Some(["2025-04-10", "2025-04-20"])),
                    ("[\"2024-12-31\",\"2025-04-20\"]", None),
                    ("[\"2025-05-20\",\"2025-04-10\"]", Some(["2025-05-20", "2025-04-10"])),
                    ("{\"2025-05-20\":1,\"2025-04-10\":[]}", Some(["2025-05-20", "2025-04-10"])),
                    ("{\"bad\":7,\"2025-04-10\":2}", None),
                    ("{\"2025-05-20\":1,\"2025-04-10\":2,\"2025-05-20\":3}", Some(["2025-05-20", "2025-04-10"])),
                ] {
                    for peer_first in [false, true] {
                        let state = SessionState::default();
                        let native = |dates: [&str; 2]| if range { serde_json::json!(dates) } else { serde_json::json!(dates[0]) };
                        let default = native(["2025-03-15", "2025-03-20"]);
                        let old = native(["2025-10-01", "2025-10-20"]);
                        let register_date = |disabled| {
                            state.register_widget(
                                WidgetSpec {
                                    kind: "date_input",
                                    key: Some("day"),
                                    disabled,
                                    query: None,
                                    identity: "stable",
                                    default: default.clone(),
                                    codec: Codec::DateInput {
                                        range,
                                        min: NaiveDate::from_ymd_opt(2025, 1, 1).expect("fixture date"),
                                        max: NaiveDate::from_ymd_opt(2025, 12, 31).expect("fixture date"),
                                        reset_native: true,
                                        default: default.clone(),
                                    },
                                    callback: Some(Arc::new(|_| {})),
                                },
                                |value| Ok(value.clone()),
                            )
                        };
                        state.set("day", old.clone())?;
                        let id = register_date(disabled)?.0;
                        let (peer_id, _, _) = state.register_widget(
                            WidgetSpec {
                                kind: "checkbox",
                                key: Some("peer"),
                                disabled: false,
                                query: None,
                                identity: "stable",
                                default: Value::Bool(false),
                                codec: Codec::Bool,
                                callback: Some(Arc::new(|_| {})),
                            },
                            |value| Ok(value.clone()),
                        )?;
                        state.finish_widgets();
                        let mut incoming = vec![
                            WidgetState {
                                id: id.clone(),
                                value: Some(widget_state::Value::JsonValue(text.into())),
                            },
                            WidgetState {
                                id: peer_id,
                                value: Some(widget_state::Value::BoolValue(true)),
                            },
                        ];
                        if peer_first {
                            incoming.reverse();
                        }

                        // 1. 同伴 callback 只读取 JSON 反序列化值；禁用日期自身不回调。
                        assert_eq!(state.begin_widgets(incoming).len(), if disabled { 1 } else { 2 });
                        assert!(state.widget_input_error().is_none());
                        let decoded = expected.map_or(default.clone(), native);
                        assert_eq!(state.get::<Value>("day")?, Some(decoded.clone()), "{text}");

                        // 2. 禁用登记恢复原生旧值并同步一次，后续无输入不重复同步。
                        let saved = if disabled { old.clone() } else { decoded };
                        let (_, value, sync) = register_date(disabled)?;
                        assert_eq!(value, saved);
                        assert!(sync == disabled && state.take_registration_error().is_none());
                        state.finish_widgets();
                        assert!(state.begin_widgets(Vec::new()).is_empty());
                        let (_, value, sync) = register_date(disabled)?;
                        assert_eq!(value, saved);
                        assert!(!sync);
                        state.finish_widgets();
                    }
                }
            }
        }
        Ok(())
    }

    #[test]
    fn disabled_date_json_invalid_prefix_stops_before_later_type_errors() -> anyhow::Result<()> {
        for range in [false, true] {
            for text in [r#"["bad",7]"#, r#"["2025-02-30",true]"#, r#"["2025-04-10","bad",{}]"#, r#"["2025/04/10","bad",[]]"#] {
                let state = SessionState::default();
                let default = if range { serde_json::json!(["2025-03-15", "2025-03-20"]) } else { serde_json::json!("2025-03-15") };
                let (id, _, _) = state.register_widget(
                    WidgetSpec {
                        kind: "date_input",
                        key: Some("day"),
                        disabled: true,
                        query: None,
                        identity: "stable",
                        default: default.clone(),
                        codec: Codec::DateInput {
                            range,
                            min: NaiveDate::from_ymd_opt(2025, 1, 1).expect("fixture date"),
                            max: NaiveDate::from_ymd_opt(2025, 12, 31).expect("fixture date"),
                            reset_native: true,
                            default,
                        },
                        callback: None,
                    },
                    |value| Ok(value.clone()),
                )?;
                state.finish_widgets();
                assert!(
                    state
                        .begin_widgets(vec![WidgetState {
                            id,
                            value: Some(widget_state::Value::JsonValue(text.into()))
                        }])
                        .is_empty()
                );
                assert!(state.widget_input_error().is_none(), "{text}");
            }
        }
        Ok(())
    }

    #[test]
    fn date_type_errors_suppress_callbacks_and_block_recovery_for_both_policies() -> anyhow::Result<()> {
        for disabled in [false, true] {
            let min = NaiveDate::from_ymd_opt(2025, 1, 1).expect("fixture date");
            let max = NaiveDate::from_ymd_opt(2025, 12, 31).expect("fixture date");
            for (wire, expected_error) in [
                (widget_state::Value::BoolValue(true), "'bool' object is not iterable"),
                (widget_state::Value::BoolValue(false), "'bool' object is not iterable"),
                (widget_state::Value::TriggerValue(true), "'bool' object is not iterable"),
                (widget_state::Value::TriggerValue(false), "'bool' object is not iterable"),
                (widget_state::Value::IntValue(7), "'int' object is not iterable"),
                (widget_state::Value::DoubleValue(1.5), "'float' object is not iterable"),
                (widget_state::Value::IntArrayValue(crate::proto::SInt64Array { data: vec![7] }), "strptime() argument 1 must be str, not int"),
                (widget_state::Value::DoubleArrayValue(crate::proto::DoubleArray { data: vec![1.5] }), "strptime() argument 1 must be str, not float"),
                (widget_state::Value::BytesValue(vec![b'x']), "strptime() argument 1 must be str, not int"),
                (widget_state::Value::JsonValue("true".into()), "'bool' object is not iterable"),
                (widget_state::Value::JsonValue("false".into()), "'bool' object is not iterable"),
                (widget_state::Value::JsonValue("7".into()), "'int' object is not iterable"),
                (widget_state::Value::JsonValue("1.5".into()), "'float' object is not iterable"),
                (widget_state::Value::JsonValue("[7]".into()), "strptime() argument 1 must be str, not int"),
                (widget_state::Value::JsonValue("[1.5]".into()), "strptime() argument 1 must be str, not float"),
                (widget_state::Value::JsonValue("[true]".into()), "strptime() argument 1 must be str, not bool"),
                (widget_state::Value::JsonValue("[null]".into()), "strptime() argument 1 must be str, not None"),
                (widget_state::Value::JsonValue("[[]]".into()), "strptime() argument 1 must be str, not list"),
                (widget_state::Value::JsonValue("[{}]".into()), "strptime() argument 1 must be str, not dict"),
                (widget_state::Value::JsonValue("[\"2025-04-10\",7]".into()), "strptime() argument 1 must be str, not int"),
                (widget_state::Value::JsonValue("[\"2025-04-10\",true]".into()), "strptime() argument 1 must be str, not bool"),
            ] {
                for range in [false, true] {
                    for peer_first in [false, true] {
                        let state = SessionState::default();
                        let default = if range { serde_json::json!(["2025-03-15", "2025-03-20"]) } else { serde_json::json!("2025-03-15") };
                        let (date_id, _, _) = state.register_widget(
                            WidgetSpec {
                                kind: "date_input",
                                key: Some("day"),
                                disabled,
                                query: None,
                                identity: "stable",
                                default: default.clone(),
                                codec: Codec::DateInput { range, min, max, reset_native: true, default },
                                callback: Some(Arc::new(|_| {})),
                            },
                            |value| Ok(value.clone()),
                        )?;
                        let (peer_id, _, _) = state.register_widget(
                            WidgetSpec {
                                kind: "checkbox",
                                key: Some("peer"),
                                disabled: false,
                                query: None,
                                identity: "stable",
                                default: Value::Bool(false),
                                codec: Codec::Bool,
                                callback: Some(Arc::new(|_| {})),
                            },
                            |value| Ok(value.clone()),
                        )?;
                        state.finish_widgets();
                        let mut incoming = vec![
                            WidgetState { id: date_id.clone(), value: Some(wire.clone()) },
                            WidgetState {
                                id: peer_id.clone(),
                                value: Some(widget_state::Value::BoolValue(true)),
                            },
                        ];
                        if peer_first {
                            incoming.reverse();
                        }

                        // 1. 全部变化判断结束前不分派 callback，正常同伴值已接收。
                        assert!(state.begin_widgets(incoming).is_empty());
                        assert_eq!(state.widget_input_error().map(|error| error.message).as_deref(), Some(expected_error));
                        assert_eq!(state.get::<bool>("peer")?, Some(true));
                        state.finish_widgets();

                        // 2. 原错误持续，正确日期和新的同伴输入也不能恢复该会话。
                        let dates = if range { vec!["2025-04-10".into(), "2025-04-20".into()] } else { vec!["2025-04-10".into()] };
                        assert!(
                            state
                                .begin_widgets(vec![
                                    WidgetState {
                                        id: date_id,
                                        value: Some(widget_state::Value::StringArrayValue(crate::proto::StringArray { data: dates }))
                                    },
                                    WidgetState {
                                        id: peer_id,
                                        value: Some(widget_state::Value::BoolValue(false))
                                    }
                                ])
                                .is_empty()
                        );
                        assert_eq!(state.widget_input_error().map(|error| error.message).as_deref(), Some(expected_error));
                        assert_eq!(state.get::<bool>("peer")?, Some(true));
                        state.finish_widgets();
                    }
                }
            }
        }
        assert!(SessionState::default().widget_input_error().is_none());
        Ok(())
    }

    #[test]
    fn array_input_failure_suppresses_callbacks_and_blocks_later_input() -> anyhow::Result<()> {
        let repeated = "cannot use 'google._upb._message.RepeatedScalarContainer' as a dict key (unhashable type: 'google._upb._message.RepeatedScalarContainer')";
        for (wire, expected_error) in [
            (widget_state::Value::StringArrayValue(crate::proto::StringArray { data: vec!["x".into()] }), repeated),
            (widget_state::Value::IntArrayValue(crate::proto::SInt64Array { data: vec![1] }), repeated),
            (widget_state::Value::DoubleArrayValue(crate::proto::DoubleArray { data: vec![1.5] }), repeated),
            (widget_state::Value::JsonValue(r#"["x"]"#.into()), "cannot use 'list' as a dict key (unhashable type: 'list')"),
            (widget_state::Value::JsonValue(r#"{"x": 1}"#.into()), "cannot use 'dict' as a dict key (unhashable type: 'dict')"),
        ] {
            for reverse_input_order in [false, true] {
                let state = SessionState::default();
                let mut ids = Vec::new();
                for (kind, key, disabled, codec, default) in [
                    ("selectbox", "bound", true, Codec::Select(vec![("x".into(), Value::String("x".into()))]), Value::from(0)),
                    ("text_input", "live", false, Codec::Text { max_chars: None }, Value::String("ready".into())),
                ] {
                    let (id, _, _) = state.register_widget(
                        WidgetSpec {
                            kind,
                            key: Some(key),
                            disabled,
                            query: None,
                            identity: "stable",
                            default,
                            codec,
                            callback: Some(Arc::new(|_| {})),
                        },
                        |value| Ok(value.clone()),
                    )?;
                    ids.push(id);
                }
                state.finish_widgets();

                // 1. 全部变化判断完成前不分派 callback，即使正常输入在数组之前。
                let mut incoming = vec![
                    WidgetState { id: ids[0].clone(), value: Some(wire.clone()) },
                    WidgetState {
                        id: ids[1].clone(),
                        value: Some(widget_state::Value::StringValue("one".into())),
                    },
                ];
                if reverse_input_order {
                    incoming.reverse();
                }
                assert!(state.begin_widgets(incoming).is_empty());
                let error = state.widget_input_error().ok_or_else(|| anyhow::anyhow!("missing array input error"))?.message;
                assert_eq!(error, expected_error);
                assert_eq!(state.get::<String>("live")?.as_deref(), Some("one"));
                state.finish_widgets();

                // 2. 下一轮在状态压缩阶段失败，新输入和 callback 都未应用。
                assert!(
                    state
                        .begin_widgets(vec![
                            WidgetState {
                                id: ids[0].clone(),
                                value: Some(widget_state::Value::StringValue("x".into()))
                            },
                            WidgetState {
                                id: ids[1].clone(),
                                value: Some(widget_state::Value::StringValue("two".into()))
                            },
                        ])
                        .is_empty()
                );
                assert_eq!(state.widget_input_error().map(|error| error.message).as_deref(), Some(error.as_str()));
                assert_eq!(state.get::<String>("live")?.as_deref(), Some("one"));
                state.finish_widgets();
            }
        }

        assert!(SessionState::default().widget_input_error().is_none());
        Ok(())
    }

    #[test]
    fn hidden_query_binding_restores_native_value_and_url_without_new_input() -> Result<(), WidgetError> {
        for (initial_query, expected, sync) in [("bound=url", "url", true), ("", "base", false)] {
            let state = SessionState::default();
            let register = || {
                state.register_widget(
                    WidgetSpec {
                        disabled: false,
                        query: Some(QueryBinding { clearable: true }),
                        kind: "text_input",
                        key: Some("bound"),
                        identity: "bound",
                        default: Value::from("base"),
                        codec: Codec::Text { max_chars: None },
                        callback: None,
                    },
                    |value| Ok(value.clone()),
                )
            };

            state.query_params.lock().load(initial_query);
            state.begin_widgets(vec![]);
            let (id, _, _) = register()?;
            state.set_query_binding(&id, true);
            state.finish_widgets();

            state.query_params.lock().load(initial_query);
            state.begin_widgets(vec![]);
            state.finish_widgets();
            assert_eq!(state.get::<String>("bound")?.as_deref(), Some(expected));
            assert!(state.widgets.lock().records.is_empty());
            assert_eq!(state.query_params.lock().get("bound"), None);

            state.query_params.lock().load("");
            state.begin_widgets(vec![]);
            let (restored_id, value, set_value) = register()?;
            assert_eq!(restored_id, id);
            assert_eq!(value, Value::from(expected));
            assert_eq!(set_value, sync);
            assert_eq!(state.query_params.lock().get("bound"), sync.then_some(expected));
        }
        Ok(())
    }

    #[test]
    fn stop_defers_stale_and_trigger_cleanup_until_the_next_run() -> Result<(), WidgetError> {
        let state = SessionState::default();
        state.query_params.lock().load("bound=url");
        state.begin_widgets(vec![]);
        let mut ids = Vec::new();

        for (kind, key, codec, default, query) in [
            ("text_input", Some("bound"), Codec::Text { max_chars: None }, Value::from("base"), Some(QueryBinding { clearable: true })),
            ("button", Some("trigger"), Codec::Trigger, Value::from(false), None),
            ("number_input", None, Codec::NumberInput { min: None, max: None, integer: true }, Value::from(7), None),
        ] {
            ids.push(
                state
                    .register_widget(
                        WidgetSpec {
                            disabled: false,
                            query,
                            kind,
                            key,
                            identity: kind,
                            default,
                            codec,
                            callback: None,
                        },
                        |value| Ok(value.clone()),
                    )?
                    .0,
            );
        }
        // 公共控件 API 在注册后单独标记查询绑定。
        state.set_query_binding(&ids[0], true);
        state.finish_widgets();

        state.begin_widgets(vec![
            WidgetState {
                id: ids[0].clone(),
                value: Some(widget_state::Value::StringValue("edited".into())),
            },
            WidgetState {
                id: ids[1].clone(),
                value: Some(widget_state::Value::TriggerValue(true)),
            },
        ]);
        state.set_run_control(crate::session::RunControl::Stop);
        state.finish_widgets();

        assert_eq!(state.get::<String>("bound")?.as_deref(), Some("edited"));
        assert_eq!(state.get::<bool>("trigger")?, Some(true));
        assert!(ids.iter().all(|id| state.widgets.lock().records.contains_key(id)));
        assert_eq!(state.query_params.lock().get("bound"), Some("url"));

        state.reset_run_control();
        state.begin_widgets(vec![]);
        assert_eq!(state.get::<bool>("trigger")?, Some(false));
        assert_eq!(state.get::<String>("bound")?.as_deref(), Some("edited"));
        state.finish_widgets();

        assert_eq!(state.get::<String>("bound")?.as_deref(), Some("edited"));
        assert!(state.widgets.lock().records.is_empty());
        assert_eq!(state.query_params.lock().get("bound"), None);
        Ok(())
    }

    #[test]
    fn internal_rerun_preserves_unseen_inputs_and_same_run_assignments() -> Result<(), WidgetError> {
        let state = SessionState::default();
        let register = |key| {
            state.register_widget(
                WidgetSpec {
                    disabled: false,
                    query: None,
                    kind: "text_input",
                    key: Some(key),
                    identity: "stable",
                    default: Value::String("base".into()),
                    codec: Codec::Text { max_chars: None },
                    callback: Some(Arc::new(|_| {})),
                },
                |value| Ok(value.clone()),
            )
        };
        let (id, _, _) = register("text")?;
        state.finish_widgets();
        assert_eq!(
            state
                .begin_widgets(vec![WidgetState {
                    id,
                    value: Some(widget_state::Value::StringValue("edited".into()))
                }])
                .len(),
            1
        );
        state.set_run_control(crate::session::RunControl::Rerun);
        state.finish_widgets();
        state.reset_run_control();
        state.continue_widgets();

        // 1. 未运行到的控件及前端优先级跨内层重跑保留。
        assert_eq!(state.get::<String>("text")?, Some("edited".into()));
        assert_eq!(register("text")?.1, Value::String("edited".into()));
        state.set("assigned", "code")?;
        assert!(register("assigned")?.2);
        state.set_run_control(crate::session::RunControl::Rerun);
        state.finish_widgets();
        state.reset_run_control();
        state.continue_widgets();

        // 2. 同一次交互的代码赋值持续同步；正常结束才清理未渲染控件。
        assert!(register("assigned")?.2);
        state.finish_widgets();
        assert_eq!(state.get::<String>("text")?, None);
        state.begin_widgets(vec![]);
        assert!(!register("assigned")?.2);
        Ok(())
    }

    #[test]
    fn internal_query_rerun_uses_announced_url_instead_of_silent_collapse() -> Result<(), WidgetError> {
        let st = Streamlit::new();
        let state = st.session_state();
        state.query_params.lock().load("bound=y&text=url");
        state.query_params.lock().remove("bound");
        state.query_params.lock().begin_internal_run();
        assert_eq!(st.query_params().get("bound").as_deref(), Some("y"));

        state.query_params.lock().remove("bound");
        st.query_params().set("marker", "announced")?;
        state.query_params.lock().begin_internal_run();
        assert_eq!(st.query_params().get("bound"), None);
        assert_eq!(st.query_params().get("marker").as_deref(), Some("announced"));
        Ok(())
    }

    #[test]
    fn disabled_transitions_use_prior_callback_policy_and_restore_value() -> Result<(), WidgetError> {
        let state = SessionState::default();
        let callback: WidgetCallback = Arc::new(|_| {});
        let register = |disabled| {
            state.register_widget(
                WidgetSpec {
                    disabled,
                    query: None,
                    kind: "checkbox",
                    key: Some("check"),
                    identity: "stable",
                    default: Value::Bool(false),
                    codec: Codec::Bool,
                    callback: Some(callback.clone()),
                },
                |value| Ok(value.clone()),
            )
        };
        let (id, _, _) = register(true)?;
        state.finish_widgets();
        let packet = || {
            vec![WidgetState {
                id: id.clone(),
                value: Some(widget_state::Value::BoolValue(true)),
            }]
        };

        // 1. 上轮禁用不回调；本轮启用仍接受合法输入。
        assert!(state.begin_widgets(packet()).is_empty());
        assert_eq!(register(false)?.1, Value::Bool(true));
        state.finish_widgets();
        let callbacks = state.begin_widgets(vec![WidgetState {
            id: id.clone(),
            value: Some(widget_state::Value::BoolValue(false)),
        }]);
        assert_eq!(callbacks.len(), 1);

        // 2. 本轮禁用恢复输入前值，但保留已经安排的回调。
        let (_, value, set) = register(true)?;
        assert_eq!(value, Value::Bool(true));
        assert!(set);
        state.finish_widgets();
        assert!(state.begin_widgets(packet()).is_empty());
        assert_eq!(register(true)?.1, Value::Bool(true));
        Ok(())
    }

    #[test]
    fn disabled_select_type_error_preserves_other_callback_and_unseen_records() -> Result<(), WidgetError> {
        for (wire, expected_error) in [
            (widget_state::Value::BoolValue(true), "'str' object cannot be interpreted as an integer"),
            (widget_state::Value::IntValue(1), "'str' object cannot be interpreted as an integer"),
            (widget_state::Value::DoubleValue(1.5), "must be real number, not str"),
            (widget_state::Value::BytesValue(Vec::new()), "expected bytes, str found"),
            (widget_state::Value::TriggerValue(true), "'str' object cannot be interpreted as an integer"),
        ] {
            let state = SessionState::default();
            let select = || {
                state.register_widget(
                    WidgetSpec {
                        disabled: true,
                        query: None,
                        kind: "selectbox",
                        key: Some("bound"),
                        identity: "stable",
                        default: Value::from(0),
                        codec: Codec::Select(vec![("x".into(), Value::String("x".into()))]),
                        callback: Some(Arc::new(|_| {})),
                    },
                    |value| Ok(value.clone()),
                )
            };
            let live = || {
                state.register_widget(
                    WidgetSpec {
                        disabled: false,
                        query: None,
                        kind: "text_input",
                        key: Some("live"),
                        identity: "stable",
                        default: Value::String("ready".into()),
                        codec: Codec::Text { max_chars: None },
                        callback: Some(Arc::new(|_| {})),
                    },
                    |value| Ok(value.clone()),
                )
            };
            let (select_id, _, _) = select()?;
            let (live_id, _, _) = live()?;
            state.finish_widgets();

            // 1. 错误禁用包不拒绝正常输入与回调，错误延迟到注册处。
            let callbacks = state.begin_widgets(vec![
                WidgetState { id: select_id, value: Some(wire) },
                WidgetState {
                    id: live_id.clone(),
                    value: Some(widget_state::Value::StringValue("one".into())),
                },
            ]);
            assert_eq!(callbacks.len(), 1);
            assert!(select().is_err());
            assert_eq!(state.take_registration_error().as_ref().map(|error| error.message.as_str()), Some(expected_error));
            assert!(state.take_registration_error().is_none());
            state.finish_widgets();

            // 2. 未运行到的正常控件仍存活，下一轮继续回调并恢复渲染。
            assert_eq!(
                state
                    .begin_widgets(vec![WidgetState {
                        id: live_id,
                        value: Some(widget_state::Value::StringValue("two".into()))
                    }])
                    .len(),
                1
            );
            assert_eq!(select()?.1, Value::from(0));
            assert_eq!(live()?.1, Value::String("two".into()));
            state.finish_widgets();
        }

        Ok(())
    }

    #[test]
    fn query_seed_codecs_keep_clearability_and_option_labels() {
        let text = Codec::Text { max_chars: None };
        assert_eq!(text.query_value("", true), Some(Value::String(String::new())));
        let options = vec![("x".into(), Value::String("x".into())), ("y".into(), Value::String("y".into()))];
        let select = Codec::Select(options.clone());
        assert_eq!(select.query_value("y", false), Some(Value::from(1)));
        assert_eq!(select.query_value("unknown", false), None);
        assert_eq!(select.query_value("", false), None);
        assert_eq!(select.query_value("", true), Some(Value::Null));
        assert_eq!(select.query_text(&Value::from(1)), Some("y".into()));
        let creation = Codec::SelectCreation(options);
        assert_eq!(creation.query_value("new", false), Some(Value::String("new".into())));
        assert_eq!(creation.query_text(&Value::String("new".into())), Some("new".into()));
    }

    #[test]
    fn text_decoding_truncates_codepoints_but_native_values_keep_their_length() {
        let text = Codec::Text { max_chars: Some(5) };
        assert_eq!(text.decode(&widget_state::Value::StringValue("中文🧊e\u{301}TAIL".into())), Some(Value::String("中文🧊e\u{301}".into())));
        assert_eq!(text.decode(&widget_state::Value::StringValue("👨\u{200d}👩\u{200d}👧\u{200d}👦!".into())), Some(Value::String("👨\u{200d}👩\u{200d}👧".into())));
        assert!(text.valid(&Value::String("code長🧊extra".into())));
        assert!(text.valid(&Value::Null));
        assert!(!text.valid(&Value::from(5)));

        let zero = Codec::Text { max_chars: Some(0) };
        assert_eq!(zero.decode(&widget_state::Value::StringValue("text".into())), Some(Value::String(String::new())));

        let unlimited = Codec::Text { max_chars: None };
        assert_eq!(unlimited.decode(&widget_state::Value::StringValue("中文🧊e\u{301}TAIL".into())), Some(Value::String("中文🧊e\u{301}TAIL".into())));
    }

    #[test]
    fn query_seed_does_not_parse_discarded_invalid_session_values() -> Result<(), WidgetError> {
        for history in [false, true] {
            let state = SessionState::default();
            let spec = |query| WidgetSpec {
                disabled: false,
                query,
                kind: "selectbox",
                key: Some("bound"),
                identity: "query-bound-select",
                default: Value::from(0),
                codec: Codec::Select(vec![("x".into(), Value::String("x".into())), ("y".into(), Value::String("y".into()))]),
                callback: None,
            };
            if history {
                state.register_widget(spec(None), |value| Ok(value.clone()))?;
                state.finish_widgets();
                state.begin_widgets(vec![]);
            }
            state.query_params.lock().load("bound=y");
            state.query_params.lock().history_navigation = history;
            state.set("bound", 99)?;
            let (_, value, changed) = state.register_widget(spec(Some(QueryBinding { clearable: false })), |value| Ok(value.clone()))?;
            assert_eq!(value, Value::from(1));
            assert!(changed);
            assert_eq!(state.get::<String>("bound")?, Some("y".into()));
        }
        Ok(())
    }

    #[test]
    fn query_binding_is_retained_until_widget_cleanup_or_explicit_unbind() -> Result<(), WidgetError> {
        for unbind in [false, true] {
            let state = SessionState::default();
            state.query_params.lock().load("bound=hello&other=kept");
            let register = || {
                state.register_widget(
                    WidgetSpec {
                        disabled: false,
                        query: None,
                        kind: "text_input",
                        key: Some("bound"),
                        identity: "bound-text",
                        default: Value::String(String::new()),
                        codec: Codec::Text { max_chars: None },
                        callback: None,
                    },
                    |value| Ok(value.clone()),
                )
            };

            // 1. 正常运行结束保留绑定；下一轮开始仍保护尚未移除的控件。
            let (id, _, _) = register()?;
            state.set_query_binding(&id, true);
            state.finish_widgets();
            state.begin_widgets(vec![]);
            assert!(state.widgets.lock().query_bound("bound"));
            assert!(!state.widgets.lock().query_bound("BOUND"));

            // 2. 显式去掉绑定立即清理；条件隐藏则等到运行结束才清理。
            if unbind {
                let (same_id, _, _) = register()?;
                assert_eq!(same_id, id);
                state.set_query_binding(&same_id, false);
                assert_eq!(state.query_params.lock().serialize(), "other=kept");
            }
            state.finish_widgets();
            assert!(!state.widgets.lock().query_bound("bound"));
            assert_eq!(state.query_params.lock().serialize(), "other=kept");
        }
        Ok(())
    }

    const DATAFRAME_SELECTION_REFERENCE: &str = include_str!("../../tests/reference/reference-browser/dataframe-selection/selection-input-output.json");

    #[test]
    fn dataframe_selection_codec_preserves_frozen_string_states() -> anyhow::Result<()> {
        let reference: Value = serde_json::from_str(DATAFRAME_SELECTION_REFERENCE)?;
        assert_eq!(reference["schema_version"], 1);
        assert_eq!(reference["reference_version"], "1.66.1");
        let stages = reference["stages"].as_array().ok_or_else(|| anyhow::anyhow!("selection reference must contain stages"))?;
        let codec = Codec::DataframeSelection { required_row: false, num_rows: 0 };
        let mut decoded_count = 0;

        // 1. 逐条读取真实 string_value，保留 rows、columns、cells 和缩行后的原位置。
        for stage in stages {
            let incoming = stage["target_widget_states"].as_array().ok_or_else(|| anyhow::anyhow!("selection stage must contain target widget states"))?;
            for widget in incoming {
                assert_eq!(widget["value_oneof"], "string_value");
                let text = widget["value"].as_str().ok_or_else(|| anyhow::anyhow!("selection string_value must be text"))?;
                let decoded = codec.decode(&widget_state::Value::StringValue(text.into()));
                assert_eq!(decoded, Some(stage["before"].clone()), "{} / {}", stage["case"], stage["name"]);
                decoded_count += 1;
            }
        }
        assert!(decoded_count > 0, "reference must exercise real selection inputs");

        // 2. 以下仅验证 Rust 的输入防御，不宣称已测 Python 的恶意输入行为。
        for text in ["{", "null", "[]", "{}", r#"{"selection":null}"#, r#"{"selection":[]}"#] {
            assert_eq!(codec.decode(&widget_state::Value::StringValue(text.into())), None);
        }
        assert_eq!(codec.decode(&widget_state::Value::JsonValue(r#"{"selection":{}}"#.into())), None);
        assert!(codec.valid(&serde_json::json!({"selection": {"rows": "filtered by emitter", "columns": null, "cells": [null]}})));

        Ok(())
    }

    #[test]
    fn malformed_dataframe_selection_rejects_the_whole_widget_batch() -> anyhow::Result<()> {
        let state = SessionState::default();
        let initial = serde_json::json!({"selection": {"rows": [0], "columns": [], "cells": []}});
        let callback: WidgetCallback = Arc::new(|_| {});

        // 1. 同时注册选择与有效按钮，确保畸形选择不会放行同批其他状态或回调。
        state.begin_widgets(vec![]);
        let (selection_id, _, _) = state.register_widget(
            WidgetSpec {
                disabled: false,
                query: None,
                kind: "dataframe",
                key: Some("selection"),
                identity: "batch-validation",
                default: initial.clone(),
                codec: Codec::DataframeSelection { required_row: false, num_rows: 0 },
                callback: Some(callback.clone()),
            },
            |value| Ok(value.clone()),
        )?;
        let (button_id, _, _) = state.register_widget(
            WidgetSpec {
                disabled: false,
                query: None,
                kind: "button",
                key: Some("action"),
                identity: "batch-validation",
                default: Value::Bool(false),
                codec: Codec::Trigger,
                callback: Some(callback),
            },
            |value| Ok(value.clone()),
        )?;
        state.finish_widgets();

        // 2. 仅验证 Rust 既有 batch 防御，不宣称 Python 对伪造恶意 payload 的兼容性。
        let invalid_fields = [
            serde_json::json!({"rows": "bad"}),
            serde_json::json!({"rows": [1.5]}),
            serde_json::json!({"columns": [1]}),
            serde_json::json!({"cells": [[0]]}),
            serde_json::json!({"cells": [[0, 4]]}),
            serde_json::json!({"cells": [[-1, "qty"]]}),
        ];
        for fields in invalid_fields {
            let value = serde_json::json!({"selection": fields});
            assert!(Codec::DataframeSelection { required_row: false, num_rows: 0 }.valid(&value), "programmatic fields remain available to the emitter's normalizer");
            let callbacks = state.begin_widgets(vec![
                WidgetState {
                    id: button_id.clone(),
                    value: Some(widget_state::Value::TriggerValue(true)),
                },
                WidgetState {
                    id: selection_id.clone(),
                    value: Some(widget_state::Value::StringValue(value.to_string())),
                },
            ]);
            assert!(callbacks.is_empty(), "malformed selection must reject the whole batch: {value}");
            assert_eq!(state.get::<Value>("selection")?, Some(initial.clone()));
            assert_eq!(state.get::<bool>("action")?, Some(false));
        }

        // 3. 合法选择仍允许同批按钮更新并安排其回调，防止 fixture 本身失效。
        let callbacks = state.begin_widgets(vec![
            WidgetState {
                id: button_id,
                value: Some(widget_state::Value::TriggerValue(true)),
            },
            WidgetState {
                id: selection_id,
                value: Some(widget_state::Value::StringValue(initial.to_string())),
            },
        ]);
        assert_eq!(callbacks.len(), 1);
        assert_eq!(state.get::<bool>("action")?, Some(true));

        Ok(())
    }

    #[test]
    fn dataframe_selection_registry_keeps_partial_state_until_browser_roundtrip() -> anyhow::Result<()> {
        let reference: Value = serde_json::from_str(DATAFRAME_SELECTION_REFERENCE)?;
        let stages = reference["stages"].as_array().ok_or_else(|| anyhow::anyhow!("selection reference must contain stages"))?;
        let program_rows = stages
            .iter()
            .find(|stage| stage["case"] == "single-combo" && stage["name"] == "program-rows")
            .ok_or_else(|| anyhow::anyhow!("reference must contain program-rows"))?;
        let program_columns = stages
            .iter()
            .find(|stage| stage["case"] == "single-combo" && stage["name"] == "program-columns")
            .ok_or_else(|| anyhow::anyhow!("reference must contain program-columns"))?;
        let state = SessionState::default();
        let callback: WidgetCallback = Arc::new(|_| {});
        let spec = || WidgetSpec {
            disabled: false,
            query: None,
            kind: "dataframe",
            key: Some("selection"),
            identity: "single-combo",
            default: program_rows["before"].clone(),
            codec: Codec::DataframeSelection { required_row: false, num_rows: 0 },
            callback: Some(callback.clone()),
        };

        // 1. 程序只写 rows；record 和 keyed state 均保留冻结的 partial 对象。
        state.begin_widgets(vec![]);
        let (id, _, _) = state.register_widget(spec(), |value| Ok(value.clone()))?;
        state.finish_widgets();
        state.begin_widgets(vec![]);
        state.set("selection", &program_rows["expected_keyed"])?;
        let (_, raw, set_value) = state.register_widget(spec(), |value| Ok(value.clone()))?;
        assert!(set_value);
        assert_eq!(raw, program_rows["expected_keyed"]);
        assert_eq!(raw, serde_json::json!({"selection": {"rows": [0]}}));
        assert_eq!(state.get::<Value>("selection")?, Some(raw.clone()));
        assert_eq!(state.widgets.lock().records.get(&id).map(|record| record.value.clone()), Some(raw));
        state.finish_widgets();

        // 非法外壳只触发 Rust 的 batch 防御，不改写已保存的 partial 状态。
        assert!(
            state
                .begin_widgets(vec![WidgetState {
                    id: id.clone(),
                    value: Some(widget_state::Value::StringValue(r#"{"selection":null}"#.into()))
                }])
                .is_empty()
        );
        assert_eq!(state.get::<Value>("selection")?, Some(program_rows["expected_keyed"].clone()));

        // 2. 浏览器回送完整对象才发生下一次变化，不能提前补齐后吞掉该回调。
        let incoming = program_columns["target_widget_states"]
            .as_array()
            .and_then(|states| states.first())
            .ok_or_else(|| anyhow::anyhow!("program-columns must include the browser roundtrip"))?;
        assert_eq!(incoming["value_oneof"], "string_value");
        let text = incoming["value"].as_str().ok_or_else(|| anyhow::anyhow!("browser selection state must be text"))?;
        let wire = WidgetState {
            id,
            value: Some(widget_state::Value::StringValue(text.into())),
        };
        let callbacks = state.begin_widgets(vec![wire.clone()]);
        assert_eq!(callbacks.len(), 1);
        assert_eq!(state.get::<Value>("selection")?, Some(program_columns["before"].clone()));
        let (_, raw, set_value) = state.register_widget(spec(), |value| Ok(value.clone()))?;
        assert!(!set_value);
        assert_eq!(raw, program_columns["before"]);
        state.finish_widgets();
        assert!(state.begin_widgets(vec![wire]).is_empty(), "the unchanged full state must not repeat the callback");

        Ok(())
    }

    #[test]
    fn dataframe_selection_registry_retains_frozen_positions_after_shrink() -> anyhow::Result<()> {
        let reference: Value = serde_json::from_str(DATAFRAME_SELECTION_REFERENCE)?;
        let stages = reference["stages"].as_array().ok_or_else(|| anyhow::anyhow!("selection reference must contain stages"))?;
        let state = SessionState::default();
        let mut observed_shrink = false;

        // 首次 pending 注册与后续缩行使用同一 codec，不按当前表行数裁剪位置。
        for stage in stages.iter().filter(|stage| stage["case"] == "multi-shrink" && stage["name"] != "load") {
            let incoming = stage["target_widget_states"].as_array().and_then(|states| states.first()).ok_or_else(|| anyhow::anyhow!("shrink stage must include selection input"))?;
            assert_eq!(incoming["value_oneof"], "string_value");
            let text = incoming["value"].as_str().ok_or_else(|| anyhow::anyhow!("shrink selection state must be text"))?;
            assert!(
                state
                    .begin_widgets(vec![WidgetState {
                        id: "shrink".into(),
                        value: Some(widget_state::Value::StringValue(text.into()))
                    }])
                    .is_empty()
            );
            let (_, raw, _) = state.register_widget_with_id(
                WidgetSpec {
                    disabled: false,
                    query: None,
                    kind: "dataframe",
                    key: Some("selection"),
                    identity: "shrink",
                    default: serde_json::json!({"selection": {"rows": [], "columns": [], "cells": []}}),
                    codec: Codec::DataframeSelection { required_row: false, num_rows: 0 },
                    callback: None,
                },
                "shrink",
                |value| Ok(value.clone()),
            )?;
            assert_eq!(raw, stage["expected_keyed"]);
            assert_eq!(state.get::<Value>("selection")?, Some(raw.clone()));
            if stage["name"] == "replace-shrink" {
                assert_eq!(stage["input_rows"].as_array().map(Vec::len), Some(1));
                assert_eq!(raw["selection"]["rows"], serde_json::json!([2]));
                observed_shrink = true;
            }
            state.finish_widgets();
        }
        assert!(observed_shrink, "reference must exercise the actual shrink stage");

        Ok(())
    }

    #[test]
    fn removed_upload_cannot_be_rebound_by_resending_old_file_state() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.uploads.lock().insert("removed".into(), "old.csv".into(), Some("text/csv".into()), vec![1, 2, 3]);
        let retained = state.uploads.lock().get("removed").ok_or_else(|| anyhow::anyhow!("test upload must be retained before removal"))?;
        let codec = Codec::Files { store: state.uploads.clone(), multiple: false };
        let old_wire = widget_state::Value::FileUploaderStateValue(crate::proto::FileUploaderState {
            uploaded_file_info: vec![crate::proto::UploadedFileInfo { file_id: "removed".into(), ..Default::default() }],
        });
        assert_eq!(codec.decode(&old_wire), Some(serde_json::json!(["removed"])));
        assert!(state.uploads.lock().remove("removed"));
        assert_eq!(codec.decode(&old_wire), Some(serde_json::json!([])));
        assert!(!state.uploads.lock().remove("removed"));
        assert_eq!(retained.as_bytes(), &[1, 2, 3]);

        Ok(())
    }

    #[test]
    fn malformed_numeric_payloads_do_not_mutate_values_or_schedule_callbacks() -> anyhow::Result<()> {
        let state = SessionState::default();
        state.begin_widgets(vec![]);
        let callback: WidgetCallback = Arc::new(|_| panic!("invalid input must not schedule a callback"));
        let (id, _, _) = state.register_widget(
            WidgetSpec {
                disabled: false,
                query: None,
                kind: "slider",
                key: Some("range"),
                identity: "range",
                default: serde_json::json!([2, 8]),
                codec: Codec::Slider { min: 0.0, max: 10.0, count: 2, integer: true },
                callback: Some(callback),
            },
            |value| Ok(value.clone()),
        )?;
        state.finish_widgets();
        // These are native decoder robustness tests, not claims about Python's
        // error handling for fabricated client payloads.
        let bad = [vec![1.0], vec![2.0, 3.0, 4.0], vec![8.0, 2.0], vec![-1.0, 8.0], vec![2.5, 8.0], vec![f64::NAN, 8.0], vec![2.0, f64::INFINITY]];
        for data in bad {
            let callbacks = state.begin_widgets(vec![WidgetState {
                id: id.clone(),
                value: Some(widget_state::Value::DoubleArrayValue(crate::proto::DoubleArray { data })),
            }]);
            assert!(callbacks.is_empty());
            assert_eq!(state.get::<[i64; 2]>("range")?, Some([2, 8]));
        }
        let callbacks = state.begin_widgets(vec![WidgetState {
            id,
            value: Some(widget_state::Value::BoolValue(true)),
        }]);
        assert!(callbacks.is_empty());
        assert_eq!(state.get::<[i64; 2]>("range")?, Some([2, 8]));

        Ok(())
    }

    #[test]
    fn temporal_codec_decodes_measured_micros_and_rejects_fabricated_payloads() {
        let kind = TemporalKind::Time;
        let codec = Codec::TemporalSlider {
            min: TIME_ANCHOR_MICROS as f64,
            max: (TIME_ANCHOR_MICROS + DAY_MICROS - 1) as f64,
            count: 1,
            kind,
        };
        // The reference End key: 23:45 on the 15-minute grid.
        let wire = widget_state::Value::DoubleArrayValue(crate::proto::DoubleArray { data: vec![946770300000000.0] });
        assert_eq!(codec.decode(&wire), Some(serde_json::json!("23:45:00")));
        // Microseconds round-trip through the typed JSON form.
        let wire = widget_state::Value::DoubleArrayValue(crate::proto::DoubleArray { data: vec![946729807123456.0] });
        assert_eq!(codec.decode(&wire), Some(serde_json::json!("12:30:07.123456")));
        // Fractional microseconds, off-grid times and wrong counts never decode.
        for data in [vec![946729807123456.5], vec![1710460800000000.0], vec![], vec![946684800000000.0, 946770300000000.0]] {
            let wire = widget_state::Value::DoubleArrayValue(crate::proto::DoubleArray { data });
            assert_eq!(codec.decode(&wire), None, "fabricated temporal payload must not decode");
        }
        // Typed JSON values validate against the same bounds; a reversed pair fails.
        let codec = Codec::TemporalSlider {
            min: 1709251200000000.0,
            max: 1711670400000000.0,
            count: 2,
            kind: TemporalKind::Date,
        };
        assert!(codec.valid(&serde_json::json!(["2024-03-10", "2024-03-20"])));
        assert!(!codec.valid(&serde_json::json!(["2024-03-20", "2024-03-10"])));
        assert!(!codec.valid(&serde_json::json!(["2024-04-01", "2024-04-02"])));
        assert!(!codec.valid(&serde_json::json!("2024-03-15")));
    }
}
