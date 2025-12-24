use ::streamlit::*;
use std::sync::atomic::{AtomicBool, AtomicI32, Ordering};

#[main]
fn main(st: &Streamlit) {
    st.title("Button Example");

    st.write("This demonstrates button functionality with conditional logic.");

    // Basic button example
    if st.button("Click me!", None) {
        st.write("🎉 You clicked the button!");
    }

    st.divider();

    // Counter example
    static COUNTER: AtomicI32 = AtomicI32::new(0);

    if st.button("Increment Counter", Some("counter_btn")) {
        COUNTER.fetch_add(1, Ordering::SeqCst);
    }

    st.write(&format!("Counter value: {}", COUNTER.load(Ordering::SeqCst)));

    st.divider();

    // Multiple buttons
    if st.button("Show Success", Some("success_btn")) {
        st.write("✅ Success message displayed!");
    }

    if st.button("Show Info", Some("info_btn")) {
        st.write("ℹ️ This is an informational message.");
    }

    if st.button("Show Warning", Some("warning_btn")) {
        st.write("⚠️ Warning: This is a warning message!");
    }

    st.divider();

    // Toggle example
    static SHOW_SECRET: AtomicBool = AtomicBool::new(false);

    if st.button("Toggle Secret Message", Some("toggle_btn")) {
        let current = SHOW_SECRET.load(Ordering::SeqCst);
        SHOW_SECRET.store(!current, Ordering::SeqCst);
    }

    if SHOW_SECRET.load(Ordering::SeqCst) {
        st.write("🤫 Secret: The answer is 42!");
    } else {
        st.write("Click the button above to reveal a secret message.");
    }

    st.divider();

    // Reset button
    if st.button("Reset Everything", Some("reset_btn")) {
        COUNTER.store(0, Ordering::SeqCst);
        SHOW_SECRET.store(false, Ordering::SeqCst);
        st.write("🔄 All values have been reset!");
    }
}