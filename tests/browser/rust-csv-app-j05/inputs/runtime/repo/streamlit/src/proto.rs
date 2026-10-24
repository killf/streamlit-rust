pub(crate) mod streamlit {
    include!(concat!(env!("OUT_DIR"), "/streamlit.rs"));
}

include!(concat!(env!("OUT_DIR"), "/proto.rs"));

pub(crate) fn delta_base_with_path(delta_path: Vec<u32>, active_script_hash: String, hash: String) -> ForwardMsg {
    ForwardMsg {
        hash,
        metadata: Some(ForwardMsgMetadata {
            cacheable: false,
            delta_path,
            active_script_hash,
        }),
        r#type: None, // Will be set by specific element methods
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn it_works() {
        let _msg = BackMsg::default();
        let _msg = ForwardMsg::default();
    }
}
