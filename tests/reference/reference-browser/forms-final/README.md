# Forms/text reference: selected Python capture

Python Streamlit 1.66.1 official-frontend evidence only; this bundle does not
exercise Rust and does not establish complete public-API compatibility.

The active fixture is `tests/reference/forms_app.py`, 21696 bytes, SHA256
`d177df7d7ef72414faffce8984d1b88547f401beff560eb103ae0bd945eda352`.
`source/forms_app.py.snapshot` must contain exactly those bytes. The selected
trace must bind that same live path/hash. Producer and canonical-case source
snapshots accompany it; `MANIFEST.json` records their exact hashes.

`trace-forms.json` preserves raw base64 protobuf payloads, hashes, request IDs,
connection/run IDs, ordered action windows, before/after DOM, original PNG
hashes and separately sampled driver/Chrome phase and screenshot clocks.
`websocket-lifecycle-events.json` preserves the original observed lifecycle;
missing WSClosed remains missing. Quiet covers a finite observed same-connection
interval; navigation/detach only ends observation. Strict checks are owned by
`forms_contract.py` and derive phase coverage from authoritative global raw.

The canonical 25-case list and ordered phases come from that contract. This
covers measured form/text interactions, layout, callbacks and J05; expander is
reference-only where Rust lacks it. Unmeasured API/IME/bind/persistence/error
surfaces remain open. Rust J05 evidence is separate from this Python bundle.

Re-derive payloads with:

    python tests/browser/forms_capture.py --verify tests/reference/reference-browser/forms-final/trace-forms.json

`capture-state.json` commits last, binds the trace SHA, and records completed
cases and producer completion/failure. A partial checkpoint is never a positive
bundle. Producer completion is not a compatibility verdict; strict results are
recorded separately in `STRICT-RESULT.json`.
New capture runs must use a new directory and the pinned interpreter; never
rewrite an existing bundle's raw, DOM, PNG or hashes to satisfy a verifier.

Historical `../forms/` and `../forms-batch2/` are not this selected gate input.
The a70ff source/trace/PNG archive and superseded attempts remain unchanged under
ignored target with explicit provenance; no ignored file is a fresh gate input.
