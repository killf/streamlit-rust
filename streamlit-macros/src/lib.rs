use proc_macro::TokenStream;
use quote::quote;
use syn::parse::{Parse, ParseStream};
use syn::punctuated::Punctuated;
use syn::{Expr, ExprLit, ItemFn, Lit, LitStr, MetaNameValue, Token, parse_macro_input};

#[derive(Default)]
struct MainArgs {
    host: Option<LitStr>,
    port: Option<u16>,
}

impl Parse for MainArgs {
    fn parse(input: ParseStream<'_>) -> syn::Result<Self> {
        let mut args = Self::default();
        for option in Punctuated::<MetaNameValue, Token![,]>::parse_terminated(input)? {
            if option.path.is_ident("host") {
                if args.host.is_some() {
                    return Err(syn::Error::new_spanned(option.path, "duplicate host setting"));
                }
                let Expr::Lit(ExprLit { lit: Lit::Str(host), .. }) = option.value else {
                    return Err(syn::Error::new_spanned(option.value, "host must be a string literal"));
                };
                args.host = Some(host);
            } else if option.path.is_ident("port") {
                if args.port.is_some() {
                    return Err(syn::Error::new_spanned(option.path, "duplicate port setting"));
                }
                let Expr::Lit(ExprLit { lit: Lit::Int(port), .. }) = option.value else {
                    return Err(syn::Error::new_spanned(option.value, "port must be an integer literal in 0..=65535"));
                };
                args.port = Some(port.base10_parse::<u16>().map_err(|_| syn::Error::new_spanned(port, "port must be an integer literal in 0..=65535"))?);
            } else {
                return Err(syn::Error::new_spanned(option.path, "unknown setting; expected host or port"));
            }
        }
        Ok(args)
    }
}

/// Start an async Streamlit application.
///
/// Optional `host = "127.0.0.1"` and `port = 8503` settings override
/// the default `0.0.0.0:8501` address independently.
#[proc_macro_attribute]
pub fn main(attr: TokenStream, item: TokenStream) -> TokenStream {
    let args = parse_macro_input!(attr as MainArgs);
    let input = parse_macro_input!(item as ItemFn);

    if input.sig.inputs.len() != 1 {
        return syn::Error::new_spanned(&input.sig, "Streamlit main function must take exactly one parameter: `st: &Streamlit`").to_compile_error().into();
    }
    if input.sig.asyncness.is_none() {
        return syn::Error::new_spanned(&input.sig, "Streamlit main function must be async").to_compile_error().into();
    }

    let host = args.host.unwrap_or_else(|| LitStr::new("0.0.0.0", proc_macro2::Span::call_site()));
    let port = args.port.unwrap_or(8501);
    let fn_vis = &input.vis;
    let fn_body = &input.block;

    quote! {
        #fn_vis async fn __streamlit_user_main(st: &::streamlit::Streamlit) #fn_body

        #[tokio::main]
        async fn main() -> Result<(), Box<dyn std::error::Error>> {
            env_logger::Builder::from_default_env().init();
            let server = ::streamlit::StreamlitServer::new(
                |st: &::streamlit::Streamlit| Box::pin(__streamlit_user_main(st)),
                #host.into(),
                #port
            );
            server.start().await?;

            Ok(())
        }
    }
    .into()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_independent_address_settings() -> syn::Result<()> {
        for (text, expected_host, expected_port) in [
            ("", None, None),
            ("host = \"127.0.0.1\"", Some("127.0.0.1"), None),
            ("port = 8503", None, Some(8503)),
            ("port = 0, host = \"::1\",", Some("::1"), Some(0)),
            ("host = \"localhost\", port = 65535", Some("localhost"), Some(65535)),
        ] {
            let args = syn::parse_str::<MainArgs>(text)?;
            assert_eq!(args.host.as_ref().map(LitStr::value).as_deref(), expected_host, "{text}");
            assert_eq!(args.port, expected_port, "{text}");
        }
        Ok(())
    }

    #[test]
    fn rejects_invalid_or_ambiguous_settings() -> syn::Result<()> {
        for (text, expected_error) in [
            ("host = \"a\", host = \"b\"", "duplicate host"),
            ("port = 0, port = 8501", "duplicate port"),
            ("address = \"127.0.0.1\"", "unknown setting"),
            ("host = 8501", "host must be a string literal"),
            ("port = \"8501\"", "port must be an integer literal"),
            ("port = -1", "port must be an integer literal"),
            ("port = 65536", "port must be an integer literal"),
        ] {
            let error = syn::parse_str::<MainArgs>(text).err().ok_or_else(|| syn::Error::new(proc_macro2::Span::call_site(), format!("invalid setting was accepted: {text}")))?;
            assert!(error.to_string().contains(expected_error), "{text}: {error}");
        }
        Ok(())
    }
}
