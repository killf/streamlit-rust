"""The DOM probe has to run: a probe that throws answers with nothing.

The capture reads the rendered page with OBSERVE_JS.  When that script
throws, the probe returns no value at all and the capture cannot tell an
empty page from a broken one -- the failure a capture with a relative
fixture path produced.  This test runs the same script in the real Chrome the
capture drives, against a page that carries the Streamlit markup, and checks
what comes back.

It needs a Chrome that speaks the DevTools Protocol on port 60667.  When
there is none, the test says so and stops: the other tests of this
repository stay free of a browser dependency.
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.parse
import urllib.request

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "reference"))

from capture_browser_trace import OBSERVE_JS, CDP  # noqa: E402

CHROME_PORT = 60667

PAGE = """<!doctype html><html><body>
<div data-testid="stMarkdown"><p>Script runs: 3</p><p>Pulses: 1</p></div>
<div data-testid="stFileUploader"><input type="file" data-testid="stFileUploaderDropzoneInput"></div>
<div data-testid="stDataFrame"><span role="gridcell">Books</span><span role="gridcell">3</span></div>
<div data-testid="stVegaLiteChart">
  <g class="mark-rect"><path d="M0,0h10v20Z"></path><path d="M0,0h10v40Z"></path></g>
  <g class="mark-text"><text>east</text></g>
</div>
<div data-testid="stAlertContent">Could not parse the uploaded CSV</div>
</body></html>"""


def _chrome_version(port: int):
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version", timeout=5
        ) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def _evaluate(page_html: str, port: int):
    """Run OBSERVE_JS in a fresh tab and return the raw CDP answer."""
    url = "data:text/html," + urllib.parse.quote(page_html)
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/json/new?{url}", method="PUT"
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        created = json.loads(response.read().decode("utf-8"))
    recorder = CDP(created["webSocketDebuggerUrl"], label="observe-js")
    recorder.start()
    try:
        return recorder.call(
            "Runtime.evaluate", {"expression": OBSERVE_JS, "returnByValue": True}
        )
    finally:
        recorder.stop()


def _probe_value(answer):
    """The value the probe answered, or None when it answered with nothing."""
    if not answer or "error" in answer:
        return None
    result = answer.get("result", {})
    if isinstance(result, dict) and "result" in result:
        result = result["result"]
    if not isinstance(result, dict) or "value" not in result:
        return None
    value = result["value"]
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def test_the_dom_probe_answers_with_the_rendered_page() -> None:
    if _chrome_version(CHROME_PORT) is None:
        pytest.skip(
            f"no Chrome on port {CHROME_PORT}; the DOM probe needs the browser "
            "the capture drives"
        )
    answer = _evaluate(PAGE, CHROME_PORT)
    assert "error" not in (answer or {}), answer
    observed = _probe_value(answer)
    assert observed is not None, f"the probe returned no value: {json.dumps(answer)[:400]}"
    assert observed["table_present"] is True
    assert observed["table_cells"] == ["Books", "3"]
    assert observed["chart_present"] is True
    assert observed["chart_bars"] == 2
    assert observed["chart_labels"] == ["east"]
    assert observed["alerts"] == ["Could not parse the uploaded CSV"]
    assert observed["script_runs"] == "3"
    assert observed["pulses"] == "1"
    assert observed["has_uploader"] is True


def test_the_dom_probe_answers_about_an_empty_page_too() -> None:
    """A page without a table must still answer, with the fields empty."""
    if _chrome_version(CHROME_PORT) is None:
        pytest.skip(
            f"no Chrome on port {CHROME_PORT}; the DOM probe needs the browser "
            "the capture drives"
        )
    answer = _evaluate("<!doctype html><html><body></body></html>", CHROME_PORT)
    observed = _probe_value(answer)
    assert observed is not None, f"the probe returned no value: {json.dumps(answer)[:400]}"
    assert observed["table_present"] is False
    assert observed["table_cells"] == []
    assert observed["chart_present"] is False
    assert observed["chart_bars"] == 0
    assert observed["alerts"] == []
