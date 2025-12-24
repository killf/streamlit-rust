//! Streamlit Rust Backend
//!
//! A Rust implementation of Streamlit backend with WebSocket support.
//!
//! ## Usage
//!
//! ```rust
//! use streamlit::*;
//!
//! #[main]
//! fn main(st: &mut Streamlit) {
//!     st.title("Hello world!");
//! }
//! ```

extern crate streamlit_macros;

mod api;
mod core;
mod elements;
pub mod error;
mod memory;
mod proto;
pub mod server;
mod utils;
mod websocket;

pub use api::*;
pub use core::*;
pub use server::StreamlitServer;

pub use streamlit_macros::main;
