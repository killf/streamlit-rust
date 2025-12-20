use thiserror::Error;

#[derive(Error, Debug)]
pub enum StreamlitError {
    #[error("WebSocket error: {0}")]
    WebSocket(String),

    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Session error: {0}")]
    Session(String),

    #[error("Script execution error: {0}")]
    ScriptExecution(String),

    #[error("Component error: {0}")]
    Component(String),

    #[error("Authentication error: {0}")]
    Authentication(String),

    #[error("Invalid message format: {0}")]
    InvalidMessage(String),

    #[error("HTTP error: {0}")]
    Http(String),
}

pub type Result<T> = std::result::Result<T, StreamlitError>;