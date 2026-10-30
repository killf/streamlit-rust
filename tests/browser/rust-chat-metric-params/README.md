# Rust chat/metric/progress wire evidence

These are native WebSocket captures against the Rust server using the unmodified
protocol. They contain no browser DOM, screenshots or real UI interaction claim.

- `trace.json`: original eight-element creation-parameter comparison.
- `string-delta-before/trace.json`: retained failed comparison; 30 of 36 string
  delta cases differ from Python Streamlit 1.66.1.
- `string-delta/trace.json`: fixed comparison; all 36 string delta cases match
  the [frozen reference](../../reference/reference-browser/chat-metric-params/string-delta/trace.json).

The string cases cover normal/inverse/off colors, literal and numeric-looking
zero strings, negative text, NaN text, indentation and preserved newlines.
Both Rust capture processes were terminated after collection; the reference
collector records its own cleanup. The failure trace is retained unchanged.

Run `python -m pytest tests/reference/test_chat_metric_params_reference.py -q`
with the pinned reference environment to decode raw protobuf and verify the
element summaries, failure reproduction and fixed comparison. The Rust runtime
regression is `metric_string_deltas_match_frozen_reference`.
