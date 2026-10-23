//! Streamlit Rust Backend
//!
//! A Rust implementation of Streamlit backend with WebSocket support.
//!
//! ## Usage
//!
//! ```rust,no_run
//! use ::streamlit::*;
//!
//! #[main]
//! async fn main(st: &Streamlit) {
//!     st.title("Hello world!");
//! }
//! ```

extern crate streamlit_macros;

pub mod api;
mod elements;
pub mod error;
mod memory;
pub mod proto;
pub mod server;
pub(crate) mod utils;
pub(crate) mod websocket;

pub use api::*;
pub use server::StreamlitServer;

pub use streamlit_macros::main;
