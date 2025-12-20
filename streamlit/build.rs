use std::io::Result;

fn main() -> Result<()> {
    prost_build::Config::new()
        .default_package_filename("proto")
        .compile_protos(
            &[
                "streamlit/proto/ForwardMsg.proto",
                "streamlit/proto/BackMsg.proto",
            ],
            &[".."],
        )?;
    Ok(())
}
