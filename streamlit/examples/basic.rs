use ::streamlit::*;

#[main]
fn main(st: &Streamlit) {
    // Set page title
    st.title("🚀 Streamlit Rust Examples");

    // Main header
    st.h1("Welcome to Streamlit in Rust!");

    st.write("This is a demonstration of various Streamlit elements implemented in Rust.");

    st.divider();

    // Section headers
    st.h2("📝 Text Elements");

    st.header("Basic Text", 3);
    st.write("This is a simple text element using st.write()");

    st.header("Markdown Content", 3);
    st.markdown(
        "You can use **bold text**, *italic text*, and `inline code` in markdown.\n\n\
        # Heading 1\n\
        ## Heading 2\n\
        ### Heading 3\n\n\
        - Bullet point 1\n\
        - Bullet point 2\n\
        - Bullet point 3\n\n\
        1. Numbered list item 1\n\
        2. Numbered list item 2\n\
        3. Numbered list item 3\n\n\
        [Link to Streamlit](https://streamlit.io/)"
    );

    st.divider();

    st.h2("💻 Code Examples");

    st.header("Rust Code Example", 3);
    st.code(
        "fn main() {\n    println!(\"Hello, Streamlit!\");\n    let numbers = vec![1, 2, 3, 4, 5];\n    \n    for num in numbers {\n        println!(\"Number: {}\", num);\n    }\n}",
        Some("rust")
    );

    st.header("Python Code Example", 3);
    st.code(
        "import streamlit as st\n\ndef main():\n    st.write(\"Hello from Python!\")\n    numbers = [1, 2, 3, 4, 5]\n    \n    for num in numbers:\n        print(f\"Number: {num}\")\n\nif __name__ == \"__main__\":\n    main()",
        Some("python")
    );

    st.header("JavaScript Code Example", 3);
    st.code(
        "function greet(name) {\n    return `Hello, ${name}!`;\n}\n\nconst numbers = [1, 2, 3, 4, 5];\nnumbers.forEach(num => {\n    console.log(`Number: ${num}`);\n});",
        Some("javascript")
    );

    st.divider();

    st.h2("🎨 Formatting Elements");

    st.header("Different Header Levels", 3);
    st.h1("This is an H1 Header");
    st.h2("This is an H2 Header");
    st.h3("This is an H3 Header");

    // Note: Frontend only supports H1-H3 headers
    st.header("This is also an H3 Header", 3);

    st.divider();

    st.h2("📦 Layout Elements");

    st.header("Empty Elements", 3);
    st.write("Below is an empty element:");
    st.empty();
    st.write("And now another divider:");
    st.divider();
    st.write("Content continues after the divider.");

    st.divider();

    st.h2("🌟 Mixed Content");

    st.header("Combining Elements", 3);
    st.markdown("You can combine **markdown** with **regular text**:");
    st.write("This is regular text following markdown.");

    st.header("Code with Explanation", 3);
    st.markdown("**Example:** A simple function to calculate factorial:");
    st.code(
        "fn factorial(n: u64) -> u64 {\n    match n {\n        0 | 1 => 1,\n        _ => n * factorial(n - 1),\n    }\n}",
        Some("rust")
    );
    st.write("This function uses recursion to calculate the factorial of a number.");

    st.divider();

    st.h2("✨ Features");

    st.markdown(
        "### Current Features:\n\n\
        ✅ **Title and Headers**: Custom page titles and various header levels\n\
        ✅ **Text Content**: Basic text rendering with st.write()\n\
        ✅ **Markdown**: Full markdown support with formatting\n\
        ✅ **Code Display**: Syntax highlighting for multiple languages\n\
        ✅ **Layout Elements**: Dividers and empty elements\n\
        ✅ **Header Levels**: H1-H6 headers with custom methods\n\n\
        ### Coming Soon:\n\n\
        🔄 **Interactive Widgets**: Buttons, sliders, input fields\n\
        🔄 **Data Display**: Tables, charts, and dataframes\n\
        🔄 **Layout Management**: Columns, tabs, and sidebars\n\
        🔄 **Media Elements**: Images, audio, and video"
    );

    st.divider();

    st.h1("🎉 Thank You!");
    st.write("This demonstrates the power of Streamlit implemented in pure Rust!");
    st.write("🚀 Built with ❤️ using Rust and Streamlit protocol");
}