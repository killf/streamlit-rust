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
pub mod data;
mod data_api;
mod elements;
pub mod error;
mod memory;
pub mod proto;
pub mod server;
mod session;
mod upload;
pub(crate) mod utils;
pub(crate) mod websocket;
mod widget_api;
mod widgets;

pub use api::*;
pub use data_api::*;
pub use server::StreamlitServer;
pub use session::SessionState;
pub use upload::{UploadedFile, UploadedFiles};
pub use widget_api::*;
pub use widgets::{WidgetCallback, WidgetError};

pub use streamlit_macros::main;
