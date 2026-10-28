//! Layout and streaming parameter variants — the frozen layout-params
//! reference's calls: expander kinds/icons, popover style/help/disabled and
//! container width, tabs with a default label, a wide dialog, toast
//! durations, status state updates.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) {
    st.title("Layout parameters");
    let e = st.expander_options(ExpanderOptions::new("Compact collapsed").icon(":material/add:").kind(ExpanderKind::Compact));
    e.write("inside compact");
    let p = st.expander_options(ExpanderOptions::new("Plain expanded").expanded(true));
    p.write("inside plain");
    let pop = st.popover_options(PopoverOptions::new("Primary").kind(PopoverKind::Primary).use_container_width(true).disabled(true).help(" popover help"));
    pop.write("inside popover");
    let tabs = st.tabs(TabsOptions::new(["Alpha", "Beta", "Gamma"]).default_tab("Beta"));
    tabs[0].write("tab one");
    tabs[1].write("tab two");
    tabs[2].write("tab three");
    st.dialog(DialogOptions::new("Wide").width(streamlit::DialogWidth::Large), |d| {
        d.write("inside dialog");
    });
    st.toast(ToastOptions::new("short default"));
    st.toast(ToastOptions::new("long").duration(10));
    st.toast(ToastOptions::new("ms").duration(1500));
    let status = st.status(StatusContainerOptions::new("Working").expanded(false));
    status.write("step");
    status.update(Some("Done".into()), Some(StatusState::Complete), Some(false));
    let broken = st.status(StatusContainerOptions::new("Broken"));
    broken.update(None, Some(StatusState::Error), None);
    st.spinner("Timing", || std::thread::sleep(std::time::Duration::from_millis(50)));
}

#[main(host = "127.0.0.1", port = 8594)]
async fn main(st: &Streamlit) {
    render(st);
}
