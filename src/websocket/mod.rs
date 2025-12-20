pub mod simple_handler;
pub mod proto_handler;
pub mod message_types;


// Use proto handler by default, fallback to simple handler for compatibility
pub use proto_handler::handle_websocket_connection;