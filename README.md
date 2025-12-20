# Streamlit Rust Backend

A pure Rust implementation of Streamlit backend with WebSocket support, compatible with the official Streamlit frontend.

## Features

- 🦀 **Pure Rust** - No Python dependencies, completely written in Rust
- 🚀 **High Performance** - Leverages Rust's performance and safety features
- 🔄 **WebSocket Compatible** - Compatible with official Streamlit frontend
- 🎨 **Python-like API** - Familiar Streamlit syntax (`st.write()`, `st.button()`, etc.)
- 🔧 **Extensible** - Easy to add new widgets and components
- 📦 **Modern Dependencies** - Uses latest versions of actix-web, tokio, and other crates

## Quick Start

### Installation

Add this to your `Cargo.toml`:

```toml
[dependencies]
streamlit-rust = "0.1.0"
```

### Basic Usage

```rust
use streamlit::*;

fn main() {
    let app = get_app();

    // Clear previous elements
    app.clear_elements();

    // Create your Streamlit app
    app.title("Hello from Rust!");
    app.write("This is a demonstration of Streamlit in Rust.");

    // Interactive widgets
    let name = app.text_input("Enter your name:", Some("World"), Some("name"));
    app.write(&format!("Hello, {}!", name));

    let slider_value = app.slider("Select a number:", 0.0, 100.0, Some(50.0), Some("slider"));
    app.write(&format!("You selected: {}", slider_value));

    if app.button("Click me!", Some("action")) {
        app.write("Button was clicked!");
    }
}
```

### Running the Server

```bash
cargo run
```

The server will start on `http://localhost:8502` by default.

## API Endpoints

- **WebSocket**: `ws://localhost:8502/_stcore/stream` - Main WebSocket connection
- **Health Check**: `GET /_stcore/health` - Server status
- **Run Script**: `POST /api/run` - Execute Rust code
- **Index**: `GET /` - Basic info page

## Available Widgets

### Text Display
- `st.write(content)` - Plain text
- `st.title(content)` - Title (h1)
- `st.header(content)` - Header (h2)
- `st.markdown(content)` - Markdown content

### Interactive Widgets
- `st.button(label, key)` - Button
- `st.slider(label, min, max, value, key)` - Slider
- `st.text_input(label, value, key)` - Text input
- `st.checkbox(label, value, key)` - Checkbox
- `st.selectbox(label, options, index, key)` - Selectbox
- `st.number_input(label, min, max, value, key)` - Number input

## Architecture

```
┌─────────────────┐    ┌─────────────────┐
│  Streamlit      │    │  Streamlit      │
│  Frontend       │◄──►│  Rust Backend   │
│  (TypeScript)    │    │  (WebSocket)     │
└─────────────────┘    └─────────────────┘
```

1. **Frontend**: Official Streamlit frontend connects via WebSocket
2. **Backend**: Rust server processes widget requests and sends responses
3. **Protocol**: Compatible with official Streamlit WebSocket protocol

## Development

### Building

```bash
cargo build
```

### Running Tests

```bash
cargo test
```

### Code Structure

```
src/
├── api.rs          # Streamlit API implementation
├── server.rs       # HTTP and WebSocket server
├── websocket/      # WebSocket handlers
├── error.rs        # Error types
└── lib.rs          # Public API
```

## Examples

### Simple Counter App

```rust
use streamlit::*;

fn main() {
    let app = get_app();
    app.clear_elements();

    app.title("Counter App");

    let count = app.number_input("Count:", 0.0, 100.0, Some(0.0), Some("counter"));
    app.write(&format!("Current count: {}", count));

    if app.button("Increment", Some("increment")) {
        // This will trigger a rerun with the new value
    }
}
```

### Data Processing App

```rust
use streamlit::*;

fn main() {
    let app = get_app();
    app.clear_elements();

    app.title("Data Processing");

    let multiplier = app.slider("Multiplier:", 1.0, 10.0, Some(2.0), Some("mult"));
    let input = app.number_input("Input number:", 0.0, 100.0, Some(50.0), Some("input"));

    let result = input * multiplier;
    app.write(&format!("{} × {} = {}", input, multiplier, result));

    app.write(&format!("Calculation performed at run #{}", app.get_run_count()));
}
```

## Compatibility

This implementation is designed to be compatible with:
- ✅ Official Streamlit frontend
- ✅ WebSocket protocol
- ✅ Standard Streamlit widgets
- 🔄 Custom widgets (planned)
- 🔄 Advanced features like session management (planned)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your improvements
4. Send a pull request

## License

Apache License 2.0 - see LICENSE file for details.

## Acknowledgments

- Official Streamlit team for the amazing frontend and protocol
- Rust community for excellent web framework support
- actix-web and actix-ws maintainers for the solid WebSocket implementation