"""Repeated query values and mutation order on the pinned native WS oracle."""
import streamlit as st


def snapshot(stage):
    st.json({"stage": stage, "value": st.query_params.get("tag"),
             "all": st.query_params.get_all("tag"),
             "pairs": list(st.query_params.to_dict().items()),
             "empty": st.query_params.get("empty")})


def run_values():
    snapshot("load")
    st.query_params["tag"] = ["replacement", "tail"]
    snapshot("replace")
    st.query_params["new"] = "中文 + text"
    snapshot("append")
    st.query_params["empty"] = []
    snapshot("empty-list")
    del st.query_params["empty"]
    snapshot("remove-empty")
    del st.query_params["tag"]
    snapshot("remove-tag")
    st.query_params.clear()
    snapshot("clear")
    st.query_params["tag"] = ["again", "last"]
    snapshot("restore")


def run_reserved():
    def report(stage):
        st.json({"stage": stage, "embed": st.query_params.get("embed"),
                 "options": st.query_params.get_all("EMBED_OPTIONS"),
                 "ordinary": st.query_params.get("st_embed"),
                 "empty_key": st.query_params.get(""),
                 "pairs": list(st.query_params.to_dict().items())})

    report("reserved-load")
    for key in ("embed", "EmBeD_OpTiOnS"):
        try:
            st.query_params[key] = "changed"
        except Exception:
            st.json({"operation": "set:" + key, "rejected": True})
        else:
            st.json({"operation": "set:" + key, "rejected": False})
    try:
        del st.query_params["embed"]
    except KeyError:
        st.json({"operation": "remove:embed", "rejected": True})
    else:
        st.json({"operation": "remove:embed", "rejected": False})
    report("after-rejections")
    st.query_params[""] = "updated empty key"
    report("empty-key-set")
    del st.query_params[""]
    report("empty-key-remove")
    st.query_params.clear()
    report("reserved-clear")
    st.query_params["restored"] = "ok"
    report("reserved-restore")


def run_binding():
    phase = st.query_params.get("phase")

    def attempt(operation, action):
        try:
            action()
        except Exception:
            st.json({"operation": operation, "rejected": True})
        else:
            st.json({"operation": operation, "rejected": False})

    if phase in ("load", "active"):
        selected = st.selectbox("Bound", ["x", "y"], key="bound", bind="query-params")
        text = st.sidebar.text_input("Text", key="text", bind="query-params")
        st.json({"phase": phase, "selected": selected, "text": text})
    if phase in ("load", "active", "hidden"):
        attempt("set:bound", lambda: st.query_params.__setitem__("bound", "manual"))
        attempt("set:text", lambda: st.query_params.__setitem__("text", "manual"))
        attempt("remove:bound", lambda: st.query_params.__delitem__("bound"))
        attempt("clear", st.query_params.clear)
        if phase == "active":
            st.query_params["BOUND"] = "case-sensitive"
    else:
        st.query_params["bound"] = "manual"
        st.query_params.clear()
    st.json({"phase": phase, "pairs": list(st.query_params.to_dict().items())})


def run_seed():
    phase = st.query_params.get("phase")
    if phase in ("bad-initial", "bad-history"):
        st.session_state["bound"] = 99
        st.session_state["text"] = 99
    elif phase in ("assign", "history", "history-missing"):
        st.session_state["bound"] = "x"
        st.session_state["text"] = "code"
    selected = st.selectbox("Bound", ["x", "y"], key="bound", bind="query-params")
    text = st.text_input("Text", value="base", key="text", bind="query-params")
    optional = st.selectbox("Optional", ["x", "y"], index=None, key="optional", bind="query-params")
    creation = st.selectbox("Creation", ["x", "y"], accept_new_options=True, key="creation", bind="query-params")
    st.json({"phase": phase, "bound": selected, "text": text, "optional": optional,
             "creation": creation, "pairs": list(st.query_params.to_dict().items())})


def run_disabled():
    phase = st.query_params.get("phase")
    disabled = phase not in ("enabled", "interactive")

    def changed(key):
        st.session_state["callbacks"] = st.session_state.get("callbacks", []) + [key]

    if phase == "code":
        st.session_state["plain"] = "code"
        st.session_state["bound"] = "x"
        st.session_state["text"] = "code"
        st.session_state["check"] = True
    plain = None
    if phase != "hidden":
        plain = st.text_input("Plain", value="safe", key="plain", disabled=disabled, on_change=changed, args=("plain",))
    bound = st.selectbox("Bound", ["x", "y"], key="bound", disabled=disabled, bind="query-params", on_change=changed, args=("bound",))
    text = st.text_input("Text", value="base", key="text", disabled=disabled, bind="query-params", on_change=changed, args=("text",))
    check = st.checkbox("Check", key="check", disabled=disabled, on_change=changed, args=("check",))
    live = st.text_input("Live", value="ready", key="live", on_change=changed, args=("live",))
    st.json({"phase": phase, "plain": plain, "bound": bound, "text": text, "check": check,
             "live": live, "callbacks": st.session_state.get("callbacks", []), "pairs": list(st.query_params.to_dict().items())})


def run_rerun():
    phase = st.query_params.get("phase")
    counter_key = "passes_" + phase
    iteration = st.session_state.get(counter_key, 0)
    st.session_state[counter_key] = iteration + 1

    def changed(key):
        st.session_state["callbacks"] = st.session_state.get("callbacks", []) + [key]

    def report(stage, **values):
        st.json({"phase": phase, "iteration": iteration, "stage": stage,
                 "bound": st.session_state.get("bound"), "text": st.session_state.get("text"),
                 "callbacks": st.session_state.get("callbacks", []),
                 "pairs": list(st.query_params.to_dict().items()), **values})

    if phase == "messages" and iteration == 0:
        st.set_page_config(page_title="Queued config")
        st.toast("Queued toast")
        st.markdown("queued content")
        st.balloons()
    st.query_params["marker"] = f"{phase}-{iteration}"
    report("before")
    if phase == "early" and iteration == 0:
        st.rerun()
    if phase in ("assign", "history") and iteration == 0:
        st.session_state["bound"] = "x" if phase == "assign" else "y"
        st.session_state["text"] = "code"
    bound = st.selectbox("Bound", ["x", "y"], key="bound", bind="query-params", on_change=changed, args=("bound",))
    text = st.text_input("Text", value="base", key="text", bind="query-params", on_change=changed, args=("text",))
    report("values", bound=bound, text=text)
    if iteration == 0:
        st.rerun()
    report("complete")


def run_queue():
    phase = st.query_params.get("phase")
    iteration = st.session_state.get("queue_iteration", 0) if phase == "queue" else 0
    if iteration == 0:
        st.set_page_config(page_title="Queued config")
        st.toast("Queued toast")
        st.markdown("queued content")
        st.balloons()
    if phase == "queue" and iteration == 0:
        st.session_state["queue_iteration"] = 1
        st.query_params["marker"] = "retained"
        st.rerun()
    st.json({"phase": phase, "iteration": iteration})


if st.query_params.get("case") == "queue":
    run_queue()
elif st.query_params.get("case") == "rerun":
    run_rerun()
elif st.query_params.get("case") == "disabled":
    run_disabled()
elif st.query_params.get("case") == "seed":
    run_seed()
elif st.query_params.get("case") == "binding":
    run_binding()
elif st.query_params.get("case") == "reserved":
    run_reserved()
else:
    run_values()
