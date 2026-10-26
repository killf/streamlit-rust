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

## Media route (image, audio, metric, progress)

[media_capture.py](media_capture.py) is the permanent entry for the W05
media-route chain; [media_contract.py](media_contract.py) is its strict
criterion (journey-media-v1, 11 checks) with unit tests in
[tests/reference/test_media_contract.py](../reference/test_media_contract.py).
The collector starts its own Chrome, records the decoded frames, the real
`GET /media/{file_id}.{ext}` round trips (status, content type,
accept-ranges, content-range, body digests and the served PNG bytes) and
the resolved DOM. The byte-identical WAV is judged under its exact measured
address; the PNG address and body length ride the per-side encoder, but the
served PNG bytes ride the trace and the contract decodes them with PIL,
pinning the measured gradient pixels. The published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\media_capture.py --replay tests\reference\reference-browser\media\trace-media.json
target\pyref-venv\Scripts\python.exe tests\browser\media_capture.py --replay tests\browser\rust-media\trace-media.json
```

Both return 11 expected / 11 executed / 11 asserted with exit 0. Raw SHA256:
python `a238dd74e97d77ab03b659f126a013717a525ac412788f1cb0fc44eb897af2dc`,
native `d20aa7c55170a62a7d621444ecde2a3fd5a9e5bb8411c1c8b2a2e6911a677d1b`,
under contract `e6a231832c3b0641f815f4862c7a9b59232b940653777a8ea5c6624f3604936e`.
The first review round caught a real defect the shape-only chain missed —
the stored-deflate encoder emitted a corrupt PNG that no browser decoded,
so st.image rendered blank while every check passed; the encoder now has a
decoder round-trip test, the contract pins the PIL-decoded pixels, and the
republished stage screenshots differ by 0.0000% (byte-identical renders).

## Video (st.video)

[video_capture.py](video_capture.py) is the permanent entry for the video
chain; [video_contract.py](video_contract.py) is its strict criterion
(journey-video-v1, 10 checks) with unit tests in
[tests/reference/test_video_contract.py](../reference/test_video_contract.py).
The page serves one committed one-second sample (a deterministic ffmpeg
testsrc2 encode) under the default `st.video` call; both runtimes embed the
same committed bytes, so the media address, the 206 Range response and the
served body digest are byte-identical across sides. The published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\video_capture.py --replay tests\reference\reference-browser\video\trace-video.json
target\pyref-venv\Scripts\python.exe tests\browser\video_capture.py --replay tests\browser\rust-video\trace-video.json
```

Both return 10 expected / 10 executed / 10 asserted with exit 0. Raw SHA256:
python `b27a3a2cf6c5c260a91a1d63700167e6615a0121f199c70dfe9530a322550602`,
native `76b6ca787e40143b5fa652f6e08c5e9fa3eac4c19d2c57fcd192f673d5110cc0`,
under contract `425a2ec0a7dd8004ed16d6866db283af371890a6aa8fd18aa5f6f00d5e6f0f47`
(the post-review criterion with the exactly-one-/media-request assertion).

## Presentation widgets (spinner, toast, balloons)

[presentation_capture.py](presentation_capture.py) is the permanent entry
for the presentation chain; [presentation_contract.py](presentation_contract.py)
is its strict criterion (journey-presentation-v1, 11 checks) with unit
tests in [tests/reference/test_presentation_contract.py](../reference/test_presentation_contract.py).
The page runs a spinner context that sleeps two seconds, one toast and
balloons; the contract pins the full delta timeline — the two
`new_transient` deltas at path [0, 0] (active spinner, then cleared,
consuming no element path), the toast as a one-shot element routed to the
dedicated root path [2, 0] with an explicit four-second duration, and the
one-shot balloons at the container's next slot [0, 1]. The published
chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\presentation_capture.py --replay tests\reference\reference-browser\presentation\trace-presentation.json
target\pyref-venv\Scripts\python.exe tests\browser\presentation_capture.py --replay tests\browser\rust-presentation\trace-presentation.json
```

Both return 11 expected / 11 executed / 11 asserted with exit 0. Raw
SHA256: python `30e882bb9460935e97c6fa67496f5834b87864000d716367c0219f1b211ef407`,
native `54843db1ba9b2ad163db7ae1a11111c32040c4c3d33f9768d517fb62cbfc011e`,
under contract `fe02d5e625da8fa0e372b7084fb0cca31b332419fe3a6e5254b154932b9938fd`
(the post-review criterion: the transient timeline carries the full element
list, an extra hidden transient element or an unknown delta kind fails the
timeline, and the spinner lifecycle reads the whole list).

## Charts (line, area, scatter, map)

[charts_capture.py](charts_capture.py) is the permanent entry for the charts
chain; [charts_contract.py](charts_contract.py) is its strict criterion
(journey-charts-v1, 12 checks) with unit tests in
[tests/reference/test_charts_contract.py](../reference/test_charts_contract.py).
The page renders one native line, area and scatter chart plus one `st.map`;
the contract pins each vega spec string (byte-equal modulo the dataset
name), requires each served dataset name to be the reference formula
`calc_hash(str(arrow_bytes))` over the bytes served in the same delta,
judges the dataset frames semantically (schema including the pandas
metadata, columns, rows), requires the deck.gl json to be byte-identical,
and pins the DOM projection. The published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\charts_capture.py --replay tests\reference\reference-browser\charts\trace-charts.json
target\pyref-venv\Scripts\python.exe tests\browser\charts_capture.py --replay tests\browser\rust-charts\trace-charts.json
```

Both return 12 expected / 12 executed / 12 asserted with exit 0. Raw
SHA256: python `eb054d26800aa245031cb38dd9a48aca3024d10f2953b3dc4860d443ea715feb`,
native `849e71b85209dfc37c45b4740176073b159ad608a957e1444f9da417fdf12d12`,
under contract `46bd806175c2090952a2bd1c3b27aee4fd38eb95ce9a2ee98eed3ca6180d9070`
(the post-review criterion: every chart must carry exactly one dataset —
a rogue appended dataset fails — and the map zoom ladder is the pinned
21-entry ladder from map.py, with the street-level tail and the empty-map
serialization frozen in the runtime regression). The two stage PNGs are
byte-identical (0 differing pixels).

## Layouts (sidebar, expander, tabs, popover, dialog)

[layouts_capture.py](layouts_capture.py) is the permanent entry for the
layouts chain; [layouts_contract.py](layouts_contract.py) is its strict
criterion (journey-layouts-v1, 9 checks) with unit tests in
[tests/reference/test_layouts_contract.py](../reference/test_layouts_contract.py).
The page renders a sidebar note, an expanded expander, two tabs, a popover
and a modal dialog; the contract pins the full 14-delta layout timeline —
the sidebar element at the fixed root [1] with no block of its own,
expander/popover children at `[slot, k]`, every tab block emitted before
any tab child, and the dialog's closed-then-reopened `add_block` pair at
the event root `[2, 0]` around the measured flex content container — with
the dialog's `$$ID` name judged by shape and pair-equality (its digest
legitimately mixes each runtime's own script identity). One leading
`main_container` add_block at [0] is the Rust runtime's documented
divergence and the only normalization the timeline applies; two or more
fail closed. The published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\layouts_capture.py --replay tests\reference\reference-browser\layouts\trace-layouts.json
target\pyref-venv\Scripts\python.exe tests\browser\layouts_capture.py --replay tests\browser\rust-layouts\trace-layouts.json
```

Both return 9 expected / 9 executed / 9 asserted with exit 0. Raw
SHA256: python `0d55720a77a829fd825a3f5277d81c288f6aa058d7d7842e29d0e132d17bc1d4`,
native `ad8543ac6012bca3a8e5a9a4ea6018c066c50a477fb942c450547cec1a96b9b3`,
under contract `9488516d0a8f34caf67c1684e612570d14ef6ef592f04bef0fb3cd94cfec8020`.
The runtime regression (streamlit/tests/runtime/layouts.rs) additionally
pins the timeline string, every block payload and the dialog id formula
over the production transport.

## Page config (st.set_page_config)

[pageconfig_capture.py](pageconfig_capture.py) is the permanent entry for
the page-config chain; [pageconfig_contract.py](pageconfig_contract.py) is
its strict criterion (journey-pageconfig-v1, 9 checks) with unit tests in
[tests/reference/test_pageconfig_contract.py](../reference/test_pageconfig_contract.py).
The page runs one full `st.set_page_config` call and a write; the contract
pins the single `page_config_changed` frame — it must stream between the
running status and the first delta, consume no element path, and carry the
measured title, material icon, WIDE layout, EXPANDED sidebar state and all
three menu entries — plus the settled DOM (document title, the
frontend-resolved material-symbols favicon, the streamlit-wide root class,
zero exceptions). One leading `main_container` add_block at [0] is the
Rust runtime's documented divergence; two or more fail closed. The
published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\pageconfig_capture.py --replay tests\reference\reference-browser\pageconfig\trace-pageconfig.json
target\pyref-venv\Scripts\python.exe tests\browser\pageconfig_capture.py --replay tests\browser\rust-pageconfig\trace-pageconfig.json
```

Both return 9 expected / 9 executed / 9 asserted with exit 0. Raw
SHA256: python `55faa132cde133fb985a369a95cc1404a6e0d6d0f7e3bf2ce62351fc8f058c73`,
native `cba8f3ce51e516dc4321988ee04b00cf3759a7d88e877a7aeccb7dfffdbe198a`,
under contract `864ef01304b698e788e0566ab1d7744d59e923994105556a4a143359ac8ad41c`.
The runtime regression (streamlit/tests/runtime/pageconfig.rs) additionally
pins the measured duplicate-call behavior — a second call streams a second
config (no exception) and the run continues — plus the LAYOUT_UNSET /
SIDEBAR_UNSET inherit markers.

## Query params (st.query_params, selectbox upgrades)

[queryparams_capture.py](queryparams_capture.py) is the permanent entry for
the query-params chain; [queryparams_contract.py](queryparams_contract.py)
is its strict criterion (journey-queryparams-v1, 11 checks) with unit tests
in [tests/reference/test_queryparams_contract.py](../reference/test_queryparams_contract.py).
The page writes one server-side param, renders a creation-mode filtered
selectbox and a query-bound selectbox; three real-interaction stages (load,
typed new option committed with Enter, bound pick through the dropdown)
pin exactly one merged alphabetically-sorted `page_info_changed` per run,
the browser-reported `ClientState.query_string` with every rerun, both
selectbox elements field-for-field (acceptNewOptions, filterMode,
queryParamKey), the creation string state and the DOM URL/markdown
projections. Widget ids are judged modulo the `$$ID` digest segment; one
leading `main_container` add_block at [0] is the Rust runtime's documented
divergence. The published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\queryparams_capture.py --replay tests\reference\reference-browser\queryparams\trace-queryparams.json
target\pyref-venv\Scripts\python.exe tests\browser\queryparams_capture.py --replay tests\browser\rust-queryparams\trace-queryparams.json
```

Both return 11 expected / 11 executed / 11 asserted with exit 0. Raw
SHA256: python `a7af243d6f6dfed18941dd31e63da91ecd6e4f0a9c113fb822eb1473701b8a90`,
native `09dfc2d91c95d65d51f1a0644a09c2cc4d6d91b81d35d7bfd6964cb6b1c1aec3`,
under contract `4f9e83f9c9b3f2fba7730b0f019591857a770124f8f3ce41b93818258a5210eb`.
The runtime regression (streamlit/tests/runtime/queryparams.rs) pins both
measured runs over the production websocket.

## Caching (st.cache_data, st.cache_resource)

[cache_capture.py](cache_capture.py) is the permanent entry for the cache
chain; [cache_contract.py](cache_contract.py) is its strict criterion
(journey-cache-v1, 12 checks) with unit tests in
[tests/reference/test_cache_contract.py](../reference/test_cache_contract.py).
The page memoizes an i64 function under two distinct arguments, a
side-effecting function writing a markdown inside, an Again button and a
runs==2 clear branch; two real-interaction stages (cold load, button click)
pin the empty cleared-spinner transient every miss streams at the call
site's entry path (before the outside write for an element-free function,
after its element for a side-effecting one), the hit replay of the
function-internal element with no transient and the slot it consumes (the
following write lands after it), the stable values across the rerun, the
post-clear remiss and the DOM projections. The Python reference must be a
fresh process for stage 01 (its cache store lives in the server process and
is shared across browser sessions); the Rust store is session state. Widget
ids are judged modulo the `$$ID` digest segment; one leading
`main_container` add_block at [0] is the Rust runtime's documented
divergence. The published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\cache_capture.py --replay tests\reference\reference-browser\cache\trace-cache.json
target\pyref-venv\Scripts\python.exe tests\browser\cache_capture.py --replay tests\browser\rust-cache\trace-cache.json
```

Both return 12 expected / 12 executed / 12 asserted with exit 0. Raw
SHA256: python `1c01c8045d141b9210b31b13ec66f6950c202293d7e4b9e28aed5e4bc51fa400`,
native `eee3ccc1c62bb2be9b049d5f779f3f03a65fed49f858079ac4cc1a3ae09f9fcd`,
under contract `8d60e0034e52fde5c512af2101777745a7ecc39911b812f0e017a4500815b94f`.
The runtime regression (streamlit/tests/runtime/cache.rs) pins both measured
runs over the production websocket plus the argument-sensitive keying, the
shared resource identity and the clear.

## Multipage navigation (st.navigation, st.Page, st.switch_page)

[navigation_capture.py](navigation_capture.py) is the permanent entry for
the navigation chain; [navigation_contract.py](navigation_contract.py) is
its strict criterion (journey-navigation-v1, 12 checks) with unit tests in
[tests/reference/test_navigation_contract.py](../reference/test_navigation_contract.py).
The page registers two function pages (a default one with session state, a
switch button and a material icon, plus one with a custom url_path); four
real-interaction stages (load, sidebar pick, pick back, switch through the
button trigger) pin the per-run navigation message (pages with their
BLAKE2b/16 url-path hashes, icon strings, the default marker, urlPathname,
SIDEBAR position, unnamed sections, the current page), the page-hash
addressing riding the rerun report and NewSession, session state across the
page round trip, the switch_page empty page_info plus
FINISHED_EARLY_FOR_RERUN and the server-only next run on the target page,
and the DOM URL/nav/markdown projections. Widget ids are judged modulo the
`$$ID` digest segment; the initial NewSession page hash is each runtime's
own main script hash, and one leading `main_container` add_block per run is
the Rust runtime's documented divergence. The published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\navigation_capture.py --replay tests\reference\reference-browser\navigation\trace-navigation.json
target\pyref-venv\Scripts\python.exe tests\browser\navigation_capture.py --replay tests\browser\rust-navigation\trace-navigation.json
```

Both return 12 expected / 12 executed / 12 asserted with exit 0. Raw
SHA256: python `52d778f9d5d437dba3850acec7397a53be2e350df1c4688b2b9c85f091e8e7cb`,
native `b857ece721f5bc91fe45cf0907e291085922210fad414fd589c08beec5d72abf`,
under contract `89922dba98f5ff9a61fc8b9590cd00d216a6428da1d17846c15c4befd7d6ed17`.
The runtime regression (streamlit/tests/runtime/navigation.rs) pins the
page hashes, nav fields, addressing, the hits round trip and the switch
two-run timeline over the production websocket.

## Text elements (st.text, st.subheader, st.latex, st.html, st.iframe, st.snow, st.echo, st.exception)

[textelements_capture.py](textelements_capture.py) is the permanent entry
for the text-elements chain; [textelements_contract.py](textelements_contract.py)
is its strict criterion (journey-textelements-v1, 12 checks) with unit
tests in [tests/reference/test_textelements_contract.py](../reference/test_textelements_contract.py).
One measured load pins every element's full wire shape: the wrapped
content-width text, the wrapped h3 subheader, latex as one markdown
element in `$$` display math, the stretch-width html embed, the scrolling
iframe with its 400 px default height, the one-shot snow, the echo
placeholder/retro-fill pair (the code replaces the placeholder's own
path), and the application exception box (type, message, trace judged by
line count). One leading `main_container` add_block at [0] is the Rust
runtime's documented divergence. The published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\textelements_capture.py --replay tests\reference\reference-browser\textelements\trace-textelements.json
target\pyref-venv\Scripts\python.exe tests\browser\textelements_capture.py --replay tests\browser\rust-textelements\trace-textelements.json
```

Both return 12 expected / 12 executed / 12 asserted with exit 0. Raw
SHA256: python `b6128c6cefaf110424cf8a8dd98259d345996f5fc3a5b6e15b7f308bb5bf001e`,
native `c534ac116d9e6492fb3f816f532ea1882601f2fd78267a2bb4095e9f60ec44f5`,
under contract `876d1128e0a9baba1c0c02df21fb6e2ea104b54068c205a0002cb3b2ed4a5530`.
The runtime regression (streamlit/tests/runtime/textelements.rs) pins the
ten-element timeline over the production websocket.

## Display containers (st.json, st.status, st.empty, st.space, st.bottom)

[display_capture.py](display_capture.py) is the permanent entry for the
display chain; [display_contract.py](display_contract.py) is its strict
criterion (journey-display-v1, 12 checks) with unit tests in
[tests/reference/test_display_contract.py](../reference/test_display_contract.py).
One measured load pins the json element (the json.dumps rendering, stretch
width), the status container's RUNNING block and its updated COMPLETE
re-stream at the same path (the state pairs the icon), the empty slot and
its same-path replacement (the reference's queue composes the placeholder
into the replacement within one flush batch — both the streamed and the
coalesced shape are accepted), the square spacer (both configs at the
pixel value) and the bottom root's [3, 0] child. One leading
`main_container` add_block at [0] is the Rust runtime's documented
divergence. The published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\display_capture.py --replay tests\reference\reference-browser\display\trace-display.json
target\pyref-venv\Scripts\python.exe tests\browser\display_capture.py --replay tests\browser\rust-display\trace-display.json
```

Both return 12 expected / 12 executed / 12 asserted with exit 0. Raw
SHA256: python `95e139d4a87816e73ced52fe461b7c57fefa4e76aad9cbd4ce735d007c4984e1`,
native `bb6ee7d0b308e6c7ab3c3aa02736636ffd9febd95d9318318603ee1f2c715052`,
under contract `9f6cbedf7030ef4a82b8e3d369b030f96408c81983eefc80e44929084fe387f0`.
The runtime regression (streamlit/tests/runtime/display.rs) pins the
full timeline over the production websocket.

## Chat elements (st.chat_message, st.chat_input)

[chat_capture.py](chat_capture.py) is the permanent entry for the chat
chain; [chat_contract.py](chat_contract.py) is its strict criterion
(journey-chat-v1, 11 checks) with unit tests in
[tests/reference/test_chat_contract.py](../reference/test_chat_contract.py).
The page renders two chat messages (the name-defaulted avatar and a
material shortcode, both ICON type) and the chat input; two real-interaction
stages (load, Enter commit of "hi" through the real input) pin the
chat_message blocks with their children paths, the chat_input widget
(placeholder, the 200 MB cap, the 16000 Hz sample rate, the auto-position
marker, the bottom-root [3, 0] routing) and the chat_input_value commit
report. Widget ids are judged modulo the `$$ID` digest segment; one leading
`main_container` add_block at [0] is the Rust runtime's documented
divergence. The published chains:

```powershell
target\pyref-venv\Scripts\python.exe tests\browser\chat_capture.py --replay tests\reference\reference-browser\chat\trace-chat.json
target\pyref-venv\Scripts\python.exe tests\browser\chat_capture.py --replay tests\browser\rust-chat\trace-chat.json
```

Both return 11 expected / 11 executed / 11 asserted with exit 0. Raw
SHA256: python `63c62667f2c5e5cf0884d7cc413720fd305de6f8e31f31574cfecb20787fe2a1`,
native `07f3f274576d85f75090ec3484764f88f1128b0e55902e59879d14d3669bcffd`,
under contract `4cfdf313ea8a0ee6b385abfc492abd10a7fa9a1ef6af733b4649aac82c87865b`.
The runtime regression (streamlit/tests/runtime/chat.rs) pins both measured
runs over the production websocket.
