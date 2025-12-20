use streamlit::api::{get_app, StreamlitElement, WidgetValue};

#[test]
fn test_streamlit_app_basic_functionality() {
    let app = get_app();
    app.clear_elements();

    // Test title functionality
    app.title("Test Title");
    let elements = app.get_elements();
    assert_eq!(elements.len(), 1);

    if let StreamlitElement::Title { body, .. } = &elements[0] {
        assert_eq!(body, "Test Title");
    } else {
        panic!("Expected Title element");
    }
}

#[test]
fn test_streamlit_app_text_functionality() {
    let app = get_app();
    app.clear_elements();

    // Test text write functionality
    app.write("Hello, World!");
    let elements = app.get_elements();
    assert_eq!(elements.len(), 1);

    if let StreamlitElement::Text { body, .. } = &elements[0] {
        assert_eq!(body, "Hello, World!");
    } else {
        panic!("Expected Text element");
    }
}

#[test]
fn test_streamlit_app_multiple_elements() {
    let app = get_app();
    app.clear_elements();

    app.title("Main Title");
    app.write("Some text content");
    app.header("Section Header");
    app.markdown("## Markdown content");

    let elements = app.get_elements();
    assert_eq!(elements.len(), 4);

    // Verify each element type
    if let StreamlitElement::Title { .. } = &elements[0] { /* OK */ } else { panic!("Expected Title") }
    if let StreamlitElement::Text { .. } = &elements[1] { /* OK */ } else { panic!("Expected Text") }
    if let StreamlitElement::Header { .. } = &elements[2] { /* OK */ } else { panic!("Expected Header") }
    if let StreamlitElement::Markdown { .. } = &elements[3] { /* OK */ } else { panic!("Expected Markdown") }
}

#[test]
fn test_streamlit_app_button_widget() {
    let app = get_app();
    app.clear_elements();

    // Test button widget
    let button_state = app.button("Click me", Some("test_button"));

    // Default state should be false
    assert!(!button_state);

    let elements = app.get_elements();
    assert_eq!(elements.len(), 1);

    if let StreamlitElement::Button { label, id, .. } = &elements[0] {
        assert_eq!(label, "Click me");
        assert_eq!(id, "test_button");
    } else {
        panic!("Expected Button element");
    }
}

#[test]
fn test_streamlit_app_text_input_widget() {
    let app = get_app();
    app.clear_elements();

    // Test text input widget
    let input_value = app.text_input("Enter text", Some("default"), Some("text_input"));
    assert_eq!(input_value, "default");

    let elements = app.get_elements();
    assert_eq!(elements.len(), 1);

    if let StreamlitElement::TextInput { label, value, id, .. } = &elements[0] {
        assert_eq!(label, "Enter text");
        assert_eq!(value, "default");
        assert_eq!(id, "text_input");
    } else {
        panic!("Expected TextInput element");
    }
}

#[test]
fn test_streamlit_app_slider_widget() {
    let app = get_app();
    app.clear_elements();

    // Test slider widget
    let slider_value = app.slider("Select value", 0.0, 100.0, Some(50.0), Some("slider"));
    assert_eq!(slider_value, 50.0);

    let elements = app.get_elements();
    assert_eq!(elements.len(), 1);

    if let StreamlitElement::Slider { label, min_value, max_value, value, id, .. } = &elements[0] {
        assert_eq!(label, "Select value");
        assert_eq!(*min_value, 0.0);
        assert_eq!(*max_value, 100.0);
        assert_eq!(*value, 50.0);
        assert_eq!(id, "slider");
    } else {
        panic!("Expected Slider element");
    }
}

#[test]
fn test_streamlit_app_checkbox_widget() {
    let app = get_app();
    app.clear_elements();

    // Test checkbox widget
    let checkbox_value = app.checkbox("Check me", Some(true), Some("checkbox"));
    assert!(checkbox_value);

    let elements = app.get_elements();
    assert_eq!(elements.len(), 1);

    if let StreamlitElement::Checkbox { label, value, id, .. } = &elements[0] {
        assert_eq!(label, "Check me");
        assert!(*value);
        assert_eq!(id, "checkbox");
    } else {
        panic!("Expected Checkbox element");
    }
}

#[test]
fn test_streamlit_app_selectbox_widget() {
    let app = get_app();
    app.clear_elements();

    let options = vec!["Option 1".to_string(), "Option 2".to_string(), "Option 3".to_string()];
    let selected_value = app.selectbox("Choose one", options.clone(), Some(1), Some("selectbox"));
    assert_eq!(selected_value, "Option 2");

    let elements = app.get_elements();
    assert_eq!(elements.len(), 1);

    if let StreamlitElement::Selectbox { label, options: element_options, index, id, .. } = &elements[0] {
        assert_eq!(label, "Choose one");
        assert_eq!(element_options, &options);
        assert_eq!(*index, 1);
        assert_eq!(id, "selectbox");
    } else {
        panic!("Expected Selectbox element");
    }
}

#[test]
fn test_streamlit_app_number_input_widget() {
    let app = get_app();
    app.clear_elements();

    let number_value = app.number_input("Enter number", 0.0, 10.0, Some(5.0), Some("number_input"));
    assert_eq!(number_value, 5.0);

    let elements = app.get_elements();
    assert_eq!(elements.len(), 1);

    if let StreamlitElement::NumberInput { label, value, min_value, max_value, id, .. } = &elements[0] {
        assert_eq!(label, "Enter number");
        assert_eq!(*value, 5.0);
        assert_eq!(*min_value, 0.0);
        assert_eq!(*max_value, 10.0);
        assert_eq!(id, "number_input");
    } else {
        panic!("Expected NumberInput element");
    }
}

#[test]
fn test_widget_state_management() {
    let app = get_app();

    // Test setting and getting widget state
    app.set_widget_state("test_key", WidgetValue::String("test_value".to_string()));

    let retrieved_value = app.get_widget_state("test_key");
    assert!(retrieved_value.is_some());

    match retrieved_value.unwrap() {
        WidgetValue::String(s) => assert_eq!(s, "test_value"),
        _ => panic!("Expected String widget value"),
    }

    // Test non-existent key
    let non_existent = app.get_widget_state("non_existent_key");
    assert!(non_existent.is_none());
}

#[test]
fn test_run_count_functionality() {
    let app = get_app();

    let initial_count = app.get_run_count();
    app.increment_run_count();
    let new_count = app.get_run_count();

    assert_eq!(new_count, initial_count + 1);
}

#[test]
fn test_clear_elements_functionality() {
    let app = get_app();

    // Add some elements
    app.title("Title 1");
    app.write("Text 1");

    assert_eq!(app.get_elements().len(), 2);

    // Clear elements
    app.clear_elements();
    assert_eq!(app.get_elements().len(), 0);
}

#[test]
fn test_convenience_functions() {
    use streamlit::api::*;

    get_app().clear_elements();

    // Test convenience functions
    write("Test write");
    title("Test title");
    header("Test header");
    markdown("Test **markdown**");

    let app = get_app();
    let elements = app.get_elements();
    assert_eq!(elements.len(), 4);
}

#[test]
fn test_widget_convenience_functions() {
    use streamlit::api::*;

    get_app().clear_elements();

    // Test widget convenience functions
    let button_val = button_with_key("Test Button", Some("btn"));
    let text_val = text_input_with_value("Test Input", Some("default"), Some("input"));
    let slider_val = slider_with_value("Test Slider", 0.0, 100.0, Some(25.0), Some("slider"));
    let checkbox_val = checkbox_with_value("Test Checkbox", Some(true), Some("checkbox"));

    assert!(!button_val);
    assert_eq!(text_val, "default");
    assert_eq!(slider_val, 25.0);
    assert!(checkbox_val);
}

#[test]
fn test_widget_value_conversions() {
    use streamlit::api::WidgetValue;

    // Test WidgetValue conversions
    let string_val: WidgetValue = "test".to_string().into();
    let float_val: WidgetValue = 3.14.into();
    let int_val: WidgetValue = 42i64.into();
    let bool_val: WidgetValue = true.into();

    match string_val {
        WidgetValue::String(s) => assert_eq!(s, "test"),
        _ => panic!("Expected String"),
    }

    match float_val {
        WidgetValue::Float(f) => assert_eq!(f, 3.14),
        _ => panic!("Expected Float"),
    }

    match int_val {
        WidgetValue::Integer(i) => assert_eq!(i, 42),
        _ => panic!("Expected Integer"),
    }

    match bool_val {
        WidgetValue::Boolean(b) => assert!(b),
        _ => panic!("Expected Boolean"),
    }
}