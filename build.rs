fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("cargo:rerun-if-changed=proto/");

    // Try to compile proto files if protoc is available
    // This is optional for now - we'll use JSON fallback if proto compilation fails
    if std::env::var("PROTOC").is_ok() || std::path::Path::new("protoc").exists() {
        println!("Found protoc, compiling proto files...");
        prost_build::compile_protos(
            &[
                "proto/BackMsg.proto",
                "proto/ForwardMsg.proto",
                "proto/Element.proto",
                "proto/Widget.proto",
                "proto/WidgetStates.proto",
                "proto/Block.proto",
                "proto/FileBuffer.proto",
                "proto/Metadata.proto",
                "proto/Streamlit.proto",
            ],
            &["proto/"],
        )?;
        println!("Proto files compiled successfully!");
    } else {
        println!("protoc not found, using JSON fallback for WebSocket messages");
        println!("To install protoc:");
        println!("  - On Ubuntu/Debian: sudo apt-get install protobuf-compiler");
        println!("  - On macOS: brew install protobuf");
        println!("  - On Windows: Download from https://github.com/protocolbuffers/protobuf/releases");
        println!("  - Or set PROTOC environment variable to the protoc binary path");
    }

    Ok(())
}