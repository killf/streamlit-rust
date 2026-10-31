//! Temporal/slider creation-parameter edges — the frozen temporal-params
//! reference's calls: date_input bounds and custom format, a select_slider
//! range default, and time_input's step.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render(st: &Streamlit) -> Result<(), WidgetError> {
    let probe = st.query_params().get("probe");
    if matches!(probe.as_deref(), Some("identity" | "unkeyed")) {
        use chrono::{NaiveDate, NaiveTime};

        // 1. 按阶段保留原始 step/format，区分约束变化和普通显示变化。
        let unkeyed = probe.as_deref() == Some("unkeyed");
        let phase = st.query_params().get("phase").unwrap_or_else(|| "load".into());
        let phases: &[&str] = if unkeyed {
            &["load", "edit", "format", "width", "restore", "edit-bounds", "bounds", "observe"]
        } else {
            &["load", "edit", "policy", "step", "edit-step", "format", "edit-format", "defaults", "bounds", "restore", "observe"]
        };
        let index = phases.iter().position(|candidate| *candidate == phase).expect("identity phase");
        let step = if !unkeyed && (3..=8).contains(&index) { 1800 } else { 900 };
        let format = if !unkeyed && (5..=8).contains(&index) { "DD/MM/YYYY" } else { "YYYY/MM/DD" };
        let defaults = !unkeyed && matches!(phase.as_str(), "defaults" | "bounds");
        let date_default = NaiveDate::from_ymd_opt(2024, if defaults { 4 } else { 3 }, if defaults { 20 } else { 15 }).expect("fixture date");
        let time_default = NaiveTime::from_hms_opt(if defaults { 10 } else { 12 }, if defaults { 0 } else { 30 }, 0).expect("fixture time");
        let visibility = if phase == "policy" { LabelVisibility::Hidden } else { LabelVisibility::Visible };
        let mut clock_options = TimeInputOptions::new("Clock")
            .value(time_default)
            .step(step)
            .format(if (unkeyed && phase == "format") || (!unkeyed && (5..=8).contains(&index)) { "12h" } else { "24h" })
            .disabled(phase == "policy")
            .label_visibility(visibility)
            .help(if unkeyed { "" } else { &phase });
        let mut moment_options = DateTimeInputOptions::new("Moment")
            .value(date_default.and_time(time_default))
            .step(step)
            .format(format)
            .disabled(phase == "policy")
            .label_visibility(visibility)
            .help(if unkeyed { "" } else { &phase });
        let mut date_options = DateInputOptions::new("Date")
            .value(date_default)
            .format(format)
            .disabled(phase == "policy")
            .label_visibility(visibility)
            .help(if unkeyed { "" } else { &phase });

        if !unkeyed {
            clock_options = clock_options.key("clock");
            moment_options = moment_options.key("moment");
            date_options = date_options.key("date");
        }

        // 2. 仅本阶段改变布局/边界，其余参数和 key 保持一致。
        if phase == "policy" || (unkeyed && phase == "width") {
            clock_options = clock_options.width(360);
            moment_options = moment_options.width(360);
            date_options = date_options.width(360);
        }
        if phase == "bounds" {
            let low = NaiveDate::from_ymd_opt(2024, 1, 1).expect("fixture min");
            let high = NaiveDate::from_ymd_opt(2024, 12, 31).expect("fixture max");
            if !unkeyed {
                date_options = date_options.min(low).max(high);
            }
            moment_options = moment_options.min(low.and_hms_opt(0, 0, 0).expect("midnight")).max(high.and_hms_opt(23, 59, 0).expect("end of day"));
        }

        // 3. 通过公开 API 渲染，并同时报告返回值和原生会话值。
        let clock = st.time_input(clock_options)?.expect("clock value").format("%H:%M").to_string();
        let moment = st.datetime_input(moment_options)?.expect("moment value").format("%Y-%m-%dT%H:%M").to_string();
        let DateSelection::Single(date) = st.date_input(date_options)? else { panic!("single date fixture") };
        let native = if unkeyed {
            Vec::new()
        } else {
            vec![
                st.session_state().get::<serde_json::Value>("clock")?,
                st.session_state().get::<serde_json::Value>("moment")?,
                st.session_state().get::<serde_json::Value>("date")?,
            ]
        };
        st.json(serde_json::json!({"phase": phase, "values": [clock, moment, date.format("%Y-%m-%d").to_string()],
            "native": native}));
        return Ok(());
    }

    st.title("Temporal parameter edges");
    st.date_input(
        DateInputOptions::new("Bounded")
            .value(chrono::NaiveDate::from_ymd_opt(2024, 3, 15).ok_or(WidgetError::InvalidValue("bad date".into()))?)
            .min(chrono::NaiveDate::from_ymd_opt(2024, 1, 1).ok_or(WidgetError::InvalidValue("bad date".into()))?)
            .max(chrono::NaiveDate::from_ymd_opt(2024, 12, 31).ok_or(WidgetError::InvalidValue("bad date".into()))?)
            .key("d1"),
    )?;
    st.date_input(
        DateInputOptions::new("Formatted")
            .value(chrono::NaiveDate::from_ymd_opt(2024, 6, 1).ok_or(WidgetError::InvalidValue("bad date".into()))?)
            .format("DD/MM/YYYY")
            .key("d2"),
    )?;
    st.select_slider(SelectSliderOptions::new("Range", ["low", "mid", "high"]).default(["low", "high"]).key("s1"))?;
    st.time_input(TimeInputOptions::new("Stepped").value(chrono::NaiveTime::from_hms_opt(12, 30, 0).ok_or(WidgetError::InvalidValue("bad time".into()))?).step(900).key("t1"))?;
    Ok(())
}

#[main(host = "127.0.0.1", port = 8600)]
async fn main(st: &Streamlit) {
    if let Err(error) = render(st) {
        st.write(format!("Temporal params error: {error}"));
    }
}
