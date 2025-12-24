use streamlit::TableData;
use streamlit::StreamlitApi;

#[streamlit::main]
fn main(st: &mut Streamlit) {
    st.title("New Features Demo");

    // ===== DataFrame and Table =====
    st.sub_header("Data Display");

    // Create a simple table
    let table_data = TableData::StringTable(vec![
        vec!["Name".to_string(), "Age".to_string(), "City".to_string()],
        vec!["Alice".to_string(), "25".to_string(), "NYC".to_string()],
        vec!["Bob".to_string(), "30".to_string(), "LA".to_string()],
        vec!["Charlie".to_string(), "35".to_string(), "Chicago".to_string()],
    ]);
    st.table(table_data);

    // Create a named column table
    let df_data = TableData::NamedColumns {
        columns: vec!["Product".to_string(), "Price".to_string(), "Stock".to_string()],
        data: vec![
            vec!["Apple".to_string(), "1.50".to_string(), "100".to_string()],
            vec!["Banana".to_string(), "0.80".to_string(), "200".to_string()],
            vec!["Orange".to_string(), "1.20".to_string(), "150".to_string()],
        ],
    };
    st.dataframe(df_data);

    st.divider();

    // ===== Form Example =====
    st.sub_header("Form Example");

    let form = st.form("user_info");
    form.write("Please enter your information:");
    let name = form.text_input("Name", "", None);
    let email = form.text_input("Email", "", None);
    let age = form.number_input("Age", 25.0, None);
    let subscribe = form.checkbox("Subscribe to newsletter", false, None);
    form.form_submit_button("Submit");

    st.write(format!(
        "Form submitted: name={}, email={}, age={}, subscribe={}",
        name, email, age, subscribe
    ));

    st.divider();

    // ===== File Uploader Example =====
    st.sub_header("File Uploader");
    st.file_uploader("Upload a file", Some("file_upload"));
    st.caption("Accepts: .txt, .csv, .json files");

    st.divider();

    // ===== Download Button Example =====
    st.sub_header("Download Button");

    let csv_data = "Name,Age,City\nAlice,25,NYC\nBob,30,LA\nCharlie,35,Chicago"
        .as_bytes()
        .to_vec();
    st.download_button(
        "Download CSV",
        csv_data,
        "data.csv",
        Some("download_csv"),
    );

    let json_data = r#"{"name": "Alice", "age": 25, "city": "NYC"}"#.as_bytes().to_vec();
    st.download_button(
        "Download JSON",
        json_data,
        "data.json",
        Some("download_json"),
    );

    st.divider();

    // ===== Plotly Chart Example =====
    st.sub_header("Plotly Chart");

    // Simple bar chart
    let bar_chart_spec = r#"{
        "data": [{
            "x": ["Apple", "Banana", "Orange", "Grape"],
            "y": [10, 15, 8, 12],
            "type": "bar"
        }],
        "layout": {
            "title": "Fruit Sales"
        }
    }"#;
    st.plotly_chart(bar_chart_spec);

    // Line chart
    let line_chart_spec = r#"{
        "data": [{
            "x": [1, 2, 3, 4, 5],
            "y": [10, 15, 13, 17, 20],
            "type": "scatter",
            "mode": "lines+markers"
        }],
        "layout": {
            "title": "Growth Over Time",
            "xaxis": {"title": "Time"},
            "yaxis": {"title": "Value"}
        }
    }"#;
    st.plotly_chart(line_chart_spec);

    st.divider();

    // ===== Combined Example =====
    st.sub_header("Interactive Dashboard");

    let refresh = st.button("Refresh Data", Some("refresh"));

    if refresh {
        st.spinner("Loading data...");
        // Simulate data loading
        st.write("Data refreshed!");
    }

    // Display metrics
    st.metric("Total Users", "1,234", "+12%");
    st.metric("Revenue", "$5,678", "+8%");
    st.metric("Active Sessions", "42", "-3%");

    // Progress indicator
    st.progress(0.75, Some("Loading progress...".to_string()));
}
