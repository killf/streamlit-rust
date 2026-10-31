//! Widget creation-parameter edges — the frozen widget-params reference's
//! calls: the number-input float path with bounds, radio index=None and
//! horizontal+captions, text_area max_chars/placeholder/height, and
//! multiselect max_selections.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) -> Result<(), WidgetError> {
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
