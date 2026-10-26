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
pub use server::StreamlitServer;
pub use session::{RunControl, SessionState};
pub use upload::{UploadedFile, UploadedFiles};
pub use widget_api::*;
pub use widgets::{WidgetCallback, WidgetError};

pub use streamlit_macros::main;
