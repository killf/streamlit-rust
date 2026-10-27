use super::*;
use crate::{InputWidgets, TextInputOptions};
use futures_util::FutureExt;
use std::io::Write;
use std::sync::Mutex;

const INPUT: &str = "synthetic-input-not-for-logs";
const OUTPUT: &str = "synthetic-output-not-for-logs";
const UNSUPPORTED: &str = "synthetic-operation-not-for-logs";
const TEXT: &str = "synthetic-text-not-for-logs";
const CLOSE: &str = "synthetic-close-not-for-logs";

struct Capture(Arc<Mutex<Vec<u8>>>);

impl Write for Capture {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        self.0.lock().map_err(|_| std::io::Error::other("capture poisoned"))?.extend_from_slice(bytes);
        Ok(bytes.len())
    }

    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

fn entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            let value = st.text_input(TextInputOptions::new("Log probe").key("log-probe"))?;
            st.write(value.unwrap_or_default());
            st.write(OUTPUT.repeat(2048));
            Ok(())
        })();
        assert!(result.is_ok(), "log fixture failed: {result:?}");
    })
}

async fn run(stream: &mut TcpStream, value: Option<(&str, &str)>) -> TestResult<(String, Vec<String>)> {
    let request = BackMsg {
        r#type: Some(back_msg::Type::RerunScript(ClientState {
            widget_states: Some(WidgetStates {
                widgets: value
                    .map(|(id, text)| WidgetState {
                        id: id.into(),
                        value: Some(widget_state::Value::StringValue(text.into())),
                    })
                    .into_iter()
                    .collect(),
            }),
            ..Default::default()
        })),
    };
    send_binary(stream, &request.encode_to_vec()).await;
    let mut input_id = None;
    let mut texts = Vec::new();
    let mut finishes = 0;
    loop {
        match receive(stream).await.r#type {
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type {
                    match element.r#type {
                        Some(element::Type::TextInput(input)) => input_id = Some(input.id),
                        Some(element::Type::Markdown(text)) => texts.push(text.body),
                        _ => {}
                    }
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                finishes += 1;
            }
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
            _ => {}
        }
    }
    assert_eq!(finishes, 1);
    Ok((input_id.ok_or("text input missing")?, texts))
}

#[actix_web::test]
async fn websocket_diagnostics_do_not_expand_application_payloads() -> TestResult {
    // 1. logger 是进程全局的；精确运行独立子进程，不改变其他测试的日志配置。
    if std::env::var_os("STREAMLIT_LOG_TEST_CHILD").is_none() {
        let child = std::process::Command::new(std::env::current_exe()?)
            .args(["server::tests::logging::websocket_diagnostics_do_not_expand_application_payloads", "--exact", "--nocapture"])
            .env("STREAMLIT_LOG_TEST_CHILD", "1")
            .output()?;
        println!("{}", String::from_utf8_lossy(&child.stdout));
        assert!(child.status.success(), "isolated logging test failed: {}", String::from_utf8_lossy(&child.stderr));
        return Ok(());
    }
    let captured = Arc::new(Mutex::new(Vec::new()));
    env_logger::Builder::new()
        .filter_module("streamlit::websocket", log::LevelFilter::Debug)
        .format(|buffer, record| writeln!(buffer, "{} {} {}", record.level(), record.target(), record.args()))
        .target(env_logger::Target::Pipe(Box::new(Capture(captured.clone()))))
        .try_init()?;
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(|| App::new().app_data(web::Data::new(StreamlitServer::new(entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let observed = std::panic::AssertUnwindSafe(tokio::time::timeout(Duration::from_secs(15), async {
        // 2. 真实控件输入和输出原样通过 wire；非法消息后连接仍可恢复。
        let mut stream = sessions::connect(address, None).await;
        let (id, initial) = run(&mut stream, None).await?;
        assert!(initial.contains(&OUTPUT.repeat(2048)));
        let (next_id, updated) = run(&mut stream, Some((&id, INPUT))).await?;
        assert_eq!(id, next_id);
        assert!(updated.contains(&INPUT.to_string()));
        assert!(updated.contains(&OUTPUT.repeat(2048)));
        send_binary(&mut stream, &[0xff]).await;
        send_binary(
            &mut stream,
            &BackMsg {
                r#type: Some(back_msg::Type::BackendOperationRequest(crate::proto::BackendOperationRequest {
                    request_id: UNSUPPORTED.into(),
                    ..Default::default()
                })),
            }
            .encode_to_vec(),
        )
        .await;

        let mut close = 1000_u16.to_be_bytes().to_vec();
        close.extend_from_slice(CLOSE.as_bytes());
        for (opcode, bytes) in [(0x81, TEXT.as_bytes()), (0x88, close.as_slice())] {
            let mask = [0x12, 0x34, 0x56, 0x78];
            let mut frame = vec![opcode, 0x80 | bytes.len() as u8];
            frame.extend(mask);
            frame.extend(bytes.iter().enumerate().map(|(index, byte)| byte ^ mask[index % 4]));
            stream.write_all(&frame).await?;
            if opcode == 0x81 {
                send_binary(
                    &mut stream,
                    &BackMsg {
                        r#type: Some(back_msg::Type::AppHeartbeat(true)),
                    }
                    .encode_to_vec(),
                )
                .await;
                assert!(matches!(receive(&mut stream).await.r#type, Some(forward_msg::Type::HeartbeatAck(true))));
            } else {
                let mut header = [0; 2];
                stream.read_exact(&mut header).await?;
                assert_eq!(header, [0x88, close.len() as u8]);
                let mut reply = vec![0; close.len()];
                stream.read_exact(&mut reply).await?;
                assert_eq!(reply, close, "logging change must not strip the close reply");
            }
        }
        Ok::<_, Box<dyn std::error::Error>>(())
    }))
    .catch_unwind()
    .await;
    handle.stop(false).await;
    task.await??;
    match observed {
        Ok(result) => result??,
        Err(panic) => std::panic::resume_unwind(panic),
    }

    // 3. 先完成协议与资源清理，再保存合成数据日志并判断载荷是否外泄。
    log::logger().flush();
    let logs = String::from_utf8(captured.lock().map_err(|_| "capture poisoned")?.clone())?;
    if let Some(path) = std::env::var_os("STREAMLIT_LOG_TEST_OUTPUT") {
        std::fs::write(path, &logs)?;
    }
    let leaked: Vec<_> = [INPUT, OUTPUT, UNSUPPORTED, TEXT, CLOSE].into_iter().filter(|marker| logs.contains(marker)).collect();
    println!(
        "logging_probe log_bytes={} leaked_markers={} wire_runs=2 heartbeat_after_invalid=true close_reply_unchanged=true owned_server_stopped=true",
        logs.len(),
        leaked.len()
    );
    assert!(leaked.is_empty(), "synthetic application markers were logged: {leaked:?}");
    assert!(logs.contains("Failed to decode BackMsg"), "malformed input diagnostics must remain enabled");
    for field in ["kind=", "frames=", "bytes=", "elapsed_ms="] {
        assert!(logs.contains(field), "diagnostic summary must retain {field}");
    }
    Ok(())
}
