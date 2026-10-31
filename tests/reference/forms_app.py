"""Reference fixture for the forms and text-input surface of Streamlit 1.66.1.

DEVELOPMENT ONLY.  This app is a black-box oracle for the browser capture in
``tests/browser/forms_capture.py``.  It is not shipped, not part of any
production path, and the Rust server must never start it.  The Rust
implementation is expected to reproduce what this app does over the wire, not
to call it.

Run it with the pinned interpreter (see tests/reference/README.md):

    python -m streamlit run tests/reference/forms_app.py --server.headless true --server.port 8606

The case is selected with the ``case`` query parameter, for example
``http://127.0.0.1:8606/?case=form-default-submit``.  Every case renders its
own widgets and its own counters; the counters are plain ``st.text`` lines so
that the browser can read them out of the DOM without guessing.

What each case is meant to make observable
------------------------------------------
``form-default-submit``
    A form with a text input and a checkbox.  Editing the text, toggling the
    checkbox and blurring the text must not reach the server; pressing the
    submit button must send both values in one batch and rerun the script
    once.  The submit button carries a callback, so the trace also shows
    whether the callback ran before the script body and which values it saw.
``form-text-enter-blur``
    A text input *outside* any form.  Typing alone must not reach the
    server, Enter must commit the value, and blurring the field must commit
    it too.
``form-none-vs-empty``
    A text input whose value is ``None`` next to one whose value is ``""``.
    The rendered values must tell the two apart.
``form-error-duplicate-key``
    Two forms with the same key.
``form-error-nested-form``
    A form inside a form.

The two error cases exist to make the server's own answer observable: the
exception the runtime raises, the elements it still sent, and the status it
finished the script with.  Nothing here predicts that answer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from forms_cases import CASES  # noqa: E402  (path setup must precede the import)

st.set_page_config(page_title="streamlit-rust forms reference", layout="centered")

CASE = str(st.query_params.get("case") or "form-default-submit").strip()

st.session_state.setdefault("run_count", 0)
st.session_state["run_count"] += 1
RUN = int(st.session_state["run_count"])

# The order log records, per script run, whether the submit callback ran
# before the script body.  ``order_mark`` is the length of the log at the end
# of the previous run, so the slice of the log that belongs to this run is
# known without guessing.
st.session_state.setdefault("order_log", [])
st.session_state.setdefault("order_mark", 0)


def render(lines: list[str]) -> None:
    """Render the counters.  The first line is the run counter."""
    st.text(f"Script runs: {RUN}")
    st.text(f"Case: {CASE}")
    for line in lines:
        st.text(line)


def _this_run_entries() -> list[tuple]:
    """The order-log entries that belong to this run, in the order they came."""
    mark = int(st.session_state["order_mark"])
    entries = list(st.session_state["order_log"])[mark:]
    st.session_state["order_mark"] = len(st.session_state["order_log"])
    return entries


def case_form_default_submit() -> None:
    st.subheader("Form with a text input and a checkbox")

    def on_apply() -> None:
        # The callback of a form submit button runs before the body of the
        # submitting run.  It reads the state of the submitted batch; what it
        # actually sees is what the capture records.
        st.session_state["order_log"].append(
            (
                "callback",
                st.session_state.get("default_note"),
                st.session_state.get("default_agree"),
            )
        )

    with st.form("default_form", clear_on_submit=False):
        note = st.text_input("Note", key="default_note")
        agree = st.checkbox("Agree", key="default_agree")
        submitted = st.form_submit_button("Apply", key="default_apply", on_click=on_apply)

    st.session_state["order_log"].append(("main", note, agree))
    entries = _this_run_entries()
    callback = next((e for e in entries if e[0] == "callback"), None)
    order = ",".join(str(e[0]) for e in entries)
    render(
        [
            f"Order this run: {order}",
            (
                f"Callback saw: note={callback[1]!r}, agree={callback[2]!r}"
                if callback is not None
                else "Callback saw: <not called>"
            ),
            f"Main saw: note={note!r}, agree={agree!r}",
            f"Submitted this run: {submitted}",
        ]
    )


def case_form_text_enter_blur() -> None:
    st.subheader("Text input outside a form")
    outside = st.text_input("Outside note", key="outside_note")
    render([f"Main saw: outside_note={outside!r}"])


def case_form_none_vs_empty() -> None:
    st.subheader("None value next to an empty string")
    none_value = st.text_input("None value", value=None, key="none_value")
    empty_value = st.text_input("Empty value", value="", key="empty_value")
    render(
        [
            f"Main saw: none_value={none_value!r}",
            f"Main saw: empty_value={empty_value!r}",
            f"None is None: {none_value is None}",
        ]
    )


def case_form_error_duplicate_key() -> None:
    st.subheader("Two forms with the same key")
    with st.form("duplicate_form"):
        st.text_input("First", key="duplicate_first")
        st.form_submit_button("First apply", key="duplicate_first_apply")
    with st.form("duplicate_form"):
        st.text_input("Second", key="duplicate_second")
        st.form_submit_button("Second apply", key="duplicate_second_apply")
    render([])


def case_form_error_nested_form() -> None:
    st.subheader("A form inside a form")
    with st.form("outer_form"):
        with st.form("inner_form"):
            st.text_input("Inner", key="nested_inner")
            st.form_submit_button("Inner apply", key="nested_inner_apply")
        st.form_submit_button("Outer apply", key="nested_outer_apply")
    render([])


def case_form_clear_on_submit_false() -> None:
    st.subheader("A form that keeps its value on submit")
    with st.form("clear_false_form", clear_on_submit=False):
        note = st.text_input("Note", key="clear_false_note")
        submitted = st.form_submit_button("Apply", key="clear_false_apply")
    if submitted:
        st.session_state.setdefault("clear_false_submissions", []).append(note)
    render(
        [
            f"Main saw: note={note!r}",
            f"Submissions: {st.session_state.get('clear_false_submissions', [])!r}",
        ]
    )


def case_form_clear_on_submit_true() -> None:
    st.subheader("A form that clears its value on submit")
    with st.form("clear_true_form", clear_on_submit=True):
        note = st.text_input("Note", key="clear_true_note")
        submitted = st.form_submit_button("Apply", key="clear_true_apply")
    if submitted:
        st.session_state.setdefault("clear_true_submissions", []).append(note)
    render(
        [
            f"Main saw: note={note!r}",
            f"Submissions: {st.session_state.get('clear_true_submissions', [])!r}",
        ]
    )


def case_form_enter_to_submit_off() -> None:
    st.subheader("A form that Enter does not submit")
    with st.form("enter_off_form", clear_on_submit=False, enter_to_submit=False):
        note = st.text_input("Note", key="enter_off_note")
        submitted = st.form_submit_button("Apply", key="enter_off_apply")
    render([f"Main saw: note={note!r}", f"Submitted this run: {submitted}"])


def case_form_first_submit_disabled() -> None:
    st.subheader("A form whose first submit button is disabled")
    with st.form("first_disabled_form", clear_on_submit=False):
        note = st.text_input("Note", key="first_disabled_note")
        st.form_submit_button("Disabled", key="first_disabled_off", disabled=True)
        submitted = st.form_submit_button("Apply", key="first_disabled_apply")
    render([f"Main saw: note={note!r}", f"Submitted this run: {submitted}"])


def case_form_two_submit_buttons() -> None:
    st.subheader("A form with two submit buttons")
    with st.form("two_submit_form", clear_on_submit=False):
        note = st.text_input("Note", key="two_submit_note")
        save = st.form_submit_button("Save", key="two_submit_save")
        save_more = st.form_submit_button("Save and continue", key="two_submit_save_more")
    render(
        [
            f"Main saw: note={note!r}",
            f"Save: {save}, Save and continue: {save_more}",
        ]
    )


def case_form_two_forms_external_button() -> None:
    st.subheader("Two forms and a button outside them")
    with st.form("left_form", clear_on_submit=False):
        left = st.text_input("Left note", key="left_note")
        st.form_submit_button("Apply left", key="left_apply")
    with st.form("right_form", clear_on_submit=False):
        right = st.text_input("Right note", key="right_note")
        st.form_submit_button("Apply right", key="right_apply")
    outside = st.button("Outside", key="outside_button")
    if outside:
        st.session_state["outside_clicks"] = int(st.session_state.get("outside_clicks", 0)) + 1
    render(
        [
            f"Main saw: left={left!r}, right={right!r}",
            f"Outside clicks: {st.session_state.get('outside_clicks', 0)}",
        ]
    )


def case_form_text_types() -> None:
    st.subheader("The text input types")
    email = st.text_input("Email", key="type_email", type="email")
    url = st.text_input("URL", key="type_url", type="url")
    phone = st.text_input("Phone", key="type_phone", type="phone")
    search = st.text_input("Search", key="type_search", type="search")
    secret = st.text_input("Secret", key="type_password", type="password")
    render(
        [
            f"Main saw: email={email!r}, url={url!r}, phone={phone!r}",
            f"Main saw: search={search!r}, secret={secret!r}",
        ]
    )


def case_form_text_live_validate() -> None:
    st.subheader("A text input that reruns while it is typed")
    digits = st.text_input("Digits", key="live_digits", validate=(r"^\d+$", "digits only"), live=True)
    render([f"Main saw: digits={digits!r}"])


def case_form_text_required_disabled() -> None:
    st.subheader("A required and a disabled text input")
    required = st.text_input("Required", key="required_note", required=True, placeholder="type here")
    disabled = st.text_input("Disabled", key="disabled_note", disabled=True, value="fixed")
    render([f"Main saw: required={required!r}, disabled={disabled!r}"])


def case_form_j05_continuous() -> None:
    """One page, one journey: the form, the submit and the button outside.

    This is the J05 shape without any of the data app: a text input inside
    a form, the form's submit button, a button outside the form, and the
    markers the journey reads -- "Script runs:", "Pulses:" and "Applied
    note:".  Typing must not reach the server, the submit must apply the
    note exactly once and keep it in the field, and the three outside clicks
    must count three pulses and three more runs.
    """
    st.subheader("A form, a submit button and a button outside the form")
    pulse_clicked = st.button("Pulse", key="pulse")
    if pulse_clicked:
        st.session_state["pulse_count"] = int(st.session_state.get("pulse_count", 0)) + 1

    with st.form("apply_form", clear_on_submit=False):
        note = st.text_input("Note", key="note")
        submitted = st.form_submit_button("Apply note", key="apply_note")

    if submitted:
        st.session_state["applied_note"] = note

    render(
        [
            f"Pulses: {st.session_state.get('pulse_count', 0)}",
            f"Applied note: {st.session_state.get('applied_note', '')}",
        ]
    )


def case_form_max_chars_cjk() -> None:
    st.subheader("A text input with a character limit")
    probe = st.query_params.get("probe") == "length"
    if probe:
        limit = st.query_params.get("limit", "5")
        limit = None if limit == "none" else int(limit)
        default = None if st.query_params.get("default") == "none" else "abcdef🧊"
        phase = st.query_params.get("phase")
        if phase == "assign":
            st.session_state["cjk_note"] = "code長🧊extra"
        elif phase == "assign-none":
            st.session_state["cjk_note"] = None

        unkeyed = st.query_params.get("unkeyed") == "on"
        policy = st.query_params.get("policy", "normal")

        def changed():
            value = "changed" if unkeyed else st.session_state["cjk_note"]
            st.session_state["length_callbacks"] = st.session_state.get("length_callbacks", []) + [value]

        widget = st.text_area if st.query_params.get("kind") == "area" else st.text_input
        validation = st.query_params.get("validation", "inherit")
        text_options = {}
        if st.query_params.get("kind") != "area":
            text_options["type"] = st.query_params.get("input_type", "default")
            if validation == "off":
                text_options["validate"] = ""
            elif validation in ("pattern-a", "pattern-b"):
                text_options["validate"] = ("^A+$", "First message" if validation == "pattern-a" else "Second message")
        if unkeyed:
            text_options.update(disabled=policy == "disabled",
                                label_visibility=policy if policy in ("hidden", "collapsed") else "visible",
                                width=int(st.query_params["pixels"]) if "pixels" in st.query_params else "stretch",
                                help=st.query_params.get("help", ""))
        if "pixels" in st.query_params:
            text_options["width"] = int(st.query_params["pixels"])
        if st.query_params.get("kind") == "area":
            if "height" in st.query_params:
                text_options["height"] = int(st.query_params["height"])
            if "placeholder" in st.query_params:
                text_options["placeholder"] = st.query_params["placeholder"]
        callback = "ignore" if policy == "ignore" else None if policy == "none" else changed
        height_error_probe = st.query_params.get("height_errors") == "on"
        error = None
        try:
            cjk = widget("中文", key=None if unkeyed else "cjk_note", value=default, max_chars=limit, on_change=callback,
                         bind="query-params" if st.query_params.get("bind") == "on" else None, **text_options)
        except Exception as exc:
            if not height_error_probe:
                raise
            error = {"type": type(exc).__name__, "message": str(exc)}
            cjk = None
        report = {"phase": phase, "value": cjk, "state": None if unkeyed else st.session_state["cjk_note"],
                  "callbacks": st.session_state.get("length_callbacks", [])}
        if height_error_probe:
            report.update(error=error, locked=None, duplicate=None)
            if error is not None:
                try:
                    st.session_state["cjk_note"] = "attempted-write"
                except Exception as exc:
                    report["locked"] = {"type": type(exc).__name__, "message": str(exc)}
                try:
                    widget("中文", key="cjk_note", value=default, max_chars=limit, on_change=changed,
                           **({"height": 122} if st.query_params.get("kind") == "area" else {}))
                except Exception as exc:
                    report["duplicate"] = {"type": type(exc).__name__, "message": str(exc)}
                report["state"] = st.session_state["cjk_note"]
        if unkeyed:
            report["has_key"] = "cjk_note" in st.session_state
        if st.query_params.get("peer") == "on":
            def peer_changed():
                st.session_state["length_peer_callbacks"] = st.session_state.get("length_peer_callbacks", []) + [st.session_state["live"]]

            report["live"] = st.text_input("Live", value="ready", key="live", on_change=peer_changed)
            report["peer_callbacks"] = st.session_state.get("length_peer_callbacks", [])
        st.json(report)
    else:
        cjk = st.text_input("中文", key="cjk_note", max_chars=5)
    length = len(cjk) if isinstance(cjk, str) else 0
    render([f"Main saw: cjk={cjk!r}", f"Length: {length}"])


# --------------------------------------------------------------------------
# the layout group: a form inside a container or a column, and a container
# or columns inside a form
# --------------------------------------------------------------------------

def case_form_inside_container() -> None:
    st.subheader("A form inside a container")
    with st.container():
        with st.form("in_container_form", clear_on_submit=False):
            note = st.text_input("Note", key="in_container_note")
            submitted = st.form_submit_button("Apply", key="in_container_apply")
    if submitted:
        st.session_state.setdefault("in_container_submissions", []).append(note)
    render(
        [
            f"Main saw: note={note!r}",
            f"Submissions: {st.session_state.get('in_container_submissions', [])!r}",
        ]
    )


def case_form_inside_column() -> None:
    st.subheader("A form inside a column")
    left, right = st.columns(2)
    with left:
        with st.form("in_column_form", clear_on_submit=False):
            note = st.text_input("Note", key="in_column_note")
            submitted = st.form_submit_button("Apply", key="in_column_apply")
    if submitted:
        st.session_state.setdefault("in_column_submissions", []).append(note)
    render(
        [
            f"Main saw: note={note!r}",
            f"Submissions: {st.session_state.get('in_column_submissions', [])!r}",
        ]
    )


def case_container_inside_form() -> None:
    st.subheader("A container inside a form")
    with st.form("container_in_form", clear_on_submit=False):
        with st.container():
            note = st.text_input("Note", key="container_in_form_note")
        submitted = st.form_submit_button("Apply", key="container_in_form_apply")
    if submitted:
        st.session_state.setdefault("container_in_form_submissions", []).append(note)
    render(
        [
            f"Main saw: note={note!r}",
            f"Submissions: {st.session_state.get('container_in_form_submissions', [])!r}",
        ]
    )


def case_columns_inside_form() -> None:
    st.subheader("Columns inside a form")
    with st.form("columns_in_form", clear_on_submit=False):
        left, right = st.columns(2)
        with left:
            note = st.text_input("Note", key="columns_in_form_note")
        with right:
            agree = st.checkbox("Agree", key="columns_in_form_agree")
        submitted = st.form_submit_button("Apply", key="columns_in_form_apply")
    if submitted:
        st.session_state.setdefault("columns_in_form_submissions", []).append((note, agree))
    render(
        [
            f"Main saw: note={note!r}, agree={agree!r}",
            f"Submissions: {st.session_state.get('columns_in_form_submissions', [])!r}",
        ]
    )


def case_form_inside_expander() -> None:
    """Reference only: the expander is not implemented on the Rust side."""
    st.subheader("A form inside an expander")
    with st.expander("More", expanded=True):
        with st.form("in_expander_form", clear_on_submit=False):
            note = st.text_input("Note", key="in_expander_note")
            submitted = st.form_submit_button("Apply", key="in_expander_apply")
    if submitted:
        st.session_state.setdefault("in_expander_submissions", []).append(note)
    render(
        [
            f"Main saw: note={note!r}",
            f"Submissions: {st.session_state.get('in_expander_submissions', [])!r}",
        ]
    )


# --------------------------------------------------------------------------
# the callback group: the arguments of the submit callback, and a disabled
# text input inside a form
# --------------------------------------------------------------------------

def case_form_submit_callback_args() -> None:
    st.subheader("A submit button whose callback takes arguments")
    def on_apply(*args, **kwargs):
        # The callback runs before the body of the submitting run and reads
        # the state of the batch that was just submitted.  It writes into the
        # shared order log, so that the page can show in which order the two
        # ran and what the callback was given.
        st.session_state["order_log"].append(
            ("callback", args, kwargs, st.session_state.get("callback_args_note"))
        )

    with st.form("callback_args_form", clear_on_submit=False):
        note = st.text_input("Note", key="callback_args_note")
        submitted = st.form_submit_button(
            "Apply",
            key="callback_args_apply",
            on_click=on_apply,
            args=("alpha", 2),
            kwargs={"beta": "gamma"},
        )
    st.session_state["order_log"].append(("main", (), {}, note))
    entries = _this_run_entries()
    callback = next((e for e in entries if e[0] == "callback"), None)
    render(
        [
            f"Order this run: {','.join(str(e[0]) for e in entries)}",
            (
                f"Callback saw: args={callback[1]!r}, kwargs={callback[2]!r}, note={callback[3]!r}"
                if callback is not None
                else "Callback saw: <not called>"
            ),
            f"Main saw: note={note!r}",
        ]
    )


def case_form_disabled_text_input() -> None:
    st.subheader("A disabled text input inside a form")
    with st.form("disabled_in_form", clear_on_submit=False):
        editable = st.text_input("Note", key="disabled_form_note")
        fixed = st.text_input("Fixed", key="disabled_form_fixed", value="fixed", disabled=True)
        submitted = st.form_submit_button("Apply", key="disabled_form_apply")
    if submitted:
        st.session_state.setdefault("disabled_form_submissions", []).append((editable, fixed))
    render(
        [
            f"Main saw: note={editable!r}, fixed={fixed!r}",
            f"Submissions: {st.session_state.get('disabled_form_submissions', [])!r}",
        ]
    )


# --------------------------------------------------------------------------
# the remaining text input fields
# --------------------------------------------------------------------------

def case_form_text_password() -> None:
    st.subheader("A password field")
    secret = st.text_input("Password", key="pw_note", type="password")
    render([f"Main saw: secret={secret!r}"])


def case_form_text_remaining_fields() -> None:
    st.subheader("The remaining text input fields")
    hidden = st.text_input("Hidden label", key="hidden_label_note", label_visibility="hidden")
    collapsed = st.text_input(
        "Collapsed label", key="collapsed_label_note", label_visibility="collapsed"
    )
    narrow = st.text_input("Narrow", key="narrow_note", width=200)
    with_icon = st.text_input("With icon", key="icon_note", icon=":material/emoji_emotions:")
    automatic = st.text_input("Autocomplete", key="auto_note", autocomplete="email")
    render(
        [
            f"Main saw: hidden={hidden!r}, collapsed={collapsed!r}",
            f"Main saw: narrow={narrow!r}, icon={with_icon!r}, auto={automatic!r}",
        ]
    )


HANDLERS = {
    "form-default-submit": case_form_default_submit,
    "form-text-enter-blur": case_form_text_enter_blur,
    "form-none-vs-empty": case_form_none_vs_empty,
    "form-error-duplicate-key": case_form_error_duplicate_key,
    "form-error-nested-form": case_form_error_nested_form,
    "form-clear-on-submit-false": case_form_clear_on_submit_false,
    "form-clear-on-submit-true": case_form_clear_on_submit_true,
    "form-enter-to-submit-off": case_form_enter_to_submit_off,
    "form-first-submit-disabled": case_form_first_submit_disabled,
    "form-two-submit-buttons": case_form_two_submit_buttons,
    "form-two-forms-external-button": case_form_two_forms_external_button,
    "form-text-types": case_form_text_types,
    "form-text-live-validate": case_form_text_live_validate,
    "form-text-required-disabled": case_form_text_required_disabled,
    "form-max-chars-cjk": case_form_max_chars_cjk,
    "form-j05-continuous": case_form_j05_continuous,
    "form-inside-container": case_form_inside_container,
    "form-inside-column": case_form_inside_column,
    "container-inside-form": case_container_inside_form,
    "columns-inside-form": case_columns_inside_form,
    "form-inside-expander": case_form_inside_expander,
    "form-submit-callback-args": case_form_submit_callback_args,
    "form-disabled-text-input": case_form_disabled_text_input,
    "form-text-password": case_form_text_password,
    "form-text-remaining-fields": case_form_text_remaining_fields,
}

# The canonical ids and the handlers must agree: a case that has no handler
# would quietly do nothing, and a handler that has no id would never run.
missing = [name for name in CASES if name not in HANDLERS]
extra = [name for name in HANDLERS if name not in CASES]
if missing or extra:
    raise RuntimeError(f"case ids and handlers disagree: missing={missing} extra={extra}")

HANDLERS[CASE]()
