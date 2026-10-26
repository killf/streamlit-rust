//! Layout regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Layouts): the sidebar takes the fixed root [1]
//! with no block of its own, the expander/popover children stream at
//! [slot, k], the tabs emit the container block plus every tab block up
//! front, and the dialog is two addBlocks on the event root [2, 0] (closed,
//! then reopened with isOpen) around a flex content container -- judged
//! modulo the script-hash segment of its $$ID name.
use super::*;
use crate::proto::{
    Block as BlockProto,
    block::{dialog, flex_container},
};
use crate::{DialogOptions, ExpanderOptions};

fn layouts_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        // Mirrors tests/reference/layouts_app.py.
        let sidebar = st.sidebar();
        sidebar.write("side note");
        let expander = st.expander(ExpanderOptions::new("Details").expanded(true));
        expander.write("inside expander");
        let tabs = st.tabs(["One", "Two"]);
        tabs[0].write("first tab");
        tabs[1].write("second tab");
        let popover = st.popover("Open settings");
        popover.write("inside popover");
        st.dialog("Confirm", |dialog| {
            dialog.write("inside dialog");
        });
    })
}

#[actix_web::test]
async fn layout_blocks_match_the_measured_wire() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(layouts_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)
        .unwrap()
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = TcpStream::connect(address).await.unwrap();
    let request = format!("GET /_stcore/stream HTTP/1.1\r\nHost: {address}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: streamlit, test-xsrf\r\n\r\n");
    stream.write_all(request.as_bytes()).await.unwrap();
    let headers = tokio::time::timeout(Duration::from_secs(5), async {
        let mut response = Vec::new();
        while !response.ends_with(b"\r\n\r\n") {
            response.push(stream.read_u8().await.unwrap());
            assert!(response.len() < 8192);
        }
        String::from_utf8(response).unwrap().to_ascii_lowercase()
    })
    .await
    .unwrap();
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
    assert!(matches!(receive(&mut stream).await.r#type, Some(forward_msg::Type::NewSession(_))));
    assert!(matches!(receive(&mut stream).await.r#type, Some(forward_msg::Type::SessionStatusChanged(status)) if status.script_is_running));

    // (kind, path, detail) of every streamed delta, plus the raw blocks for
    // structural assertions afterwards.
    let mut timeline: Vec<(String, Vec<u32>, String)> = Vec::new();
    let mut blocks: Vec<(Vec<u32>, BlockProto)> = Vec::new();
    let mut finished = false;
    loop {
        let message = receive(&mut stream).await;
        let path = message.metadata.as_ref().map(|meta| meta.delta_path.clone()).unwrap_or_default();
        match message.r#type {
            Some(forward_msg::Type::Delta(delta)) => match delta.r#type {
                Some(delta::Type::AddBlock(block)) => {
                    let detail = match &block.r#type {
                        Some(crate::proto::block::Type::Vertical(_)) => "main_container".to_string(),
                        Some(crate::proto::block::Type::Expandable(expandable)) => format!("expander:{}", expandable.label),
                        Some(crate::proto::block::Type::TabContainer(_)) => "tabContainer".to_string(),
                        Some(crate::proto::block::Type::Tab(tab)) => format!("tab:{}", tab.label),
                        Some(crate::proto::block::Type::Popover(popover)) => format!("popover:{}", popover.label),
                        Some(crate::proto::block::Type::Dialog(wire)) => format!("dialog:{}:open={:?}", wire.title, wire.is_open),
                        Some(crate::proto::block::Type::FlexContainer(_)) => "flex".to_string(),
                        other => format!("unexpected:{other:?}"),
                    };
                    blocks.push((path.clone(), block));
                    timeline.push(("add_block".into(), path, detail));
                }
                Some(delta::Type::NewElement(element)) => {
                    let detail = match element.r#type {
                        Some(element::Type::Markdown(text)) => format!("markdown:{}", text.body),
                        Some(other) => format!("unexpected:{other:?}"),
                        None => "empty".to_string(),
                    };
                    timeline.push(("new_element".into(), path, detail));
                }
                Some(delta::Type::NewTransient(_)) => timeline.push(("new_transient".into(), path, "transient".into())),
                None => {}
            },
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

    let describe = |timeline: &[(String, Vec<u32>, String)]| timeline.iter().map(|(kind, path, detail)| format!("{kind}{path:?}:{detail}")).collect::<Vec<_>>().join(" | ");
    assert_eq!(
        describe(&timeline),
        "add_block[0]:main_container \
         | new_element[1, 0]:markdown:side note \
         | add_block[0, 0]:expander:Details \
         | new_element[0, 0, 0]:markdown:inside expander \
         | add_block[0, 1]:tabContainer \
         | add_block[0, 1, 0]:tab:One \
         | add_block[0, 1, 1]:tab:Two \
         | new_element[0, 1, 0, 0]:markdown:first tab \
         | new_element[0, 1, 1, 0]:markdown:second tab \
         | add_block[0, 2]:popover:Open settings \
         | new_element[0, 2, 0]:markdown:inside popover \
         | add_block[2, 0]:dialog:Confirm:open=None \
         | add_block[2, 0]:dialog:Confirm:open=Some(true) \
         | add_block[2, 0, 0]:flex \
         | new_element[2, 0, 0, 0]:markdown:inside dialog",
    );

    let block_at = |path: &[u32]| blocks.iter().filter(|(block_path, _)| block_path == path).collect::<Vec<_>>();
    use crate::proto::streamlit::gap_config::GapSpec;
    use crate::proto::streamlit::height_config::HeightSpec;
    use crate::proto::streamlit::width_config::WidthSpec;
    fn width(block: &BlockProto) -> String {
        block
            .width_config
            .as_ref()
            .map(|config| match &config.width_spec {
                Some(WidthSpec::UseStretch(true)) => "stretch".into(),
                Some(WidthSpec::UseContent(true)) => "content".into(),
                other => format!("{other:?}"),
            })
            .unwrap_or_else(|| "absent".into())
    }
    fn height(block: &BlockProto) -> String {
        block
            .height_config
            .as_ref()
            .map(|config| match &config.height_spec {
                Some(HeightSpec::UseContent(true)) => "content".into(),
                other => format!("{other:?}"),
            })
            .unwrap_or_else(|| "absent".into())
    }

    // The documented leading main block: an id-tagged vertical container.
    let main = block_at(&[0]);
    assert_eq!(main.len(), 1);
    assert!(matches!(main[0].1.r#type, Some(crate::proto::block::Type::Vertical(_))));
    assert_eq!(main[0].1.id.as_deref(), Some("main_container"));

    // Expander: measured subset label/expanded, allowEmpty, stretch width.
    let expander = block_at(&[0, 0]);
    assert_eq!(expander.len(), 1);
    assert!(expander[0].1.allow_empty);
    assert_eq!(width(&expander[0].1), "stretch");
    assert_eq!(height(&expander[0].1), "absent");
    match &expander[0].1.r#type {
        Some(crate::proto::block::Type::Expandable(wire)) => {
            assert_eq!(wire.label, "Details");
            assert_eq!(wire.expanded, Some(true));
            assert_eq!(wire.icon, "");
        }
        other => panic!("expected an expander block, got {other:?}"),
    }

    // Tabs: the container plus every tab block, emitted before any child.
    let tabs = block_at(&[0, 1]);
    assert_eq!(tabs.len(), 1);
    assert!(!tabs[0].1.allow_empty);
    assert_eq!(width(&tabs[0].1), "stretch");
    assert_eq!(height(&tabs[0].1), "content");
    assert!(matches!(tabs[0].1.r#type, Some(crate::proto::block::Type::TabContainer(_))));
    for (path, label) in [([0u32, 1, 0], "One"), ([0, 1, 1], "Two")] {
        let tab = block_at(&path);
        assert_eq!(tab.len(), 1, "one block per tab at {path:?}");
        assert!(tab[0].1.allow_empty);
        match &tab[0].1.r#type {
            Some(crate::proto::block::Type::Tab(wire)) => assert_eq!(wire.label, label),
            other => panic!("expected a tab block, got {other:?}"),
        }
    }

    // Popover: secondary trigger starting closed, content width.
    let popover = block_at(&[0, 2]);
    assert_eq!(popover.len(), 1);
    assert!(popover[0].1.allow_empty);
    assert_eq!(width(&popover[0].1), "content");
    match &popover[0].1.r#type {
        Some(crate::proto::block::Type::Popover(wire)) => {
            assert_eq!(wire.label, "Open settings");
            assert_eq!(wire.r#type, "secondary");
            assert_eq!(wire.open, Some(false));
            assert_eq!(wire.help, "");
            assert!(!wire.disabled);
        }
        other => panic!("expected a popover block, got {other:?}"),
    }

    // Dialog: the block pair at [2, 0] (closed then reopened) plus the flex
    // content container, with the $$ID name judged modulo its hash segment.
    let dialogs = block_at(&[2, 0]);
    assert_eq!(dialogs.len(), 2, "the dialog is added twice: closed, then isOpen");
    for (index, (path, wire_block)) in dialogs.iter().enumerate() {
        assert_eq!(path, &[2, 0]);
        let id = wire_block.id.as_deref().expect("dialog blocks carry the $$ID name");
        assert!(id.starts_with("$$ID-") && id.ends_with("-None"), "dialog id shape: {id}");
        let hex = id.trim_start_matches("$$ID-").trim_end_matches("-None");
        assert_eq!(hex.len(), 32, "blake2b16 digest segment: {id}");
        assert!(hex.chars().all(|c| c.is_ascii_hexdigit()));
        match &wire_block.r#type {
            Some(crate::proto::block::Type::Dialog(wire)) => {
                assert_eq!(wire.title, "Confirm");
                assert!(wire.dismissible);
                assert_eq!(wire.width, dialog::DialogWidth::Small as i32);
                assert_eq!(wire.position, dialog::DialogPosition::Center as i32);
                assert_eq!(wire.id, "");
                assert_eq!(wire.is_open, if index == 0 { None } else { Some(true) });
            }
            other => panic!("expected a dialog block, got {other:?}"),
        }
    }
    let content = block_at(&[2, 0, 0]);
    assert_eq!(content.len(), 1);
    assert!(!content[0].1.allow_empty);
    assert_eq!(width(&content[0].1), "stretch");
    assert_eq!(height(&content[0].1), "content");
    match &content[0].1.r#type {
        Some(crate::proto::block::Type::FlexContainer(wire)) => {
            assert!(!wire.border);
            assert_eq!(wire.direction, flex_container::Direction::Vertical as i32);
            assert_eq!(wire.justify, flex_container::Justify::Start as i32);
            assert_eq!(wire.align, flex_container::Align::Start as i32);
            assert_eq!(wire.gap_config.as_ref().and_then(|gap| gap.gap_spec), Some(GapSpec::GapSize(1)));
        }
        other => panic!("expected a flex container block, got {other:?}"),
    }

    drop(stream);
    handle.stop(false).await;
    task.await.unwrap().unwrap();
}

#[test]
fn dialog_id_is_deterministic_and_input_sensitive() {
    let base = DialogOptions::new("Confirm");
    let first = crate::elements::layouts::dialog_id(&base, "aaaa");
    assert_eq!(first, crate::elements::layouts::dialog_id(&DialogOptions::new("Confirm"), "aaaa"), "equal options hash the same id");
    assert_ne!(first, crate::elements::layouts::dialog_id(&base, "bbbb"), "the script identity is mixed in");
    assert_ne!(first, crate::elements::layouts::dialog_id(&DialogOptions::new("Other"), "aaaa"), "the title is mixed in");
    assert_ne!(first, crate::elements::layouts::dialog_id(&DialogOptions::new("Confirm").width(dialog::DialogWidth::Large), "aaaa"), "the width is mixed in");
    assert_ne!(first, crate::elements::layouts::dialog_id(&DialogOptions::new("Confirm").position(dialog::DialogPosition::Left), "aaaa"), "the position is mixed in");
    assert_ne!(first, crate::elements::layouts::dialog_id(&DialogOptions::new("Confirm").dismissible(false), "aaaa"), "dismissible is mixed in");
    assert_ne!(first, crate::elements::layouts::dialog_id(&DialogOptions::new("Confirm").icon(":material/check:"), "aaaa"), "the icon is mixed in");
}
