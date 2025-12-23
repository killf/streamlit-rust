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
mod elements;
pub mod error;
pub mod proto;
pub mod server;
mod utils;
pub(crate) mod websocket;

pub use api::*;
pub use server::StreamlitServer;

pub use streamlit_macros::main;
