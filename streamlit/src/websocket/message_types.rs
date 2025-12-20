use serde::{Deserialize, Serialize};

/// Simplified message structure for WebSocket communication
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StreamlitMessage {
    #[serde(rename = "type")]
    pub type_field: String,
    pub data: serde_json::Value,
}

/// Command structure for Streamlit operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StreamlitCommand {
    pub command: String,
    pub data: serde_json::Value,
}