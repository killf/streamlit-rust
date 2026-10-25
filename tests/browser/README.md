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

## Execution semantics (J04-S4)

[execution_capture.py](execution_capture.py) is the permanent entry for the
st.rerun/st.stop journey; [execution_contract.py](execution_contract.py) is
its strict criterion (journey-execution-v1, 8 checks) with unit tests in
[tests/reference/test_execution_contract.py](../reference/test_execution_contract.py).
The collector starts its own Chrome, drives the mirrored mode selector
(plain / one guarded rerun / stop) and records the decoded frames, the DOM
end states and one PNG per stage. The published chains, independently
reviewed on 2026-10-25:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\execution_capture.py --replay tests\reference\reference-browser\execution-j04\trace-execution.json
target\pyref-venv\Scripts\python.exe tests\browser\execution_capture.py --replay tests\browser\rust-execution-j04\trace-execution.json
```

Both return 8 expected / 8 executed / 8 asserted with exit 0. Raw SHA256:
python `c4da12b8481a535a2cd073b3a6a8c6dbac29ad9f5421286d9e53ad5fc3024ba9`,
native `ab79372a8e2d2f29a1f6d8804b9cde4cd3217b4e579f517bc0adf2064285378f`,
under contract `ae1c098afe94e235003ee1a8a6eb4be2f2233681f3ebbb9dd1dc93a130aab29e`.
The three documented cross-side differences (per-run `main_block` delta,
fast-rerun live streaming, populated `ForwardMsg.hash` on lifecycle frames)
are recorded in [compatibility](../../.codex/compatibility.md#execution-semantics-st-rerun--st-stop).

## Temporal sliders

[temporal_capture.py](temporal_capture.py) is the permanent entry for the
date/time/datetime slider chain; [temporal_contract.py](temporal_contract.py)
is its strict criterion (journey-temporal-v1, 11 checks) with unit tests in
[tests/reference/test_temporal_contract.py](../reference/test_temporal_contract.py).
The collector starts its own Chrome and drives every slider's hidden native
range input with real End/Home keys across the 13 measured stages. The
published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\temporal_capture.py --replay tests\reference\reference-browser\temporal\trace-temporal.json
target\pyref-venv\Scripts\python.exe tests\browser\temporal_capture.py --replay tests\browser\rust-temporal\trace-temporal.json
```

Both return 11 expected / 11 executed / 11 asserted with exit 0. Raw SHA256:
python `0bafb49dbe5ed904771d7dd1d7f86272f04cb4a5c26468f6f21217d2133a987b`,
native `4d43936e402aeb298eaa5bd72bc72af3ad1d5c3a802a3e24deecc1bcee115f47`,
under contract `c375aafd11d725a104510a8ae91dd22104cb8a533addf065b26e67936e02fd65`.
The Rust side carries the pre-existing per-run `main_block` delta (one extra
frame per stage); the contract compares content, not frame counts.

## Elements page (fifteen APIs)

[elements_capture.py](elements_capture.py) is the permanent entry for the
fifteen-API elements chain (title, header, caption, badge, divider, code,
markdown, write, columns, container, form, text_input, form_submit_button,
table, bar_chart); [elements_contract.py](elements_contract.py) is its strict
criterion (journey-elements-v1, 11 checks) with unit tests in
[tests/reference/test_elements_contract.py](../reference/test_elements_contract.py).
The collector starts its own Chrome and drives the second stage with real
typing into the form's Note input plus a real Apply click. The published
chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\elements_capture.py --replay tests\reference\reference-browser\elements\trace-elements.json
target\pyref-venv\Scripts\python.exe tests\browser\elements_capture.py --replay tests\browser\rust-elements\trace-elements.json
```

Both return 11 expected / 11 executed / 11 asserted with exit 0. Raw SHA256:
python `b4b26a61be511d0de18ac393c53b052d28a4302429c5e8532148ac3423ac1119`,
native `14ab0ea580c2183d2f9e43db05d2de48f53aaaffcb9a755a91dd006a19a9159a`,
under contract `d54226fabc0e2e09f69787d01de5b5fb6c108602e38f358681210167350aab1c`.
The contract tolerates only the documented leading `main_block` delta on the
Rust side; the vega shape and the table's arrow payload are compared as
normalized shapes, not bytes.

## Input widgets (radio, multiselect, number_input, text_area)

[inputs_capture.py](inputs_capture.py) is the permanent entry for the
four-widget input chain; [inputs_contract.py](inputs_contract.py) is its
strict criterion (journey-inputs-v1, 11 checks) with unit tests in
[tests/reference/test_inputs_contract.py](../reference/test_inputs_contract.py).
The collector starts its own Chrome and drives a radio pick, a multiselect
pick through its real popover, number_input retyping with real key events
and a text_area append across the five measured stages. The tables freeze
the measured commit semantics: radio and multiselect commit immediately,
number_input and text_area commit on blur — the typed text sits in the DOM
while the widget state keeps the previously committed value until the next
stage's click blurs the control. The published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\inputs_capture.py --replay tests\reference\reference-browser\inputs\trace-inputs.json
target\pyref-venv\Scripts\python.exe tests\browser\inputs_capture.py --replay tests\browser\rust-inputs\trace-inputs.json
```

Both return 11 expected / 11 executed / 11 asserted with exit 0. Raw SHA256:
python `af839527e3ac0d55e2626b10768ae3caae2d8904df6588b5e0f418489f90980c`,
native `e9cbb682f47ba4d1ab14cab92904b3985fd1c7360091b6f1c814ba6449635854`,
under contract `0e88f76b2cd2689c0791cd4f7236db4d86e855210c41f7a45494245a648a3689`.
The Rust side carries the pre-existing per-run `main_block` delta (one extra
frame per stage); the contract compares content, not frame counts.
