# Actual CSV data app J05 evidence

Original python raw and six PNGs, separate from the old standalone
forms fixture. Main J05 status awaits archive acceptance; this does not claim J00.

The raw bytes are unchanged. MANIFEST.path_map binds each original screenshot
path/case/phase/length/SHA one-to-one to its stored file. The explicit manifest
option checks raw identity and package file hashes before decoding, then resolves
only PNG.file in memory. No ignored target directory is required for this command:

    python tests/browser/forms_capture.py --verify tests/reference/reference-browser/csv-app-j05/trace-forms.json --artifact-manifest tests/reference/reference-browser/csv-app-j05/MANIFEST.json --j05-profile csv-data-app --cases form-j05-continuous

Use an installed Python environment with the pinned official1.66.1 protobuf
and PyArrow dependencies. Interpreter location is independent of evidence data.
The recorded fixture source bytes must match their retained snapshots.

PB and contract results are separate; total ok and process exit require both.
The CSV profile is explicit and J05-only with required PNGs. Without this profile,
the full-CSV capture retains its four original standalone rejections. Capture
completion in capture/capture-state.json is producer state, not acceptance.

The original three journey steps map from actual ordered phases: S1 PNG02 type,
S2 PNG03 submit, S3 PNG06 third Pulse. See journey_steps for exact filenames and
phase IDs. PNG01 is preparation; PNG04/05 preserve both intermediate Pulses.
No steps are added and no image is synthesized or renumbered.

Capture source34325 remains under capture/source/ with original filenames and
byte hashes. Python capture/source/forms_contract.loaded.py.snapshot is the forms_contract module file recorded by source-identity.loaded_contract_sha256 (032f). The separately named forms_contract.standalone-v3.py.snapshot is ee292; it accompanies the archived standalone replay. These names do not assert that the loaded032f file was that replay verifier.
The original replay/source/forms_capture.py.snapshot (a70) and
replay/source/forms_contract.py.snapshot (0b), with replay/result.json, record
the earlier successful CSV CLI run. portable-replay/ records the later explicit
location-mapping CLI separately; it does not relabel capture or erase failures.

Source identity, actual fixture bytes and optional native candidate/config JSON
are retained under capture/. Python app.py/refcore.py snapshots preserve exact
worktree bytes and Git769 correspondence. Native runtime_inputs enumerates all
130 historical candidate members and exact stored hashes; the actual dirty42e
app uses its capture snapshot. The recorded runtime identity04dd differs from
the candidate JSON file hash. Executable bytes are not bundled: the original
binary7297 fingerprint is retained, not presented as an offline binary rebuild.
No executable/debug cache or borrowed-tab URL logs are needed for byte checks.
