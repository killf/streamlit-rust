//! Widget creation-parameter edges — the frozen widget-params reference's
//! calls: the number-input float path with bounds, radio index=None and
//! horizontal+captions, text_area max_chars/placeholder/height, and
//! multiselect max_selections.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) -> Result<(), WidgetError> {
    if st.query_params().get("probe").as_deref() == Some("feedback-empty") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let state = st.session_state();
        if phase == "assign" {
            state.set("feedback_primary", serde_json::Value::Null)?;
            state.set("feedback_peer", 4)?;
        }
        let changed = |source: &'static str| {
            move |st: &Streamlit| {
                let state = st.session_state();
                let mut calls = state.get::<Vec<serde_json::Value>>("feedback_calls").expect("calls").unwrap_or_default();
                calls.push(serde_json::json!([
                    source,
                    state.get::<serde_json::Value>("feedback_primary").expect("primary"),
                    state.get::<serde_json::Value>("feedback_peer").expect("peer")
                ]));
                state.set("feedback_calls", calls).expect("callback write");
            }
        };
        let default = if ["default", "fallback", "assign", "observe", "clear-both", "recover"].contains(&phase.as_str()) { 0 } else { 2 };
        let primary = st.feedback(FeedbackOptions::new(FeedbackKind::Stars).default(default).key("feedback_primary").on_change(changed("primary")))?;
        let peer = st.feedback(FeedbackOptions::new(FeedbackKind::Faces).key("feedback_peer").on_change(changed("peer")))?;
        let calls = state.get::<Vec<serde_json::Value>>("feedback_calls")?.unwrap_or_default();
        st.json(serde_json::json!({"phase": phase, "values": [primary, peer], "calls": calls}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("feedback-identity") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let kind = match phase.as_str() {
            "faces" | "faces-edit" => FeedbackKind::Faces,
            "thumbs" | "thumbs-edit" => FeedbackKind::Thumbs,
            _ => FeedbackKind::Stars,
        };
        let options = |keyed| {
            let mut options = FeedbackOptions::new(kind);
            if keyed {
                options = options.key("feedback_choice");
            }
            if ["zero", "zero-edit", "width", "width-edit"].contains(&phase.as_str()) {
                options = options.default(0);
            }
            if phase == "width" || phase == "width-edit" {
                options = options.width(300);
            }
            options
        };
        let values = [st.feedback(options(false))?, st.feedback(options(true))?];
        let native = st.session_state().get::<serde_json::Value>("feedback_choice")?;
        st.json(serde_json::json!({"phase": phase, "values": values, "native": native}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("group-defaults") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let choices = if phase == "empty" { vec![] } else { vec!["Alpha", "Beta"] };
        let defaults = if phase == "empty" {
            vec![]
        } else if phase == "default" || phase == "default-edit" {
            vec!["Alpha", "Alpha", "Alpha"]
        } else {
            vec!["Beta", "Beta", "Alpha", "Beta"]
        };
        let labels = ["Plain pills", "Keyed pills", "Plain segments", "Keyed segments"];
        let mut values = Vec::new();
        for (position, label) in labels.iter().enumerate() {
            let mut options = ButtonGroupOptions::new(*label, choices.clone()).selection_mode(SelectionMode::Multi).default(defaults.clone());
            if position % 2 == 1 {
                options = options.key(*label);
            }
            let value = if position < 2 { st.pills(options)? } else { st.segmented_control(options)? };
            let ButtonGroupValue::Multi(value) = value else { unreachable!() };
            values.push(value);
        }
        st.json(serde_json::json!({"phase": phase, "values": values}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("group-state") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let state = st.session_state();
        let labels = ["Single pills", "Multi pills", "Single segments", "Multi segments"];
        for (position, label) in labels.iter().enumerate() {
            if phase == "assign" {
                let value = if position % 2 == 0 { serde_json::json!("Gone") } else { serde_json::json!(["Gone", "Beta", "Beta", "Alpha"]) };
                state.set(*label, value)?;
            } else if phase == "clear" {
                state.set(*label, if position % 2 == 0 { serde_json::Value::Null } else { serde_json::json!([]) })?;
            }
        }
        let choices = if phase == "empty" {
            vec![]
        } else if phase == "subset" {
            vec!["Beta"]
        } else {
            vec!["Alpha", "Beta"]
        };
        let mut values = Vec::new();
        for (position, label) in labels.iter().enumerate() {
            let mut options = ButtonGroupOptions::new(*label, choices.clone()).key(*label);
            if position % 2 == 1 {
                options = options.selection_mode(SelectionMode::Multi);
            }
            if !choices.is_empty() {
                options = options.default(["Beta"]);
            }
            let value = if position < 2 { st.pills(options)? } else { st.segmented_control(options)? };
            values.push(match value {
                ButtonGroupValue::Single(value) => serde_json::json!(value),
                ButtonGroupValue::Multi(value) => serde_json::json!(value),
            });
        }
        let native = labels.map(|label| state.get::<serde_json::Value>(label).expect("native"));
        st.json(serde_json::json!({"phase": phase, "values": values, "native": native}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("group-policy") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let options = |label, keyed| {
            let mut options = ButtonGroupOptions::new(label, ["Alpha", "Beta"]);
            if keyed {
                options = options.key(label);
            }
            if phase == "multi" || phase == "multi-edit" {
                options = options.selection_mode(SelectionMode::Multi);
            }
            options.required(phase == "required" || phase == "required-edit")
        };
        let values = [
            st.pills(options("Plain pills", false))?,
            st.pills(options("Keyed pills", true))?,
            st.segmented_control(options("Plain segments", false))?,
            st.segmented_control(options("Keyed segments", true))?,
        ];
        let values: Vec<serde_json::Value> = values
            .into_iter()
            .map(|value| match value {
                ButtonGroupValue::Single(value) => serde_json::json!(value),
                ButtonGroupValue::Multi(value) => serde_json::json!(value),
            })
            .collect();
        st.json(serde_json::json!({"phase": phase, "values": values}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("group-width") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let options = |label, keyed, multi| {
            let mut options = ButtonGroupOptions::new(label, ["Alpha", "Beta"]);
            if keyed {
                options = options.key(label);
            }
            if multi {
                options = options.selection_mode(SelectionMode::Multi);
            }
            if phase == "width" || phase == "width-edit" {
                options = options.width(300);
            }
            options
        };
        let values = [
            st.pills(options("Plain pills", false, false))?,
            st.pills(options("Keyed pills", true, false))?,
            st.segmented_control(options("Plain segments", false, true))?,
            st.segmented_control(options("Keyed segments", true, true))?,
        ];
        let values: Vec<serde_json::Value> = values
            .into_iter()
            .map(|value| match value {
                ButtonGroupValue::Single(value) => serde_json::json!(value),
                ButtonGroupValue::Multi(value) => serde_json::json!(value),
            })
            .collect();
        st.json(serde_json::json!({"phase": phase, "values": values}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("radio-duplicates") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let changed = |source: &'static str| {
            move |st: &Streamlit| {
                let state = st.session_state();
                let mut calls = state.get::<Vec<serde_json::Value>>("radio_duplicate_calls").expect("calls").unwrap_or_default();
                calls.push(serde_json::json!([source, state.get::<String>("choice").expect("choice"), state.get::<String>("peer").expect("peer")]));
                state.set("radio_duplicate_calls", calls).expect("callback write");
            }
        };
        let choice = st.radio(RadioOptions::new("Choice", ["Same", "Same", "Other"]).index(Some(1)).key("choice").on_change(changed("choice")))?;
        let peer = st.radio(RadioOptions::new("Peer", ["Idle", "Ready"]).key("peer").on_change(changed("peer")))?;
        let calls = st.session_state().get::<Vec<serde_json::Value>>("radio_duplicate_calls")?.unwrap_or_default();
        st.json(serde_json::json!({"phase": phase, "values": [choice, peer], "calls": calls}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("format-collisions") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        if phase == "assign" {
            st.session_state().set("choice", 2_i64)?;
            st.session_state().set("choices", vec![2_i64])?;
        }
        let values = if matches!(phase.as_str(), "reorder" | "reorder-edit" | "assign" | "observe") { vec![2_i64, 1, 3] } else { vec![1_i64, 2, 3] };
        let format = |value: &i64| if *value == 3 { "Other".into() } else { "Same".into() };
        let plain = st.selectbox(SelectboxOptions::new("Choice", values.clone()).format_func(format))?;
        let keyed = st.selectbox(SelectboxOptions::new("Keyed choice", values.clone()).format_func(format).key("choice"))?;
        let multiple = st.multiselect(MultiselectOptions::new("Choices", values).format_func(format).default_indices([1]).key("choices"))?;
        st.json(serde_json::json!({"phase": phase, "values": [plain, keyed, multiple]}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("multi-limits") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        if matches!(phase.as_str(), "repair" | "repair-final") {
            st.session_state().set("limited", vec![2_i64])?;
        } else if phase == "partial" {
            st.session_state().set("limited", vec![99_i64, 2, 99])?;
        }
        let mut cases = Vec::new();
        if phase == "load" {
            cases.extend([
                ("Repeat", vec![1, 1], None),
                ("Repeat long", vec![1, 1, 1, 1], None),
                ("Repeat capped", vec![1, 1], Some(2)),
                ("Default over", vec![0, 1], Some(1)),
                ("Zero", Vec::new(), Some(0)),
                ("Outside", vec![3], None),
            ]);
        }
        cases.push(("State", vec![1], Some(2)));
        for (label, defaults, limit) in cases {
            let mut options = MultiselectOptions::new(label, vec![1_i64, 2, 3]).default_indices(defaults);
            if label == "State" {
                options = options.key("limited");
            }
            if let Some(limit) = limit {
                options = options.max_selections(limit);
            }
            let report = match st.multiselect(options) {
                Ok(value) => serde_json::json!({"case": label, "phase": phase, "accepted": true, "value": value}),

                Err(error) => serde_json::json!({"case": label, "phase": phase, "accepted": false, "error_type": "InvalidValue", "error": error.to_string()}),
            };
            st.json(report);
        }
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("multi-empty") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        if phase == "assign-partial" {
            st.session_state().set("choice", vec!["Missing", "Beta", "Missing", "Charlie"])?;
            st.session_state().set("number", vec![99_i64, 2, 99, 3])?;
        } else if phase == "assign-repeat" {
            st.session_state().set("choice", vec!["Beta", "Beta"])?;
            st.session_state().set("number", vec![2_i64, 2])?;
        }

        let (labels, numbers) = match phase.as_str() {
            "subset" => (vec!["Beta", "Charlie"], vec![2_i64, 3]),

            "reorder" => (vec!["Charlie", "Beta", "Alpha"], vec![3_i64, 2, 1]),

            "empty" | "empty-observe" => (Vec::new(), Vec::new()),

            _ => (vec!["Alpha", "Beta", "Charlie"], vec![1_i64, 2, 3]),
        };
        let plain = st.multiselect(MultiselectOptions::new("Choice", labels.clone()))?;
        let keyed = st.multiselect(MultiselectOptions::new("Keyed choice", labels).key("choice"))?;
        let number = st.multiselect(MultiselectOptions::new("Number", numbers).key("number"))?;
        st.json(serde_json::json!({"phase": phase, "values": [plain, keyed, number]}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("select-empty") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        if phase == "assign-none" {
            st.session_state().set("choice", serde_json::Value::Null)?;
            st.session_state().set("number", serde_json::Value::Null)?;
        } else if phase == "assign-missing" {
            st.session_state().set("choice", "Missing")?;
            st.session_state().set("number", 99_i64)?;
        }

        let labels = if phase.starts_with("empty") { Vec::new() } else { vec!["Alpha", "Beta", "Charlie"] };
        let numbers = if phase.starts_with("empty") { Vec::new() } else { vec![1_i64, 2, 3] };
        let index = if matches!(phase.as_str(), "none" | "none-edit" | "none-observe" | "empty-none") { None } else { Some(0) };
        let plain = st.selectbox(SelectboxOptions::new("Choice", labels.clone()).index(index))?;
        let keyed = st.selectbox(SelectboxOptions::new("Keyed choice", labels).index(index).key("choice"))?;
        let number = st.selectbox(SelectboxOptions::new("Number", numbers).index(index).key("number"))?;
        st.json(serde_json::json!({"phase": phase, "values": [plain, keyed, number]}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("radio-empty") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        if phase == "assign-none" {
            st.session_state().set("choice", serde_json::Value::Null)?;
        } else if phase == "assign-missing" {
            st.session_state().set("choice", "Missing")?;
        }

        let labels = if phase.starts_with("empty") { Vec::new() } else { vec!["Alpha", "Beta", "Charlie"] };
        let index = if matches!(phase.as_str(), "none" | "none-edit" | "none-observe" | "empty-none") { None } else { Some(0) };
        let values = [st.radio(RadioOptions::new("Choice", labels.clone()).index(index))?, st.radio(RadioOptions::new("Keyed choice", labels).index(index).key("choice"))?];
        st.json(serde_json::json!({"phase": phase, "values": values}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("radio-identity") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let mut plain = RadioOptions::new("Choice", ["Alpha", "Beta", "Charlie"]);
        let mut keyed = RadioOptions::new("Keyed choice", ["Alpha", "Beta", "Charlie"]).key("choice");
        match phase.as_str() {
            "width" | "width-edit" => {
                plain = plain.width(320);
                keyed = keyed.width(320);
            }

            "horizontal" | "horizontal-edit" => {
                plain = plain.horizontal(true);
                keyed = keyed.horizontal(true);
            }

            "captions" | "captions-edit" => {
                plain = plain.captions(["First", "Second", "Third"]);
                keyed = keyed.captions(["First", "Second", "Third"]);
            }

            "empty" | "empty-edit" => {
                plain = plain.captions(Vec::<String>::new());
                keyed = keyed.captions(Vec::<String>::new());
            }

            _ => {}
        }

        let values = [st.radio(plain)?, st.radio(keyed)?];
        st.json(serde_json::json!({"phase": phase, "values": values}));
        return Ok(());
    }

    if matches!(st.query_params().get("probe").as_deref(), Some("select-policy" | "select-policy-unkeyed")) {
        let unkeyed = st.query_params().get("probe").as_deref() == Some("select-policy-unkeyed");
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let creation = !matches!(phase.as_str(), "load" | "edit" | "restore" | "observe");
        let mut multiple = MultiselectOptions::new("Choices", ["Alpha", "Beta", "Charlie"]).default_indices([0]);
        if !unkeyed {
            multiple = multiple.key("choices");
        }
        if creation {
            multiple = multiple.max_selections(if matches!(phase.as_str(), "mode" | "mode-edit" | "width") { 2 } else { 3 });
        }

        let selected = if creation {
            let mut options = SelectboxCreationOptions::new("Choice", ["Alpha", "Beta", "Charlie"]);
            if !unkeyed {
                options = options.key("choice");
            }
            if phase.starts_with("placeholder") || phase.starts_with("filter") {
                options = options.placeholder("Pick one");
            } else if phase.starts_with("empty") {
                options = options.placeholder("");
            } else if phase == "space-placeholder" {
                options = options.placeholder(" ");
            }
            if matches!(phase.as_str(), "filter" | "filter-edit") {
                options = options.filter_mode(SelectFilterMode::Prefix);
            }
            if phase == "width" {
                options = options.width(320);
            }
            st.selectbox_creation(options)?
        } else {
            let options = SelectboxOptions::new("Choice", ["Alpha", "Beta", "Charlie"]);
            st.selectbox(if unkeyed { options } else { options.key("choice") })?.map(str::to_string)
        };
        if phase == "width" {
            multiple = multiple.width(320);
        }

        let selections = st.multiselect(multiple)?;
        st.json(serde_json::json!({"phase": phase, "values": [selected, selections]}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("bool-width") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let mut check = CheckboxOptions::new("Unkeyed check");
        let mut toggle = ToggleOptions::new("Unkeyed toggle");
        let mut keyed_check = CheckboxOptions::new("Keyed check").key("keyed-check");
        let mut keyed_toggle = ToggleOptions::new("Keyed toggle").key("keyed-toggle");
        if matches!(phase.as_str(), "width" | "width-edit") {
            check = check.width(320);
            toggle = toggle.width(320);
            keyed_check = keyed_check.width(320);
            keyed_toggle = keyed_toggle.width(320);
        }

        let values = [st.checkbox(check)?, st.toggle(toggle)?, st.checkbox(keyed_check)?, st.toggle(keyed_toggle)?];
        st.json(serde_json::json!({"phase": phase, "values": values}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("color-unkeyed") {
        // 1. 区分原始省略值与显式黑色，保持 label/help 和其他选项不变。
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let implicit = matches!(phase.as_str(), "load" | "edit" | "implicit-return" | "observe");
        let mut options = ColorPickerOptions::new("Unkeyed accent");
        if !implicit {
            options = options.value("#000000");
        }

        // 2. 只改变原始宽度，验证归一化后的等价类及普通结束后的回收。
        let width = match phase.as_str() {
            "width-zero" | "width-edit" => Some(0),
            "width-neg" => Some(-5),
            "width-one" => Some(1),
            "width39" => Some(39),
            "width40" | "width40-return" => Some(40),
            "width41" | "width41-edit" => Some(41),
            _ => None,
        };
        if let Some(width) = width {
            options = options.width(width);
        }

        let value = st.color_picker(options)?;
        st.json(serde_json::json!({"phase": phase, "value": value}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("color") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());

        // 1. 创建参数使用独立 key，记录合法/非法默认值及最小宽度，不中止后续案例。
        if phase == "defaults" {
            let mut reports = Vec::new();
            for (name, value) in [
                ("short-upper", Some("#ABC")),
                ("short-lower", Some("#abc")),
                ("long-mixed", Some("#aBcDeF")),
                ("black", Some("#000000")),
                ("missing-hash", Some("ABCDEF")),
                ("short-unprefixed", Some("abc")),
                ("alpha", Some("#12345678")),
                ("bad-digit", Some("#12G")),
                ("too-short", Some("#12")),
                ("leading-space", Some(" #123")),
                ("trailing-space", Some("#123 ")),
                ("lf", Some("#ABC\n")),
                ("crlf", Some("#ABC\r\n")),
                ("double-lf", Some("#ABC\n\n")),
                ("empty", Some("")),
                ("plain-default", None),
            ] {
                let options = ColorPickerOptions::new(name).key(name);
                let options = if let Some(value) = value { options.value(value) } else { options };
                reports.push(match st.color_picker(options) {
                    Ok(value) => serde_json::json!({"case": name, "accepted": true, "value": value}),
                    Err(error) => serde_json::json!({"case": name, "accepted": false, "error_type": "InvalidValue", "error": error.to_string()}),
                });
            }

            for width in [-5, 0, 1, 39, 40, 41] {
                let name = format!("width-{width}");
                reports.push(match st.color_picker(ColorPickerOptions::new(&name).key(&name).value("#123456").width(width)) {
                    Ok(value) => serde_json::json!({"case": name, "accepted": true, "value": value}),
                    Err(error) => serde_json::json!({"case": name, "accepted": false, "error_type": "InvalidValue", "error": error.to_string()}),
                });
            }

            st.json(reports);
            return Ok(());
        }

        // 2. 分别观察前端输入、默认值变化和代码赋值；callback 在主函数之前记录原生值。
        let state = st.session_state();
        if phase == "assign" {
            state.set("accent", "#135")?;
        }
        if phase == "native-invalid" {
            state.set("accent", "nothex")?;
        }
        let alternate = matches!(phase.as_str(), "default-change" | "changed-invalid" | "width" | "assign" | "native-invalid" | "observe" | "recover");
        let mut options = ColorPickerOptions::new("Accent").key("accent").value(if alternate { "#FED" } else { "#123456" }).on_change(|st| {
            let state = st.session_state();
            let mut events = state.get::<Vec<String>>("color_calls").expect("callback events").unwrap_or_default();
            events.push(state.get::<String>("accent").expect("callback color").expect("registered color"));
            state.set("color_calls", events).expect("callback write");
        });
        if phase == "width" {
            options = options.width(-5);
        }

        let mut report = match st.color_picker(options) {
            Ok(value) => serde_json::json!({"accepted": true, "value": value}),
            Err(error) => serde_json::json!({"accepted": false, "error_type": "InvalidValue", "error": error.to_string()}),
        };
        report["phase"] = phase.into();
        report["native"] = serde_json::to_value(state.get::<String>("accent")?)?;
        report["events"] = serde_json::to_value(state.get::<Vec<String>>("color_calls")?.unwrap_or_default())?;
        st.json(report);
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("form-identity") {
        fn draw<C: InputWidgets>(parent: &C, phase: &str) -> Result<(i64, Option<String>, i64), WidgetError> {
            let number = parent.number_input(NumberInputOptions::new(format!("Number {phase}"), 4_i64).key("number").help(phase))?;
            let note = parent.text_input(TextInputOptions::new(format!("Note {phase}")).value("base").key("note").max_chars(5).help(phase))?;
            let unkeyed = parent.number_input(("Unkeyed", 4_i64))?;
            Ok((number, note, unkeyed))
        }

        let phase = if st.query_params().get("ui").as_deref() == Some("on") {
            st.selectbox(SelectboxOptions::new("Location", ["root", "form-a", "form-b"]).key("identity_location"))?.unwrap_or("root").to_string()
        } else {
            st.query_params().get("phase").unwrap_or_else(|| "load".into())
        };
        let (number, note, unkeyed, submitted) = if phase.starts_with("form-") {
            let form_id = if matches!(phase.as_str(), "form-a" | "form-a-return") { "alpha" } else { "beta" };
            st.form(FormOptions::new(form_id), |form| {
                let (number, note, unkeyed) = draw(form, &phase)?;
                let submitted = form.form_submit_button(FormSubmitButtonOptions::new("Apply").key("apply"))?;
                Ok((number, note, unkeyed, Some(submitted)))
            })?
        } else {
            let (number, note, unkeyed) = draw(st, &phase)?;
            (number, note, unkeyed, None)
        };
        st.json(serde_json::json!({"phase": phase, "number": number, "note": note, "unkeyed": unkeyed,
            "submitted": submitted, "native": [st.session_state().get::<serde_json::Value>("number")?, st.session_state().get::<serde_json::Value>("note")?]}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("number-permissive") {
        let report = |label: &str, result: Result<serde_json::Value, WidgetError>| -> Result<(), WidgetError> {
            match result {
                Ok(value) => {
                    st.json(serde_json::json!({"case": label, "accepted": true, "value": value,
                        "state": st.session_state().get::<serde_json::Value>(label)?}));
                }
                Err(_) => {
                    st.json(serde_json::json!({"case": label, "accepted": false}));
                }
            }
            Ok(())
        };

        for (label, value, low, high, step) in [("Int equal", 2_i64, Some(2), Some(2), 1.0), ("Int zero step", 4, None, None, 0.0), ("Int negative step", 4, None, None, -2.0)] {
            let mut options = NumberInputOptions::new(label, value).key(label).step(step);
            if let Some(low) = low {
                options = options.min(low);
            }
            if let Some(high) = high {
                options = options.max(high);
            }
            report(label, st.number_input(options).map(serde_json::Value::from))?;
        }

        for (label, value, low, high, step) in [("Float equal", 2.5_f64, Some(2.5), Some(2.5), 0.25), ("Float zero step", 1.5, None, None, 0.0), ("Float negative step", 1.5, None, None, -0.25)] {
            let mut options = NumberInputOptions::new(label, value).key(label).step(step);
            if let Some(low) = low {
                options = options.min(low);
            }
            if let Some(high) = high {
                options = options.max(high);
            }
            report(label, st.number_input(options).map(serde_json::Value::from))?;
        }

        for (label, value, low, high) in [("Int inverted", 2_i64, 3, 2), ("Int below", 1, 2, 8), ("Int above", 9, 2, 8)] {
            report(label, st.number_input(NumberInputOptions::new(label, value).key(label).min(low).max(high)).map(serde_json::Value::from))?;
        }

        for (label, value, low, high) in [("Float inverted", 2.0_f64, 3.0, 2.0), ("Float below", 1.0, 2.0, 8.0), ("Float above", 9.0, 2.0, 8.0)] {
            report(label, st.number_input(NumberInputOptions::new(label, value).key(label).min(low).max(high).step(0.25)).map(serde_json::Value::from))?;
        }
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("stop-lifecycle") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let state = st.session_state();
        let changed = |key: &'static str| {
            move |st: &Streamlit| {
                let state = st.session_state();
                let value = state.get::<serde_json::Value>(key).expect("widget state");
                let mut calls = state.get::<Vec<serde_json::Value>>("lifecycle_calls").expect("callback state").unwrap_or_default();
                calls.push(serde_json::json!({"key": key, "value": value}));
                state.set("lifecycle_calls", calls).expect("callback write");
            }
        };
        let report = |stage: &str, returns: Option<serde_json::Value>| -> Result<(), WidgetError> {
            st.json(serde_json::json!({"phase": phase, "stage": stage, "fire": state.get::<serde_json::Value>("fire")?,
                "plain": state.get::<serde_json::Value>("plain")?, "bound": state.get::<serde_json::Value>("bound")?,
                "callbacks": state.get::<Vec<serde_json::Value>>("lifecycle_calls")?.unwrap_or_default(),
                "pairs": st.query_params().to_vec(), "returns": returns}));
            Ok(())
        };

        report("before", None)?;
        if matches!(phase.as_str(), "submit" | "peek") {
            st.stop();
            return Ok(());
        }
        if matches!(phase.as_str(), "load" | "resume" | "restore") {
            let fire = st.button(ButtonOptions::new("Fire").key("fire").on_click(changed("fire")));
            let plain = st.text_input(TextInputOptions::new("Plain").value("base").key("plain").on_change(changed("plain")))?;
            let bound = st.text_input(TextInputOptions::new("Bound").value("base").key("bound").bind(TextBind::QueryParams).on_change(changed("bound")))?;
            report("values", Some(serde_json::json!({"fire": fire, "plain": plain, "bound": bound})))?;
            if phase == "resume" {
                st.stop();
            }
        }
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("number-unkeyed") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let default = if matches!(phase.as_str(), "maxzero" | "negative-edit" | "maxnone") {
            -4_i64
        } else if phase == "default" {
            5
        } else {
            4
        };
        let mut options = NumberInputOptions::new("Unkeyed", default)
            .disabled(phase == "disabled")
            .label_visibility(if phase == "hidden" { LabelVisibility::Hidden } else { LabelVisibility::Visible });
        if phase != "none" {
            options = options.on_change(|st| {
                let state = st.session_state();
                let mut calls = state.get::<Vec<String>>("unkeyed_calls").expect("callback state").unwrap_or_default();
                calls.push("changed".into());
                state.set("unkeyed_calls", calls).expect("callback write");
            });
        }
        if phase == "ignore" {
            options = options.ignore_rerun(true);
        }
        if matches!(phase.as_str(), "minzero" | "min-edit") {
            options = options.min(0);
        }
        if matches!(phase.as_str(), "maxzero" | "negative-edit") {
            options = options.max(0);
        }
        if matches!(phase.as_str(), "explicit-step" | "explicit-edit") {
            options = options.step(1.0);
        } else if phase == "step2" {
            options = options.step(2.0);
        }
        if matches!(phase.as_str(), "width" | "width-edit") {
            options = options.width(360);
        }
        if phase == "help" {
            options = options.help("hint");
        }

        let value = st.number_input(options)?;
        st.json(serde_json::json!({"phase": phase, "value": value,
            "callbacks": st.session_state().get::<Vec<String>>("unkeyed_calls")?.unwrap_or_default()}));
        if st.query_params().get("stop").as_deref() == Some("on") {
            st.stop();
        }
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("number-float") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let state = st.session_state();
        if phase == "assign" {
            state.set("number", 8.25_f64)?;
        }

        let mut options = NumberInputOptions::new("Dynamic float", if phase == "default" { 5.5_f64 } else { 4.25 })
            .key("number")
            .step(if phase == "step" { 0.5 } else { 0.25 })
            .disabled(phase == "disabled")
            .on_change(|st| {
                let state = st.session_state();
                let value = state.get::<f64>("number").expect("number state").expect("registered number");
                let mut calls = state.get::<Vec<f64>>("number_calls").expect("callback state").unwrap_or_default();
                calls.push(value);
                state.set("number_calls", calls).expect("callback write");
            });
        if phase == "raise-min" {
            options = options.min(3.0);
        } else if !matches!(phase.as_str(), "load" | "edit") {
            options = options.min(0.0);
        }
        if phase == "narrow-max" {
            options = options.max(6.0);
        } else if !matches!(phase.as_str(), "load" | "edit" | "zero-min") {
            options = options.max(10.0);
        }

        let value = st.number_input(options)?;
        st.json(serde_json::json!({"phase": phase, "value": value, "state": state.get::<f64>("number")?,
            "callbacks": state.get::<Vec<f64>>("number_calls")?.unwrap_or_default()}));
        return Ok(());
    }

    if st.query_params().get("probe").as_deref() == Some("number-sequence") {
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let state = st.session_state();
        if phase == "assign" {
            state.set("number", 8_i64)?;
        }

        let mut options = NumberInputOptions::new("Dynamic", if phase == "default" { 5_i64 } else { 4 })
            .key("number")
            .step(if phase == "step" { 2.0 } else { 1.0 })
            .disabled(phase == "disabled")
            .on_change(|st| {
                let state = st.session_state();
                let value = state.get::<i64>("number").expect("number state").expect("registered number");
                let mut calls = state.get::<Vec<i64>>("number_calls").expect("callback state").unwrap_or_default();
                calls.push(value);
                state.set("number_calls", calls).expect("callback write");
            });
        if phase == "raise-min" {
            options = options.min(3);
        } else if !matches!(phase.as_str(), "load" | "edit") {
            options = options.min(0);
        }
        if phase == "narrow-max" {
            options = options.max(6);
        } else if !matches!(phase.as_str(), "load" | "edit" | "zero-min") {
            options = options.max(10);
        }

        let value = st.number_input(options)?;
        st.json(serde_json::json!({"phase": phase, "value": value, "state": state.get::<i64>("number")?,
            "callbacks": state.get::<Vec<i64>>("number_calls")?.unwrap_or_default()}));
        return Ok(());
    }

    st.title("Widget parameter edges");
    st.number_input(("Float free", 1.5_f64))?;
    st.number_input(NumberInputOptions::<f64>::new("Float bounded", 2.5).min(0.25).max(9.75).step(0.25))?;
    st.number_input(NumberInputOptions::<i64>::new("Int bounded", 4).min(2).max(8).step(2.0))?;
    st.radio(RadioOptions::new("Plain", ["a", "b"]).index(None).key("r1"))?;
    st.radio(RadioOptions::new("Horizontal", ["x", "y"]).horizontal(true).captions(["first", "second"]).key("r2"))?;
    st.text_area(TextAreaOptions::new("Bounded", "hello").max_chars(10).placeholder("type here").height(200).key("t1"))?;
    st.multiselect(MultiselectOptions::new("Capped", ["p", "q", "r"]).max_selections(2).key("m1"))?;

    // 仅显式探针追加整数边界，保留原有参数示例的默认输出。
    if st.query_params().get("probe").as_deref() == Some("integer-bounds") {
        st.number_input(("Int free", 4_i64))?;
        st.number_input(NumberInputOptions::new("Int min only", 4_i64).min(2))?;
        st.number_input(NumberInputOptions::new("Int max only", 4_i64).max(8))?;
        st.number_input(NumberInputOptions::new("Int zero min", 4_i64).min(0))?;
        st.number_input(NumberInputOptions::new("Int zero max", -4_i64).max(0))?;
        st.number_input(("Int safe high", 9_007_199_254_740_991_i64))?;
        st.number_input(("Int safe low", -9_007_199_254_740_991_i64))?;
    }

    Ok(())
}

#[main(host = "127.0.0.1", port = 8599)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Widget params error: {error}"));
    }
}
