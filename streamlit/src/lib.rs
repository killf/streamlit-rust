//! Streamlit Rust Backend
//!
//! A Rust implementation of Streamlit backend with WebSocket support.
//!
//! ## Usage
//!
//! ```rust
//! use streamlit::*;
//!
//! #[streamlit_macros::main]
//! fn main(st: &mut Streamlit) {
//!     st.title("Hello world!");
//! }
//! ```

extern crate streamlit_macros;

pub mod api;
pub mod error;
pub mod server;
pub mod websocket;

pub mod proto;

// Re-export main components
pub use api::StreamlitApp as Streamlit;
pub use api::*;
pub use server::{set_main_function, StreamlitServer};

// Re-export the proc-macro for convenience
pub use streamlit_macros::main;
