fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("cargo:rerun-if-changed=streamlit/proto/");

    // Try to compile proto files if protoc is available
    if std::env::var("PROTOC").is_ok() || std::path::Path::new("protoc").exists() {
        println!("Found protoc, compiling official Streamlit proto files...");

        // Configure prost build
        let mut config = prost_build::Config::new();
        config.protoc_arg("--experimental_allow_proto3_optional");

        // Compile the official ForwardMsg.proto and its dependencies
        // ForwardMsg.proto will automatically pull in its imports
        config.compile_protos(
            &[
                "streamlit/proto/ForwardMsg.proto",
                "streamlit/proto/BackMsg.proto",
            ],
            &["streamlit/proto/"],
        )?;
        println!("Official Streamlit proto files compiled successfully!");
    } else {
        println!("protoc not found, using manual protobuf encoding");
        println!("To install protoc:");
        println!("  - On Ubuntu/Debian: sudo apt-get install protobuf-compiler");
        println!("  - On macOS: brew install protobuf");
        println!("  - On Windows: Download from https://github.com/protocolbuffers/protobuf/releases");
        println!("  - Or set PROTOC environment variable to the protoc binary path");
    }

    Ok(())
}