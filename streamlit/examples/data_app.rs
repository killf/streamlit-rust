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
    let text = std::str::from_utf8(bytes).context("the uploaded file is not valid UTF-8")?.trim_start_matches('\u{feff}');
    let mut reader = csv::ReaderBuilder::new().flexible(false).from_reader(text.as_bytes());
    let headers: Vec<String> = reader.headers()?.iter().map(|s| s.trim().to_owned()).collect();
    if headers.is_empty() || headers.iter().all(String::is_empty) {
        bail!("the CSV header row is empty");
    }
    let index: BTreeMap<_, _> = headers.iter().enumerate().map(|(i, name)| (name.as_str(), i)).collect();
    for required in ["amount", "region"] {
        if !index.contains_key(required) {
            bail!("the CSV header is missing required column: {required}");
        }
    }
    let mut parsed = Parsed { rows: Vec::new(), invalid_amounts: 0 };
    for record in reader.records() {
        let record = record?;
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
        averages.push(rounded(sum.checked_div(Decimal::from(count)).context("average exceeds native precision")?)?);
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

fn render(st: &Streamlit) -> Result<()> {
    st.title("Streamlit Rust CSV data app");
    let selection = st.file_uploader(FileUploaderOptions::new("Upload sales CSV").accepted_types(["csv"]).key("upload"))?;
    let group = st.selectbox(SelectboxOptions::new("Group by", ["category", "region", "channel"]).key("group_by"))?.unwrap_or("category");
    let minimum = st.slider(SliderOptions::new("Minimum amount", 0_i64).max(200).step(10).key("min_amount"))?;
    let include_unknown = st.checkbox(CheckboxOptions::new("Include unknown region").value(true).key("include_unknown"))?;
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

#[main]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Data app error: {error}"));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ::streamlit::data::from_ipc_stream;

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
    }
}
