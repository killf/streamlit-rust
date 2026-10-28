//! Remaining media/layout parameter edges — the frozen media-more
//! reference's calls: a direct video URL, an SRT subtitle track, a wrapped
//! popover, and tabs with explicit pixel width/height.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) {
    st.title("Media and layout edges");
    st.video(VideoOptions::from_url("https://example.com/clip.mp4").start_time(1.0).end_time(5.0));
    st.video(VideoOptions::new(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free".to_vec(), "video/mp4").subtitle("en", "1\n00:00:01,000 --> 00:00:02,000\nHello SRT"));
    let popover = st.popover_options(PopoverOptions::new("Wrapped").wrap(true));
    popover.write("inside wrapped");
    let tabs = st.tabs(TabsOptions::new(["A", "B"]).default_tab("B").width(500).height(200));
    tabs[0].write("one");
    tabs[1].write("two");
}

#[main(host = "127.0.0.1", port = 8597)]
async fn main(st: &Streamlit) {
    render(st);
}
