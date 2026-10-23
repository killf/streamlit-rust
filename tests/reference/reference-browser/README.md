# Python reference browser traces

These are real black-box observations of the pinned Python Streamlit 1.66.1 application in a browser. They record HTTP requests, WebSocket handshakes and frames, decoded protobuf, DOM observations, and selected screenshots. They are oracle evidence only; the Rust server is not exercised by these files.

Current captures:

- `closed-loop/`: startup, upload, selectbox, slider, checkbox, button pulse.
- `errors/`: malformed CSV, soft-failure amounts, empty data, no-match filter.
- `form/`: typing without submit and one form submit.
- `tabs/`: two concurrent browser tabs with isolated sessions.

The failed reconnect attempt is intentionally not product evidence; it remains under `target/checks/ref-reconnect-failed/`. Recapture it before claiming reconnect behavior.

Regenerate to a temporary directory first, then review before replacing a committed trace:

```powershell
python tests/reference/capture_browser_trace.py --url http://localhost:8601 --scenario closed-loop --out <temporary-path>
```