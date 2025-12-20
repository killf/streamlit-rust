pub mod streamlit {
    include!(concat!(env!("OUT_DIR"), "/streamlit.rs"));
}

include!(concat!(env!("OUT_DIR"), "/proto.rs"));

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn it_works() {
        let _msg = BackMsg::default();
        let _msg = ForwardMsg::default();
    }
}
