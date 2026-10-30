# Rust status element capture

Black-box capture of the Rust status example against the frozen emoji build,
using the official Streamlit 1.66.1 frontend.  `trace-status.json` holds every
decoded frame, the DOM measurement of every rendered alert and the comparison
against the Python 1.66.1 oracle.

**Server under test** `target/status-demo/status-emoji.exe` sha256
`20c03e25ec2a9a901043e3c72b855446803e81d8c2b233046e8a1333da794d9d`, source
`git 7215312 + owner status-emoji build`.

The Python oracle it is compared against is
`tests/reference/reference-browser/status/`: the four styles, the icon, width
and title variants, the leading-icon extraction, the invalid-parameter
semantics and the icon grammar (ZWJ sequence, skin tone, flag, two independent
emoji).  All 16 comparable alerts matched, `oracle_mismatches: []`:

- the four formats carry `widthConfig {"useStretch": true}`, and the fixed
  width alert carries `{"pixelWidth": 240}` and measures 240 px in the DOM
  while every other alert measures 704 px;
- `icon` is absent unless one is set, and `title` appears only for the
  titled alert;
- a leading emoji is moved to `icon` and removed from the body, a leading
  Material shortcode likewise, and `icon=""` keeps the emoji in the body;
- the composite icon cases pass the whole grapheme through: the ZWJ sequence,
  the skin-tone emoji and the flag are all carried verbatim, and the leading
  composite is moved to `icon` as a whole.

The script finished successfully (`script_finished` status 0,
`FINISHED_SUCCESSFULLY`) and no exception element was rendered, `failures: []`.

The stretched alerts are 704 px wide because the Rust example uses the default
centered page layout; the Python fixture used `layout="wide"`, which is why
its stretched alerts are 1094 px.  That is a page-layout difference, not a
difference in the element: the fixed width is 240 px in both.

Regenerate:

~~~powershell
python tests/reference/capture_browser_trace.py --scenario status --url http://127.0.0.1:8502/ --target rust --binary target/status-demo/status-emoji.exe --out <temporary-path>
~~~


## Alert normalization (2026-10-30)

The existing status example/fixture support ?case=normalization. The shared
text_misc_params_capture.py --scenario alert-normalization selects status_app.py
for Python and can compare --url http://127.0.0.1:8502 for Rust. Twelve inputs
across all four alert formats emit 48 alerts and two JSON reports (50 complete
Elements). Python status/normalization and Rust normalization match in full,
including inner Alert width and absent outer layout config.

normalization-before retains 34 Elements / 16 erroneously rejected valid icon
calls. normalization-attempt retains the first fix's four U+001C over-trims.
Final body/title clean_text and explicit icon strip are distinct from auto
extraction: Material swallows Python whitespace, emoji only space/underscore/
hyphen. The separately frozen icon-separators.json is a direct private Python
helper oracle with 16 cases, not public WS or browser proof. Seven coherent
wrong-wire guards check body/icon/title, explicit blank icon, separators, width
placement and returned-call report. Original captures remain untouched.

No new browser/UI, full emoji/material-catalog, invalid-argument ordering or
non-string claim is made. Public signatures/error types/hash policy are kept;
macro/Entry and other pending decisions are not implemented here.


## Real Chrome normalization UI (2026-10-30)

normalization/ui/trace.json and the matching Python directory retain four
Browser Use observations per runtime (initial/middle/bottom/restored) and
three JPEGs each. After collapsing only the two JSON report views, all 48
alerts match text/paragraphs, title/strong, emoji or Material icon/font, four
foreground/background colors, ARIA roles and 240/704px sizes. PageDown, End
and Home were real keyboard actions; bottom reaches max and Home restores 0.

Raw viewport heights, x/y and scroll offsets remain in the captures. Python
initial height 1305 becomes 1249, changing max from 2844 to 2900; Rust is 1249.
Comparisons use document-relative geometry, not identical viewport pixels.
Screenshots use supported tab CDP after owned-tab activation; there was no
capture timeout. Six JPEG hashes/decoded dimensions and nine wrong-observation
guards are checked. U+001C can render as a control/missing glyph on both sides,
matching the reference rather than claiming general character sanitization.

Warn/error buffers were empty in the measured window, tabs/services/listeners
were cleaned up, and original WS/helper/failed records remain unchanged. This
batch changes no production code and does not verify parameter updates, callback
behavior, invalid-icon combinations or arbitrary themes/viewports.


## Alert validation boundary (2026-10-30)

normalization/errors-before and normalization/errors retain all twenty inputs
across four formats: 80 receipts each, with 12 and 20 emitted Alerts respectively.
Python normalization/errors has 16 Alerts. Rejected calls emit no Alert and do
not consume a delta slot; caught errors are followed by valid recovery calls.
Icon-before-width, categorized error text and spinner acceptance now align for
68/80 complete calls, compared with 20/80 before. The remaining 12 differences
are cases 3/15 (unknown Material names) and 19 (quoted-width repr), four formats
each. Every case remains in the gate; this is explicitly partial compatibility.

Receipts classify the actual error by icon/width, not by a claimed equivalent
Python exception class or error_id. No new browser, uncaught-error, callback or
full icon-catalog proof is made. Catalog data/generation alternatives await the
user's choice in .codex/architecture.md; no production catalog is added.


## Width repr follow-up (2026-10-30)

normalization/width-repr-before and width-repr retain the original twenty inputs
plus eighteen width strings, all four formats: 152 calls, 173 Elements/20 Alerts
each; Python width-repr has 169 Elements/16 Alerts. Quoting, backslashes and
ASCII controls now match, as do Chinese/emoji/combining accents. In the original
twenty-input prefix, 72/80 calls align; for the complete expanded corpus,
112/152 align versus 84/152 before. The remaining 40 are Material cases 3/15
and Unicode printability cases 30..37, four formats each. These are recorded
failures, not accepted differences or filtered cases. Six coherent old-style
error mutations fail the gate. No new browser or full Unicode repr claim.

Rust Debug differs in combining-mark escaping and Unicode version; a production
Unicode table/exporter has not been added. Its three design options are in
.codex/architecture.md, independent of the pending Material catalog decision.
