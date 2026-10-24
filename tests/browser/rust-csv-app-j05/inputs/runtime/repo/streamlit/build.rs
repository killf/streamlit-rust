use std::io::Result;

fn main() -> Result<()> {
    println!("cargo:rerun-if-changed=proto");
    let mut protos = std::fs::read_dir("proto")?.map(|entry| entry.map(|entry| format!("streamlit/proto/{}", entry.file_name().to_string_lossy()))).collect::<Result<Vec<_>>>()?;
    // OpenMetrics is an independent monitoring schema, not part of the browser wire protocol.
    protos.retain(|path| path.ends_with(".proto") && !path.ends_with("openmetrics_data_model.proto"));
    protos.sort();
    let mut config = prost_build::Config::new();
    config.default_package_filename("proto");
    // Keep prost's upstream oneof representation without hand-editing generated code.
    for oneof in [".ForwardMsg.type", ".Element.type", ".Delta.type"] {
        config.type_attribute(oneof, "#[allow(clippy::large_enum_variant)]");
    }
    // The official enum intentionally shares FILTER_MODE prefixes.
    config.type_attribute(".streamlit.SelectWidgetFilterMode", "#[allow(clippy::enum_variant_names)]");
    // Upstream prose uses >0 as a numeric threshold, which rustdoc reads as a quote.
    config.disable_comments([".WidgetState", ".MultiSelect.select_all"]);
    config.compile_protos(&protos, &[".."])?;
    Ok(())
}
