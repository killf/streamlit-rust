# Streamlit Rust Backend

A pure Rust implementation of Streamlit backend with WebSocket support, compatible with the official Streamlit frontend.

## Features

- 🦀 **Pure Rust** - No Python dependencies, completely written in Rust
- 🚀 **High Performance** - Leverages Rust's performance and safety features
- 🔄 **WebSocket Compatible** - Compatible with official Streamlit frontend
- 🎨 **Python-like API** - Familiar Streamlit syntax (`st.write()`, `st.button()`, etc.)
- 🔧 **Extensible** - Easy to add new widgets and components
- 📦 **Modern Dependencies** - Uses latest versions of actix-web, tokio, and other crates

## Project Structure

This is a Cargo workspace with the following members:

```
streamlit-rust/
├── streamlit/          # Main library crate
│   ├── src/
│   │   ├── api.rs          # Streamlit API implementation
│   │   ├── server.rs       # HTTP and WebSocket server
│   │   ├── elements/       # UI element implementations
│   │   ├── websocket/      # WebSocket handlers
│   │   ├── error.rs        # Error types
│   │   └── lib.rs          # Public API
│   └── examples/           # Example applications
└── streamlit-macros/   # Procedural macros (#[main])
```

## Quick Start

### Running Examples

The easiest way to try out streamlit-rust is to run the included examples:

```bash
# Run the basic example
cargo run --example basic

# Run the hello world example
cargo run --example hello

# Run the timer example
cargo run --example timer

# Run the container/columns example
cargo run --example container
```

The server will start on `http://localhost:8501` by default.

### Basic Usage

```rust
use streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    // Set page title
    st.title("Hello from Rust!");

    // Write some text
    st.write("This is a demonstration of Streamlit in Rust.");

    // Display code
    st.code("fn main() { println!(\"Hello, world!\"); }", "rust");

    // Add a button
    if st.button("Click me!") {
        st.write("Button was clicked!");
    }
}
```

## API Endpoints

- **WebSocket**: `ws://localhost:8501/_stcore/stream` - Main WebSocket connection
- **Health Check**: `GET /_stcore/health` - Server status
- **Run Script**: `POST /api/run` - Execute Rust code
- **Index**: `GET /` - Basic info page

## Available Components

### Text Display
- `st.write(content)` - Plain text (supports markdown)
- `st.title(content)` / `st.h1(content)` - Title (h1)
- `st.header(content)` / `st.h2(content)` - Header (h2)
- `st.sub_header(content)` / `st.h3(content)` - Sub-header (h3)
- `st.markdown(content)` - Markdown content with extended options
- `st.caption(content)` - Small caption text
- `st.badge(label)` - Badge/icon component

### Code Display
- `st.code(code, language)` - Syntax-highlighted code block
- `CodeOptions::new(code, language)` - Advanced code display options
  - `.line_numbers(bool)` - Show line numbers
  - `.wrap_lines(bool)` - Wrap long lines
  - `.height(...)` - Set height
  - `.width(...)` - Set width

### Layout Components
- `st.container()` - Container for grouping elements
- `st.container_options(...)` - Container with options
  - `.border(bool)` - Show border
  - `.horizontal(bool)` - Horizontal layout
  - `.gap(...)` - Set gap size
  - `.alignment(...)` - Set alignment
- `st.columns(n)` - Create N columns
- `st.columns([v1, v2, ...])` - Create columns with custom weights
- `ColumnsOptions::new(...)` - Advanced column options

### Interactive Components
- `st.button(label)` - Button (returns true if clicked)
- `st.button_options(...)` - Button with options
  - `.key(...)` - Unique key
  - `.help(...)` - Help tooltip
  - `.type(...)` - Button type (primary/secondary)
  - `.icon(...)` - Icon
  - `.disabled(bool)` - Disable button
  - `.shortcut(...)` - Keyboard shortcut

### Utility Components
- `st.divider()` - Horizontal divider
- `st.divider_options(...)` - Custom divider width

## Architecture

```
┌─────────────────┐    ┌─────────────────┐
│  Streamlit      │    │  Streamlit      │
│  Frontend       │◄──►│  Rust Backend   │
│  (JavaScript)    │    │  (WebSocket)     │
└─────────────────┘    └─────────────────┘
```

1. **Frontend**: Official Streamlit frontend connects via WebSocket
2. **Backend**: Rust server processes widget requests and sends responses
3. **Protocol**: Compatible with official Streamlit WebSocket protocol

## Development

### Prerequisites

- Rust 2024 edition or later
- Cargo

### Building

```bash
# Build the workspace
cargo build

# Build with optimizations
cargo build --release
```

### Running Tests

```bash
cargo test
```

### Formatting

```bash
cargo fmt
```

## Examples

### Hello World

```rust
use streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    st.write("Hello world!");
}
```

### Markdown and Headers

```rust
use streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    st.title("🚀 Streamlit Rust Examples");
    st.header("Welcome to Streamlit in Rust!");
    st.sub_header("This is a sub-header");

    st.markdown(
        "You can use **bold text**, *italic text*, and `inline code` in markdown.\n\n\
        - Bullet point 1\n\
        - Bullet point 2\n\
        - Bullet point 3",
    );
}
```

### Code Display

```rust
use streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    st.header("Code Examples");

    st.sub_header("Rust Code");
    st.code(
        "fn main() {
            println!(\"Hello, Streamlit!\");
        }",
        "rust",
    );

    st.sub_header("Python Code with line numbers");
    st.code_options(
        CodeOptions::new(
            "import streamlit as st\n\nst.write(\"Hello from Python!\")",
            "python",
        )
        .line_numbers(true),
    );
}
```

### Layout with Containers and Columns

```rust
use streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    st.title("Container and Columns");

    st.write("Content outside container");

    // Container with border
    let container = st.container_options(ContainerOptions::new().border(true));
    container.write("Inside container");
    container.write("Also inside container");

    st.write("Back to main content");

    // Create columns
    if let [col1, col2, col3] = st.columns([1, 2, 1]) {
        col1.write("Left column (narrow)");
        col2.write("Middle column (wide)");
        col3.write("Right column (narrow)");
    }
}
```

### Buttons and Interactions

```rust
use streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    st.title("Button Examples");

    // Simple button
    if st.button("Click me!") {
        st.write("Button was clicked!");
    }

    // Button with options
    if st.button_options(
        ButtonOptions::new("Primary Action")
            .icon("🚀")
            .help("This is a helpful tooltip"),
    ) {
        st.write("Primary action triggered!");
    }

    // Multiple buttons in columns
    if let [col1, col2, col3] = st.columns(3) {
        if col1.button("Button 1") {
            col1.write("Clicked 1");
        }
        if col2.button("Button 2") {
            col2.write("Clicked 2");
        }
        if col3.button("Button 3") {
            col3.write("Clicked 3");
        }
    }
}
```

### Badge and Caption

```rust
use streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    st.title("Badges and Captions");

    st.badge(BadgeOptions::new("Home").color("red").icon("🏠"));
    st.badge(BadgeOptions::new("Active").color("green").icon("✅"));
    st.badge(BadgeOptions::new("Warning").color("orange").icon("⚠️"));

    st.write("Some content here");

    st.caption("This is a small caption text below the content");
}
```

## Compatibility

This implementation is designed to be compatible with:
- ✅ Official Streamlit frontend
- ✅ WebSocket protocol
- ✅ Standard Streamlit widgets and layout components
- 🔄 More widgets (slider, text_input, checkbox, etc.) - planned
- 🔄 Session management - planned
- 🔄 Advanced features - planned

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Add your improvements
4. Ensure tests pass (`cargo test`)
5. Send a pull request

## License

Apache License 2.0 - see LICENSE file for details.

## Acknowledgments

- Official Streamlit team for the amazing frontend and protocol
- Rust community for excellent web framework support
- actix-web and actix-ws maintainers for the solid WebSocket implementation