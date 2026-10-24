# Rust forms: J05 official-frontend evidence

Original 70-frame / six-PNG capture of the frozen Rust candidate on loopback
8504. Same page: editing hello sends no frame and leaves runs=1/applied empty;
Apply once gives runs=2/applied hello; three outside Pulse clicks give runs=5,
pulses=3, with hello retained. This example exposes only J05.

`trace-forms.json` is the original 9160ce04... raw byte sequence. Its historical
screenshot/provenance paths remain unchanged. `MANIFEST.json.path_map` maps each
original PNG path one-to-one onto its exact stored bytes. Provenance JSON and
producer/example snapshots live under `source/`; no binary or debug tree is copied.

A gate must first verify original trace SHA and all mapping byte hashes, then
may resolve only file paths in an in-memory copy for the author's strict verifier.
Never rewrite raw PB, DOM, clocks or recorded hashes. `reference_runtime` is the
Python official-PB decoder environment, not the Rust process runtime. Binary,
runtime-source-set and configuration fingerprints are the captured provenance.

The independently reviewed v3 contract returns no failures for the original J05
raw. This is finite observed same-connection evidence, not all 25 public cases
or complete application compatibility. Python reference captures are separate.
