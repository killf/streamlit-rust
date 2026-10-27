use ::streamlit::*;

fn render(st: &Streamlit) -> Result<(), WidgetError> {
    let state = st.session_state();
    let runs = state.get::<u64>("runs")?.unwrap_or(0) + 1;
    state.set("runs", runs)?;
    st.title("Streamlit Rust form journey");
    let pulse_clicked = st.try_button(ButtonOptions::new("Pulse").key("pulse"))?;
    if pulse_clicked {
        let state = st.session_state();
        let pulses = state.get::<u64>("pulses")?.unwrap_or(0) + 1;
        state.set("pulses", pulses)?;
    }

    let note = st.form(FormOptions::new("apply_form"), |form| {
        let note = form.text_input(TextInputOptions::new("Note").key("note"))?;
        let submitted = form.form_submit_button(FormSubmitButtonOptions::new("Apply note").key("apply_note"))?;
        Ok((note, submitted))
    })?;
    let (note, submitted) = note;
    if submitted {
        st.session_state().set("applied_note", note.clone())?;
    }
    let state = st.session_state();
    st.write(format!("Script runs: {}", state.get::<u64>("runs")?.unwrap_or(0)));
    st.write(format!("Pulses: {}", state.get::<u64>("pulses")?.unwrap_or(0)));
    st.write(format!("Applied note: {}", state.get::<String>("applied_note")?.unwrap_or_default()));
    Ok(())
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    StreamlitServer::new(
        |st| {
            Box::pin(async move {
                if let Err(error) = render(st) {
                    st.write(format!("Forms example error: {error}"));
                }
            })
        },
        "127.0.0.1".into(),
        8504,
    )
    .start()
    .await
}
