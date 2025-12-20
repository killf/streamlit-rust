// Include the generated protobuf modules
#[cfg(feature = "proto-compiled")]
pub mod proto {
    // Import the streamlit module first to satisfy dependencies
    use super::super::streamlit;

    include!(concat!(env!("OUT_DIR"), "/streamlit.rs"));
    include!(concat!(env!("OUT_DIR"), "/proto.rs"));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn it_works() {
        let _msg = proto::proto::BackMsg::default();
    }
}
