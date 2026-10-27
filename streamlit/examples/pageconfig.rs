//! Page-config demo: one full st.set_page_config call on the measured 1.66.1
//! wire. Mirrors tests/reference/pageconfig_app.py so the browser
//! differential compares identical pages.
use ::streamlit::*;

fn render(st: &Streamlit) {
    st.set_page_config(
        PageConfigOptions::new()
            .page_title("Wide demo")
            .page_icon(":material/check_circle:")
            .layout(PageLayout::Wide)
            .initial_sidebar_state(InitialSidebarState::Expanded)
            .menu_items(
                MenuItems::new()
                    .get_help("https://docs.streamlit.io/")
                    .report_bug("https://github.com/streamlit/streamlit/issues")
                    .about("### About text\nCreated with the reference fixture."),
            ),
    );
    st.write("configured");
}

#[main(host = "127.0.0.1", port = 8514)]
async fn main(st: &Streamlit) {
    render(st);
}
