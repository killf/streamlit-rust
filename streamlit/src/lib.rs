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

// Include protobuf module if available
#[cfg(feature = "proto-compiled")]
pub mod proto;

// Include the streamlit module from protobuf generation
#[cfg(feature = "proto-compiled")]
pub mod streamlit {
    include!(concat!(env!("OUT_DIR"), "/streamlit.rs"));
}

// Re-export main components
pub use api::*;
pub use server::{set_main_function, StreamlitServer};
pub use api::StreamlitApp as Streamlit;

// Re-export the proc-macro for convenience
pub use streamlit_macros::main;
