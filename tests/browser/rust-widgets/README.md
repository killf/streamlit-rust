# Rust widgets capture (final build)

The widgets example of the Rust server, driven with the official Streamlit
1.66.1 frontend.  `trace-widgets.json` holds the full Element protobuf of
every widget, every client widget state, the script results and the DOM before
and after each change.

**Server under test**

- binary `target/checks/widgets-live/widgets-current-20261024T120409.exe`
- sha256 `292ED585398C738BC5432AF46F22C4753D31AA99CEEF8FDCAF2932A35118F259`
- source: `83dfea5` plus the owner's uncommitted increment
- `widget_api` sha256 `C4CA692118CD4485282C31757483FD2F72E099894394E51E5F5F6E54F6B7F3B8`

The capture ran the `rust-widgets` suite: **expected 6, executed 6,
asserted 6**, `failures: []`.

| widget | wire value before -> after | the page shows |
|---|---|---|
| Group by (selectbox) | -- -> `"region"` | `region` |
| Include unknown region (checkbox) | `true` -> `false` | `false` |
| Minimum amount (one int value) | `[0]` -> `[10]` | `10` |
| Ratio (one float value) | `[0.25]` -> `[0.3]` | `0.30` |
| Amount range (two int values) | `[20, 80]` -> `[30, 80]` | `30..80` |
| Ratio range (two float values) | `[0.2, 0.8]` -> `[0.3, 0.8]` | `0.30..0.80` |

Every case is decided by the verdict the capture and the harness share: the
action ran, the widget's own state inside the window carries a changed value
in the field that kind of widget sends, a `script_finished` with status 0
follows it **on the same connection**, and the page shows that value.  Every
frame in the raw carries the DevTools request id of its socket and the
connection it belongs to.

The ranges are written `30..80` by the example, where the Python reference
writes `(30, 80)`; the values are the same.

The capture was produced by the committed entry:

~~~powershell
python tests/browser/numeric_capture.py --url "http://127.0.0.1:8501/" --label rust-widgets --suite rust-widgets --kind rust-browser-widget-trace --scope "RUST SIDE ONLY" --binary "<path> sha256 <sha>" --port <chrome-cdp-port>
~~~

`agent-browser` could not start its daemon in this environment, so the entry
sends the input over the DevTools Protocol to the same real Chrome; the reason
is recorded in the `capture` block of the raw.  The capture opened its own tab,
so it ran against a fresh session.

Two earlier captures are kept under `target/` and are not part of the
repository: the four numeric representatives alone, taken before the
selectbox and the checkbox could be exercised
(`target/rust-widgets-numeric-partial/`), and this six case capture taken
before the frames carried their connection
(sha256 `808da30232cc6dd954c13e4f0fe0a523703098df15f623dbeb48da5e4e6f5089`,
`target/numeric-rust-final/`).  No frame of either was edited.
