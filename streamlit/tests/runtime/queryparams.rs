//! Query-params regressions against the measured Python 1.66.1 wire (see
//! .codex/compatibility.md, Query params): writes stream one
//! page_info_changed{query_string} at the call point merged with the
//! browser-reported URL state (key insertion order and repeated values), the
//! creation-mode selectbox carries acceptNewOptions plus the filter mode and
//! keeps a freshly typed label as its string state, and a bound selectbox
//! carries queryParamKey.
use super::*;
use crate::InputWidgets;
use crate::proto::{PageInfo, forward_msg};

fn queryparams_values_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let snapshot = |stage: &str| {
            let query = st.query_params();
            st.json(serde_json::json!({"stage": stage, "value": query.get("tag"), "all": query.get_all("tag"), "pairs": query.to_vec(), "empty": query.get("empty")}));
        };
        let result: Result<(), crate::WidgetError> = (|| {
            snapshot("load");
            st.query_params().set_all("tag", ["replacement", "tail"])?;
            snapshot("replace");
            st.query_params().set("new", "中文 + text")?;
            snapshot("append");
            st.query_params().set_all("empty", std::iter::empty::<&str>())?;
            snapshot("empty-list");
            st.query_params().remove("empty")?;
            snapshot("remove-empty");
            st.query_params().remove("tag")?;
            snapshot("remove-tag");
            st.query_params().clear()?;
            snapshot("clear");
            st.query_params().set_all("tag", ["again", "last"])?;
            snapshot("restore");
            Ok(())
        })();
        if let Err(error) = result {
            st.write(format!("query-value-error: {error}"));
        }
    })
}

fn queryparams_reserved_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let snapshot = |stage: &str| {
            let query = st.query_params();
            st.json(serde_json::json!({"stage": stage, "embed": query.get("embed"), "options": query.get_all("EMBED_OPTIONS"),
                "ordinary": query.get("st_embed"), "empty_key": query.get(""), "pairs": query.to_vec()}));
        };
        let result: Result<(), crate::WidgetError> = (|| {
            // 1. 读取保留键，并检查被拒绝操作不改变状态。
            snapshot("reserved-load");
            for key in ["embed", "EmBeD_OpTiOnS"] {
                let rejected = st.query_params().set(key, "changed").is_err();
                st.json(serde_json::json!({"operation": format!("set:{key}"), "rejected": rejected}));
            }
            let rejected = st.query_params().remove("embed").is_err();
            st.json(serde_json::json!({"operation": "remove:embed", "rejected": rejected}));
            snapshot("after-rejections");

            // 2. 空键正常往返，公开清空保留嵌入参数，随后可再写普通键。
            st.query_params().set("", "updated empty key")?;
            snapshot("empty-key-set");
            st.query_params().remove("")?;
            snapshot("empty-key-remove");
            st.query_params().clear()?;
            snapshot("reserved-clear");
            st.query_params().set("restored", "ok")?;
            snapshot("reserved-restore");
            Ok(())
        })();
        if let Err(error) = result {
            st.write(format!("query-reserved-error: {error}"));
        }
    })
}

fn queryparams_binding_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let query = st.query_params();
        let phase = query.get("phase").unwrap_or_default();
        let result: Result<(), crate::WidgetError> = (|| {
            if matches!(phase.as_str(), "load" | "active") {
                let selected = st.selectbox(crate::SelectboxOptions::new("Bound", ["x", "y"]).key("bound").bind(crate::TextBind::QueryParams))?;
                let text = st.sidebar().text_input(crate::TextInputOptions::new("Text").key("text").bind(crate::TextBind::QueryParams))?;
                st.json(serde_json::json!({"phase": phase, "selected": selected, "text": text}));
            }
            if matches!(phase.as_str(), "load" | "active" | "hidden") {
                for key in ["bound", "text"] {
                    let rejected = query.set(key, "manual").is_err();
                    st.json(serde_json::json!({"operation": format!("set:{key}"), "rejected": rejected}));
                }
                let rejected = query.remove("bound").is_err();
                st.json(serde_json::json!({"operation": "remove:bound", "rejected": rejected}));
                let rejected = query.clear().is_err();
                st.json(serde_json::json!({"operation": "clear", "rejected": rejected}));
                if phase == "active" {
                    query.set("BOUND", "case-sensitive")?;
                }
            } else {
                query.set("bound", "manual")?;
                query.clear()?;
            }
            st.json(serde_json::json!({"phase": phase, "pairs": query.to_vec()}));
            Ok(())
        })();
        if let Err(error) = result {
            st.write(format!("query-binding-error: {error}"));
        }
    })
}

fn queryparams_seed_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let phase = st.query_params().get("phase").unwrap_or_default();
        let result: TestResult = (|| {
            // 1. 代码赋值在控件创建前发生，用于验证 URL/前端/代码的优先级。
            if matches!(phase.as_str(), "bad-initial" | "bad-history") {
                st.session_state().set("bound", 99)?;
                st.session_state().set("text", 99)?;
            } else if matches!(phase.as_str(), "assign" | "history" | "history-missing") {
                st.session_state().set("bound", "x")?;
                st.session_state().set("text", "code")?;
            }
            let bound = st.selectbox(crate::SelectboxOptions::new("Bound", ["x", "y"]).key("bound").bind(crate::TextBind::QueryParams))?;
            let text = st.text_input(crate::TextInputOptions::new("Text").value("base").key("text").bind(crate::TextBind::QueryParams))?;
            let optional = st.selectbox(crate::SelectboxOptions::new("Optional", ["x", "y"]).index(None).key("optional").bind(crate::TextBind::QueryParams))?;
            let creation = st.selectbox_creation(crate::SelectboxCreationOptions::new("Creation", ["x", "y"]).key("creation").bind(crate::TextBind::QueryParams))?;
            st.json(serde_json::json!({"phase": phase, "bound": bound, "text": text, "optional": optional, "creation": creation, "pairs": st.query_params().to_vec()}));
            Ok(())
        })();
        if let Err(error) = result {
            st.write(format!("query-seed-error: {error}"));
        }
    })
}

fn record_disabled_callback(st: &Streamlit, key: &str) {
    let result: TestResult = (|| {
        let state = st.session_state();
        let mut calls = state.get::<Vec<String>>("callbacks")?.unwrap_or_default();
        calls.push(key.into());
        state.set("callbacks", calls)?;
        Ok(())
    })();
    assert!(result.is_ok(), "callback fixture failed: {result:?}");
}

fn queryparams_disabled_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let phase = st.query_params().get("phase").unwrap_or_default();
        let disabled = !matches!(phase.as_str(), "enabled" | "interactive");
        let result: TestResult = (|| {
            // 1. 应用可以修改禁用控件值；前端同批提交不应覆盖代码赋值。
            if phase == "code" {
                st.session_state().set("plain", "code")?;
                st.session_state().set("bound", "x")?;
                st.session_state().set("text", "code")?;
                st.session_state().set("check", true)?;
            }
            let plain = if phase == "hidden" {
                None
            } else {
                st.text_input(crate::TextInputOptions::new("Plain").value("safe").key("plain").disabled(disabled).on_change(|st| record_disabled_callback(st, "plain")))?
            };
            let bound = st.selectbox(
                crate::SelectboxOptions::new("Bound", ["x", "y"])
                    .key("bound")
                    .disabled(disabled)
                    .bind(crate::TextBind::QueryParams)
                    .on_change(|st| record_disabled_callback(st, "bound")),
            )?;
            let text = st.text_input(
                crate::TextInputOptions::new("Text")
                    .value("base")
                    .key("text")
                    .disabled(disabled)
                    .bind(crate::TextBind::QueryParams)
                    .on_change(|st| record_disabled_callback(st, "text")),
            )?;
            let check = st.checkbox(crate::CheckboxOptions::new("Check").key("check").disabled(disabled).on_change(|st| record_disabled_callback(st, "check")))?;
            let live = st.text_input(crate::TextInputOptions::new("Live").value("ready").key("live").on_change(|st| record_disabled_callback(st, "live")))?;
            st.json(serde_json::json!({"phase": phase, "plain": plain, "bound": bound, "text": text, "check": check,
                "live": live, "callbacks": st.session_state().get::<Vec<String>>("callbacks")?.unwrap_or_default(), "pairs": st.query_params().to_vec()}));
            Ok(())
        })();
        if let Err(error) = result {
            st.write(format!("query-disabled-error: {error}"));
        }
    })
}

fn bound_queryparams_rerun_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            let state = st.session_state();
            let phase = st.query_params().get("phase").unwrap_or_default();
            let counter_key = format!("passes_{phase}");
            let iteration = state.get::<u32>(&counter_key)?.unwrap_or(0);
            state.set(counter_key, iteration + 1)?;
            let report = |stage: &str| -> TestResult {
                st.json(serde_json::json!({"phase": phase, "iteration": iteration, "stage": stage,
                    "bound": state.get::<String>("bound")?, "text": state.get::<String>("text")?,
                    "callbacks": state.get::<Vec<String>>("callbacks")?.unwrap_or_default(), "pairs": st.query_params().to_vec()}));
                Ok(())
            };

            // 1. 中断前的 URL 写入必须保留，旧控件不能因此提前清理。
            st.query_params().set("marker", format!("{phase}-{iteration}"))?;
            report("before")?;
            if phase == "early" && iteration == 0 {
                st.rerun();
                return Ok(());
            }
            if matches!(phase.as_str(), "assign" | "history") && iteration == 0 {
                state.set("bound", if phase == "assign" { "x" } else { "y" })?;
                state.set("text", "code")?;
            }
            st.selectbox(crate::SelectboxOptions::new("Bound", ["x", "y"]).key("bound").bind(crate::TextBind::QueryParams).on_change(|st| record_disabled_callback(st, "bound")))?;
            st.text_input(crate::TextInputOptions::new("Text").value("base").key("text").bind(crate::TextBind::QueryParams).on_change(|st| record_disabled_callback(st, "text")))?;
            report("values")?;

            // 2. 仅首次调用服务端重跑，后续执行不重放前端 callback。
            if iteration == 0 {
                st.rerun();
                return Ok(());
            }
            report("complete")?;
            Ok(())
        })();
        assert!(result.is_ok(), "rerun fixture failed: {result:?}");
    })
}

fn queryparams_queue_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = (|| {
            let phase = st.query_params().get("phase").unwrap_or_default();
            let state = st.session_state();
            let iteration = if phase == "queue" { state.get::<u32>("queue_iteration")?.unwrap_or(0) } else { 0 };
            if iteration == 0 {
                st.set_page_config(crate::PageConfigOptions::new().page_title("Queued config"));
                st.toast("Queued toast");
                st.markdown("queued content");
                st.balloons();
            }
            if phase == "queue" && iteration == 0 {
                state.set("queue_iteration", 1)?;
                st.query_params().set("marker", "retained")?;
                st.rerun();
                return Ok(());
            }
            st.json(serde_json::json!({"phase": phase, "iteration": iteration}));
            Ok(())
        })();
        assert!(result.is_ok(), "queue fixture failed: {result:?}");
    })
}

async fn assert_queryparams_reference(entry: fn(&Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>>, capture: &str, expected_count: usize) -> TestResult {
    // 1. 使用固定参考输入启动独立服务及真实 WS。
    let reference: serde_json::Value = serde_json::from_str(capture)?;
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    let mut widget_ids = std::collections::HashMap::new();
    let mut observed = Vec::new();
    for frame in reference["frames"].as_array().ok_or("missing frames")? {
        let Some(request) = frame["message"].get("rerun_script") else { continue };
        if reference["scenario"] == "disabled-types" && request["query_string"].as_str().is_some_and(|query| query.contains("phase=load&")) && !widget_ids.is_empty() {
            drop(stream);
            stream = sessions::connect(address, None).await;
            widget_ids.clear();
        }
        let mut widgets = Vec::new();
        if let Some(states) = request["widget_states"]["widgets"].as_array() {
            for state in states {
                let reference_id = state["id"].as_str().ok_or("missing reference widget id")?;
                let key = ["bound", "text", "optional", "creation", "plain", "check", "live"]
                    .into_iter()
                    .find(|key| reference_id.ends_with(&format!("-{key}")))
                    .ok_or("unknown reference binding")?;
                widgets.push(WidgetState {
                    id: widget_ids.get(key).cloned().ok_or("missing live widget id")?,
                    value: Some(if let Some(value) = state["bool_value"].as_bool() {
                        widget_state::Value::BoolValue(value)
                    } else if let Some(value) = state.get("int_value") {
                        widget_state::Value::IntValue(value.as_str().ok_or("missing int64 wire string")?.parse()?)
                    } else if let Some(value) = state["double_value"].as_f64() {
                        widget_state::Value::DoubleValue(value)
                    } else {
                        widget_state::Value::StringValue(state["string_value"].as_str().ok_or("missing widget text")?.into())
                    }),
                });
            }
        }
        send_binary(
            &mut stream,
            &BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    query_string: request["query_string"].as_str().ok_or("missing reference query")?.into(),
                    is_history_navigation: request["is_history_navigation"].as_bool().unwrap_or(false),
                    widget_states: Some(WidgetStates { widgets }),
                    ..Default::default()
                })),
            }
            .encode_to_vec(),
        )
        .await;

        // 2. 按真实到达顺序保留 URL 写入和应用状态。
        let finish = loop {
            match receive(&mut stream).await.r#type {
                Some(forward_msg::Type::PageConfigChanged(config)) if reference["scenario"] == "rerun-queue" => observed.push(serde_json::json!({"config": config.title})),
                Some(forward_msg::Type::PageInfoChanged(info)) => observed.push(serde_json::json!({"url": info.query_string})),
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type {
                        match element.r#type {
                            Some(element::Type::Toast(toast)) if reference["scenario"] == "rerun-queue" => observed.push(serde_json::json!({"toast": {"body": toast.body, "icon": toast.icon, "duration": toast.duration}})),
                            Some(element::Type::Markdown(text)) if reference["scenario"] == "rerun-queue" => observed.push(serde_json::json!({"markdown": text.body})),
                            Some(element::Type::Balloons(balloons)) if reference["scenario"] == "rerun-queue" => observed.push(serde_json::json!({"balloons": balloons.show})),
                            Some(element::Type::Exception(error)) => observed.push(serde_json::json!({"exception": {"type": error.r#type, "message": error.message,
                                "message_is_markdown": error.message_is_markdown, "is_streamlit_exception": error.is_streamlit_exception}})),
                            Some(element::Type::Json(json)) => observed.push(serde_json::json!({"snapshot": serde_json::from_str::<serde_json::Value>(&json.body)?})),
                            Some(element::Type::Selectbox(widget)) => {
                                let key = widget.query_param_key.unwrap_or_else(|| widget.id.rsplit('-').next().unwrap_or("").into());
                                if matches!(reference["scenario"].as_str(), Some("disabled-valid" | "disabled" | "disabled-types")) {
                                    observed.push(serde_json::json!({"widget": key, "disabled": widget.disabled, "set": widget.set_value, "value": widget.raw_value}));
                                }
                                if matches!(reference["scenario"].as_str(), Some("seed" | "seed-code" | "rerun")) {
                                    observed.push(serde_json::json!({"widget": key, "set": widget.set_value, "value": widget.raw_value}));
                                }
                                widget_ids.insert(key, widget.id);
                            }
                            Some(element::Type::TextInput(widget)) => {
                                let key = widget.query_param_key.unwrap_or_else(|| widget.id.rsplit('-').next().unwrap_or("").into());
                                if matches!(reference["scenario"].as_str(), Some("disabled-valid" | "disabled" | "disabled-types")) {
                                    observed.push(serde_json::json!({"widget": key, "disabled": widget.disabled, "set": widget.set_value, "value": widget.value}));
                                }
                                if matches!(reference["scenario"].as_str(), Some("seed" | "seed-code" | "rerun")) {
                                    observed.push(serde_json::json!({"widget": key, "set": widget.set_value, "value": widget.value}));
                                }
                                widget_ids.insert(key, widget.id);
                            }
                            Some(element::Type::Checkbox(widget)) if matches!(reference["scenario"].as_str(), Some("disabled-valid" | "disabled" | "disabled-types")) => {
                                let key = widget.id.rsplit('-').next().unwrap_or("").to_string();
                                observed.push(serde_json::json!({"widget": key, "disabled": widget.disabled, "set": widget.set_value, "value": widget.value}));
                                widget_ids.insert(key, widget.id);
                            }
                            _ => {}
                        }
                    }
                }
                Some(forward_msg::Type::ScriptFinished(status)) if matches!(reference["scenario"].as_str(), Some("rerun" | "rerun-queue")) => {
                    observed.push(serde_json::json!({"finish": status}));
                    if status != 2 {
                        break status;
                    }
                }
                Some(forward_msg::Type::ScriptFinished(status)) => break status,
                _ => {}
            }
        };
        assert_eq!(finish, 0);
    }
    drop(stream);
    handle.stop(false).await;
    task.await??;

    // 3. 自有服务停止后，对照参考的全部交错事件。
    let mut expected = Vec::new();
    for frame in reference["frames"].as_array().ok_or("missing reference frames")? {
        let message = &frame["message"];
        if matches!(reference["scenario"].as_str(), Some("rerun" | "rerun-queue"))
            && let Some(status) = message.get("script_finished")
        {
            let status = match status.as_str() {
                Some("FINISHED_EARLY_FOR_RERUN") => 2,
                Some("FINISHED_SUCCESSFULLY") => 0,
                other => panic!("unexpected reference finish: {other:?}"),
            };
            expected.push(serde_json::json!({"finish": status}));
        }
        if let Some(info) = message.get("page_info_changed") {
            expected.push(serde_json::json!({"url": info["query_string"].as_str().unwrap_or("")}));
        }
        if matches!(reference["scenario"].as_str(), Some("seed" | "seed-code" | "rerun")) {
            let element = &message["delta"]["new_element"];
            for (kind, field) in [("selectbox", "raw_value"), ("text_input", "value")] {
                if let Some(widget) = element.get(kind) {
                    expected.push(serde_json::json!({"widget": widget["query_param_key"], "set": widget["set_value"].as_bool().unwrap_or(false), "value": widget[field]}));
                }
            }
        }
        if matches!(reference["scenario"].as_str(), Some("disabled-valid" | "disabled" | "disabled-types")) {
            let element = &message["delta"]["new_element"];
            for (kind, field) in [("selectbox", "raw_value"), ("text_input", "value"), ("checkbox", "value")] {
                if let Some(widget) = element.get(kind) {
                    let key = widget["id"].as_str().ok_or("missing widget id")?.rsplit('-').next().ok_or("missing widget key")?;
                    let value = if kind == "checkbox" { serde_json::Value::Bool(widget[field].as_bool().unwrap_or(false)) } else { widget[field].clone() };
                    expected.push(serde_json::json!({"widget": key, "disabled": widget["disabled"].as_bool().unwrap_or(false), "set": widget["set_value"].as_bool().unwrap_or(false), "value": value}));
                }
            }
        }
        if let Some(error) = message["delta"]["new_element"].get("exception") {
            expected.push(serde_json::json!({"exception": {"type": error["type"], "message": error["message"],
                "message_is_markdown": error["message_is_markdown"].as_bool().unwrap_or(false), "is_streamlit_exception": error["is_streamlit_exception"].as_bool().unwrap_or(false)}}));
        }
        if reference["scenario"] == "rerun-queue" {
            if let Some(config) = message.get("page_config_changed") {
                expected.push(serde_json::json!({"config": config["title"]}));
            }
            let element = &message["delta"]["new_element"];
            if let Some(toast) = element.get("toast") {
                expected.push(serde_json::json!({"toast": {"body": toast["body"], "icon": toast["icon"].as_str().unwrap_or(""), "duration": toast["duration"]}}));
            }
            if let Some(markdown) = element.get("markdown") {
                expected.push(serde_json::json!({"markdown": markdown["body"]}));
            }
            if let Some(balloons) = element.get("balloons") {
                expected.push(serde_json::json!({"balloons": balloons["show"]}));
            }
        }
        if let Some(body) = message["delta"]["new_element"]["json"]["body"].as_str() {
            expected.push(serde_json::json!({"snapshot": serde_json::from_str::<serde_json::Value>(body)?}));
        }
    }
    assert_eq!(expected.len(), expected_count, "reference must retain every snapshot and URL write");
    assert_eq!(observed, expected);
    Ok(())
}

#[actix_web::test]
async fn query_param_values_and_mutations_match_frozen_reference() -> TestResult {
    assert_queryparams_reference(queryparams_values_entry, include_str!("../../../tests/reference/reference-browser/queryparams/values/trace.json"), 15).await
}

#[actix_web::test]
async fn query_param_reserved_and_empty_keys_match_frozen_reference() -> TestResult {
    assert_queryparams_reference(queryparams_reserved_entry, include_str!("../../../tests/reference/reference-browser/queryparams/reserved/trace.json"), 13).await
}

#[actix_web::test]
async fn query_param_binding_lifecycle_matches_frozen_reference() -> TestResult {
    assert_queryparams_reference(queryparams_binding_entry, include_str!("../../../tests/reference/reference-browser/queryparams/binding/trace.json"), 23).await
}

#[actix_web::test]
async fn query_param_url_seeding_matches_frozen_reference() -> TestResult {
    assert_queryparams_reference(queryparams_seed_entry, include_str!("../../../tests/reference/reference-browser/queryparams/seed/trace.json"), 49).await
}

#[actix_web::test]
async fn query_param_url_seeds_discard_invalid_code_values() -> TestResult {
    assert_queryparams_reference(queryparams_seed_entry, include_str!("../../../tests/reference/reference-browser/queryparams/seed-code/trace.json"), 10).await
}

#[actix_web::test]
async fn disabled_widget_inputs_and_callbacks_match_frozen_reference() -> TestResult {
    assert_queryparams_reference(queryparams_disabled_entry, include_str!("../../../tests/reference/reference-browser/queryparams/disabled-valid/trace.json"), 58).await
}

#[actix_web::test]
async fn disabled_malformed_input_keeps_callbacks_error_and_recovery() -> TestResult {
    assert_queryparams_reference(queryparams_disabled_entry, include_str!("../../../tests/reference/reference-browser/queryparams/disabled/trace.json"), 52).await
}

#[actix_web::test]
async fn disabled_numeric_wire_types_preserve_callback_and_recovery() -> TestResult {
    let mut reference: serde_json::Value = serde_json::from_str(include_str!("../../../tests/reference/reference-browser/queryparams/disabled-types-isolated/trace.json"))?;
    let frames = reference["frames"].as_array_mut().ok_or("missing disabled type frames")?;
    // Only the first three independent cases (bool/int/double) belong to this
    // numeric regression. The full frozen corpus keeps array/JSON/other controls.
    let end = frames.iter().enumerate().filter(|(_, frame)| frame["direction"] == "client->server").nth(9).ok_or("missing fourth isolated case")?.0;
    frames.truncate(end);
    assert_queryparams_reference(queryparams_disabled_entry, &serde_json::to_string(&reference)?, 42).await
}

#[actix_web::test]
async fn bound_widget_server_reruns_match_frozen_reference() -> TestResult {
    assert_queryparams_reference(bound_queryparams_rerun_entry, include_str!("../../../tests/reference/reference-browser/queryparams/rerun/trace.json"), 47).await
}

#[actix_web::test]
async fn rerun_queue_messages_match_frozen_reference() -> TestResult {
    assert_queryparams_reference(queryparams_queue_entry, include_str!("../../../tests/reference/reference-browser/queryparams/rerun-queue/trace.json"), 11).await
}

fn queryparams_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            // Mirrors tests/reference/queryparams_app.py.
            st.query_params().set("mode", "demo")?;
            let pick = st.selectbox_creation(crate::SelectboxCreationOptions::new("Pick", ["a", "b"]).filter_mode(crate::SelectFilterMode::Contains))?;
            st.write(format!("pick={}", pick.as_deref().unwrap_or("a")));
            let bound = st.selectbox(crate::SelectboxOptions::new("Bound", ["x", "y"]).key("bound").bind(crate::TextBind::QueryParams))?;
            st.write(format!("bound={}", bound.unwrap_or("x")));
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "query params fixture failed: {result:?}");
    })
}

fn queryparams_rerun_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let result: TestResult = async {
            let state = st.session_state();
            let runs = state.get::<u32>("runs")?.unwrap_or(0) + 1;
            state.set("runs", runs)?;
            let ready = st.query_params().get("ready");
            st.write(format!("run={runs};ready={}", ready.as_deref().unwrap_or("missing")));
            // 独立计数让旧实现也在第三轮结束，避免错误重载 URL 后无限 rerun。
            if ready.is_none() && runs < 3 {
                st.query_params().set("ready", "1")?;
                st.rerun();
            }
            Ok(())
        }
        .await;
        assert!(result.is_ok(), "query params rerun fixture failed: {result:?}");
    })
}

fn switched_queryparams_entry(st: &Streamlit) -> Pin<Box<dyn Future<Output = ()> + '_>> {
    Box::pin(async move {
        let first = crate::Page::new("Main", |st| {
            let result: TestResult = (|| {
                st.query_params().set("written", "main")?;
                st.switch_page("two")?;
                Ok(())
            })();
            assert!(result.is_ok(), "source page fixture failed: {result:?}");
        })
        .default(true)
        .url_path("render_main");

        let second = crate::Page::new("Two", |st| {
            let result: TestResult = (|| {
                let state = st.session_state();
                let visits = state.get::<u8>("target_visits")?.unwrap_or(0) + 1;
                state.set("target_visits", visits)?;
                st.write(format!("target={}", serde_json::to_string(&st.query_params().to_vec())?));
                if visits == 1 {
                    st.query_params().set("target", "1")?;
                    st.rerun();
                }
                Ok(())
            })();
            assert!(result.is_ok(), "target page fixture failed: {result:?}");
        })
        .url_path("two");

        st.navigation([first, second]).run();
    })
}

#[actix_web::test]
async fn page_switch_clears_previous_query_but_target_rerun_keeps_new_writes() -> TestResult {
    // 1. 带非空 URL 请求首个页面，随后由服务端切页并普通重跑。
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(switched_queryparams_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    send_binary(
        &mut stream,
        &BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState {
                query_string: "seed=browser".into(),
                page_script_hash: "4e89e30dce2a0c9070887e292d3255e7".into(),
                ..Default::default()
            })),
        }
        .encode_to_vec(),
    )
    .await;

    // 2. 保留跨轮事件顺序；整体限时防止持续输出掩盖意外重跑。
    let mut timeline = Vec::new();
    let completed = tokio::time::timeout(Duration::from_secs(5), async {
        let mut successful = false;
        loop {
            match receive(&mut stream).await.r#type {
                Some(forward_msg::Type::NewSession(session)) => timeline.push(format!("session:{}", session.page_script_hash)),
                Some(forward_msg::Type::PageInfoChanged(info)) => timeline.push(format!("query:{}", info.query_string)),
                Some(forward_msg::Type::Delta(delta)) => {
                    if let Some(delta::Type::NewElement(element)) = delta.r#type
                        && let Some(element::Type::Markdown(text)) = element.r#type
                    {
                        timeline.push(text.body);
                    }
                }
                Some(forward_msg::Type::ScriptFinished(status)) => {
                    timeline.push(format!("finish:{status}"));
                    successful = status == 0;
                }
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running && successful => break,
                Some(forward_msg::Type::Navigation(_) | forward_msg::Type::SessionStatusChanged(_)) => {}
                other => panic!("unexpected query/navigation response: {other:?}"),
            }
        }
    })
    .await;

    // 3. 清理自己启动的服务后再检查，失败也不遗留监听端口。
    drop(stream);
    handle.stop(false).await;
    task.await??;
    completed?;
    assert_eq!(
        timeline,
        [
            "session:4e89e30dce2a0c9070887e292d3255e7",
            "query:seed=browser&written=main",
            "query:",
            "finish:2",
            "session:d681734f8c454b90df4d5feea7487445",
            "query:target=1",
            "finish:2",
            "session:d681734f8c454b90df4d5feea7487445",
            "target=[[\"target\",\"1\"]]",
            "finish:0",
        ]
    );
    Ok(())
}

#[actix_web::test]
async fn query_params_write_survives_server_started_rerun() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(queryparams_rerun_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
        .workers(1)
        .listen(listener)?
        .run();
    let handle = server.handle();
    let task = actix_web::rt::spawn(server);
    let mut stream = sessions::connect(address, None).await;
    send_binary(
        &mut stream,
        &BackMsg {
            r#type: Some(back_msg::Type::RerunScript(ClientState::default())),
        }
        .encode_to_vec(),
    )
    .await;

    let mut runs = 0;
    let mut markdowns = Vec::new();
    let mut finish_statuses = Vec::new();
    loop {
        match receive(&mut stream).await.r#type {
            Some(forward_msg::Type::NewSession(_)) => runs += 1,
            Some(forward_msg::Type::Delta(delta)) => {
                if let Some(delta::Type::NewElement(element)) = delta.r#type
                    && let Some(element::Type::Markdown(text)) = element.r#type
                {
                    markdowns.push(text.body);
                }
            }
            Some(forward_msg::Type::ScriptFinished(status)) => finish_statuses.push(status),
            Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running && finish_statuses.last() == Some(&0) => break,
            Some(forward_msg::Type::PageInfoChanged(_) | forward_msg::Type::SessionStatusChanged(_)) => {}
            other => panic!("unexpected lifecycle response: {other:?}"),
        }
    }
    drop(stream);
    handle.stop(false).await;
    task.await??;

    assert_eq!(
        (runs, &finish_statuses, &markdowns),
        (2, &vec![2, 0], &vec!["run=2;ready=1".to_string()]),
        "one BackMsg must produce two runs; the server-started run must retain the query write"
    );
    Ok(())
}

#[actix_web::test]
async fn query_params_and_selectbox_upgrades_match_the_measured_wire() -> TestResult {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let address = listener.local_addr()?;
    let server = HttpServer::new(move || App::new().app_data(web::Data::new(StreamlitServer::new(queryparams_entry, "127.0.0.1".into(), 0))).configure(configure_routes))
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

    // Run two: the browser reports the bound pick in its URL and the typed
    // creation value in widget state, like the measured stage 03.
    let mut pick_id = String::new();
    let mut bound_id = String::new();
    for (query_string, pick_state, expected_url, expected_pick, expected_bound) in [("", "", "mode=demo", "pick=a", "bound=x"), ("bound=y&mode=demo", "c", "bound=y&mode=demo", "pick=c", "bound=y")] {
        let widgets = if pick_id.is_empty() {
            vec![]
        } else {
            vec![
                WidgetState {
                    id: pick_id.clone(),
                    value: Some(widget_state::Value::StringValue(pick_state.into())),
                },
                WidgetState {
                    id: bound_id.clone(),
                    value: Some(widget_state::Value::StringValue("y".into())),
                },
            ]
        };
        send_binary(
            &mut stream,
            &(BackMsg {
                r#type: Some(back_msg::Type::RerunScript(ClientState {
                    query_string: query_string.into(),
                    widget_states: Some(WidgetStates { widgets }),
                    ..Default::default()
                })),
            })
            .encode_to_vec(),
        )
        .await;
        let mut page_info: Option<PageInfo> = None;
        let mut selects: Vec<crate::proto::Selectbox> = Vec::new();
        let mut markdowns = Vec::new();
        let mut finished = false;
        loop {
            let message = receive(&mut stream).await;
            match message.r#type {
                Some(forward_msg::Type::NewSession(_)) => {}
                Some(forward_msg::Type::SessionStatusChanged(status)) if !status.script_is_running => break,
                Some(forward_msg::Type::PageInfoChanged(info)) => page_info = Some(info),
                Some(forward_msg::Type::Delta(delta)) => match delta.r#type {
                    Some(delta::Type::AddBlock(_)) => {}
                    Some(delta::Type::NewElement(element)) => match element.r#type {
                        Some(element::Type::Selectbox(select)) => selects.push(select),
                        Some(element::Type::Markdown(text)) => markdowns.push(text.body),
                        Some(other) => panic!("unexpected element: {other:?}"),
                        None => {}
                    },
                    _ => {}
                },
                Some(forward_msg::Type::ScriptFinished(status)) => {
                    assert_eq!(status, 0);
                    assert!(!finished);
                    finished = true;
                }
                Some(forward_msg::Type::SessionStatusChanged(_)) => {}
                other => panic!("unexpected lifecycle response: {other:?}"),
            }
        }
        assert!(finished);
        // One merged query string in insertion order per write, like the
        // measured page_info_changed.
        assert_eq!(page_info.ok_or("query params write must stream page_info_changed")?.query_string, expected_url, "run {query_string:?}");
        assert_eq!(selects.len(), 2);
        let creation = &selects[0];
        assert_eq!(creation.label, "Pick");
        assert_eq!(creation.options, vec!["a", "b"]);
        assert_eq!(creation.accept_new_options, Some(true));
        assert_eq!(creation.filter_mode, crate::proto::streamlit::SelectWidgetFilterMode::FilterModeContains as i32);
        assert!(creation.query_param_key.is_none());
        let bound = &selects[1];
        assert_eq!(bound.label, "Bound");
        assert_eq!(bound.query_param_key.as_deref(), Some("bound"));
        assert_eq!(bound.accept_new_options, Some(false));
        assert_eq!(bound.filter_mode, crate::proto::streamlit::SelectWidgetFilterMode::FilterModeFuzzy as i32);
        pick_id = creation.id.clone();
        bound_id = bound.id.clone();
        assert_eq!(markdowns, vec![expected_pick, expected_bound]);
    }

    drop(stream);
    handle.stop(false).await;
    task.await??;
    Ok(())
}

#[test]
fn query_param_reserved_visibility_keeps_wire_values_and_empty_keys() {
    let mut store = crate::query_params::QueryParamStore::default();
    store.load("embed=true&EMBED_OPTIONS=light_theme&st_embed=ordinary&=empty-key");
    assert_eq!(store.get("embed"), None);
    assert_eq!(store.get("EMBED_OPTIONS"), None);
    assert!(store.get_all("EMBED_OPTIONS").is_empty());
    assert_eq!(store.get("st_embed"), Some("ordinary"));
    assert_eq!(store.get(""), Some("empty-key"));
    store.set("", vec!["updated empty key".into()]);
    assert_eq!(store.serialize(), "embed=true&EMBED_OPTIONS=light_theme&st_embed=ordinary&=updated+empty+key");
    assert!(store.remove(""));
    store.clear();
    assert_eq!(store.serialize(), "", "internal run/page reset still clears the complete store");
}

#[test]
fn query_param_store_round_trips_and_serializes_like_the_reference() {
    let mut store = crate::query_params::QueryParamStore::default();
    store.load("bound=y&mode=demo");
    assert_eq!(store.serialize(), "bound=y&mode=demo");
    store.set("mode", vec!["demo".into()]);
    assert_eq!(store.serialize(), "bound=y&mode=demo", "an equal write keeps the merged state");
    store.set("alpha", vec!["one".into(), "two".into()]);
    assert_eq!(store.serialize(), "bound=y&mode=demo&alpha=one&alpha=two");
    assert_eq!(store.get("mode"), Some("demo"));
    assert_eq!(store.get("alpha"), Some("two"));
    assert_eq!(store.get_all("alpha"), &["one".to_string(), "two".to_string()]);
    assert!(store.remove("bound"));
    assert_eq!(store.serialize(), "mode=demo&alpha=one&alpha=two");
    store.set("empty", vec![]);
    assert_eq!(store.get("empty"), Some(""));
    assert!(store.remove("empty"), "an empty-list key still exists");
    store.load("q=%E4%B8%AD%E6%96%87+text");
    assert_eq!(store.get("q"), Some("\u{4e2d}\u{6587} text"));
    assert_eq!(store.serialize(), "q=%E4%B8%AD%E6%96%87+text", "non-ascii round-trips percent-encoded like urlencode");
    store.clear();
    assert_eq!(store.serialize(), "");
}
