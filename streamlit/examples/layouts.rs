//! Layouts demo: sidebar, expander, tabs, popover and dialog on the measured
//! 1.66.1 wire. Mirrors tests/reference/layouts_app.py so the browser
//! differential compares identical pages.
use ::streamlit::*;

fn render(st: &Streamlit) {
    let sidebar = st.sidebar();
    sidebar.write("side note");

    let expander = st.expander(ExpanderOptions::new("Details").expanded(true));
    expander.write("inside expander");

    let tabs = st.tabs(["One", "Two"]);
    tabs[0].write("first tab");
    tabs[1].write("second tab");

    let popover = st.popover("Open settings");
    popover.write("inside popover");

    st.dialog("Confirm", |dialog| {
        dialog.write("inside dialog");
    });
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                render(st);
            })
        },
        "127.0.0.1".into(),
        8513,
    )
    .start()
    .await
}
