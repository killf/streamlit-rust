use ::streamlit::*;

#[main]
async fn main(st: &Streamlit) {
    // Set page title
    st.title("🚀 Streamlit Rust Examples");

    // Main header
    st.header("Welcome to Streamlit in Rust!");

    st.write("This is a demonstration of various Streamlit elements implemented in Rust.");

    st.divider();

    // Section headers
    st.header("📝 Text Elements");

    st.sub_header("Markdown Content");
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
        [Link to Streamlit](https://streamlit.io/)",
    );

    st.divider();

    st.badge(BadgeOptions::new("Home").color("red").icon("🚨"));
    st.caption("This is caption");

    st.header("💻 Code Examples");

    st.sub_header("Rust Code Example");
    st.code(
        "fn main() {\n    println!(\"Hello, Streamlit!\");\n    let numbers = vec![1, 2, 3, 4, 5];\n    \n    for num in numbers {\n        println!(\"Number: {}\", num);\n    }\n}",
        "rust",
    );

    st.sub_header("Python Code Example");
    st.code(
        "import streamlit as st\n\ndef main():\n    st.write(\"Hello from Python!\")\n    numbers = [1, 2, 3, 4, 5]\n    \n    for num in numbers:\n        print(f\"Number: {num}\")\n\nif __name__ == \"__main__\":\n    main()",
        "python",
    );

    st.sub_header("JavaScript Code Example");
    st.code(
        "function greet(name) {\n    return `Hello, ${name}!`;\n}\n\nconst numbers = [1, 2, 3, 4, 5];\nnumbers.forEach(num => {\n    console.log(`Number: ${num}`);\n});",
        "javascript",
    );

    st.divider();

    st.h2("📦 Layout Elements");

    let container = st.container_options(ContainerOptions::new().border(true));
    container.write("This is inside the container");
    st.write("This is outside the container");

    container.write("This is inside too");

    if let [col1, col2] = st.columns(2) {
        col1.write("left");
        col2.write("right");
    }

    st.write("This is a outside");

    st.h2("📦 Button Elements");

    if let [col1, col2, col3, col4] = st.columns(4) {
        if col1.button("Click 1") {
            col1.write("Click 1");
        }

        if col2.button("Click 2") {
            col2.write("Click 2");
        }

        if col3.button("Click 3") {
            col3.write("Click 3");
        }

        if col4.button("Click 4") {
            col4.write("Click 4");
        }
    }
}
