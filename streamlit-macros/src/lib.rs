use proc_macro::TokenStream;
use quote::quote;
use syn::{parse_macro_input, ItemFn};

/// Main attribute macro for Streamlit applications
/// This attribute transforms a user's main function that takes a Streamlit parameter
/// into a proper main function that starts the server and registers the user function.
#[proc_macro_attribute]
pub fn main(_attr: TokenStream, item: TokenStream) -> TokenStream {
    let input = parse_macro_input!(item as ItemFn);

    // Extract function name and signature
    let _fn_name = &input.sig.ident;
    let fn_vis = &input.vis;

    // Validate that the function takes exactly one parameter of type &Streamlit
    let params = &input.sig.inputs;
    if params.len() != 1 {
        let error = syn::Error::new_spanned(
            &input.sig,
            "Streamlit main function must take exactly one parameter: `st: &Streamlit`"
        );
        return error.to_compile_error().into();
    }

    // Extract the function body
    let fn_body = &input.block;

    // Generate the transformed code
    let expanded = quote! {
        // Rename the original function to avoid conflict
        #fn_vis fn __streamlit_user_main(st: &::streamlit::Streamlit) #fn_body

        // Generate the actual main function
        #[tokio::main]
        async fn main() -> Result<(), Box<dyn std::error::Error>> {
            // Initialize logging
            env_logger::Builder::from_default_env().init();
            log::info!("Starting Streamlit Rust Backend v0.1.0");

            // Set the user main function globally
            ::streamlit::set_main_function(__streamlit_user_main);

            // Create and start the server
            let server = ::streamlit::StreamlitServer::new();
            server.start("0.0.0.0", 8502).await?;

            Ok(())
        }
    };

    expanded.into()
}