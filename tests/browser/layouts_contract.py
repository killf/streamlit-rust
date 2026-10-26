"""The strict layouts contract: journey-layouts-v1.

This criterion judges the observation the committed collector
(layouts_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Layouts). The collector states no verdict; this module owns it:

* the delta stream is exactly the measured 14 layout deltas in order,
  modulo (a) at most one leading main-container add_block at [0] -- the
  Rust runtime's documented divergence -- and (b) the hash segment of the
  dialog's $$ID name, which mixes each runtime's own script identity;
* the expander/popover children land at [slot, k] (not one level deeper),
  every tab block is emitted before any tab child, and the sidebar element
  takes the fixed root [1] with no block of its own;
* the dialog is added twice at [2, 0] -- closed, then reopened with
  isOpen -- around the measured flex content container;
* the DOM resolves the sidebar, expander, tabs, popover and dialog with no
  exception, and the run finishes FINISHED_SUCCESSFULLY.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

LAYOUTS_CASE = "layouts-page"
LAYOUTS_CONTRACT = "journey-layouts-v1"

LAYOUTS_STAGES = ["01-load"]

# The measured (kind, path, payload) timeline, dialog ids normalized.
LAYOUTS_TIMELINE = [
    {
        'type': 'new_element',
        'path': [
            1,
            0
        ],
        'element': 'markdown',
        'body': 'side note',
        'block_id': None,
        'block_type': None,
        'block': None
    },
    {
        'type': 'add_block',
        'path': [
            0,
            0
        ],
        'element': None,
        'body': None,
        'block_id': '',
        'block_type': 'expandable',
        'block': {
            'expandable': {
                'label': 'Details',
                'expanded': True
            },
            'allowEmpty': True,
            'widthConfig': {
                'useStretch': True
            }
        }
    },
    {
        'type': 'new_element',
        'path': [
            0,
            0,
            0
        ],
        'element': 'markdown',
        'body': 'inside expander',
        'block_id': None,
        'block_type': None,
        'block': None
    },
    {
        'type': 'add_block',
        'path': [
            0,
            1
        ],
        'element': None,
        'body': None,
        'block_id': '',
        'block_type': 'tab_container',
        'block': {
            'tabContainer': {},
            'heightConfig': {
                'useContent': True
            },
            'widthConfig': {
                'useStretch': True
            }
        }
    },
    {
        'type': 'add_block',
        'path': [
            0,
            1,
            0
        ],
        'element': None,
        'body': None,
        'block_id': '',
        'block_type': 'tab',
        'block': {
            'tab': {
                'label': 'One'
            },
            'allowEmpty': True
        }
    },
    {
        'type': 'add_block',
        'path': [
            0,
            1,
            1
        ],
        'element': None,
        'body': None,
        'block_id': '',
        'block_type': 'tab',
        'block': {
            'tab': {
                'label': 'Two'
            },
            'allowEmpty': True
        }
    },
    {
        'type': 'new_element',
        'path': [
            0,
            1,
            0,
            0
        ],
        'element': 'markdown',
        'body': 'first tab',
        'block_id': None,
        'block_type': None,
        'block': None
    },
    {
        'type': 'new_element',
        'path': [
            0,
            1,
            1,
            0
        ],
        'element': 'markdown',
        'body': 'second tab',
        'block_id': None,
        'block_type': None,
        'block': None
    },
    {
        'type': 'add_block',
        'path': [
            0,
            2
        ],
        'element': None,
        'body': None,
        'block_id': '',
        'block_type': 'popover',
        'block': {
            'allowEmpty': True,
            'popover': {
                'label': 'Open settings',
                'type': 'secondary',
                'open': False
            },
            'widthConfig': {
                'useContent': True
            }
        }
    },
    {
        'type': 'new_element',
        'path': [
            0,
            2,
            0
        ],
        'element': 'markdown',
        'body': 'inside popover',
        'block_id': None,
        'block_type': None,
        'block': None
    },
    {
        'type': 'add_block',
        'path': [
            2,
            0
        ],
        'element': None,
        'body': None,
        'block_id': '$$ID-<hash>-None',
        'block_type': 'dialog',
        'block': {
            'dialog': {
                'title': 'Confirm',
                'dismissible': True
            },
            'id': '$$ID-<hash>-None'
        }
    },
    {
        'type': 'add_block',
        'path': [
            2,
            0
        ],
        'element': None,
        'body': None,
        'block_id': '$$ID-<hash>-None',
        'block_type': 'dialog',
        'block': {
            'dialog': {
                'title': 'Confirm',
                'dismissible': True,
                'isOpen': True
            },
            'id': '$$ID-<hash>-None'
        }
    },
    {
        'type': 'add_block',
        'path': [
            2,
            0,
            0
        ],
        'element': None,
        'body': None,
        'block_id': '',
        'block_type': 'flex_container',
        'block': {
            'flexContainer': {
                'gapConfig': {
                    'gapSize': 'SMALL'
                },
                'direction': 'VERTICAL',
                'justify': 'JUSTIFY_START',
                'align': 'ALIGN_START'
            },
            'heightConfig': {
                'useContent': True
            },
            'widthConfig': {
                'useStretch': True
            }
        }
    },
    {
        'type': 'new_element',
        'path': [
            2,
            0,
            0,
            0
        ],
        'element': 'markdown',
        'body': 'inside dialog',
        'block_id': None,
        'block_type': None,
        'block': None
    }
]

# The DOM projection the official frontend resolves.
LAYOUTS_DOM = {
    'blocks': [
        'stSidebar',
        'stSidebarContent',
        'stSidebarHeader',
        'stSidebarCollapseButton',
        'stSidebarUserContent',
        'stVerticalBlock',
        'stSidebarResizeHandle',
        'stVerticalBlock',
        'stExpander',
        'stExpanderDetails',
        'stVerticalBlock',
        'stTabs',
        'stTab',
        'stTab',
        'stTabPanel',
        'stVerticalBlock',
        'stTabPanel',
        'stVerticalBlock',
        'stPopover',
        'stPopoverButton',
        'stVerticalBlock',
        'stDialog',
        'stVerticalBlock',
        'stVerticalBlock'
    ],
    'markdowns': [
        'side note',
        'inside expander',
        'first tab',
        'second tab',
        'inside dialog'
    ],
    'expanderOpen': 0,
    'exceptions': []
}

LAYOUTS_SOURCE_PINS = {
    "python": [
    'tests/reference/layouts_app.py',
    '4bb61a02a09d9e9ec12526e86da4f5bab1cc28fec2655ac2149df25f124ad74b'
],
    "native": [
    'streamlit/examples/layouts.rs',
    '41832195dba7d68fb0f603660285a2ae9f9ae211b7266a1d77f3d6c6611818d8'
],
}

LAYOUTS_REQUIRED = (
    "contract", "stage_set", "source_pin", "layout_timeline",
    "dialog_wire", "dom_projection", "no_exceptions", "finishes",
    "png_sources",
)

_DIALOG_ID = re.compile(r"^\$\$ID-[0-9a-f]{32}-None$")
_ID_SUB = re.compile(r"\$\$ID-[0-9a-f]{32}-None")


def _record(checks, name, ok, expected, actual):
    checks.append({"step": LAYOUTS_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _normalize(delta):
    """One observed delta in the timeline's comparable shape."""
    block = delta.get("block")
    if block is not None:
        block = json.loads(_ID_SUB.sub("$$ID-<hash>-None", json.dumps(block, ensure_ascii=False)))
    block_id = delta.get("block_id")
    if isinstance(block_id, str):
        block_id = _ID_SUB.sub("$$ID-<hash>-None", block_id)
    return {"type": delta.get("type"), "path": delta.get("path"), "element": delta.get("element"),
            "body": delta.get("body"), "block_id": block_id, "block_type": delta.get("block_type"),
            "block": block}


def _layout_deltas(stage):
    """Every layout delta of the stage, after the optional leading main
    container block is peeled off (the Rust side emits exactly one, the
    reference none)."""
    out = []
    stripped = 0
    for frame in stage.get("new_frames") or []:
        delta = (frame.get("summary") or {}).get("delta") or {}
        if not delta:
            continue
        kind = delta.get("type")
        _need(kind in ("new_transient", "new_element", "add_block"), f"unexpected delta kind {kind!r}")
        if kind == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block_type")) == "vertical" and (delta.get("block") or {}).get("id") == "main_container":
            stripped += 1
            _need(stripped <= 1, "more than one leading main-container block")
            continue
        out.append(delta)
    return out


def layouts_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 layouts wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 layouts wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == LAYOUTS_CASE and observation.get("contract") == LAYOUTS_CONTRACT,
              "missing versioned layouts contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(LAYOUTS_STAGES),
              f"stages must be exactly the {len(LAYOUTS_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        source = observation.get("source") or {}
        side = "python" if observation.get("scope") == "PYTHON SIDE ONLY" else "native"
        path, pinned = LAYOUTS_SOURCE_PINS[side]
        _need(source.get("file") == path and source.get("sha256") == pinned,
              f"driven source is not the pinned {path} of this contract")
        mark("source_pin")

        deltas = _layout_deltas(stages[0])
        observed = [_normalize(delta) for delta in deltas]
        _need(observed == LAYOUTS_TIMELINE,
              "the layout delta timeline differs from the measured 14-delta wire "
              f"(got {len(observed)} deltas after the leading main block)")
        mark("layout_timeline")

        dialogs = [delta for delta in deltas if (delta.get("path") or None) == [2, 0]]
        _need(len(dialogs) == 2, f"the dialog must be added exactly twice at [2, 0], got {len(dialogs)}")
        first_id, second_id = dialogs[0].get("block_id"), dialogs[1].get("block_id")
        _need(isinstance(first_id, str) and bool(_DIALOG_ID.match(first_id)),
              f"the dialog block id must match $$ID-<32hex>-None, got {first_id!r}")
        _need(first_id == second_id, "both dialog blocks must carry the same $$ID name")
        first_payload = (dialogs[0].get("block") or {}).get("dialog") or {}
        second_payload = (dialogs[1].get("block") or {}).get("dialog") or {}
        _need(first_payload.get("isOpen") is None, "the first dialog block must be the closed one")
        _need(second_payload.get("isOpen") is True, "the second dialog block must reopen with isOpen")
        _need(first_payload.get("title") == "Confirm" and second_payload.get("title") == "Confirm"
              and first_payload.get("dismissible") is True and second_payload.get("dismissible") is True,
              "the dialog payloads differ from the measured wire")
        content = [delta for delta in deltas if (delta.get("path") or None) == [2, 0, 0]]
        _need(len(content) == 1, "exactly one content container at [2, 0, 0]")
        flex = (content[0].get("block") or {}).get("flexContainer") or {}
        _need(flex == {"gapConfig": {"gapSize": "SMALL"}, "direction": "VERTICAL", "justify": "JUSTIFY_START", "align": "ALIGN_START"},
              f"the dialog content flex differs from the measured wire: {flex}")
        children = [delta for delta in deltas if (delta.get("path") or [])[0:3] == [2, 0, 0] and len(delta.get("path") or []) == 4]
        _need(len(children) == 1 and children[0].get("body") == "inside dialog",
              "the dialog content must stream its child element at [2, 0, 0, 0]")
        mark("dialog_wire")

        page = (observation.get("url") or "").rstrip("/")
        dom_text = json.dumps({key: (stages[0]["dom"] or {}).get(key) for key in ("blocks", "markdowns", "expanderOpen", "exceptions")}, ensure_ascii=False)
        dom_text = dom_text.replace(page, "<page>")
        _need(json.loads(dom_text) == LAYOUTS_DOM, "the resolved DOM projection differs from the measured page")
        mark("dom_projection")

        _need(not ((stages[0]["dom"] or {}).get("exceptions") or []), "the page renders an exception")
        for frame in stages[0]["new_frames"]:
            delta = (frame.get("summary") or {}).get("delta") or {}
            _need(delta.get("element") != "exception", "the stream carries an exception element")
        mark("no_exceptions")

        finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                    for frame in stages[0]["new_frames"]
                    if (frame.get("summary") or {}).get("type") == "script_finished"]
        _need(finishes == [0], "the run must finish exactly once with FINISHED_SUCCESSFULLY")
        mark("finishes")

        root = pathlib.Path(observation.get("ipc_dir", ".")).resolve()
        for stage in stages:
            record = stage.get("screenshot") or {}
            _need(not pathlib.Path(record.get("file", "")).is_absolute(), "screenshot path must be relative")
            png = (root / record.get("file", "")).resolve()
            _need(png.is_relative_to(root) and png.is_file(), f"missing stage PNG {record.get('file')}")
            data = png.read_bytes()
            _need(data.startswith(b"\x89PNG\r\n\x1a\n") and hashlib.sha256(data).hexdigest() == record.get("sha256"),
                  f"stage PNG sha/magic mismatch for {record.get('file')}")
        mark("png_sources")
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError, StopIteration) as exc:
        for name in LAYOUTS_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def layouts_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = layouts_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(LAYOUTS_REQUIRED),
    }
