# Rust session counter capture (S1 handover build)

Black-box capture of the Rust counter against the frozen S1 binary, using the
official Streamlit 1.66.1 frontend.  `trace-counter.json` is the raw record:
HTTP requests, the WebSocket connections that were observed, every decoded frame
with the connection it travelled on, and the DOM observation of each step.

**Server under test** `target/checks/session-live/counter-session-boundary.exe`
sha256 `2c66841195bafdfd2f71c95d4372e981f3cde3eac8c3229f012b40567d55693b`,
source `git 7215312 + owner S1 handover fix`.  The trace records this itself in
`server_under_test`.

Four connections were observed: tab A's first connection, the reconnection, the
reload, and tab B.  Three of them have a complete handshake (HTTP 101 with its
subprotocol entries).  **Tab B's initial handshake was not captured** -- its
recorder was attached after the page had already opened, so the record for that
connection carries no url, no status and no subprotocol entries, and it keeps
the default target label while the frames on that connection are labelled
tab-b.  The raw is left exactly as it was captured: the missing handshake is
not reconstructed.

What it covers, and what the raw shows:

| journey | observation |
|---|---|
| two tabs, isolated sessions | tab A `dd2d79df-…`, tab B `c366fafb-…`, disjoint |
| tab B click does not touch tab A | tab B pulses 1, tab A still 0 with 1 script run |
| same-session recovery | the socket is closed from the page; the frontend reconnects and the handshake carries a third subprotocol entry with the session id; the session id is unchanged and the counter survives at 2 |
| the page still works after the recovery | the click on the reconnected session advances the counter to 3 |
| reload starts a new session | after the reload the session id is `d63f719e-…` and the counter is back to 0 |

Every click was verified against the wire, not only against the DOM: each click
window contains a `trigger_value=true` frame and, **after** it on the **same**
connection, a `script_finished` with status 0 (`FINISHED_SUCCESSFULLY`).
Four clicks, four verified windows, `failures: []`.

Regenerate:

~~~powershell
python tests/reference/capture_browser_trace.py --scenario counter --url http://127.0.0.1:8501/ --target rust --binary target/checks/session-live/counter-session-boundary.exe --source-version "git 7215312 + owner S1 handover fix" --out <temporary-path>
~~~

The superseded pre-S1 draft (binary SHA-256 `f1998e79d03577dd3e23aa1e6debcdbf941b754212485a84f99944d3538cd9fb`, raw SHA-256 `0903bd0df4bfcd421048a34eeb30d70f579585e6af83df94d86e5ec3f729ba44`) is preserved unchanged only under ignored `target/checks/rust-counter-provisional-*` and is not current evidence.
