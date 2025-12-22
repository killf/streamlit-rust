// use ::streamlit::*;

// #[main]
// fn main(st: &Streamlit) {
//     st.title("Button Example");

//     st.write("This demonstrates button functionality with conditional logic.");

//     // Basic button example
//     if st.button("Click me!", None) {
//         st.write("🎉 You clicked the button!");
//     }

//     st.divider();

//     // Counter example
//     static mut COUNTER: i32 = 0;

//     if st.button("Increment Counter", Some("counter_btn")) {
//         unsafe {
//             COUNTER += 1;
//         }
//     }

//     st.write(&format!("Counter value: {}", unsafe { COUNTER }));

//     st.divider();

//     // Multiple buttons
//     if st.button("Show Success", Some("success_btn")) {
//         st.write("✅ Success message displayed!");
//     }

//     if st.button("Show Info", Some("info_btn")) {
//         st.write("ℹ️ This is an informational message.");
//     }

//     if st.button("Show Warning", Some("warning_btn")) {
//         st.write("⚠️ Warning: This is a warning message!");
//     }

//     st.divider();

//     // Toggle example
//     static mut SHOW_SECRET: bool = false;

//     if st.button("Toggle Secret Message", Some("toggle_btn")) {
//         unsafe {
//             SHOW_SECRET = !SHOW_SECRET;
//         }
//     }

//     if unsafe { SHOW_SECRET } {
//         st.write("🤫 Secret: The answer is 42!");
//     } else {
//         st.write("Click the button above to reveal a secret message.");
//     }

//     st.divider();

//     // Reset button
//     if st.button("Reset Everything", Some("reset_btn")) {
//         unsafe {
//             COUNTER = 0;
//             SHOW_SECRET = false;
//         }
//         st.write("🔄 All values have been reset!");
//     }
// }