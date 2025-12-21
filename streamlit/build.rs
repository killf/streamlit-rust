use std::io::Result;

fn main() -> Result<()> {
    prost_build::Config::new()
        .default_package_filename("proto")
        .compile_protos(
            &[
                "streamlit/proto/ForwardMsg.proto",
                "streamlit/proto/BackMsg.proto",
                "streamlit/proto/Element.proto",
                "streamlit/proto/Text.proto",
                "streamlit/proto/Heading.proto",
                "streamlit/proto/Code.proto",
                "streamlit/proto/Markdown.proto",
                "streamlit/proto/Empty.proto",
                "streamlit/proto/Button.proto",
                "streamlit/proto/HeightConfig.proto",
                "streamlit/proto/WidthConfig.proto",
                "streamlit/proto/TextAlignmentConfig.proto",
                "streamlit/proto/ButtonLikeIconPosition.proto",
            ],
            &[".."],
        )?;
    Ok(())
}
