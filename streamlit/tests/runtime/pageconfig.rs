//! Page-config regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Page config): st.set_page_config streams one
//! page_config_changed ForwardMsg at the call point -- after the running
//! status, before any later delta, consuming no element path -- a second
//! call streams a second message (no exception; the run continues), and
//! unset fields ride the wire as the reference's inherit markers
//! (LAYOUT_UNSET / SIDEBAR_UNSET).
use super::*;
use crate::proto::forward_msg::Type as ForwardKind;
use crate::proto::page_config;

fn pageconfig_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/pageconfig_app.py.
        st.set_page_config(
            crate::PageConfigOptions::new()
                .page_title("Wide demo")
                .page_icon(":material/check_circle:")
                .layout(crate::PageLayout::Wide)
                .initial_sidebar_state(crate::InitialSidebarState::Expanded)
                .menu_items(
                    crate::MenuItems::new()
                        .get_help("https://docs.streamlit.io/")
                        .report_bug("https://github.com/streamlit/streamlit/issues")
                        .about("### About text\nCreated with the reference fixture."),
                ),
        );
        st.write("configured");
    })
}

async fn collect_kinds_and_configs(entry: fn(&Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>>) -> TestResult<(Vec<&'static str>, Vec<crate::proto::PageConfig>, Vec<String>)> {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    send_binary(
        &mut stream,
        &(BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState {
                widget_states: Some(WidgetStates { widgets: vec![] }),
                ..Default::default()
            })),
        })
        .encode_to_vec(),
    )
    .await;

    let mut kinds: Vec<&'static str> = Vec::new();
    let mut configs: Vec<crate::proto::PageConfig> = Vec::new();
    let mut markdowns: Vec<String> = Vec::new();
    loop {
        let message = receive(&mut stream).await;
        match message.r#type {
            Some(ForwardKind::NewSession(_)) => kinds.push("new_session"),
            Some(ForwardKind::SessionStatusChanged(status)) => kinds.push(if status.script_is_running { "running" } else { "idle" }),
            Some(ForwardKind::PageConfigChanged(config)) => {
                kinds.push("page_config_changed");
                configs.push(config);
            }
            Some(ForwardKind::Delta(delta)) => match delta.r#type {
                Some(delta::Type::NewElement(element)) => match element.r#type {
                    Some(element::Type::Markdown(text)) => {
                        kinds.push("markdown");
                        markdowns.push(text.body);
                    }
                    Some(other) => panic!("unexpected element: {other:?}"),
                    None => {}
                },
                other => panic!("unexpected delta kind: {other:?}"),
            },
            Some(ForwardKind::ScriptFinished(status)) => {
                assert_eq!(status, 0);
                kinds.push("finished");
            }
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
        if kinds.last() == Some(&"idle") {
            break;
        }
    }
    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok((kinds, configs, markdowns))
}

#[actix_web::test]
async fn page_config_streams_once_at_the_call_point_on_the_measured_wire() -> TestResult {
    let (kinds, configs, markdowns) = collect_kinds_and_configs(pageconfig_entry).await?;
    // The message lands between the running status and the first delta, and
    // consumes no element path: the write still streams at [0, 0].
    assert_eq!(kinds, vec!["new_session", "running", "page_config_changed", "markdown", "finished", "idle"]);
    assert_eq!(markdowns, vec!["configured"]);
    assert_eq!(configs.len(), 1);
    let config = &configs[0];
    assert_eq!(config.title, "Wide demo");
    assert_eq!(config.favicon, ":material/check_circle:");
    assert_eq!(config.layout, page_config::Layout::Wide as i32);
    assert_eq!(config.initial_sidebar_state, page_config::SidebarState::Expanded as i32);
    let menu = config.menu_items.as_ref().expect("menu items ride the page config");
    assert_eq!(menu.get_help_url, "https://docs.streamlit.io/");
    assert_eq!(menu.report_a_bug_url, "https://github.com/streamlit/streamlit/issues");
    assert_eq!(menu.about_section_md, "### About text\nCreated with the reference fixture.");
    assert!(!menu.hide_get_help && !menu.hide_report_a_bug && !menu.clear_about_md);
    assert!(config.initial_sidebar_width.is_none());

    Ok(())
}

fn duplicate_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors the duplicate-call probe: the reference streams a second
        // page_config_changed instead of failing.
        st.set_page_config("Once");
        st.set_page_config("Twice");
        st.write("after");
    })
}

#[actix_web::test]
async fn a_second_call_streams_a_second_config_and_the_run_continues() -> TestResult {
    let (kinds, configs, markdowns) = collect_kinds_and_configs(duplicate_entry).await?;
    assert_eq!(kinds, vec!["new_session", "running", "page_config_changed", "page_config_changed", "markdown", "finished", "idle"]);
    assert_eq!(markdowns, vec!["after"]);
    assert_eq!(configs.len(), 2);
    assert_eq!(configs[0].title, "Once");
    assert_eq!(configs[1].title, "Twice");
    // Unset fields inherit: the reference sends the *_UNSET markers.
    assert_eq!(configs[0].layout, page_config::Layout::Unset as i32);
    assert_eq!(configs[0].initial_sidebar_state, page_config::SidebarState::SidebarUnset as i32);
    assert!(configs[0].menu_items.is_none());
    assert_eq!(configs[1].favicon, "");

    Ok(())
}

#[test]
fn shorthand_and_builders_cover_the_measured_options() {
    let from_title: crate::proto::PageConfig = crate::PageConfigOptions::from("Wide demo").into();
    assert_eq!(from_title.title, "Wide demo");
    assert_eq!(from_title.layout, page_config::Layout::Unset as i32);
    let explicit: crate::proto::PageConfig = crate::PageConfigOptions::new().layout(crate::PageLayout::Centered).initial_sidebar_state(crate::InitialSidebarState::Auto).into();
    assert_eq!(explicit.layout, page_config::Layout::Centered as i32);
    assert_eq!(explicit.initial_sidebar_state, page_config::SidebarState::Auto as i32);
}
