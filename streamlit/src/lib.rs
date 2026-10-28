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
//!
//! Configure either address setting independently; omitted settings keep
//! host `0.0.0.0` and port `8501`.
//!
//! ```rust,no_run
//! use ::streamlit::*;
//!
//! #[main(host = "127.0.0.1")]
//! async fn main(st: &Streamlit) {
//!     st.title("Host configured; port 8501");
//! }
//! ```
//!
//! ```rust,no_run
//! use ::streamlit::*;
//!
//! #[main(port = 8503)]
//! async fn main(st: &Streamlit) {
//!     st.title("Port configured; host 0.0.0.0");
//! }
//! ```

extern crate streamlit_macros;

pub mod api;
mod cache;
mod charts;
pub mod column_config;
pub mod data;
mod data_api;
mod elements;
pub mod error;
pub mod media;
mod memory;
mod navigation;
pub mod proto;
pub mod pywire;
mod query_params;
pub mod request_context;
mod server;
mod session;
mod upload;
pub(crate) mod utils;
pub(crate) mod websocket;
mod widget_api;
mod widgets;

pub use api::*;
pub use cache::{CachedData, CachedResource};
pub use charts::{AreaChartOptions, LineChartOptions, MapOptions, ScatterChartOptions};
pub use column_config::{ColumnBase, ColumnConfig, ColumnConfigs};
pub use data_api::*;
pub use elements::common::{ElementHeight, ElementWidth};
pub use elements::components::{ComponentMount, ComponentV2};
pub use media::{ByteRange, RgbaImage};
pub use navigation::{Navigation, Page, PageLinkOptions, PageTarget};
pub use query_params::QueryParams;
pub use request_context::{HeaderAuthenticator, RequestAuthenticator, RequestContext, RequestHeaderAccess, UserIdentity, UserView};
pub use server::StreamlitServer;
pub use session::{RunControl, SessionState};
pub use upload::{UploadedFile, UploadedFiles};
pub use widget_api::*;
pub use widgets::{WidgetCallback, WidgetError};

/// Macro support only: the `#[main]` macro expands to these re-exports so a
/// consumer needs no direct tokio or env_logger dependency. Not a public API;
/// the support contract moves with the macro in this workspace.
#[doc(hidden)]
pub mod __macro {
    pub use env_logger;
    pub use tokio;
}

pub use streamlit_macros::main;
