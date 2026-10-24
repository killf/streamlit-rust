# Numeric widget reference (Python 1.66.1)

The four numeric representatives, rendered by the pinned Python 1.66.1
reference app with the official frontend.  `trace-widgets-numeric.json` holds
the full Element protobuf of every slider, every client widget state, the
script results and the DOM before and after each change.

The fixture is `tests/reference/numeric_app.py` (sha256 `78d9fde6708407ee1f265457834d37032ca5a6135aa12c306331044c80ece388`), one
page, started on port 8604.  It is development only and never shipped.

The capture ran the `python-numeric` suite: **expected 4, executed 4,
asserted 4**, no failures.

| widget | shape | wire value before -> after | the page shows |
|---|---|---|---|
| Minimum amount | one int value | -- -> `[10]` | `10` |
| Ratio | one float value | `[0.25]` -> `[0.3]` | `0.3` |
| Amount range | two int values | `[20, 80]` -> `[30, 80]` | `(30, 80)` |
| Ratio range | two float values | `[0.2, 0.8]` -> `[0.3, 0.8]` | `(0.3, 0.8)` |

Every slider sends a `double_array_value`: one element for a single value, two
for a range.  Each case is decided by the verdict the capture and the harness
share: the action ran, the widget's own state inside the window carries a
changed value, a `script_finished` with status 0 follows it **on the same
connection**, and the page shows the value that was sent.  Every frame in the
raw carries the DevTools request id of its socket and the connection it
belongs to.

The capture was produced by the committed entry, which shares the case list,
the verdict and the assertions with the harness:

~~~powershell
python -m streamlit run tests\\reference\\numeric_app.py --server.headless true --server.port 8604
python tests\\browser\\numeric_capture.py --url "http://127.0.0.1:8604/?case=numeric" \\
    --label python-numeric --suite python-numeric
~~~

The `agent-browser` CLI could not start its daemon in this environment, so the
entry sends the input over the DevTools Protocol to the same real Chrome; the
reason is recorded in the `capture` block of the raw.

An earlier capture of the same four cases, taken before the frames carried
their connection, is kept under `target/numeric-python-suite/`
(sha256 `7bb391a19ddfea70cd524f3766c75327b8b09b4840efa67c9b76379c25c3c27e`); it is not part
of the repository and no frame of it was edited.
