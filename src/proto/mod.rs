// Generated protobuf modules will be included here when protoc is available
// For now, this module serves as a placeholder for future proto integration

#[cfg(feature = "proto-compiled")]
pub mod streamlit {
    include!(concat!(env!("OUT_DIR"), "/streamlit.rs"));
}

#[cfg(not(feature = "proto-compiled"))]
pub mod streamlit {
    // Placeholder module for when protoc is not available
    // The actual proto functionality is handled in websocket/proto_handler.rs
    // with JSON-based communication for compatibility

    use serde::{Deserialize, Serialize};

    #[derive(Debug, Clone, Serialize, Deserialize)]
    pub struct MockBackMsg {
        pub hash: Option<String>,
        pub run_script: Option<bool>,
    }

    #[derive(Debug, Clone, Serialize, Deserialize)]
    pub struct MockForwardMsg {
        pub delta_path: Vec<String>,
        pub data: serde_json::Value,
    }

    pub type BackMsg = MockBackMsg;
    pub type ForwardMsg = MockForwardMsg;
}

// Re-export proto handler for easy access
pub use crate::websocket::proto_handler::*;