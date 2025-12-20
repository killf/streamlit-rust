pub mod simple_handler;
pub mod proto_handler;
pub mod message_types;
// pub mod frontend_handler; // Temporarily disabled - has protobuf compatibility issues
pub mod simple_frontend_handler;
pub mod minimal_handler;
pub mod streamlit_handler;

// Use Streamlit-compatible handler for real frontend
pub use streamlit_handler::handle_streamlit_websocket_connection;