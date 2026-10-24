# Browser captures

`numeric_capture.py` is the committed entry point for the numeric widget
comparison.  It reuses the recorder, the protobuf decoders, the DOM probe, the
case list and the strict click verification of
`tests/reference/capture_browser_trace.py`; it only adds the input.

~~~powershell
# a Python reference app
python -m streamlit run tests\reference\numeric_app.py --server.headless true --server.port 8604
python tests\browser\numeric_capture.py --url "http://127.0.0.1:8604/?case=numeric" --label python-numeric --suite python-numeric

# the Rust widgets example
python tests\browser\numeric_capture.py --url "http://127.0.0.1:8501/" --label rust-widgets --suite rust-widgets --kind rust-browser-widget-trace --scope "RUST SIDE ONLY" --out target/rust-widgets
~~~

For a version-bound Rust capture, also pass `--binary "<running binary path> sha256 <full SHA256>"`
and `--port <actual Chrome CDP port>`, as in the final capture README. The fingerprint
must describe the running server, not another build. The collector retains real
request IDs/connection identities and requires a successful action and changed
target value; resending an old state or observing old DOM cannot satisfy a case.

The output goes to `target/` by default.  Only a capture that has been
reviewed belongs under `tests/browser/`:

- [rust-widgets/](rust-widgets/README.md): the final six-case capture (selectbox,
  checkbox, integer/float scalars and integer/float ranges), bound to the final
  binary/source fingerprints. Expected, executed and asserted counts are all six.
- The earlier four-only partial attempt is preserved under ignored
  `target/rust-widgets-numeric-partial/`; it is not a product evidence directory.

The frozen captures used real Chrome CDP input after their CLI daemon connection
failed; each raw records that capture-time reason. A later named CLI session
worked with agent-browser 0.25.4; that does not change the frozen capture method.
The permanent entry opens a fresh tab, checks the six required cases without
silently skipping them, and compares each returned DOM value with its actual
client wire value and successful same-connection completion.

The data journeys of the Rust data app live in
[rust-journeys/](rust-journeys/README.md): the closed loop and the recovery,
empty and two-session journeys, each with its counts, its observed values and
the command that regenerates it.

Run every capture with `target\pyref-venv\Scripts\python.exe`, the
interpreter that carries streamlit 1.66.1 and its protobuf definitions; the
entry stops before it records anything when the decoder is missing, so a
capture can never be a page of empty frames.  The fixture paths have to be
absolute: Chrome resolves a relative path against its own working directory
and the uploader would receive no file.

[test_observe_js.py](test_observe_js.py) runs the DOM probe in the same real
Chrome and checks what it answers, so a probe that stops answering is caught
before a capture relies on it.
