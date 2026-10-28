//! A text CSV working copy owned by one session; uploads stay immutable.
use ::streamlit::data::{Array, ArrayRef, Int64Array, RecordBatch, StringArray};
use ::streamlit::*;
use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, HashSet},
    sync::Arc,
};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
struct Sheet {
    headers: Vec<String>,
    rows: Vec<Vec<String>>,
}

impl Sheet {
    fn parse(bytes: &[u8]) -> Result<Self> {
        let text = std::str::from_utf8(bytes).context("CSV must be UTF-8")?;
        let text = text.strip_prefix('\u{feff}').unwrap_or(text);
        if text.is_empty() {
            bail!("CSV header is empty");
        }
        // 1. csv 解析器容忍未闭合引号，此处按严格 CSV 校验。
        let (mut quoted, mut start, mut closed) = (false, true, false);
        for byte in text.bytes() {
            if quoted {
                if byte == b'"' {
                    quoted = false;
                    closed = true;
                }
            } else if closed && byte == b'"' {
                quoted = true;
                closed = false;
            } else if matches!(byte, b',' | b'\r' | b'\n') {
                start = true;
                closed = false;
            } else if closed {
                bail!("CSV has characters after a closing quote");
            } else {
                quoted = start && byte == b'"';
                start = false;
            }
        }
        if quoted {
            bail!("CSV has an unfinished quoted field");
        }

        // 2. 列名和单元格保留文本、空格与空串，不做类型推断。
        let mut reader = csv::ReaderBuilder::new().flexible(false).from_reader(text.as_bytes());
        let headers: Vec<String> = reader.headers()?.iter().map(str::to_owned).collect();
        let mut seen = HashSet::new();
        if headers.is_empty() || headers.iter().any(|name| name.is_empty() || !seen.insert(name)) {
            bail!("CSV column names must be nonempty and unique");
        }
        let rows = reader.records().map(|record| record.map(|row| row.iter().map(str::to_owned).collect())).collect::<Result<_, _>>()?;
        Ok(Self { headers, rows })
    }

    fn batch(&self, positions: &[usize]) -> Result<RecordBatch> {
        let columns = self.headers.iter().enumerate().map(|(column, name)| {
            let values = positions.iter().map(|row| self.rows[*row][column].as_str()).collect::<Vec<_>>();
            (name.as_str(), Arc::new(StringArray::from(values)) as ArrayRef)
        });
        Ok(RecordBatch::try_from_iter(columns)?)
    }

    fn csv(&self) -> Result<Vec<u8>> {
        let mut writer = csv::WriterBuilder::new().terminator(csv::Terminator::Any(b'\n')).from_writer(Vec::new());
        writer.write_record(&self.headers)?;
        for row in &self.rows {
            writer.write_record(row)?;
        }
        Ok(writer.into_inner()?)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
struct Filter {
    column: usize,
    enabled: bool,
    value: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct DetailToken {
    version: u64,
    view: u64,
    epoch: u64,
    row: usize,
}

#[derive(Default, Serialize, Deserialize)]
struct Workbench {
    sheet: Option<Sheet>,

    // 当前上传选择与上次有效工作来源可能不同。
    upload_id: Option<String>,
    source_id: String,
    source_name: String,
    upload_error: Option<String>,

    version: u64,
    view_epoch: u64,
    detail_epoch: u64,

    filter: Option<Filter>,
    selected: Option<usize>,
}

impl Workbench {
    fn reset_drafts(&mut self) -> Result<()> {
        self.version = self.version.checked_add(1).context("working version overflow")?;
        self.change_view(None)?;
        Ok(())
    }

    fn source(&mut self, upload: Option<(&str, &str, &[u8])>) -> Result<()> {
        let id = upload.map(|(id, _, _)| id);
        if self.upload_id.as_deref() == id {
            return Ok(());
        }
        self.upload_id = id.map(str::to_owned);
        self.upload_error = None;
        // The real frontend emits an empty uploader state before a
        // replacement file arrives; it only clears the selection. The working
        // copy is removed exclusively by the explicit clear.
        if let Some((id, name, bytes)) = upload {
            match Sheet::parse(bytes) {
                Ok(sheet) => {
                    self.sheet = Some(sheet);
                    self.source_id = id.into();
                    self.source_name = name.into();
                    self.reset_drafts()?;
                }
                Err(error) => self.upload_error = Some(error.to_string()),
            }
        }
        Ok(())
    }

    fn clear(&mut self) -> Result<()> {
        self.sheet = None;
        self.upload_id = None;
        self.source_id.clear();
        self.source_name.clear();
        self.upload_error = None;
        self.reset_drafts()
    }

    fn change_view(&mut self, filter: Option<Filter>) -> Result<()> {
        if self.filter != filter {
            self.view_epoch = self.view_epoch.checked_add(1).context("view version overflow")?;
            self.filter = filter;
        }
        self.select(None)?;
        Ok(())
    }

    fn select(&mut self, row: Option<usize>) -> Result<()> {
        if self.selected != row {
            self.detail_epoch = self.detail_epoch.checked_add(1).context("detail version overflow")?;
            self.selected = row;
        }
        Ok(())
    }

    fn token(&self) -> Option<DetailToken> {
        self.selected.map(|row| DetailToken {
            version: self.version,
            view: self.view_epoch,
            epoch: self.detail_epoch,
            row,
        })
    }

    fn positions(&self) -> Result<Vec<usize>> {
        let sheet = self.sheet.as_ref().context("no working source")?;
        Ok(sheet
            .rows
            .iter()
            .enumerate()
            .filter_map(|(index, row)| {
                let matches = self.filter.as_ref().is_none_or(|filter| !filter.enabled || row.get(filter.column) == Some(&filter.value));
                matches.then_some(index)
            })
            .collect())
    }

    fn apply(&mut self, token: &DetailToken, edited: &RecordBatch) -> Result<()> {
        if self.token().as_ref() != Some(token) {
            bail!("The detail draft belongs to an older row or view; select the row again.");
        }
        let sheet = self.sheet.as_mut().context("no working source")?;
        let mut rows = edited_rows(sheet, edited)?;
        if rows.len() != 1 {
            bail!("Detail draft must contain exactly one row");
        }
        *sheet.rows.get_mut(token.row).context("selected row no longer exists")? = rows.remove(0);
        self.reset_drafts()
    }

    fn append(&mut self, version: u64, edited: &RecordBatch) -> Result<bool> {
        if self.version != version {
            bail!("The new-row draft belongs to an older source version.");
        }
        let sheet = self.sheet.as_mut().context("no working source")?;
        let rows = edited_rows(sheet, edited)?;
        if rows.is_empty() {
            return Ok(false);
        }
        sheet.rows.extend(rows);
        self.reset_drafts()?;
        Ok(true)
    }
}

fn edited_rows(sheet: &Sheet, batch: &RecordBatch) -> Result<Vec<Vec<String>>> {
    if batch.schema().fields().iter().map(|field| field.name()).ne(sheet.headers.iter()) {
        bail!("Editor columns no longer match the working source");
    }
    let columns = batch.columns().iter().map(|column| column.as_any().downcast_ref::<StringArray>().context("Editor must return text columns")).collect::<Result<Vec<_>>>()?;
    Ok((0..batch.num_rows())
        .map(|row| columns.iter().map(|column| if column.is_null(row) { String::new() } else { column.value(row).to_owned() }).collect())
        .collect())
}

fn counts(sheet: &Sheet, positions: &[usize], column: usize) -> Result<RecordBatch> {
    let mut groups: BTreeMap<&str, i64> = BTreeMap::new();
    for row in positions {
        *groups.entry(&sheet.rows[*row][column]).or_default() += 1;
    }
    Ok(RecordBatch::try_from_iter(vec![
        ("value", Arc::new(StringArray::from(groups.keys().copied().collect::<Vec<_>>())) as ArrayRef),
        ("count", Arc::new(Int64Array::from(groups.values().copied().collect::<Vec<_>>())) as ArrayRef),
    ])?)
}

fn render(st: &Streamlit) -> Result<()> {
    let state = st.session_state();
    let mut work = state.get::<Workbench>("wb-working-copy")?.unwrap_or_default();
    st.title("CSV workbench");
    let upload = st.file_uploader(FileUploaderOptions::new("Upload CSV").accepted_types(["csv"]).key("wb-upload"))?;
    work.source(upload.as_slice().first().map(|file| (file.id(), file.name(), file.as_bytes())))?;
    st.try_button(ButtonOptions::new("Ordinary rerun").key("wb-rerun"))?;
    if work.sheet.is_some() && st.try_button(ButtonOptions::new("Clear working copy").key("wb-clear"))? {
        work.clear()?;
        state.set("wb-working-copy", &work)?;
        st.rerun();
        return Ok(());
    }
    if let Some(error) = &work.upload_error {
        st.error(format!("Could not read CSV: {error}"))?;
        if work.sheet.is_some() {
            st.warning(format!("Showing previous valid source: {}", work.source_name))?;
        }
    }
    let Some(sheet) = work.sheet.as_ref() else {
        st.info("Upload a CSV to start a working copy.")?;
        state.set("wb-working-copy", &work)?;
        return Ok(());
    };
    st.write(format!("Working source: {}", work.source_name));

    // 1. 视图变化重置选择身份，筛选位置映射回源行。
    let column = st
        .selectbox(SelectboxOptions::new("Filter column", sheet.headers.clone()).key(format!("wb-filter-column-{}", work.source_id)))?
        .context("filter column is missing")?;
    let enabled = st.checkbox(CheckboxOptions::new("Filter enabled").key(format!("wb-filter-enabled-{}", work.source_id)))?;
    let value = st.text_input(TextInputOptions::new("Exact value").key(format!("wb-filter-value-{}", work.source_id)))?.unwrap_or_default();
    let count_by = st.selectbox(SelectboxOptions::new("Count by", sheet.headers.clone()).key(format!("wb-count-by-{}", work.source_id)))?.context("count column is missing")?;
    let filter = Filter {
        column: sheet.headers.iter().position(|name| name == &column).context("unknown filter column")?,
        enabled,
        value,
    };
    let count_column = sheet.headers.iter().position(|name| name == &count_by).context("unknown count column")?;
    if work.filter.as_ref() != Some(&filter) {
        work.change_view(Some(filter))?;
    }
    let positions = work.positions()?;
    let sheet = work.sheet.as_ref().context("no working source")?;
    st.write(format!("Rows: {}; matching: {}", sheet.rows.len(), positions.len()));
    st.sub_header("Rows");
    let batch = sheet.batch(&positions)?;
    let selection = st.dataframe(
        DataframeOptions::new(&batch)
            .key(format!("wb-rows-{}-{}", work.version, work.view_epoch))
            .on_select(OnSelect::Rerun)
            .selection_mode(DataframeSelectionMode::SingleRow)
            .hide_index(true)
            .height(190)
            .width(700),
    )?;
    let selected = selection.and_then(|state| state.selection.rows.first().copied()).and_then(|index| positions.get(index).copied());
    if positions.is_empty() {
        st.info(if sheet.rows.is_empty() { "The working copy has no data rows." } else { "No rows match the current filter." })?;
    } else {
        let chart = counts(sheet, &positions, count_column)?;
        st.bar_chart(
            BarChartOptions::new(&chart, "value", "count")
                .x_order(chart.column(0).as_any().downcast_ref::<StringArray>().context("count labels must be text")?.iter().flatten())
                .plot_height(200),
        )?;
    }

    work.select(selected)?;

    // 2. Apply 绑定当前视图、来源版本和详情，隔离过期输入。
    if let Some(token) = work.token() {
        st.sub_header("Detail draft");
        let detail = work.sheet.as_ref().context("no working source")?.batch(&[token.row])?;
        let identity = format!("{}-{}-{}", token.version, token.view, token.epoch);
        let edited = st.data_editor(DataEditorOptions::new(&detail).key(format!("wb-detail-{identity}")).height(150).width(700))?;
        if st.try_button(ButtonOptions::new("Apply").key(format!("wb-apply-{identity}")))? {
            work.apply(&token, &edited)?;
            state.set("wb-working-copy", &work)?;
            st.rerun();
            return Ok(());
        }
    } else {
        st.info("Select a row to edit its detail.")?;
    }

    // 3. 新增草稿跨筛选保留，提交新数据版本后重置。
    st.sub_header("New rows draft");
    let sheet = work.sheet.as_ref().context("no working source")?;
    let empty = sheet.batch(&[])?;
    let added = st.data_editor(DataEditorOptions::new(&empty).key(format!("wb-new-{}", work.version)).num_rows(EditorRows::Dynamic).height(190).width(700))?;
    if st.try_button(ButtonOptions::new("Append").key(format!("wb-append-{}", work.version)))? {
        if work.append(work.version, &added)? {
            state.set("wb-working-copy", &work)?;
            st.rerun();
            return Ok(());
        }
        st.info("No new rows to append.")?;
    }
    let sheet = work.sheet.as_ref().context("no working source")?;
    st.download_button(DownloadButtonOptions::new("Download CSV", sheet.csv()?).file_name("workbench.csv").mime("text/csv").key(format!("wb-download-{}", work.version)))?;
    state.set("wb-working-copy", &work)?;
    Ok(())
}

#[main(host = "127.0.0.1", port = 8545)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.error(format!("CSV workbench error: {error}")).ok();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn csv_preserves_text_columns_quotes_and_empty_records() -> Result<()> {
        let input = "\u{feff} code ,note,empty\n001,\"two\nlines and \"\"quotes\"\"\",\n\n002, plain ,\n";
        let sheet = Sheet::parse(input.as_bytes())?;
        assert_eq!(sheet.headers, [" code ", "note", "empty"]);
        assert_eq!(sheet.rows, vec![vec!["001", "two\nlines and \"quotes\"", ""], vec!["002", " plain ", ""]]);
        assert_eq!(Sheet::parse(&sheet.csv()?)?, sheet);
        assert!(Sheet::parse(b"a,b\n")?.rows.is_empty());
        assert_eq!(Sheet::parse(b"a,b\n,\n")?.rows, vec![vec!["", ""]]);
        assert_eq!(Sheet::parse(b"\na,b\n1,2\n")?.rows, vec![vec!["1", "2"]]);
        Ok(())
    }

    #[test]
    fn csv_rejects_invalid_sources_and_empty_states_keep_a_valid_copy() -> Result<()> {
        let mut work = Workbench::default();
        work.source(Some(("first", "good.csv", b"a,b\n1,2\n")))?;
        let original = work.sheet.clone();
        for (index, bytes) in [b"".as_slice(), b"\xff", b",b\n", b"a,a\n", b"a,b\n1\n", b"a,b\n\"open,2", b"a,b\n\"closed\"x,2"].into_iter().enumerate() {
            work.source(Some((&format!("bad-{index}"), "bad.csv", bytes)))?;
            assert!(work.upload_error.is_some());
            assert_eq!(work.sheet, original);
            assert_eq!(work.source_name, "good.csv");
        }
        // The empty uploader state (real replacement prologue) keeps the copy.
        work.source(None)?;
        assert_eq!(work.sheet, original);
        assert_eq!(work.source_name, "good.csv");
        assert!(work.upload_error.is_none());
        // Only the explicit clear removes the working copy.
        work.clear()?;
        assert!(work.sheet.is_none());
        assert_eq!(work.source_name, "");
        Ok(())
    }

    #[test]
    fn filtered_apply_maps_to_the_source_and_rejects_old_drafts() -> Result<()> {
        let mut work = Workbench::default();
        work.source(Some(("first", "input.csv", b"id,region\nA,north\nB,south\nC,north\n")))?;
        work.change_view(Some(Filter { column: 1, enabled: true, value: "north".into() }))?;
        assert_eq!(work.positions()?, [0, 2]);
        work.select(Some(work.positions()?[1]))?;
        let token = work.token().context("a row must be selected")?;
        let edited = Sheet::parse(b"id,region\nC,east\n")?.batch(&[0])?;
        assert_eq!(work.sheet.as_ref().context("missing sheet")?.rows[2][1], "north");
        work.apply(&token, &edited)?;
        assert_eq!(work.sheet.as_ref().context("missing sheet")?.rows[2][1], "east");
        assert!(work.apply(&token, &edited).is_err());
        assert!(work.selected.is_none());
        Ok(())
    }

    #[test]
    fn view_or_selection_changes_invalidate_detail_without_mutating_rows() -> Result<()> {
        let mut work = Workbench::default();
        work.source(Some(("first", "input.csv", b"id\nA\nB\n")))?;
        let original = work.sheet.clone();
        work.select(Some(0))?;
        let token = work.token().context("missing selection")?;
        let edit = Sheet::parse(b"id\nchanged\n")?.batch(&[0])?;
        work.change_view(Some(Filter { column: 0, enabled: true, value: "B".into() }))?;
        work.select(Some(1))?;
        assert!(work.apply(&token, &edit).is_err());
        let token = work.token().context("missing selection")?;
        work.select(Some(0))?;
        assert!(work.apply(&token, &edit).is_err());
        assert_eq!(work.sheet, original);
        Ok(())
    }

    #[test]
    fn append_keeps_duplicates_converts_null_to_empty_and_updates_counts() -> Result<()> {
        let mut work = Workbench::default();
        work.source(Some(("first", "input.csv", b"id,region\nA,north\n")))?;
        let input = work.sheet.as_ref().context("missing sheet")?.clone();
        let added = RecordBatch::try_from_iter(vec![("id", Arc::new(StringArray::from(vec![Some("A"), None])) as ArrayRef), ("region", Arc::new(StringArray::from(vec![Some("north"), None])) as ArrayRef)])?;
        assert!(work.append(work.version, &added)?);
        let sheet = work.sheet.as_ref().context("missing sheet")?;
        assert_eq!(sheet.rows, vec![vec!["A", "north"], vec!["A", "north"], vec!["", ""]]);
        assert_eq!(input.rows, vec![vec!["A", "north"]]);
        assert_eq!(Sheet::parse(&sheet.csv()?)?, *sheet);
        let chart = counts(sheet, &work.positions()?, 1)?;
        let values = chart.column(1).as_any().downcast_ref::<Int64Array>().context("expected counts")?;
        assert_eq!(values.values().as_ref(), [1, 2]);
        Ok(())
    }
}
