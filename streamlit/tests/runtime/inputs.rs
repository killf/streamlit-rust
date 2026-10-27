//! Input-widget regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md): radio and multiselect carry index defaults with
//! text-valued states, number_input splits int/float, and text_area is a
//! plain string widget.
use super::*;
use crate::InputWidgets;
use crate::MultiselectOptions;

fn inputs_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // Mirrors tests/reference/inputs_app.py.
            let channel = st.radio(("Channel", ["email", "sms", "push"]))?;
            let tags = st.multiselect(MultiselectOptions::new("Tags", ["alpha", "beta", "gamma"]).default_indices([0]))?;
            let count = st.number_input(("Count", 7_i64, 0..=100))?;
            let note = st.text_area(("Note", "first line\nsecond line"))?;
            let channel_repr = match &channel {
                Some(text) => format!("'{text}'"),
                None => "None".to_string(),
            };
            let tags_repr = tags.iter().map(|tag| format!("'{tag}'")).collect::<Vec<_>>().join(", ");
            let note_repr = match &note {
                Some(text) => format!("'{}'", text.replace('\n', "\\n")),
                None => "None".to_string(),
            };
            st.write(format!("channel={channel_repr}"));
            st.write(format!("tags=[{tags_repr}]"));
            st.write(format!("count={count} type=int"));
            st.write(format!("note={note_repr}"));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "inputs_entry fixture failed: {result:?}");
    })
}

#[derive(Default)]
struct InputWires {
    radio: Option<crate::proto::Radio>,
    multiselect: Option<crate::proto::MultiSelect>,
    number: Option<crate::proto::NumberInput>,
    text_area: Option<crate::proto::TextArea>,
}

async fn start_inputs_server() -> TestResult<(std::net::SocketAddr, actix_web::dev::ServerHandle, tokio::task::JoinHandle<std::io::Result<()>>, TcpStream)> {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(inputs_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = TcpStream::connect(address).await?;
    let request = format!("GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit, test-xsrf\r\n\r\n");
    stream.write_all(request.as_bytes()).await?;
    let headers = tokio::time::timeout(Duration::from_secs(5), async {
        let mut response = Vec::new();
        while !response.ends_with(b"\r\n\r\n") {
            response.push(stream.read_u8().await?);
            assert!(response.len() < 8192);
        }
        Ok::<_, Box<dyn std::error::Error>>(String::from_utf8(response)?.to_ascii_lowercase())
    })
    .await??;
    assert!(headers.starts_with("http/1.1 101"));
    Ok((address, handle, task, stream))
}

async fn run_once(stream: &mut TcpStream, session_id: &mut String, widgets: Vec<WidgetState>) -> TestResult<(InputWires, Vec<String>)> {
    let request = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates { widgets }),
            ..Default::default()
        })),
    };
    send_binary(stream, &request.encode_to_vec()).await;
    let first = receive(stream).await;
    let Some(forward_msg::Type::NewSession(new_session)) = first.r#type else {
        panic!("a run must start with NewSession, got {:?}", first.r#type)
    };
    let init = new_session.initialize.ok_or("NewSession must include initialization")?;
    if session_id.is_empty() {
        *session_id = init.session_id;
    } else {
        assert_eq!(init.session_id, *session_id);
    }
    assert!(matches!(receive(stream).await.r#type, Some(forward_msg::Type::SessionStatusChanged(status)) if status.script_is_running));
    let mut wires = InputWires::default();
    let mut markdowns = Vec::new();
    let mut finished = false;
    loop {
        match receive(stream).await.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                let Some(delta::Type::NewElement(element)) = delta.r#type else { continue };
                match element.r#type {
                    Some(element::Type::Radio(radio)) => wires.radio = Some(radio),
                    Some(element::Type::Multiselect(multiselect)) => wires.multiselect = Some(multiselect),
                    Some(element::Type::NumberInput(number)) => wires.number = Some(number),
                    Some(element::Type::TextArea(text)) => wires.text_area = Some(text),
                    Some(element::Type::Markdown(text)) => markdowns.push(text.body),
                    _ => {}
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                assert!(!finished);
                finished = true;
            }
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    assert!(finished);
    Ok((wires, markdowns))
}

#[actix_web::test]
async fn input_widgets_match_the_measured_wire_and_round_trip_states() -> TestResult {
    let (_address, handle, task, mut stream) = start_inputs_server().await?;
    let mut session_id = String::new();

    let (wires, markdowns) = run_once(&mut stream, &mut session_id, vec![]).await?;
    let radio = wires.radio.as_ref().ok_or("radio widget must be rendered")?;
    assert_eq!(radio.default, Some(0));
    assert_eq!(radio.options, ["email", "sms", "push"]);
    assert_eq!((radio.disabled, radio.horizontal), (false, false));
    let multiselect = wires.multiselect.as_ref().ok_or("multiselect widget must be rendered")?;
    assert_eq!(multiselect.default, [0]);
    assert_eq!(multiselect.options, ["alpha", "beta", "gamma"]);
    assert_eq!((multiselect.accept_new_options, multiselect.select_all), (Some(false), Some(1000)));
    let number = wires.number.as_ref().ok_or("number widget must be rendered")?;
    assert_eq!(number.format, "%d");
    assert_eq!((number.data_type, number.has_min, number.has_max), (0, true, true));
    assert_eq!((number.default, number.step, number.min, number.max), (Some(7.0), 1.0, 0.0, 100.0));
    let text_area = wires.text_area.as_ref().ok_or("text_area widget must be rendered")?;
    assert_eq!(text_area.default.as_deref(), Some("first line\nsecond line"));
    assert_eq!((text_area.max_chars, text_area.placeholder.as_str()), (0, ""));
    assert_eq!(markdowns, vec!["channel='email'".to_string(), "tags=['alpha']".to_string(), "count=7 type=int".to_string(), "note='first line\\nsecond line'".to_string(),]);

    // The measured interaction states: radio/multiselect send selected texts,
    // number_input sends int_value, text_area sends the appended string.
    let states = vec![
        WidgetState {
            id: radio.id.clone(),
            value: Some(widget_state::Value::StringValue("sms".into())),
        },
        WidgetState {
            id: multiselect.id.clone(),
            value: Some(widget_state::Value::StringArrayValue(crate::proto::StringArray { data: vec!["alpha".into(), "beta".into()] })),
        },
        WidgetState {
            id: number.id.clone(),
            value: Some(widget_state::Value::IntValue(42)),
        },
        WidgetState {
            id: text_area.id.clone(),
            value: Some(widget_state::Value::StringValue("first line\nsecond line third".into())),
        },
    ];
    let (second, markdowns) = run_once(&mut stream, &mut session_id, states).await?;
    assert_eq!(second.radio.ok_or("rerun must render radio widget")?.default, Some(0), "an unchanged wire stays stable");
    assert_eq!(
        markdowns,
        vec!["channel='sms'".to_string(), "tags=['alpha', 'beta']".to_string(), "count=42 type=int".to_string(), "note='first line\\nsecond line third'".to_string(),]
    );

    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}
