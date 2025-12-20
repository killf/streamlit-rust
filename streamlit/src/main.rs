use streamlit::StreamlitServer;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    env_logger::Builder::from_default_env().init();
    log::info!("Starting Streamlit Rust Backend v0.1.0");

    // Create and start the server
    let server = StreamlitServer::new();
    server.start("0.0.0.0", 8502).await?;

    Ok(())
}