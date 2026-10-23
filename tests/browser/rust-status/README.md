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
