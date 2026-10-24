# Rust data loop capture

The same closed loop as the Python reference, driven against the Rust data app
with the official Streamlit 1.66.1 frontend: upload a CSV, then change the
group, switch the unknown regions off and raise the minimum amount.

**Server under test**

- binary `target/checks/data-app-live/data-app-20261024T141223140.exe`
- sha256 `F8A0D4CA241F64F98CC7CF5736869491DE07D958E0428C2EC3EB687DC9AC44A3`
- source sha256 `321d57e2f016274cecd20c06987700b71bb435ad582d28fa0342c901e06756d4`
- config sha256 `1a94e7d4b592e5301dbc49823f4a5be3e9a0ea710c5d1caaa7c1df776a4d7a08`
- `data_app.rs` sha256 `7f383910c55b68c00d3443a9300598ea0b1d1f92f7690fbd824d0122d1927a27`
- `data_api.rs` sha256 `dd1bdc230ef66aa499a0ded40a4c95993715dd3be67b89084925f1d0ae344f74`
- source: `HEAD 1d0f7c2` plus the owner's uncommitted increment

The upload went through the same exchange as the Python reference: the client
asks for the upload URLs, the server answers with the file id and the
upload and delete URLs, and the browser puts the file there with a `PUT` that
answered **204**.

## The steps

| step | the rows | the page |
|---|---|---|
| after the upload | Books 3/245.75, Games 3/409.48, Music 3/139, Toys 3/104.49 | 4 bars |
| Group by -> region | (missing) 1/88, East 2/209.49, North 3/264.5, South 2/245.24, UNKNOWN 2/40.49, West 2/51 | 6 bars |
| Include unknown region off | East 2/209.49, North 3/264.5, South 2/245.24, West 2/51 | 4 bars |
| Minimum amount 100 | East 1/149.5, North 1/120.5, South 1/199.99 | 3 bars |

The same values, the same order and the same number of groups as the Python
reference capture in
`tests/reference/reference-browser/data-loop/updates-strict/`.

The capture ran the `rust-widgets` suite of the permanent entry: **expected 3,
executed 3, asserted 3**, `failures: []`, exit 0.  Every step is checked
against the wire: the action ran, the widget's own state carried a changed
value, a `script_finished` with status 0 followed on the same connection, the
Arrow of that step is in the window, the page shows its rows cell by cell, and
the bars stand for the values with one positive scale.

The Arrow payloads are `arrow-1..4.bin`, one per step and stored once per
digest.  They are 1224 bytes each, while the Python reference writes 1640:
the Rust IPC does not carry the pandas metadata block of the reference.

Regenerate:

~~~powershell
python tests\\browser\\numeric_capture.py --url "http://127.0.0.1:8501/" --case data-loop \\
    --fixture tests\\fixtures\\csv\\sales_basic.csv --label rust-data \\
    --kind rust-browser-data-loop-trace --scope "RUST SIDE ONLY" --binary "<path> sha256 <sha>"
~~~

The `agent-browser` CLI could not start its daemon in this environment, so the
entry drives the same real Chrome over the DevTools Protocol; the reason is
recorded in the `capture` block of the raw.
