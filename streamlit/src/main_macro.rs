use crate::streamlit::Streamlit;

/// Main macro for Streamlit applications
/// This attribute macro replaces the user's main function with the actual streamlit main
/// that starts the server, and preserves the user function to be called by the server
///
/// Usage:
/// ```rust
/// use streamlit::*;
///
/// #[main]
/// fn my_app(st: &mut Streamlit) {
///     st.title("Hello World!");
/// }
/// ```


/// Global function registry for Streamlit apps
pub static mut STREAMLIT_MAIN_FUNCTION: Option<fn(&mut Streamlit)> = None;

/// Set the main function for the Streamlit app
pub fn set_main_function(f: fn(&mut Streamlit)) {
    unsafe {
        STREAMLIT_MAIN_FUNCTION = Some(f);
    }
}

/// Get the main function for the Streamlit app
pub fn get_main_function() -> Option<fn(&mut Streamlit)> {
    unsafe {
        STREAMLIT_MAIN_FUNCTION
    }
}

/// Execute the user's main function if it exists
/// This function operates on the global StreamlitApp
pub fn execute_user_main() {
    if let Some(user_main) = get_main_function() {
        // Create a Streamlit instance that uses the global app
        let mut st = Streamlit::new();
        user_main(&mut st);

        // The elements are automatically added to the global app through StreamlitApp
    }
}

