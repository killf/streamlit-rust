use streamlit::websocket::message_types::{StreamlitCommand, StreamlitMessage};

#[test]
fn test_streamlit_message_serialization() {
    let message = StreamlitMessage {
        type_field: "init".to_string(),
        data: serde_json::json!({
            "title": "Test App",
            "version": "0.1.0"
        }),
    };

    let json = serde_json::to_string(&message).unwrap();
    assert!(json.contains("init"));
    assert!(json.contains("Test App"));
}

#[test]
fn test_streamlit_command_parsing() {
    let command_json = r#"
    {
        "command": "run_script",
        "data": {}
    }
    "#;

    let command: StreamlitCommand = serde_json::from_str(command_json).unwrap();
    assert_eq!(command.command, "run_script");
}

#[test]
fn test_streamlit_command_invalid() {
    let invalid_json = r#"
    {
        "invalid": "json"
    }
    "#;

    let result: Result<StreamlitCommand, _> = serde_json::from_str(invalid_json);
    assert!(result.is_err());
}
