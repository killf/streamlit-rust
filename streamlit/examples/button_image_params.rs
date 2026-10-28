//! Button/image creation-parameter edges — the frozen button-image-params
//! reference's calls: primary+icon and disabled buttons, named/default
//! download buttons, and two images with captions in one element.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn png(width: u32, height: u32, rgba: [u8; 4]) -> streamlit::RgbaImage {
    streamlit::RgbaImage::new(width, height, rgba.repeat((width * height) as usize))
}

fn render(st: &Streamlit) {
    st.title("Button and image parameter edges");
    st.button(ButtonOptions::new("Primary").r#type("primary").icon(":material/star:").key("b1"));
    st.button(ButtonOptions::new("Disabled").disabled(true).key("b2"));
    let _ = st.download_button(DownloadButtonOptions::new("Save named", b"named payload".to_vec()).file_name("report.txt").mime("text/plain").key("d1"));
    let _ = st.download_button(DownloadButtonOptions::new("Save default name", b"plain bytes".to_vec()).key("d2"));
    st.images(ImageListOptions::new([png(4, 3, [255, 0, 0, 255]), png(4, 3, [255, 0, 0, 255])]).captions(["first", "second"]).width(120.into()));
}

#[main(host = "127.0.0.1", port = 8601)]
async fn main(st: &Streamlit) {
    render(st);
}
