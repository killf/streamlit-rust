# Widget reference capture (Python 1.66.1)

Real browser observations of the input widgets against the pinned Python 1.66.1
reference app, with the official frontend.  One directory per case; the raw
holds the full Element protobuf of the selectbox, the slider and the checkbox,
every client `WidgetState` the frontend sent, the `script_finished` results
and the DOM before and after the change.

The reference app is `tests/reference/widgets_app.py`, one page per case
(`?case=...`); it is development only and never shipped.

## How it was captured, and the tool limitation

The `agent-browser` CLI could not start its daemon in this environment -- every
command failed with a connection timeout (`os error 10060`), including a fresh
named session -- while the browser itself was healthy.  The capture therefore
drove **the same real Chrome** over the DevTools Protocol, reusing the recorder
and the protobuf decoders of `tests/reference/capture_browser_trace.py`:
`Page.navigate` to load the page, `Input.dispatchMouseEvent` for the clicks and
`Input.dispatchKeyEvent` for the keys.  No widget state was ever fabricated and
no framework state was touched; every value in these files came from the wire or
from the page.  The Chrome, its CDP port and the limitation are recorded inside
each raw under `capture`.

## What each case shows

| case | what it establishes |
|---|---|
| `defaults` | the three widgets with their default values, and the return values and their types as the page renders them |
| `options` | a non-zero `default` (the index), a slider `default` of `[50]`, a checkbox whose `default` is absent because False is the proto default, and one real change of the selectbox |
| `keys` | a key-bound widget: the id ends in the key, the Element carries `setValue` and `rawValue`, and the page shows the seeded `session_state` value |
| `on_change` | the callback order, from the log the page renders: `order: ['script', 'callback:selectbox', 'script']` |
| `disabled` | `disabled: true` on all three widgets.  The selectbox and the checkbox were really clicked -- no client frame, no rerun, the page unchanged; the slider was not clicked, it only carries the `disabled` parameter |
| `dup_key` | two widgets with the same key: the error the page shows, and that `script_finished` is still status 0 |
| `none_option` | `[None, "red"]` with index 0: `default: 0`, the option list carries the string `"None"`, the page shows `None` |
| `none_unset` | the same options with index None: **no `default` field at all**, the widget shows an empty value, the return value is still None |

The last two are the difference between "the None option is selected" and
"nothing is selected": the first sends `default: 0` and shows `None`, the
second omits `default` entirely and shows an empty value.  Both return Python
None.

Regenerate with the reference app:

~~~powershell
python -m streamlit run tests\reference\widgets_app.py --server.headless true --server.port 8603
~~~
