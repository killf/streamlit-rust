use streamlit::*;

#[main]
fn main(st: &mut Streamlit) {
    st.title("Streamlit Rust - New Features Demo");

    st.write("This demonstrates the newly added alert elements, image display, and visual effects.");

    st.divider();

    // ===== Alert Elements =====
    st.header("Alert Elements");

    st.sub_header("Error Alert");
    st.error("This is an error message! Something went wrong.");

    st.sub_header("Warning Alert");
    st.warning("This is a warning message! Be careful.");

    st.sub_header("Info Alert");
    st.info("This is an info message! Here's some useful information.");

    st.sub_header("Success Alert");
    st.success("This is a success message! Operation completed successfully.");

    st.divider();

    // ===== Image Display =====
    st.header("Image Display");

    st.sub_header("Image with URL");
    st.image(
        Some("https://www.rust-lang.org/static/images/rust-logo-blk.svg".to_string()),
        Some("Rust Logo".to_string()),
    );

    st.divider();

    // ===== Visual Effects =====
    st.header("Visual Effects");

    if st.button("Show Balloons!", Some("balloons_btn")) {
        st.balloons();
        st.write("🎉 Balloons! 🎉");
    }

    st.write(" ");

    if st.button("Let it Snow!", Some("snow_btn")) {
        st.snow();
        st.write("❄️ Snow! ❄️");
    }

    st.divider();

    // ===== Combined Example =====
    st.header("Combined Example");

    st.write("Click the button to see all effects at once:");

    if st.button("Show Everything!", Some("all_effects")) {
        st.success("All effects activated!");
        st.balloons();
        st.snow();
        st.image(
            Some("https://www.rust-lang.org/static/images/rust-logo-blk.svg".to_string()),
            Some("Rust Programming Language".to_string()),
        );
    }

    st.divider();

    // ===== Interactive Alert Demo =====
    st.header("Interactive Alert Demo");

    let alert_type = st.radio(
        "Select alert type",
        vec![
            "Error".to_string(),
            "Warning".to_string(),
            "Info".to_string(),
            "Success".to_string(),
        ],
        0,
        Some("alert_type"),
    ).1;

    if st.button("Show Alert", Some("show_alert")) {
        match alert_type.as_str() {
            "Error" => {
                st.error("An error occurred!");
            }
            "Warning" => {
                st.warning("This is a warning!");
            }
            "Info" => {
                st.info("Here's some information!");
            }
            "Success" => {
                st.success("Operation successful!");
            }
            _ => {
                st.info("Unknown alert type");
            }
        }
    }

    st.divider();
    st.caption("Built with Streamlit Rust - New Features Demo");
}
