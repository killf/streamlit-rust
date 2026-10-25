# Lessons

The working ledger of process lessons. Distilled at every milestone close (a
roadmap maintenance rule); an entry that no longer changes how we work is
deleted. Product-level quality norms live in the
[roadmap](roadmap.md#cross-cutting-quality-acceptance), not here.

1. **Freeze, generate, review.** Freeze the reference bytes with a throwaway
   probe, generate contract constants programmatically from the frozen trace,
   then elevate the probe into the committed collector. Hand-transcribed
   constants and hand-written diff scripts transcribe errors; generators stay
   in ignored `target/checks` rounds.
2. **Format before capture.** Run `cargo fmt` on every file a chain pins
   *before* the capture. A post-capture reformat invalidates source pins and
   forces a recapture (hit during the elements chain, `f6087e5`).
3. **CMD scripting rules.** Multi-line `python -c` and heredocs silently
   misbehave — write script files under `target/checks`. Never name an
   analysis script after a stdlib module (an `inspect.py` once shadowed the
   interpreter and broke the protobuf decoder).
4. **Silent frame drops hide elements.** A probe must print every dropped
   frame loudly. A missing element in the census (st.table once) means the
   shared summariser crashed on a proto field — make field reads optional so
   one missing field cannot drop a whole frame.
5. **Differentials pay for themselves.** The temporal chain proved an exact
   encoding with zero defects; the elements chain caught three real parity
   bugs (badge stray space, missing `tickMinStep`, nominal-vs-ordinal x).
   No matrix row is promoted without the differential.
6. **Generated Python constants need boolean fixing.** `json.dumps` literals
   carry `true/false`; fix to `True/False` when emitting contract constants.
   Scalar widget states (`string_value`, `int_value`) expose `value` only —
   `value_full` exists just for array shapes.
7. **Adversarial review is cheap and finds real issues.** Give review agents
   tamper-test and pixel-diff mandates; act on every non-blocking flag (the
   st.container prose error) and record accepted boundaries honestly (the
   `capture_sources` custody note).
8. **Usability is acceptance-grade.** Under full parity the API must stay
   concise, stable and fast: value-first builders, `Into` conversions,
   measured defaults so the plain call renders the reference page, and a
   one-line shorthand documented next to every full-options form.
9. **Resolve widgets from registry values, not generic serde.** A generic
   `from_value::<Vec<T>>` inside a closure trips the higher-ranked lifetime
   check, and `DeserializeOwned` bounds exclude borrowed option types (`&str`)
   outright. Resolve on the internal representation (indices) and clone the
   caller's options instead — the selectbox pattern generalizes (hit during
   the inputs chain).
10. **Deterministic DOM lag is semantics, not a race.** A DOM echo that lags
    one stage behind on every capture is measured behavior (number_input and
    text_area commit on blur), not a capture-timing bug. Cross-check the
    state snapshot against the DOM pattern in the wire itself before adding
    wait-for-stability heuristics; keep the heuristic anyway as a guard for
    genuinely racy repaints.
11. **Guard tests must not alias the oracle tables.** Spreading contract
    constants into a synthetic observation shares dict references; a mutation
    then edits the oracle itself and the mutation test passes vacuously.
    Deep-copy in synthetic builders.
