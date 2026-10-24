# Rust data journeys

## J06: continuous two-tab isolation

[Original native raw](j06-sequence/trace-data-loop.json), SHA256
`ca291a274305455a41c34495d50ec59e3a47e5de2c21fc41f11fe9e940acc6f1`,
retains 199 frames (A132/B67), all 18 PNGs, two deduplicated IPCs and both
loaded source files. The
[Python counterpart](../../reference/reference-browser/journeys/j06-sequence/trace-data-loop.json)
retains 208 frames and the same nine-phase contract. Both captures completed
with 18/18/18 checks, no failures, exit 0, before independent Hooke review.
No raw events, counts or source identities were rewritten during publication.

Historical capture invocation is recorded separately in each original
execution manifest:
[native](j06-sequence/execution-manifest.json) and
[Python](../../reference/reference-browser/journeys/j06-sequence/execution-manifest.json).
Use its `executable`, the entry `tests/browser/numeric_capture.py`, then its
exact `argv` to identify the command that ran. Those commands drove real
Chrome over CDP60667 and wrote unique ignored target directories. They are
not the replay commands below; do not rerun into historical output paths.

These formal-path commands were actually executed after copying the archive,
each returning 18/18/18, no failures, exit 0:

```powershell
target/pyref-venv/Scripts/python.exe tests/browser/numeric_capture.py --replay tests/browser/rust-journeys/j06-sequence/trace-data-loop.json
target/pyref-venv/Scripts/python.exe tests/browser/numeric_capture.py --replay tests/reference/reference-browser/journeys/j06-sequence/trace-data-loop.json
```

Replay reads adjacent IPC/PNG files, uses the repository criterion and needs
no browser/server or old ignored capture/build directories. It ignores cached
verdicts and never writes the raw. The exact producer SHA256 is
`6b0caa4d1be607720e226361adc5a8ff4f6e3b1a171a23ded7eb991188f0f42f`;
criteria SHA256 is
`b6fea182d5bd5e6552c7f4a05f4917c46ba91b86600a5634a72c58c8964e57f1`.
Both capture and formal replay used those identities; each raw keeps the
original loaded bytes in `capture-source/`.

The [verification/step fragment](j06-sequence/verification.json) is for the
integration owner's global manifest merge, not a change to the original
five steps or 10/42 denominator. Every row below references two separate
tab observations within one recorded phase, never a composite or a claim
that both tabs were photographed simultaneously.

| Original step | Phase | A image | B image | Canonical E2E primary |
|---|---|---|---|---|
| S1 | initial | [A](j06-sequence/01-initial-a.png) | [B](j06-sequence/01-initial-b.png) | [A](../../e2e/J06/J06-S1.png) |
| S2 | a-pulse-3 | [A](j06-sequence/05-a-pulse-3-a.png) | [B](j06-sequence/05-a-pulse-3-b.png) | [A](../../e2e/J06/J06-S2.png) |
| S3 | b-untouched | [A](j06-sequence/06-b-untouched-a.png) | [B](j06-sequence/06-b-untouched-b.png) | [B](../../e2e/J06/J06-S3.png) |
| S4 | b-group-region | [A](j06-sequence/08-b-group-region-a.png) | [B](j06-sequence/08-b-group-region-b.png) | [B](../../e2e/J06/J06-S4.png) |
| S5 | a-refresh | [A](j06-sequence/09-a-refresh-a.png) | [B](j06-sequence/09-a-refresh-b.png) | [A](../../e2e/J06/J06-S5.png) |

Canonical images are unchanged copies of the indicated primary; the peer
image is explicitly linked in the fragment. PNG02 (A upload) and PNG07
(B upload) are preparation. PNG03/04 (first/second Pulse) are intermediate.
All eight extra images remain beside the ten business-role images.

A's runs/pulses are 1/0, 2/0, 3/1, 4/2, 5/3, retained through B's actions;
refresh gives a new A session and defaults/empty file at 1/0. B remains
1/0 and empty through all three A pulses, then explicitly uploads at 2/0
and selects region at 3/0; B retains that file/region/session after A refresh.
Each side retains its own raw frame stream and HTTP ownership. Original
17 targets are conserved; the capture-owned targets were closed.

Capture HEAD is `82542723ec2231a5d06ac227639d380adb6f9195`. The native binary
remains the original 729743 candidate built from Git76938fb plus dirty42e,
not a build of HEAD825. Reuse the single
[shared candidate](j00-sequence/candidate/candidate.json), configuration and
archived example under [Shared 7297 candidate inputs](#shared-7297-candidate-inputs).
The recipe there was rerun after publication: all 130 input hashes and the
04dd runtime set match (110 direct Git blobs, 19 captured CRLF, one archived
42e override). No binary or duplicate 130-file source package is added.

## J00 and J02: integrated formal example

The unchanged native captures are
[J00](j00-sequence/trace-data-loop.json) (177 frames, eight PNGs, four IPCs;
SHA256 `69a22226500506d2d022c6991f6b40b59aacbdf9520ca23aca213dfe65019aeb`)
and [J02](j02-sequence/trace-data-loop.json) (133 frames, six PNGs, five IPCs;
SHA256 `3ea8e4749859c115a0f0b9bf178df01144cc832fdbeb374ad48c8ea38231f9f4`).
The [J00 verification/step fragment](j00-sequence/verification.json) and
[J02 verification/step fragment](j02-sequence/verification.json) are inputs
for the integration owner's manifest merge, not replacements for the original
six/five business expectations.

Capture and verification are distinct. Both J00 raws retain the actual 84
stub result **1/1/0, capture exit 1**. J02 Python retains the e0db stub result
**1/1/0, capture exit 1**; J02 Rust retains its c14 strict **15/15/15, capture
exit 0**. Exact loaded source bytes and `SHA256SUMS` are preserved in each
raw's adjacent `capture-source/` directory: J00 used 84/08/0b, J02 Python
e0db/3b and J02 Rust c14/3b. No raw verdict or historical metadata was rewritten.

After Hooke's independent candidate review, the repository CLI below was
actually run on all four archived raws: final replay is **19/19/19 for J00**
and **15/15/15 for J02**, no failures, exit 0, under criteria SHA256
`1990f920dbc0eebe28ce40de46bf8a8b3b71c0610a735706bc388ad77861fa9d`.
The read-only replay producer SHA256 is
`df2734eef3db2d6ab1973f04586ad82ca887ca702ef01c4ed7bcd7a11443f2c8`;
this is not asserted as the historical capture producer identity.

```powershell
target\pyref-venv\Scripts\python.exe tests/browser/numeric_capture.py --replay tests/browser/rust-journeys/j00-sequence/trace-data-loop.json
target\pyref-venv\Scripts\python.exe tests/browser/numeric_capture.py --replay tests/browser/rust-journeys/j02-sequence/trace-data-loop.json
```

These commands need the pinned development dependencies but no browser or
server. They resolve IPC/PNG beside the raw in memory, ignore cached verdicts,
re-run the shared predicate and return nonzero on missing/invalid evidence or
predicate exceptions. They do not write the raw or depend on an ignored audit
script. The original capture used `python.exe -` with a source-byte bootstrap;
its body was not archived. Retained source files and recorded entry parameters
are evidence of that capture, not a claim that today's replay command was
the original browser invocation.

J00 S1-S6 map to PNG01/02/03/05/08/08; prep PNG04/06/07 stays in the raw
directory. J02 S1-S5 map to PNG03/04/05/06/06; prep PNG01/02 stays there.
The shared final image is copied unchanged to both required step paths under
`tests/e2e/J00/` or `tests/e2e/J02/`: it is one observation with two roles,
not an extra action or run. All three J00 prep runs are in its 1-through-8
ledger; J02's ledger is 1-through-6. J00 verifies initial Note/Apply form
membership with real DOM plus retained protobuf and the canonical forms
helper; Note, Submit and Pulse are never operated in this journey.

### Shared 7297 candidate inputs

Both captures used the actual formal example at loopback8501. One unchanged
[candidate manifest](j00-sequence/candidate/candidate.json),
[launch configuration](j00-sequence/candidate/launch-config.json) and
[actual dirty example source](j00-sequence/candidate/source-snapshot/repo/streamlit/examples/data_app.rs)
are retained for both journeys. This is Git base
`76938fb643149424e69af0ddbccc3127be751178` plus the recorded 42e54 example,
not clean HEAD and not a generated launcher. The original metadata binds
binary `7297430d...`, runtime set `04dd33aa...` and configuration `5ab7564d...`;
the full hashes and exact source membership remain in that single manifest.

Its 130 source inputs can be reconstructed without the old ignored target:
110 Git blobs match directly, 19 differ only by captured CRLF convention,
and the one actual example override is archived above. This exact recipe was
run and all 130 member hashes matched:

```python
import hashlib, json, subprocess
from pathlib import Path
archive = Path("tests/browser/rust-journeys/j00-sequence/candidate")
meta = json.loads((archive / "candidate.json").read_bytes())
members = meta["runtime_members"]
digest = lambda b: hashlib.sha256(b).hexdigest()
assert digest(json.dumps(members, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()) == meta["runtime_set_sha256"]
root = Path("target/j00-j02-source-replay").resolve()
assert root.is_relative_to(Path.cwd().resolve()) and not root.exists()
root.mkdir()
for name, expected in members.items():
    captured = archive / "source-snapshot" / name
    if captured.is_file():
        data = captured.read_bytes()
    else:
        assert name.startswith("repo/")
        data = subprocess.check_output(["git", "show", meta["git_base"] + ":" + name[5:]])
        if digest(data) != expected:
            data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    assert digest(data) == expected, name
    dest = (root / name).resolve()
    assert dest.is_relative_to(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
config = (archive / "launch-config.json").read_bytes()
assert digest(config) == meta["config_sha256"]
(root / "launch-config.json").write_bytes(config)
print(len(members), "source inputs verified")
```

The archived build/config paths describe the real run. Relocate only working
copies when rebuilding; retain the same compiler, locked dependencies and
official `www` from the base commit. Source reconstruction does not claim a
byte-identical executable across changed toolchains or paths.

## J03: table and chart synchronization

[j03-sequence/trace-data-loop.json](j03-sequence/trace-data-loop.json) is the
unchanged 109-frame Rust capture at `http://127.0.0.1:8505/`, with four adjacent
IPC files and six original PNGs. SHA256:
`1123e211376fa3c8f7eb307329036aed0facdb2b81172da822dd913c1dcd86e0`.
The corresponding [Python oracle](../../reference/reference-browser/journeys/j03-sequence/trace-data-loop.json)
has 139 frames. Both raws retain **NOT VERIFIED, 1/1/0, capture exit 1**.
The observed capture-time stub hash was `842b908d9f7f9c7d7aa99e31ae775a6cdd4a3f88d0c2cbe8ac643c5d8241d95b`;
its source snapshot was not retained and has not been reconstructed or
backfilled. Hooke independently reviewed the two chains and all twelve PNGs.
Final replay of the original bytes gives **15/15/15, no failures** under
criteria SHA256
`dd2b80b217ffd2cf97008333010b3c66f8ffd45654c17e75a2c47b66d81e3a58`.
The capture producer was frozen at SHA256
`8a96699820d6f6307d3ec2230f8fcfd25d7053ab760952e015145256acc4183c`.

The shared `journey-j03-sync-v1` contract preserves four business steps:
S1/S2/S3/S4 map to PNGs **02/03/05/06**, copied byte-for-byte to
`tests/e2e/J03/J03-S1.png` through `J03-S4.png`. PNG01 is initial state; PNG04
is the explicit reset to minimum zero before selecting region. The three
slider operations each use one visible pointer gesture, with native value
and ARIA readings in `action.pointer`; runs read 1/2/3/4/5/6. Include-unknown
stays observed true, pulses stay zero. The final table has zero rows and no
chart or stale bars. Only the empty `group_key` type differs: Python double,
Rust large_string; the other field types and all nonempty rows agree.

### J03 candidate inputs

The actual dev-only loopback candidate is documented by the original
[candidate.json](j03-sequence/candidate/candidate.json), including the AAE6
binary, runtime-set/config hashes, all 134 member hashes, compiler and build
command. The original [launcher source](j03-sequence/candidate/launcher/main.rs),
[Cargo manifest](j03-sequence/candidate/launcher/Cargo.toml),
[lock](j03-sequence/candidate/launcher/Cargo.lock),
[configuration](j03-sequence/candidate/launch-config.json) and
[entry patch](j03-sequence/candidate/entry.patch) are archived unchanged.
The compiled launcher hash `6ef44038...` is distinct from the original d94
business source. The patch expands the entry point and binds loopback8505;
this generated launcher is evidence input, not a production source change.

The 128 `repo/*` inputs are recoverable from commit
`f2a3a787f27fa52d1b5734c2e616bca9686782c9`. Of those, 117 match Git bytes
directly and eleven differ only by the captured CRLF checkout convention.
The following reconstructs **all 134 original input bytes** in a new ignored
directory, using the existing manifest and rejecting every hash mismatch:

```python
import hashlib, json, subprocess
from pathlib import Path
archive = Path("tests/browser/rust-journeys/j03-sequence/candidate")
meta = json.loads((archive / "candidate.json").read_bytes())
members = meta["runtime_members"]
digest = lambda b: hashlib.sha256(b).hexdigest()
assert digest(json.dumps(members, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()) == meta["runtime_set_sha256"]
root = Path("target/j03-source-replay").resolve()
assert root.is_relative_to(Path.cwd().resolve())
assert not root.exists()
root.mkdir()
ordered = sorted(members, key=lambda name: not name.startswith("repo/"))
for name in ordered:
    if name.startswith("repo/"):
        data = subprocess.check_output(["git", "show", meta["git_commit"] + ":" + name[5:]])
        if digest(data) != members[name]:
            data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    elif name == "business-source.rs":
        data = (root / "repo/streamlit/examples/data_app.rs").read_bytes()
    else:
        data = (archive / name).read_bytes()
    assert digest(data) == members[name], name
    dest = (root / name).resolve()
    assert dest.is_relative_to(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
print(len(members), "source inputs verified")
```

The archived build/config files retain their original absolute paths as
historical inputs. To build in another location, relocate **only working
copies**: point the reconstructed launcher's `streamlit` dependency to
`../repo/streamlit`, use the recorded compiler and lock, and set
`STREAMLIT_STATIC_DIR` to the official `www` from the same f2a commit. Use the
candidate's loopback address/port. This reproduces source inputs and behavior;
it does not claim a byte-identical executable across toolchain/path changes.
Do not modify the archived files or use a later HEAD as the captured core.

For portable evidence replay, use the J01 in-memory `ipc_dir` example below
with this raw and `j03_checks` instead of `j01_checks`; the raw stays unchanged.

## J01: continuous input and aggregation

[j01-sequence/trace-data-loop.json](j01-sequence/trace-data-loop.json) is the
unchanged 165-frame capture from `target/j01-rust-preserved-20261025T002726`,
with its four adjacent IPC files and seven PNGs. SHA256:
`ec3f21129a47da4c09fbff278605907eb1d26527d034d5c001d5833d6de5e71d`.
Its binary/source identity is the historical 943/810f build recorded in the
raw, build base `ef359b1`, capture HEAD `1f2a852`; this is not a claim about
later source changes.

The raw retains its capture-time 15/15/15 result and exit 0. Its capture-time
criteria SHA was not recorded. Hooke independently reviewed the complete
Python/Rust chains and their PNGs; final replay of both unchanged raws gives
15 expected / 15 executed / 15 asserted, no failures, under criteria SHA256
`5e8cc8ee305dde3615dffea3b09f05ed1d3ea88e1f6a41c06fd9b2e68d7714c3`.
This is a **final replay identity**, not metadata backfilled into the raw.
The subsequently reviewed producer is `tests/browser/numeric_capture.py`, SHA256
`85071c856c0d0af709b71c26cd4885f9b7277c373ad6a590d017e0d3d092b1f6`;
that hash is not asserted as the capture-time driver identity.

The shared `journey-j01-input-v1` contract keeps five original business steps:
S1/S2/S3/S4/S5 map to PNGs 02/03/04/06/07, copied byte-for-byte to
`tests/e2e/J01/J01-S1.png` through `J01-S5.png`. PNGs 01 and 05 retain initial
and explicit category/0/on preparation evidence. Phase roles and all PNG hashes
remain in the raw. No reload or reconnect joins the phases; runs are
1/2/3/4/5/7/9 and pulses stay 0. Unicode and BOM have equal logical results
and IPC, with distinct issued file IDs, target runs and new result frames.

Replay the archived bytes with the pinned interpreter, resolving adjacent
IPC/PNG files in memory; never rewrite the historical `ipc_dir` in the raw:

```python
import json
from pathlib import Path
from capture_browser_trace import j01_checks, journey_result
raw = Path("tests/browser/rust-journeys/j01-sequence/trace-data-loop.json")
observation = json.loads(raw.read_bytes())["observation"]
observation["ipc_dir"] = str(raw.parent.resolve())
result = journey_result(j01_checks(observation=observation))
print(result)
assert result["ok"] and result["counts"]["asserted"] == 15
```

Run with `target/pyref-venv/Scripts/python.exe` and
`PYTHONPATH=tests/reference`; use the corresponding reference raw path to replay
Python. The docs cache label is 1.66.0; the measured Python runtime is 1.66.1.

The data app of the Rust implementation, driven with the official Streamlit
1.66.1 frontend: the closed loop and the three journeys of the data app.

**Server under test**

- binary `target/checks/data-app-live/data-app-csv-stage2-20261024T172854620.exe`
- sha256 `9430149DE61EA521AE873D2AE77A97A62D9BE5F63F547F00E9D5F7A1D23F4A57`
- source sha256 `810f4c1ecffa419a5f9217c311d4e863faef71e6e3779eb69fba2c6516d0f2f7`
- config sha256 `a552d879a67c536617e42933128e85329f30aafadd83cb34fd763f55ba2f26fc`
- the four raws of this round were captured against this binary; the four rows
  above carry the earlier one (`427F3AF7...`)
- `HEAD 1c6161d` plus the owner's uncommitted increment

**The captures**

| raw | journey | expected | executed | asserted | failures | exit |
|---|---|---|---|---|---|---|
| [data-loop/](data-loop/trace-data-loop.json) | upload, group by region, unknown off, minimum 100 | 3 | 3 | 3 | none | 0 |
| [recover/](recover/trace-data-loop.json) | a file that cannot be read, then a good one | 12 | 12 | 12 | none | 0 |
| [empty/](empty/trace-data-loop.json) | a file without data rows | 7 | 7 | 7 | none | 0 |
| [sessions/](sessions/trace-data-loop.json) | two tabs, two sessions | 11 | 11 | 11 | none | 0 |
| [state/](state/trace-data-loop.json) | first load, one control, one upload, the Pulse click | 14 | 14 | 14 | none | 0 |
| [soft-invalid/](soft-invalid/trace-data-loop.json) | the file with two unusable amounts, then the good file | 13 | 13 | 2 | the criterion of the case is not written | 1 |
| [non-utf8/](non-utf8/trace-data-loop.json) | the file that is not UTF-8, then the good file | 13 | 13 | 3 | the criterion of the case is not written | 1 |
| [filter-empty/](filter-empty/trace-data-loop.json) | the slider that empties the table, and back | 13 | 13 | 3 | the criterion of the case is not written | 1 |
| [j07-sequence/](j07-sequence/trace-data-loop.json) | the whole parse journey in one session | 13 | 13 | 13 | none | 0 |
| [j08-sequence/](j08-sequence/trace-data-loop.json) | the whole empty journey in one session | 14 | 14 | 14 | none | 0 |

The counts are the checks of the journey, not the steps of the manifest: every
check says what it expected, what it saw and whether it held, and the shared
criterion requires the whole fixed set of them.

**What the pages showed**

- the upload: the client asks for the upload URLs, the server answers with the
  file id and the upload and delete URLs, the browser puts the file there with
  a `PUT` that answered **204**.
- the recovery: the malformed CSV answered the error
  `Could not parse the uploaded CSV: CSV error: record 2 (line: 3, byte: 119):
  found record with 7 fields, but the previous record has 8 fields` together
  with `Upload a valid CSV to continue.`, no table and no chart.  Replacing
  the file with `sales_basic.csv` answered a **DELETE 204** for the file the
  server had signed out, left only the new file on the page and restored the
  table and the chart.
- the empty file: `The uploaded CSV contains no data rows.`, the four columns
  of the file with no body row and no bar.
- the two tabs: different session ids, their own file, their own group
  (`region` against `category`) and their own result.

**Where the evidence came from**

The capture ran once, in `target\final-427F-20261024T162828`, under the criteria
`B29B4F85AC9BEBE885C4B3EEE8E2142D8A44DC4724C6A9F1075BB09062DA08F6`, and the files here are those bytes.
The same raws were re-validated against the newer criterion `DA2E746A8267E1DFAC65CF0CB5513B3C6B729B33C5035C3CF5C253F016925D9A`,
which binds the result to the run that carries the target state, by the script
run id the server names in NewSession: the same counts and the same verdicts
(191 related tests).  A capture under the newer criterion stands in
`target\final-427F-20261024T164330`.
The raw keeps the capture-time `ipc_dir` of that directory; the IPC payloads
are the `arrow-N.bin` files **beside each raw** (one per digest, 1224 bytes
each -- the Rust IPC does not carry the pandas metadata block of the
reference), so a replay resolves them next to the raw instead of in the
ignored `target/` tree.

**Regenerate** (the paths are absolute: Chrome resolves a relative path
against its own working directory and the uploader would get no file):

~~~powershell
$fx = (Resolve-Path tests\fixtures\csv).Path
$bin = "target/checks/data-app-live/data-app-security-final-20261024T152745018.exe sha256 427F3AF719559C14B8A207660B9BA562D42C6F2C9A6B16E7C3864DED9B1D3A19"
$binNew = "target/checks/data-app-live/data-app-csv-stage2-20261024T172854620.exe sha256 9430149DE61EA521AE873D2AE77A97A62D9BE5F63F547F00E9D5F7A1D23F4A57"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --files "$fx\sales_basic.csv" --label rust-final-positive \
    --out target\rust-positive --binary $bin --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey recover --files "$fx\sales_malformed.csv,$fx\sales_basic.csv" \
    --label rust-final-recover --out target\rust-recover --binary $bin --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey empty --files "$fx\sales_empty.csv" \
    --label rust-final-empty --out target\rust-empty --binary $bin --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey sessions --files "$fx\sales_basic.csv,$fx\sales_unicode.csv" \
    --label rust-final-sessions --out target\rust-sessions --binary $bin --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey state --files "$fx\sales_basic.csv" \
    --label rust-state --out target\rust-state --binary $binNew --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey soft-invalid --files "$fx\sales_with_missing.csv,$fx\sales_basic.csv" \
    --label rust-soft-invalid --out target\rust-soft-invalid --binary $binNew --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey non-utf8 --files "$fx\sales_latin1.csv,$fx\sales_basic.csv" \
    --label rust-non-utf8 --out target\rust-non-utf8 --binary $binNew --scope "RUST SIDE ONLY"
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey filter-empty --files "$fx\sales_basic.csv" \
    --label rust-filter-empty --out target\rust-filter-empty --binary $binNew --scope "RUST SIDE ONLY"
~~~
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey j07-sequence --out target\rust-j07-sequence \
    --label rust-j07-sequence --binary $binNew --scope "RUST SIDE ONLY" --build-base ef359b1
target\pyref-venv\Scripts\python.exe tests\browser\numeric_capture.py --url http://127.0.0.1:8501/ \
    --case data-loop --journey j08-sequence --out target\rust-j08-sequence \
    --label rust-j08-sequence --binary $binNew --scope "RUST SIDE ONLY" --build-base ef359b1
~~~

The driver is `tests/browser/numeric_capture.py` (sha256
`AF2519D40235883E3A09F8EAE5D6AA52A0E3969695EE482B41C66580080662A4` for the two whole journeys,
`4194835B77379A2E63D783D292183B70061DBD8D221575EFE8C50D0A5BF462AD` for the four raws of this round,
`9EDC3FA1D456E5592771C448AC5E600C99D71398C5E55CCB7E8A541F61E5F966` when the four rows above were captured; the driver now names the journeys in one
constant (`A8F93500D544780F9358AE9D6F015424C882BA1249FE4CDE141A32426E31D5D0`), which changed no byte of a capture); the
criteria live in `tests/reference/capture_browser_trace.py` (sha256
`FF39DD51F8439ABED32205C50395D0E4CAFA7194BCF37A0338F62DD6E0139C00` for the two whole journeys,
`1D1A5C8415C8D212948045EF75B971E9AC278E4C925D3110CD75AA70C3AB422F` for the four raws of this round,
`B29B4F85AC9BEBE885C4B3EEE8E2142D8A44DC4724C6A9F1075BB09062DA08F6`, re-validated against `DA2E746A8267E1DFAC65CF0CB5513B3C6B729B33C5035C3CF5C253F016925D9A`, for the four rows above).
The `agent-browser` CLI could not start its daemon in this environment, so
the entry drives the same real Chrome over the DevTools Protocol; the reason
is recorded in the `capture` block of every raw.  The decoder needs the
pinned interpreter `target\pyref-venv\Scripts\python.exe` (streamlit
1.66.1 with its protobuf definitions); without it the entry stops before it
records anything.

**The earlier closed loop**

`tests/browser/rust-data-loop/` was the same closed loop against the earlier
build `data-app-20261024T141223140.exe` (sha256
`F8A0D4CA241F64F98CC7CF5736869491DE07D958E0428C2EC3EB687DC9AC44A3`).  Its raw
carries the kind and the scope of a Python reference capture, because the
positive path labelled itself that way before the label was taken from the
command line; the raw is left as it is and the capture above supersedes it.

**The four raws of this round**

They were recorded on 2026-10-24 against the binary above, with the upload
window bound the way the shared reader binds it: the window of an upload is
the request of the URLs of the newly issued file, the state that names that
file, the server run that answered it and that run's successful completion.
The Rust app answers a replacement in two runs -- first the run that clears
the uploader, then the run of the new file -- and the window holds both, with
the completion of the run of the new file at its end.  The earlier rule, which
stopped at the first successful completion, ended the window at the clearing
run and left the result outside it.

`state/` is a pass: the shared criterion judges the counters of the window,
the distinct script run ids and the three pictures, and it holds.  The other
three are measured but not judged -- the criterion of those cases is not
written yet, so the entry exits 1 and the journeys of
`tests/journeys/journeys.json` stay `failed` for exactly those parts.

**The two whole journeys**

`j07-sequence/` and `j08-sequence/` are one capture each: the whole journey is
driven in one tab and one session, never a page per case.  The parse journey
reads the malformed file, the file with two unusable amounts, a good file, the
file that is not UTF-8 and a good file again -- the counters read 2, 4, 6, 8,
10 and the session id is the same in every step.  The empty journey reads the
file without rows, a good file, the filter that leaves no row and the filter
back -- the counters read 2, 4, 5, 6, so the filter is one run and the way
back is one run, without a reload and without a new session.

Every step is bound to the run that answered it: the window of an upload is
the request of the URLs of the newly issued file, the state that names that
file, the server run that answered it and that run's successful completion.
The Rust app answers a replacement in two runs -- first the run that clears
the uploader, then the run of the new file -- and the window holds both, with
the completion of the run of the new file at its end.

The shared criterion of the whole journey is `sequence_checks` in
`tests/reference/capture_browser_trace.py`; the phase names, the inputs and
the picture roles are its own, and the driver reads them from there.

**What these captures do not cover**

The parse-error wording of the Rust app differs from the reference text
(`Could not parse the uploaded CSV: CSV error: record 2 ...` against
`Could not parse the uploaded CSV: row 3: expected 8 fields, found 7`); that
case and the recovery of it (J07-S1 and J07-S3) were not run in this round.
