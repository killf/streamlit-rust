//! code/skeleton/logo parameter edges — the frozen code-logo-params
//! reference's calls: an exotic language tag with line numbers, the default
//! skeleton, and an emoji logo at its measured default size.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    st.title("Code skeleton logo edges");
    st.code_options(CodeOptions::new("print('hi')", "rust").line_numbers(true));
    st.skeleton(SkeletonOptions::new());
    st.logo(LogoOptions::new("🧊"));
    Ok(())
}

#[main(host = "127.0.0.1", port = 8607)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Code/skeleton/logo error: {error}"));
    }
}
