# Rust server smoke capture

A browser observation of the Rust server's `button` example, captured with the
official Streamlit 1.66.1 frontend.  It covers the title, the rendering of the
button, three clicks, and the wire traffic of each click.

**This is not a journey pass.**  It proves only that the page renders, that the
button is reachable, that every click produced a true widget trigger answered
by a successful `script_finished` on the same connection, and that the
connection stays usable.  It says nothing about the data loop.

The journey artefacts for the Rust side live under `tests/e2e/<journey>/`; this
directory is a standalone observation, not a journey artefact.

Regenerate:

```
python tests/reference/capture_browser_trace.py --scenario smoke --clicks 3 \
    --url http://127.0.0.1:8501/ --out <temporary-path>
```

The current S1 session-counter capture lives next door in `../rust-counter-s1/`: it covers the
two-tab isolation, the same-session recovery and the reload reset against the
Rust session implementation.
