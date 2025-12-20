use streamlit::{get_app};

fn main() {
    let app = get_app();

    // Clear previous elements
    app.clear_elements();

    // Create a simple Streamlit app in Rust
    app.title("Hello Streamlit Rust!");

    app.write("This is a demonstration of the Rust implementation of Streamlit.");
    app.write("You can use the same familiar API as Python Streamlit, but written in pure Rust!");

    app.header("Interactive Widgets");

    let name = app.text_input("Enter your name:", Some("World"), Some("name_input"));
    app.write(&format!("Hello, {}!", name));

    let slider_value = app.slider("Select a number:", 0.0, 100.0, Some(50.0), Some("slider"));
    app.write(&format!("You selected: {}", slider_value));

    let checkbox_value = app.checkbox("Enable something", Some(false), Some("enable_feature"));
    if checkbox_value {
        app.write("✅ Feature is enabled!");
    } else {
        app.write("❌ Feature is disabled.");
    }

    let options = vec!["Option A".to_string(), "Option B".to_string(), "Option C".to_string()];
    let selected = app.selectbox("Choose an option:", options, Some(0), Some("selectbox"));
    app.write(&format!("You chose: {}", selected));

    if app.button("Click me!", Some("action_button")) {
        app.write("🎉 Button was clicked!");
    }

    app.header("Markdown Content");

    let markdown_content = r#"
## Markdown Example

This demonstrates **bold text** and *italic text*.

### Code Example

```rust
fn hello() -> String {
    "Hello from Rust!".to_string()
}
```

### Lists

- Item 1
- Item 2
- Item 3

### Math

The formula for the area of a circle: A = πr²
"#;

    app.markdown(markdown_content);

    app.header("Data Display");

    // In a real implementation, you could display data frames, charts, etc.
    app.write("Data visualization components will be implemented in future versions.");

    app.write(&format!("App has been run {} times", app.get_run_count()));
}