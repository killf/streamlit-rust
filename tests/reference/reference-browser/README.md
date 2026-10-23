# Python reference browser traces

These are real black-box observations of the pinned Python Streamlit 1.66.1 application in a browser. They record HTTP requests, WebSocket handshakes and frames, decoded protobuf, DOM observations, and selected screenshots. They are oracle evidence only; the Rust server is not exercised by these files.

Current captures:

- `closed-loop/`: startup, upload, selectbox, slider, checkbox, button pulse.
- `errors/`: malformed CSV, soft-failure amounts, empty data, no-match filter.
- `form/`: typing without submit and one form submit.
- `tabs/`: two concurrent browser tabs with isolated sessions.
- `reconnect/`: a real client-side close of the live socket; the frontend reconnects on its own and the handshake carries a third subprotocol entry, the session id. The same session id is seen before and after, and the counter survives.
- `refresh/`: a page reload; the handshake carries only two entries and a new session id is issued.
- `reconnect/`: the live socket is closed from the page, the frontend reconnects on its own, and the
  reconnect handshake carries a third subprotocol entry.  Every connection is recorded separately with
  its handshake, its close event and the frames that travelled on it, and a click on the reconnected
  session proves it works: a true trigger and a successful `script_finished` on the new connection.


Regenerate to a temporary directory first, then review before replacing a committed trace:

```powershell
python tests/reference/capture_browser_trace.py --url http://localhost:8601 --scenario closed-loop --out <temporary-path>
```
Superseded captures (replaced, not kept):

- `reconnect/` trace.json sha256:3504db1967797c34d92bf93b197551bbfe822e4982bbddb829b9ede3febc0cb1
- `refresh/` trace.json sha256:34e69133663ec1364ccd7512bfe94e7d93e60275885d8239660691cb95c0fbb7

Both were replaced because they merged the handshakes per tab and kept only the
last one, so they could not show which connection a frame belonged to.
