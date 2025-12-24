use streamlit::*;

#[main]
fn main(st: &Streamlit) {
    st.title("Streamlit Rust - Complete Feature Demo");

    st.write("This demo showcases all implemented Streamlit features in Rust.");

    st.divider();

    // ===== Headers =====
    st.header("Headers & Text");

    st.title("Title (H1)");
    st.header("Header (H2)");
    st.sub_header("Sub Header (H3)");

    st.write("Regular text using write()");
    st.markdown("**Bold**, *italic*, and `code` in markdown.");
    st.caption("This is a caption text");
    st.badge("New Feature");
    st.code("fn main() { println!(\"Hello, Rust!\"); }", "rust");

    st.divider();

    // ===== Layout =====
    st.header("Layout & Containers");

    st.write("Using columns to display content side by side:");
    let cols = st.columns(3);
    cols[0].write("Column 1");
    cols[1].write("Column 2");
    cols[2].write("Column 3");

    st.write("Using a container with border:");
    let container = st.container();
    container.write("Content inside a container");
    container.write("Multiple elements can be added");

    st.divider();

    // ===== Metrics =====
    st.header("Metrics / KPIs");

    let metric_cols = st.columns(4);
    metric_cols[0].metric("Revenue", "$123,456", "+12.5%");
    metric_cols[1].metric("Users", "1,234", "+5.2%");
    metric_cols[2].metric("Conversion", "3.45%", "-0.8%");
    metric_cols[3].metric("Sessions", "567", "+2.1%");

    st.divider();

    // ===== Buttons =====
    st.header("Buttons");

    if st.button("Click Me!", None) {
        st.success("You clicked the button!");
    }

    if st.button("Show Info", Some("show_info")) {
        st.info("Info button clicked!");
    }

    st.divider();

    // ===== Input Widgets =====
    st.header("Input Widgets");

    // Checkbox
    let show_advanced = st.checkbox("Show Advanced Options", false, Some("show_advanced"));
    if show_advanced {
        st.info("Advanced options are now visible!");
    }

    // Text Input
    let name = st.text_input("Enter your name", "Guest", Some("name"));
    if !name.is_empty() {
        st.write(&format!("Hello, {}!", name));
    }

    // Number Input
    let age = st.number_input("Enter your age", 25.0, Some("age"));
    st.write(&format!("Age: {}", age));

    // Slider
    let rating = st.slider("Rate this demo", 1.0, 5.0, 4.0, Some("rating"));
    st.write(&format!("Rating: {}/5", rating));

    // Selectbox
    let options = vec![
        "Option A".to_string(),
        "Option B".to_string(),
        "Option C".to_string(),
    ];
    let (idx, selected) = st.selectbox("Choose an option", options.clone(), 0, Some("select_option"));
    st.write(&format!("Selected: {} (index {})", selected, idx));

    // Radio
    let colors = vec!["Red".to_string(), "Green".to_string(), "Blue".to_string()];
    let (_color_idx, color) = st.radio("Favorite color", colors, 0, Some("fav_color"));
    st.write(&format!("Favorite color: {}", color));

    // Color Picker
    let picked_color = st.color_picker("Choose a color", "#FF0000", Some("color_picker"));
    st.write(&format!("Selected color: {}", picked_color));

    // Time Input
    let time = st.time_input("Select a time", Some("12:00:00"), Some("time_input"));
    if let Some(t) = time {
        st.write(&format!("Selected time: {}", t));
    }

    // Date Input
    let date = st.date_input("Select a date", vec!["2024-01-01"], Some("date_input"));
    if !date.is_empty() {
        st.write(&format!("Selected date: {}", date.join(", ")));
    }

    // Multiselect
    let fruits = vec![
        "Apple".to_string(),
        "Banana".to_string(),
        "Orange".to_string(),
        "Grape".to_string(),
    ];
    let (_fruit_indices, fruit_values) = st.multiselect(
        "Choose fruits",
        fruits,
        vec![0, 2], // Default: Apple and Orange
        Some("multiselect_fruits")
    );
    if !fruit_values.is_empty() {
        st.write(&format!("Selected fruits: {}", fruit_values.join(", ")));
    }

    st.divider();

    // ===== Forms =====
    st.header("Forms");

    let form = st.form("user_feedback");
    form.write("Please provide your feedback:");
    let feedback_name = form.text_input("Name", "", None);
    let feedback_email = form.text_input("Email", "", None);
    let feedback_rating = form.slider("Rating", 1.0, 5.0, 3.0, None);
    let feedback_recommend = form.checkbox("I recommend this app", true, None);
    form.form_submit_button("Submit Feedback");

    st.write(&format!(
        "Feedback: name={}, email={}, rating={}/5, recommend={}",
        feedback_name, feedback_email, feedback_rating, feedback_recommend
    ));

    st.divider();

    // ===== Data Display =====
    st.header("Data Display");

    st.sub_header("Simple Table");
    let table_data = TableData::StringTable(vec![
        vec!["Name".to_string(), "Age".to_string(), "City".to_string()],
        vec!["Alice".to_string(), "25".to_string(), "NYC".to_string()],
        vec!["Bob".to_string(), "30".to_string(), "LA".to_string()],
        vec!["Charlie".to_string(), "35".to_string(), "Chicago".to_string()],
    ]);
    st.table(table_data);

    st.sub_header("DataFrame with Named Columns");
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

    // ===== File Upload & Download =====
    st.header("File Operations");

    st.file_uploader("Upload a file", Some("file_upload"));
    st.caption("Accepts: .txt, .csv, .json files");

    let csv_data = "Name,Age,City\nAlice,25,NYC\nBob,30,LA".as_bytes().to_vec();
    st.download_button("Download CSV", csv_data, "data.csv", Some("download_csv"));

    st.divider();

    // ===== Charts =====
    st.header("Charts");

    let bar_chart = r#"{
        "data": [{
            "x": ["Apple", "Banana", "Orange"],
            "y": [10, 15, 8],
            "type": "bar"
        }],
        "layout": {
            "title": "Fruit Sales"
        }
    }"#;
    st.plotly_chart(bar_chart);

    st.divider();

    // ===== Alerts =====
    st.header("Alert Messages");

    st.success("This is a success message!");
    st.info("This is an info message!");
    st.warning("This is a warning message!");
    st.error("This is an error message!");

    st.divider();

    // ===== Progress & Status =====
    st.header("Progress & Status");

    st.write("Progress bars:");
    st.progress(0.25, Some("25% complete".to_string()));
    st.progress(0.50, Some("50% complete".to_string()));
    st.progress(0.75, Some("75% complete".to_string()));

    st.write("Spinners (loading indicators):");
    st.spinner("Loading data...");
    st.spinner("Processing request...");

    st.divider();

    // ===== Visual Effects =====
    st.header("Visual Effects");

    if st.button("Show Balloons", Some("balloons")) {
        st.balloons();
    }

    if st.button("Show Snow", Some("snow")) {
        st.snow();
    }

    st.divider();

    // ===== Images =====
    st.header("Images");

    st.image(
        Some("https://picsum.photos/400/200".to_string()),
        Some("Random image from picsum.photos".to_string()),
    );

    st.divider();

    // ===== Combined Example =====
    st.header("Interactive Dashboard Example");

    let refresh = st.button("Refresh Dashboard", Some("refresh"));

    if refresh {
        st.spinner("Refreshing data...");
        st.success("Dashboard refreshed!");
    }

    // Dashboard metrics
    let dash_cols = st.columns(3);
    dash_cols[0].metric("Today's Sales", "$4,250", "+15%");
    dash_cols[1].metric("New Users", "123", "+8%");
    dash_cols[2].metric("Conversion Rate", "2.5%", "+0.3%");

    st.divider();
    st.caption("Built with Streamlit Rust - Pure Rust implementation!");
}
