"""Text-only CSV workbench reference; session edits never rewrite upload bytes."""

import csv
import io
from collections import Counter

import pandas as pd
import streamlit as st


def parse_csv(raw):
    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    records = [row for row in reader if row]
    if not records:
        raise ValueError("The CSV header is empty.")
    headers = records[0]
    if any(name == "" for name in headers):
        raise ValueError("CSV column names must not be empty.")
    if len(set(headers)) != len(headers):
        raise ValueError("CSV column names must be unique.")
    for number, row in enumerate(records[1:], 2):
        if len(row) != len(headers):
            raise ValueError(f"CSV row {number}: expected {len(headers)} fields, found {len(row)}.")
    return headers, records[1:]


def export_csv(headers, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def table(headers, rows):
    return pd.DataFrame(rows, columns=headers, dtype="str")


def text_rows(frame):
    return [["" if pd.isna(value) else str(value) for value in row] for row in frame.itertuples(index=False, name=None)]


def reset_drafts(work):
    work["version"] += 1
    work["view"] = None
    work["view_epoch"] += 1
    work["selected"] = None
    work["detail_token"] = None
    work["detail_epoch"] += 1


def render():
    st.title("CSV workbench")
    uploaded = st.file_uploader("Upload CSV", type=["csv"], accept_multiple_files=False, key="wb-upload")
    st.button("Ordinary rerun", key="wb-rerun")
    if "wb-work" in st.session_state and st.button("Clear working copy", key="wb-clear"):
        st.session_state.pop("wb-work", None)
        st.session_state.pop("wb-attempt", None)
        st.rerun()
        return

    # 1. The real frontend emits an empty uploader state before a replacement
    # file; it only clears the selection. The working copy is removed
    # exclusively by the explicit Clear button above.
    if uploaded is None:
        st.session_state.pop("wb-attempt", None)
    else:
        attempt = st.session_state.get("wb-attempt")
        if attempt is None or attempt["id"] != uploaded.file_id:
            attempt = {"id": uploaded.file_id, "error": None}
            raw = uploaded.getvalue()
            try:
                headers, rows = parse_csv(raw)
            except (UnicodeError, ValueError, csv.Error) as error:
                attempt["error"] = str(error)
            else:
                st.session_state["wb-work"] = {"source": uploaded.file_id, "name": uploaded.name, "original": raw,
                                               "headers": headers, "rows": rows, "version": 1, "view": None,
                                               "view_epoch": 0, "selected": None, "detail_token": None, "detail_epoch": 0}
            st.session_state["wb-attempt"] = attempt
        if st.session_state["wb-attempt"]["error"] is not None:
            st.error("Could not parse CSV: " + st.session_state["wb-attempt"]["error"])
    work = st.session_state.get("wb-work")
    if work is not None and st.session_state.get("wb-attempt", {}).get("error") is not None:
        st.warning("Showing previous valid source: " + work["name"])
    if work is None:
        st.info("Upload a CSV to begin.")
        return

    st.write("Working source: " + work["name"])
    source = work["source"]
    headers = work["headers"]
    filter_column = st.selectbox("Filter column", headers, key="wb-filter-column-" + source)
    enabled = st.checkbox("Filter enabled", value=False, key="wb-filter-enabled-" + source)
    exact = st.text_input("Exact value", value="", key="wb-filter-value-" + source)
    count_by = st.selectbox("Count by", headers, key="wb-count-" + source)
    view = (filter_column, enabled, exact)
    view_changed = work["view"] != view
    if view_changed:
        work["view"] = view
        work["view_epoch"] += 1
        work["selected"] = None
        work["detail_token"] = None
        work["detail_epoch"] += 1
    column = headers.index(filter_column)
    indices = [index for index, row in enumerate(work["rows"]) if not enabled or row[column] == exact]
    visible = [work["rows"][index] for index in indices]
    st.write(f"Rows: {len(work['rows'])}; matching: {len(visible)}")

    # 2. 选择位置映射回源行，详情草稿绑定来源、版本、筛选视图和源行。
    st.subheader("Rows")
    event = st.dataframe(table(headers, visible), key=f"wb-rows-{source}-{work['version']}-{work['view_epoch']}",
                         on_select="rerun", selection_mode="single-row", height=190, width=700, hide_index=True)
    selected = indices[event.selection.rows[0]] if event.selection.rows and event.selection.rows[0] < len(indices) else None
    selection_changed = selected != work["selected"]
    if selection_changed:
        work["selected"] = selected
        work["detail_token"] = None
        work["detail_epoch"] += 1
    count_index = headers.index(count_by)
    counts = Counter(row[count_index] for row in visible)
    chart = pd.DataFrame({"value": pd.Series(sorted(counts), dtype="str"), "count": pd.Series([counts[value] for value in sorted(counts)], dtype="int64")})
    st.vega_lite_chart(chart, {"mark": "bar", "encoding": {"x": {"field": "value", "type": "nominal"},
                                                             "y": {"field": "count", "type": "quantitative"}}})

    st.subheader("Detail draft")
    if selected is None:
        st.info("Select a row to edit.")
    else:
        token = (source, work["version"], view, selected, work["detail_epoch"])
        previous_token = work["detail_token"]
        work["detail_token"] = token
        detail = st.data_editor(table(headers, [work["rows"][selected]]), num_rows="fixed", height=150, width=700,
                                key=f"wb-detail-{source}-{work['version']}-{work['detail_epoch']}-{selected}")
        if st.button("Apply", key=f"wb-apply-{source}-{work['version']}-{work['detail_epoch']}-{selected}"):
            if previous_token != token or view_changed or selection_changed:
                st.warning("The detail draft changed. Select and edit the current row before applying.")
            else:
                work["rows"][selected] = text_rows(detail)[0]
                reset_drafts(work)
                st.session_state["wb-work"] = work
                st.rerun()
                return

    # 3. 新增草稿只随来源/工作版本重置，不随筛选或详情选择重置。
    st.subheader("New rows draft")
    added = st.data_editor(table(headers, []), num_rows="dynamic", height=190, width=700,
                           key=f"wb-add-{source}-{work['version']}")
    if st.button("Append", key=f"wb-append-{source}-{work['version']}"):
        rows = text_rows(added)
        if not rows:
            st.info("No new rows to append.")
        else:
            work["rows"].extend(rows)
            reset_drafts(work)
            st.session_state["wb-work"] = work
            st.rerun()
            return
    st.download_button("Download CSV", export_csv(headers, work["rows"]), file_name="workbench.csv", mime="text/csv", on_click="ignore",
                       key=f"wb-download-{source}-{work['version']}")
    st.session_state["wb-work"] = work


render()
