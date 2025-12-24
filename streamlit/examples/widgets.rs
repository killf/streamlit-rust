use ::streamlit::*;
use std::sync::atomic::{AtomicI32, Ordering};

#[main]
fn main(st: &Streamlit) {
    st.title("Streamlit Rust - Complete Widgets Demo");

    st.write("This demonstrates all implemented widgets.");

    st.divider();

    // Metrics Section
    st.header("Metrics (KPI Display)");

    let col1 = st.columns(3);
    col1[0].metric("Revenue", "$123,456", "+12.5%");
    col1[1].metric("Users", "1,234", "+5.2%");
    col1[2].metric("Conversion", "3.45%", "-0.8%");

    st.divider();

    // Button Section
    st.header("Buttons");

    if st.button("Click me!", None) {
        st.write("You clicked the button!");
    }

    st.divider();

    // Counter example with buttons
    static COUNTER: AtomicI32 = AtomicI32::new(0);

    st.sub_header("Counter Example");
    let cols = st.columns(2);
    cols[0].write("Counter:");
    cols[1].write(&format!("{}", COUNTER.load(Ordering::SeqCst)));

    if st.button("Increment", Some("increment")) {
        COUNTER.fetch_add(1, Ordering::SeqCst);
    }

    if st.button("Decrement", Some("decrement")) {
        COUNTER.fetch_sub(1, Ordering::SeqCst);
    }

    if st.button("Reset", Some("reset_counter")) {
        COUNTER.store(0, Ordering::SeqCst);
    }

    st.divider();

    // Checkbox Section
    st.header("Checkboxes");

    let show_details = st.checkbox("Show details", false, Some("show_details"));

    if show_details {
        st.write("Here are the details you asked for!");
    } else {
        st.write("Check the box to see details.");
    }

    st.divider();

    // Slider Section
    st.header("Sliders");

    let age = st.slider("Age", 0.0, 100.0, 25.0, Some("age"));
    st.write(&format!("Selected age: {}", age));

    let temperature = st.slider("Temperature (C)", -50.0, 50.0, 20.0, Some("temp"));
    st.write(&format!("Selected temperature: {}°C", temperature));

    let rating = st.slider("Rating", 1.0, 5.0, 3.0, Some("rating"));
    st.write(&format!("Rating: {}/5", rating));

    st.divider();

    // Text Input Section
    st.header("Text Inputs");

    let name = st.text_input("Your name", "Guest", Some("name"));
    st.write(&format!("Hello, {}!", name));

    let message = st.text_input("Message", "", Some("message"));
    if !message.is_empty() {
        st.write(&format!("You said: {}", message));
    }

    st.divider();

    // Number Input Section
    st.header("Number Inputs");

    let count = st.number_input("Count", 10.0, Some("count"));
    st.write(&format!("Count: {}", count));

    let price = st.number_input("Price", 99.99, Some("price"));
    st.write(&format!("Price: ${}", price));

    st.divider();

    // Selectbox Section
    st.header("Selectbox (Dropdown)");

    let options = vec![
        "Option A".to_string(),
        "Option B".to_string(),
        "Option C".to_string(),
        "Option D".to_string(),
    ];

    let (index, selected) = st.selectbox("Choose an option", options.clone(), 0, Some("select_option"));
    st.write(&format!("You selected: {} (index {})", selected, index));

    st.divider();

    // Radio Section
    st.header("Radio Buttons");

    let colors = vec![
        "Red".to_string(),
        "Green".to_string(),
        "Blue".to_string(),
        "Yellow".to_string(),
    ];

    let (color_index, color) = st.radio("Choose your favorite color", colors, 0, Some("fav_color"));
    st.write(&format!("Your favorite color: {} (index {})", color, color_index));

    st.divider();

    // Combined Example
    st.header("Combined Example");

    let enabled = st.checkbox("Enable advanced options", false, Some("advanced"));

    if enabled {
        let category_idx = st.selectbox("Category", vec!["Electronics".to_string(), "Books".to_string(), "Clothing".to_string()], 0, Some("category")).0;
        let threshold = st.slider("Price Threshold", 0.0, 1000.0, 500.0, Some("threshold"));
        let discount = st.number_input("Discount %", 10.0, Some("discount"));
        let notes = st.text_input("Notes", "", Some("notes"));

        st.write(&format!("Category: {}", if category_idx == 0 { "Electronics" } else if category_idx == 1 { "Books" } else { "Clothing" }));
        st.write(&format!("Price Threshold: ${}", threshold));
        st.write(&format!("Discount: {}%", discount));
        if !notes.is_empty() {
            st.write(&format!("Notes: {}", notes));
        }
    }

    st.divider();

    // Dashboard Example
    st.header("Mini Dashboard");

    // Metrics row
    let metric_cols = st.columns(4);
    metric_cols[0].metric("Sales", "$42,500", "+15%");
    metric_cols[1].metric("Orders", "1,234", "+8%");
    metric_cols[2].metric("Avg Order", "$34.50", "-2%");
    metric_cols[3].metric("Returns", "2.3%", "-0.5%");

    // Filters
    st.sub_header("Filters");

    let status = st.selectbox(
        "Order Status",
        vec!["All".to_string(), "Pending".to_string(), "Completed".to_string(), "Cancelled".to_string()],
        0,
        Some("status_filter")
    ).1;

    let min_amount = st.number_input("Min Amount", 0.0, Some("min_amount"));
    let show_details = st.checkbox("Show detailed view", false, Some("show_details"));

    st.write(&format!("Showing {} orders with amount >= ${}", status, min_amount));

    if show_details {
        st.code(
            "fn main(st: &Streamlit) {
    // Metrics
    st.metric(\"Revenue\", \"$123,456\", \"+12.5%\");

    // Widgets
    let name = st.text_input(\"Name\", \"Guest\", None);
    let age = st.slider(\"Age\", 0.0, 100.0, 25.0, None);
    let checked = st.checkbox(\"Enable\", false, None);
    let (idx, value) = st.selectbox(\"Choose\", options, 0, None);
    let num = st.number_input(\"Count\", 10.0, None);

    // Button
    if st.button(\"Submit\", None) {
        st.write(\"Submitted!\");
    }
}",
            "rust"
        );
    }

    st.divider();

    // Progress and Spinner Section
    st.header("Progress Indicators");

    st.sub_header("Progress Bar");
    st.write("Different progress levels:");

    st.progress(0.25, Some("25% complete".to_string()));
    st.progress(0.50, Some("50% complete".to_string()));
    st.progress(0.75, Some("75% complete".to_string()));
    st.progress(1.00, Some("100% complete!".to_string()));

    st.divider();

    st.sub_header("Spinner");
    st.write("Loading indicators:");
    st.spinner("Loading data...");
    st.spinner("Processing...");
    st.spinner("In progress...");

    st.divider();
    st.caption("Built with Streamlit Rust - Pure Rust implementation");
}
