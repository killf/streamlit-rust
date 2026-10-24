//! Native CSV processing and input-driven columnar views. Run from the repo root.
use ::streamlit::data::{ArrayRef, DataType, Field, Float64Array, Int64Array, LargeStringArray, RecordBatch, Schema};
use ::streamlit::*;
use anyhow::{Context, Result, bail};
use rust_decimal::{Decimal, RoundingStrategy, prelude::ToPrimitive};
use std::{collections::BTreeMap, sync::Arc};

const COLUMNS: [&str; 4] = ["group_key", "row_count", "total_amount", "avg_amount"];

struct Row {
    category: String,
    region: String,
    channel: String,
    amount: Option<Decimal>,
}
struct Parsed {
    rows: Vec<Row>,
    invalid_amounts: usize,
}

fn amount(text: &str) -> Result<Option<Decimal>> {
    let text = text.trim();
    let digits = text.strip_prefix(['+', '-']).unwrap_or(text);
    let mut dots = 0;
    let mut count = 0;
    for c in digits.bytes() {
        if c == b'.' {
            dots += 1;
        } else if c.is_ascii_digit() {
            count += 1;
        } else {
            return Ok(None);
        }
    }
    if count == 0 || dots > 1 {
        return Ok(None);
    }
    // Never silently round a syntactically valid input at the parser boundary.
    // This example's native precision is bounded by rust_decimal's 96-bit value.
    Decimal::from_str_exact(text).map(Some).context("amount exceeds the example's native decimal precision")
}

fn parse(bytes: &[u8]) -> Result<Parsed> {
    if bytes.is_empty() {
        bail!("the uploaded file is empty");
    }
    let text = std::str::from_utf8(bytes).context("the uploaded file is not valid UTF-8")?;
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    if text.is_empty() {
        bail!("the uploaded file is empty");
    }
    if text.starts_with(['\r', '\n']) {
        bail!("the CSV header row is empty");
    }
    let mut reader = csv::ReaderBuilder::new().flexible(false).from_reader(text.as_bytes());
    let headers: Vec<String> = reader.headers().map_err(|error| csv_error(error, text))?.iter().map(|s| s.trim().to_owned()).collect();
    if headers.is_empty() || headers.iter().all(String::is_empty) {
        bail!("the CSV header row is empty");
    }
    let index: BTreeMap<_, _> = headers.iter().enumerate().map(|(i, name)| (name.as_str(), i)).collect();
    let missing: Vec<_> = ["amount", "region"].into_iter().filter(|required| !headers.iter().any(|name| name.to_lowercase() == *required)).collect();
    if !missing.is_empty() {
        bail!("the CSV header is missing required column(s): {}", missing.join(", "));
    }
    let mut parsed = Parsed { rows: Vec::new(), invalid_amounts: 0 };
    for record in reader.records() {
        let record = record.map_err(|error| csv_error(error, text))?;
        let cell = |name: &str| index.get(name).and_then(|i| record.get(*i)).unwrap_or("").trim().to_owned();
        let amount = amount(&cell("amount"))?;
        if amount.is_none() {
            parsed.invalid_amounts += 1;
        }
        parsed.rows.push(Row {
            category: cell("category"),
            region: cell("region"),
            channel: cell("channel"),
            amount,
        });
    }
    Ok(parsed)
}

fn csv_error(error: csv::Error, text: &str) -> anyhow::Error {
    if let csv::ErrorKind::UnequalLengths { pos: Some(position), expected_len, len } = error.kind() {
        // The reference numbers CSV records, including blank records, rather
        // than physical lines inside a quoted field. csv skips blank records.
        let mut end = usize::try_from(position.byte()).unwrap_or(text.len()).min(text.len());
        let bytes = text.as_bytes();
        // csv's stored start position precedes any skipped blank records.
        while end < bytes.len() && matches!(bytes[end], b'\r' | b'\n') {
            end += 1;
        }
        let (mut row, mut quoted, mut field_start, mut i) = (1, false, true, 0);
        while i < end {
            match bytes[i] {
                b'"' if quoted && bytes.get(i + 1) == Some(&b'"') => i += 1,
                b'"' if quoted => quoted = false,
                b'"' if field_start => {
                    quoted = true;
                    field_start = false;
                }
                b',' if !quoted => field_start = true,
                b'\r' | b'\n' if !quoted => {
                    row += 1;
                    field_start = true;
                    if bytes[i] == b'\r' && bytes.get(i + 1) == Some(&b'\n') {
                        i += 1;
                    }
                }
                _ if !quoted => field_start = false,
                _ => (),
            }
            i += 1;
        }
        return anyhow::anyhow!("row {row}: expected {expected_len} fields, found {len}");
    }
    anyhow::anyhow!("the file is not valid CSV: {error}")
}

fn rounded_average(sum: Decimal, count: i64) -> Result<Decimal> {
    if count <= 0 {
        bail!("average requires a positive row count");
    }
    // Work in integer cents so division cannot round onto a half-cent before
    // HALF_UP is applied. The 96-bit coefficient times 100 fits in i128.
    let numerator = sum.mantissa() * 100;
    let Some(denominator) = 10_i128.pow(sum.scale()).checked_mul(i128::from(count)) else {
        // An overflowing denominator is far larger than twice any possible
        // 96-bit coefficient times 100, so the rounded cents are exactly zero.
        return Ok(Decimal::ZERO);
    };
    let mut cents = numerator / denominator;
    if (numerator % denominator).abs() * 2 >= denominator {
        cents += numerator.signum();
    }
    let mut scale = 2;
    while scale > 0 && cents % 10 == 0 {
        cents /= 10;
        scale -= 1;
    }
    let mut average = Decimal::try_from_i128_with_scale(cents, scale).context("average exceeds native decimal precision")?;
    average.set_sign_negative(sum.is_sign_negative());
    Ok(average)
}

fn aggregate(parsed: &Parsed, group: &str, minimum: i64, include_unknown: bool) -> Result<RecordBatch> {
    if !matches!(group, "category" | "region" | "channel") {
        bail!("unsupported group column");
    }
    let mut sums: BTreeMap<String, (i64, Decimal)> = BTreeMap::new();
    for row in &parsed.rows {
        let Some(value) = row.amount else { continue };
        if value < Decimal::from(minimum) {
            continue;
        }
        let unknown = matches!(row.region.to_lowercase().as_str(), "" | "unknown" | "n/a" | "na" | "null" | "none" | "-");
        if !include_unknown && unknown {
            continue;
        }
        let key = match group {
            "region" => &row.region,
            "channel" => &row.channel,
            _ => &row.category,
        };
        let key = if key.is_empty() { "(missing)" } else { key };
        let entry = sums.entry(key.to_owned()).or_insert((0, Decimal::ZERO));
        entry.0 += 1;
        entry.1 = entry.1.checked_add(value).context("sum exceeds native decimal precision")?;
    }
    let mut keys = Vec::new();
    let mut counts = Vec::new();
    let mut totals = Vec::new();
    let mut averages = Vec::new();
    let rounded = |value: Decimal| value.round_dp_with_strategy(2, RoundingStrategy::MidpointAwayFromZero).to_f64().context("result cannot be represented in the displayed float column");
    for (key, (count, sum)) in sums {
        keys.push(key);
        counts.push(count);
        totals.push(rounded(sum)?);
        averages.push(rounded_average(sum, count)?.to_f64().context("average cannot be represented in the displayed float column")?);
    }
    let schema = Schema::new(vec![
        Field::new(COLUMNS[0], DataType::LargeUtf8, true),
        Field::new(COLUMNS[1], DataType::Int64, true),
        Field::new(COLUMNS[2], DataType::Float64, true),
        Field::new(COLUMNS[3], DataType::Float64, true),
    ]);
    let arrays: Vec<ArrayRef> = vec![Arc::new(LargeStringArray::from(keys)), Arc::new(Int64Array::from(counts)), Arc::new(Float64Array::from(totals)), Arc::new(Float64Array::from(averages))];
    Ok(RecordBatch::try_new(Arc::new(schema), arrays)?)
}

fn render_result(st: &Streamlit, selection: &UploadedFiles, group: &str, minimum: i64, include_unknown: bool) -> Result<()> {
    st.sub_header("Aggregated result");
    let Some(file) = selection.as_slice().first() else {
        st.info("Upload a CSV to see the aggregated result.")?;
        return Ok(());
    };
    let parsed = match parse(file.as_bytes()) {
        Ok(parsed) => parsed,
        Err(error) => {
            st.error(format!("Could not parse the uploaded CSV: {error}"))?;
            st.info("Upload a valid CSV to continue.")?;
            return Ok(());
        }
    };
    if parsed.invalid_amounts > 0 {
        st.warning(format!("{} row(s) with an unusable 'amount' were excluded from the aggregation.", parsed.invalid_amounts))?;
    }
    let batch = aggregate(&parsed, group, minimum, include_unknown)?;
    if parsed.rows.is_empty() {
        st.info("The uploaded CSV contains no data rows.")?;
    } else if batch.num_rows() == 0 {
        st.info("No rows match the current filters.")?;
    }
    st.dataframe(DataframeOptions::new(&batch).hide_index(true).column_order(COLUMNS))?;
    if batch.num_rows() > 0 {
        let keys = batch.column(0).as_any().downcast_ref::<LargeStringArray>().context("group column has an unexpected type")?;
        st.bar_chart(
            BarChartOptions::new(&batch, "group_key", "total_amount")
                .x_order(keys.iter().flatten().map(str::to_owned))
                .tooltip("group_key", "group")
                .tooltip("row_count", "rows")
                .tooltip("total_amount", "total")
                .tooltip("avg_amount", "avg")
                .plot_height(260),
        )?;
    }
    Ok(())
}

fn begin_run(state: &SessionState) -> Result<u64> {
    let runs = state.get::<u64>("run_count")?.unwrap_or(0).checked_add(1).context("script run counter overflow")?;
    state.set("run_count", runs)?;
    Ok(runs)
}

fn apply_pulse(state: &SessionState, clicked: bool) -> Result<u64> {
    let pulses = state.get::<u64>("pulse_count")?.unwrap_or(0);
    let pulses = pulses.checked_add(u64::from(clicked)).context("pulse counter overflow")?;
    state.set("pulse_count", pulses)?;
    Ok(pulses)
}

fn render(st: &Streamlit) -> Result<()> {
    let state = st.session_state();
    let runs = begin_run(&state)?;
    st.title("Streamlit Rust CSV data app");
    let selection = st.file_uploader(FileUploaderOptions::new("Upload sales CSV").accepted_types(["csv"]).key("upload"))?;
    let group = st.selectbox(SelectboxOptions::new("Group by", ["category", "region", "channel"]).key("group_by"))?.unwrap_or("category");
    let minimum = st.slider(SliderOptions::new("Minimum amount", 0_i64).max(200).step(10).key("min_amount"))?;
    let include_unknown = st.checkbox(CheckboxOptions::new("Include unknown region").value(true).key("include_unknown"))?;
    render_result(st, &selection, group, minimum, include_unknown)?;
    st.sub_header("Interaction");
    let clicked = st.try_button(ButtonOptions::new("Pulse").key("pulse"))?;
    let pulses = apply_pulse(&state, clicked)?;
    st.write(format!("Script runs: {runs}"));
    st.write(format!("Pulses: {pulses}"));
    Ok(())
}

async fn __streamlit_user_main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Data app error: {error}"));
    }
}
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::Builder::from_default_env().init();
    log::info!("Starting Streamlit Rust Backend v0.1.0");
    let server = StreamlitServer::new(
        |st: &Streamlit| Box::pin(__streamlit_user_main(st)),
        "127.0.0.1".into(),
        8505,
    );
    server.start().await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use ::streamlit::data::from_ipc_stream;

    #[test]
    fn ragged_rows_report_reference_record_numbers_and_field_counts() {
        let cases: &[(&[u8], &str)] = &[
            (include_bytes!("../../tests/fixtures/csv/sales_malformed.csv"), "row 3: expected 8 fields, found 7"),
            (b"amount,region\n1,North,extra\n", "row 2: expected 2 fields, found 3"),
            (b"amount,region\n\n1,North,extra\n", "row 3: expected 2 fields, found 3"),
            (b"amount,region,category\n1,North,\"A\nB\"\n2,North\n", "row 3: expected 3 fields, found 2"),
        ];
        for (bytes, expected) in cases {
            let error = match parse(bytes) {
                Ok(_) => panic!("ragged input was accepted"),
                Err(error) => error,
            };
            assert_eq!(error.to_string(), *expected);
        }
    }

    #[test]
    fn average_rounds_the_exact_ratio_once_at_the_half_cent_boundary() {
        let parsed = parse(b"amount,region,category\n0.0099999999999999999999999999,North,A\n0,North,A\n").unwrap();
        let batch = aggregate(&parsed, "category", 0, true).unwrap();
        assert_eq!(batch.column(2).as_any().downcast_ref::<Float64Array>().unwrap().value(0), 0.01);
        assert_eq!(batch.column(3).as_any().downcast_ref::<Float64Array>().unwrap().value(0), 0.00);
        for (sum, count, expected) in [("0.01", 2, "0.01"), ("-0.01", 2, "-0.01"), ("3.01", 2, "1.51"), ("-3.01", 2, "-1.51"), ("0.0149999999999999999999999999", 3, "0")] {
            assert_eq!(rounded_average(sum.parse().unwrap(), count).unwrap(), expected.parse::<Decimal>().unwrap());
        }
        assert_eq!(rounded_average(Decimal::MAX, 1).unwrap(), Decimal::MAX);
        assert!(rounded_average(Decimal::ONE, 0).is_err());
    }

    #[test]
    fn soft_amount_errors_keep_ten_rows_and_all_four_reference_aggregates() {
        let parsed = parse(include_bytes!("../../tests/fixtures/csv/sales_with_missing.csv")).unwrap();
        assert_eq!((parsed.rows.len(), parsed.invalid_amounts), (12, 2));
        let batch = aggregate(&parsed, "category", 0, true).unwrap();
        let expected = [("Books", 2, 200.50, 100.25), ("Games", 3, 409.48, 136.49), ("Music", 2, 51.00, 25.50), ("Toys", 3, 104.49, 34.83)];
        assert_eq!(batch.num_rows(), expected.len());
        for (i, (key, count, total, average)) in expected.into_iter().enumerate() {
            assert_eq!(batch.column(0).as_any().downcast_ref::<LargeStringArray>().unwrap().value(i), key);
            assert_eq!(batch.column(1).as_any().downcast_ref::<Int64Array>().unwrap().value(i), count);
            assert_eq!(batch.column(2).as_any().downcast_ref::<Float64Array>().unwrap().value(i), total);
            assert_eq!(batch.column(3).as_any().downcast_ref::<Float64Array>().unwrap().value(i), average);
        }
    }

    #[test]
    fn non_utf8_is_hard_failure_and_valid_unicode_bom_upload_recovers() {
        for bytes in [b"amount,region\n1,\xff\n".as_slice(), b"amount,region\n1,\xe2\x82".as_slice()] {
            let error = match parse(bytes) {
                Ok(_) => panic!("invalid UTF-8 was accepted"),
                Err(error) => error,
            };
            assert_eq!(error.to_string(), "the uploaded file is not valid UTF-8");
        }
        let plain = parse(include_bytes!("../../tests/fixtures/csv/sales_unicode.csv")).unwrap();
        let bom = parse(include_bytes!("../../tests/fixtures/csv/sales_utf8_bom.csv")).unwrap();
        let plain = aggregate(&plain, "category", 0, true).unwrap();
        let recovered = aggregate(&bom, "category", 0, true).unwrap();
        assert_eq!(plain.schema(), recovered.schema());
        for (a, b) in plain.columns().iter().zip(recovered.columns()) {
            assert_eq!(a.to_data(), b.to_data());
        }
        assert_eq!(plain.column(0).as_any().downcast_ref::<LargeStringArray>().unwrap().iter().collect::<Vec<_>>(), [Some("Bücher"), Some("Jogos"), Some("游戏")]);
    }

    #[test]
    fn run_and_pulse_counters_follow_reruns_without_cross_session_state() {
        let a = SessionState::default();
        let b = SessionState::default();
        for (expected_run, clicked, expected_pulses) in [(1, false, 0), (2, false, 0), (3, true, 1), (4, false, 1), (5, true, 2)] {
            assert_eq!(begin_run(&a).unwrap(), expected_run);
            assert_eq!(apply_pulse(&a, clicked).unwrap(), expected_pulses);
        }
        assert_eq!(begin_run(&b).unwrap(), 1);
        assert_eq!(apply_pulse(&b, false).unwrap(), 0);
        assert_eq!(a.get::<u64>("run_count").unwrap(), Some(5));
        assert_eq!(a.get::<u64>("pulse_count").unwrap(), Some(2));
    }

    #[test]
    fn native_csv_rebuilds_the_four_observed_arrow_results() {
        let parsed = parse(include_bytes!("../../tests/fixtures/csv/sales_basic.csv")).unwrap();
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../tests/reference/reference-browser/data-loop/updates");
        let mut previous = None;
        for (i, (group, minimum, unknown)) in [("category", 0, true), ("region", 0, true), ("region", 0, false), ("region", 100, false)].into_iter().enumerate() {
            let actual = aggregate(&parsed, group, minimum, unknown).unwrap();
            let expected = from_ipc_stream(&std::fs::read(root.join(format!("arrow-{}.bin", i + 1))).unwrap()).unwrap().remove(0);
            assert_eq!(actual.num_rows(), expected.num_rows());
            for column in 0..4 {
                assert_eq!(actual.column(column).to_data(), expected.column(column).to_data(), "stage={} column={column}", i + 1);
            }
            let ipc = ::streamlit::data::to_ipc_stream(&actual).unwrap();
            if let Some(previous) = previous {
                assert_ne!(ipc, previous);
            }
            previous = Some(ipc);
        }
    }

    #[test]
    fn malformed_csv_errors_and_plain_decimals_use_application_half_up() {
        for invalid in [b"".as_slice(), b"a,b\nx,y\n", b"amount,region\n1,North,extra\n", b"\xff"] {
            assert!(parse(invalid).is_err());
        }
        for invalid in ["NaN", "Infinity", "1_000", "1,000", ""] {
            assert_eq!(amount(invalid).unwrap(), None);
        }
        let parsed = parse(b"amount,region,category\n1.005,North,A\n2.005,North,A\ninvalid,North,A\n").unwrap();
        assert_eq!(parsed.invalid_amounts, 1);
        let batch = aggregate(&parsed, "category", 0, true).unwrap();
        let total = batch.column(2).as_any().downcast_ref::<Float64Array>().unwrap().value(0);
        let avg = batch.column(3).as_any().downcast_ref::<Float64Array>().unwrap().value(0);
        assert_eq!((total, avg), (3.01, 1.51));
    }

    #[test]
    fn failed_parse_does_not_poison_next_upload_and_empty_results_keep_schema() {
        assert!(parse(b"bad,header\n1,2\n").is_err());
        let valid = parse(include_bytes!("../../tests/fixtures/csv/sales_basic.csv")).unwrap();
        assert_eq!(aggregate(&valid, "category", 0, true).unwrap().num_rows(), 4);
        let headers_only = parse(b"amount,region,category\n").unwrap();
        let empty = aggregate(&headers_only, "category", 0, true).unwrap();
        assert_eq!(empty.num_rows(), 0);
        assert_eq!(empty.num_columns(), 4);
        assert_eq!(empty.schema_ref().fields().iter().map(|field| field.name().as_str()).collect::<Vec<_>>(), COLUMNS);
        let filtered = aggregate(&valid, "region", 200, false).unwrap();
        assert_eq!(filtered.num_rows(), 0);
        assert_eq!(filtered.schema(), empty.schema());
        for (field, data_type) in empty.schema().fields().iter().zip([DataType::LargeUtf8, DataType::Int64, DataType::Float64, DataType::Float64]) {
            assert_eq!(field.data_type(), &data_type);
            assert!(field.is_nullable());
        }
        let restored = aggregate(&valid, "category", 0, true).unwrap();
        assert_eq!(restored.schema(), empty.schema());
        let reference = from_ipc_stream(include_bytes!("../../tests/reference/reference-browser/data-loop/updates/arrow-1.bin")).unwrap().remove(0);
        for (a, b) in restored.columns().iter().zip(reference.columns()) {
            assert_eq!(a.to_data(), b.to_data());
        }
    }
}
