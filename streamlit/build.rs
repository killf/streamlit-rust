use std::ffi::OsString;
use std::io::Result;
use std::path::PathBuf;

fn main() -> Result<()> {
    println!("cargo:rerun-if-changed=proto");
    // 1. 从当前 crate 定位协议，不依赖父目录或 crate 的文件夹名称。
    let manifest = PathBuf::from(std::env::var_os("CARGO_MANIFEST_DIR").ok_or_else(|| std::io::Error::new(std::io::ErrorKind::NotFound, "CARGO_MANIFEST_DIR is missing"))?);
    let proto_dir = manifest.join("proto");
    let mut protos = std::fs::read_dir(&proto_dir)?
        .map(|entry| entry.map(|entry| format!("streamlit/proto/{}", entry.file_name().to_string_lossy())))
        .collect::<Result<Vec<_>>>()?;
    // OpenMetrics is an independent monitoring schema, not part of the browser wire protocol.
    protos.retain(|path| path.ends_with(".proto") && !path.ends_with("openmetrics_data_model.proto"));
    protos.sort();
    let mut config = prost_build::Config::new();
    // 2. 保留官方 import 前缀，把虚拟路径映射到当前协议目录。
    let mut mapping = OsString::from("--proto_path=streamlit/proto=");
    mapping.push(proto_dir);
    config.protoc_arg(mapping);

    config.default_package_filename("proto");
    // Keep prost's upstream oneof representation without hand-editing generated code.
    for oneof in [".ForwardMsg.type", ".Element.type", ".Delta.type"] {
        config.type_attribute(oneof, "#[allow(clippy::large_enum_variant)]");
    }
    // The official enum intentionally shares FILTER_MODE prefixes.
    config.type_attribute(".streamlit.SelectWidgetFilterMode", "#[allow(clippy::enum_variant_names)]");
    // Upstream prose uses >0 as a numeric threshold, which rustdoc reads as a quote.
    config.disable_comments([".WidgetState", ".MultiSelect.select_all"]);
    config.compile_protos(&protos, &[] as &[PathBuf])?;
    Ok(())
}
