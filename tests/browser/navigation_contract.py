"""The strict navigation contract: journey-navigation-v1.

This criterion judges the observation the committed collector
(navigation_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Multipage navigation). The collector states no verdict; this module owns it:

* st.navigation streams one navigation ForwardMsg per run carrying the pages
  (each named by the BLAKE2b/16 hash of its url path, the raw icon string,
  the default marker, the url pathname for non-default pages), the sidebar
  position, the unnamed section and the current page;
* the browser addresses reruns by page hash (ClientState.page_script_hash)
  and NewSession echoes it; an unaddressed load runs the default page and
  reports the runtime's own main script hash;
* session state survives page switches (the hits counter climbs across the
  round trip);
* st.switch_page ends the run FINISHED_EARLY_FOR_RERUN after streaming the
  empty query string and the server alone runs the target page (no second
  browser request), ending FINISHED_SUCCESSFULLY;
* the settled DOM shows the sidebar nav entries, the page bodies and no
  exception.

Widget ids are judged modulo the $$ID digest segment; the initial
NewSession page hash is the runtime's own main script hash (the documented
custom-hash divergence) and at most one leading main-container add_block at
[0] is the Rust runtime's documented divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

NAVIGATION_CASE = "navigation-page"
NAVIGATION_CONTRACT = "journey-navigation-v1"

NAVIGATION_STAGES = [
    '01-load',
    '02-click-two',
    '03-back-main',
    '04-switch-button'
]

# Per stage: the normalized frame timeline (navigation messages with the
# page hashes, NewSession's addressed page, elements, the rerun reports,
# the page_info payload and the finish statuses), the navigation messages
# and the DOM projection.
NAVIGATION_TIMELINE = {
    '01-load': [
        {
            'kind': 'rerun',
            'page_script_hash': '',
            'widget_states': []
        },
        {
            'kind': 'new_session',
            'page': '<main>'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'navigation',
            'pages': [
                {
                    'hash': '4e89e30dce2a0c9070887e292d3255e7',
                    'name': 'Main',
                    'icon': ':material/home:',
                    'default': True,
                    'url_path': ''
                },
                {
                    'hash': 'd681734f8c454b90df4d5feea7487445',
                    'name': 'Two',
                    'icon': '',
                    'default': False,
                    'url_path': 'two'
                }
            ],
            'position': 'SIDEBAR',
            'current': '4e89e30dce2a0c9070887e292d3255e7',
            'sections': [
                ''
            ],
            'expanded': False
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                0
            ],
            'body': 'page=main hits=1'
        },
        {
            'kind': 'button',
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'finished',
            'status': 0
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '02-click-two': [
        {
            'kind': 'rerun',
            'page_script_hash': 'd681734f8c454b90df4d5feea7487445',
            'widget_states': []
        },
        {
            'kind': 'new_session',
            'page': 'd681734f8c454b90df4d5feea7487445'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'navigation',
            'pages': [
                {
                    'hash': '4e89e30dce2a0c9070887e292d3255e7',
                    'name': 'Main',
                    'icon': ':material/home:',
                    'default': True,
                    'url_path': ''
                },
                {
                    'hash': 'd681734f8c454b90df4d5feea7487445',
                    'name': 'Two',
                    'icon': '',
                    'default': False,
                    'url_path': 'two'
                }
            ],
            'position': 'SIDEBAR',
            'current': 'd681734f8c454b90df4d5feea7487445',
            'sections': [
                ''
            ],
            'expanded': False
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                0
            ],
            'body': 'page=two'
        },
        {
            'kind': 'finished',
            'status': 0
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '03-back-main': [
        {
            'kind': 'rerun',
            'page_script_hash': '4e89e30dce2a0c9070887e292d3255e7',
            'widget_states': []
        },
        {
            'kind': 'new_session',
            'page': '4e89e30dce2a0c9070887e292d3255e7'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'navigation',
            'pages': [
                {
                    'hash': '4e89e30dce2a0c9070887e292d3255e7',
                    'name': 'Main',
                    'icon': ':material/home:',
                    'default': True,
                    'url_path': ''
                },
                {
                    'hash': 'd681734f8c454b90df4d5feea7487445',
                    'name': 'Two',
                    'icon': '',
                    'default': False,
                    'url_path': 'two'
                }
            ],
            'position': 'SIDEBAR',
            'current': '4e89e30dce2a0c9070887e292d3255e7',
            'sections': [
                ''
            ],
            'expanded': False
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                0
            ],
            'body': 'page=main hits=2'
        },
        {
            'kind': 'button',
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'finished',
            'status': 0
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '04-switch-button': [
        {
            'kind': 'rerun',
            'page_script_hash': '4e89e30dce2a0c9070887e292d3255e7',
            'widget_states': [
                {
                    'id': '$$ID-None',
                    'value_field': 'trigger_value',
                    'value': True
                }
            ]
        },
        {
            'kind': 'new_session',
            'page': '4e89e30dce2a0c9070887e292d3255e7'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'navigation',
            'pages': [
                {
                    'hash': '4e89e30dce2a0c9070887e292d3255e7',
                    'name': 'Main',
                    'icon': ':material/home:',
                    'default': True,
                    'url_path': ''
                },
                {
                    'hash': 'd681734f8c454b90df4d5feea7487445',
                    'name': 'Two',
                    'icon': '',
                    'default': False,
                    'url_path': 'two'
                }
            ],
            'position': 'SIDEBAR',
            'current': '4e89e30dce2a0c9070887e292d3255e7',
            'sections': [
                ''
            ],
            'expanded': False
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                0
            ],
            'body': 'page=main hits=3'
        },
        {
            'kind': 'button',
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'page_info',
            'query_string': ''
        },
        {
            'kind': 'finished',
            'status': 2
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'new_session',
            'page': 'd681734f8c454b90df4d5feea7487445'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'navigation',
            'pages': [
                {
                    'hash': '4e89e30dce2a0c9070887e292d3255e7',
                    'name': 'Main',
                    'icon': ':material/home:',
                    'default': True,
                    'url_path': ''
                },
                {
                    'hash': 'd681734f8c454b90df4d5feea7487445',
                    'name': 'Two',
                    'icon': '',
                    'default': False,
                    'url_path': 'two'
                }
            ],
            'position': 'SIDEBAR',
            'current': 'd681734f8c454b90df4d5feea7487445',
            'sections': [
                ''
            ],
            'expanded': False
        },
        {
            'kind': 'markdown',
            'path': [
                0,
                0
            ],
            'body': 'page=two'
        },
        {
            'kind': 'finished',
            'status': 0
        },
        {
            'kind': 'session_status_changed'
        }
    ]
}

NAVIGATION_NAVS = {
    '01-load': [
        {
            'kind': 'navigation',
            'pages': [
                {
                    'hash': '4e89e30dce2a0c9070887e292d3255e7',
                    'name': 'Main',
                    'icon': ':material/home:',
                    'default': True,
                    'url_path': ''
                },
                {
                    'hash': 'd681734f8c454b90df4d5feea7487445',
                    'name': 'Two',
                    'icon': '',
                    'default': False,
                    'url_path': 'two'
                }
            ],
            'position': 'SIDEBAR',
            'current': '4e89e30dce2a0c9070887e292d3255e7',
            'sections': [
                ''
            ],
            'expanded': False
        }
    ],
    '02-click-two': [
        {
            'kind': 'navigation',
            'pages': [
                {
                    'hash': '4e89e30dce2a0c9070887e292d3255e7',
                    'name': 'Main',
                    'icon': ':material/home:',
                    'default': True,
                    'url_path': ''
                },
                {
                    'hash': 'd681734f8c454b90df4d5feea7487445',
                    'name': 'Two',
                    'icon': '',
                    'default': False,
                    'url_path': 'two'
                }
            ],
            'position': 'SIDEBAR',
            'current': 'd681734f8c454b90df4d5feea7487445',
            'sections': [
                ''
            ],
            'expanded': False
        }
    ],
    '03-back-main': [
        {
            'kind': 'navigation',
            'pages': [
                {
                    'hash': '4e89e30dce2a0c9070887e292d3255e7',
                    'name': 'Main',
                    'icon': ':material/home:',
                    'default': True,
                    'url_path': ''
                },
                {
                    'hash': 'd681734f8c454b90df4d5feea7487445',
                    'name': 'Two',
                    'icon': '',
                    'default': False,
                    'url_path': 'two'
                }
            ],
            'position': 'SIDEBAR',
            'current': '4e89e30dce2a0c9070887e292d3255e7',
            'sections': [
                ''
            ],
            'expanded': False
        }
    ],
    '04-switch-button': [
        {
            'kind': 'navigation',
            'pages': [
                {
                    'hash': '4e89e30dce2a0c9070887e292d3255e7',
                    'name': 'Main',
                    'icon': ':material/home:',
                    'default': True,
                    'url_path': ''
                },
                {
                    'hash': 'd681734f8c454b90df4d5feea7487445',
                    'name': 'Two',
                    'icon': '',
                    'default': False,
                    'url_path': 'two'
                }
            ],
            'position': 'SIDEBAR',
            'current': '4e89e30dce2a0c9070887e292d3255e7',
            'sections': [
                ''
            ],
            'expanded': False
        },
        {
            'kind': 'navigation',
            'pages': [
                {
                    'hash': '4e89e30dce2a0c9070887e292d3255e7',
                    'name': 'Main',
                    'icon': ':material/home:',
                    'default': True,
                    'url_path': ''
                },
                {
                    'hash': 'd681734f8c454b90df4d5feea7487445',
                    'name': 'Two',
                    'icon': '',
                    'default': False,
                    'url_path': 'two'
                }
            ],
            'position': 'SIDEBAR',
            'current': 'd681734f8c454b90df4d5feea7487445',
            'sections': [
                ''
            ],
            'expanded': False
        }
    ]
}

NAVIGATION_DOMS = {
    '01-load': {
        'url': '/',
        'nav': [
            'homeMain',
            'Two'
        ],
        'markdowns': [
            'page=main hits=1'
        ],
        'exceptions': []
    },
    '02-click-two': {
        'url': '/two',
        'nav': [
            'homeMain',
            'Two'
        ],
        'markdowns': [
            'page=two'
        ],
        'exceptions': []
    },
    '03-back-main': {
        'url': '/',
        'nav': [
            'homeMain',
            'Two'
        ],
        'markdowns': [
            'page=main hits=2'
        ],
        'exceptions': []
    },
    '04-switch-button': {
        'url': '/two',
        'nav': [
            'homeMain',
            'Two'
        ],
        'markdowns': [
            'page=two'
        ],
        'exceptions': []
    }
}

NAVIGATION_SOURCE_FILES = {
    "python": "tests/reference/navigation_app.py",
    "native": "streamlit/examples/navigation.rs",
}

NAVIGATION_REQUIRED = (
    "contract", "stage_set", "timeline", "nav_wire",
    "page_hash_wire", "session_state_wire", "switch_wire",
    "dom_projection", "no_exceptions", "finishes", "png_sources",
)

_ID_SUB = re.compile(r"\$\$ID-[0-9a-f]{32}-")
_UUID_SUB = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _record(checks, name, ok, expected, actual):
    checks.append({"step": NAVIGATION_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _timeline(stage, main_hash):
    """The stage's normalized frames, the optional leading main container
    peeled off (the Rust side emits exactly one per run -- a switched stage
    carries two runs -- the reference none)."""
    out = []
    stripped = 0
    for frame in stage.get("new_frames") or []:
        summary = frame.get("summary") or {}
        kind = summary.get("type")
        if kind == "delta":
            delta = summary.get("delta") or {}
            inner = delta.get("type")
            _need(inner in ("new_element", "add_block", "new_transient"), f"unexpected delta kind {inner!r}")
            if inner == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                stripped += 1
                _need(stripped <= 1, "more than one leading main-container block per run")
                continue
            if delta.get("element") == "button":
                out.append({"kind": "button", "path": delta.get("path")})
            elif inner == "new_element":
                out.append({"kind": delta.get("element"), "path": delta.get("path"), "body": delta.get("body")})
            else:
                out.append({"kind": inner, "path": delta.get("path")})
        elif kind == "navigation":
            nav = summary.get("navigation") or {}
            pages = [
                {
                    "hash": page.get("pageScriptHash"),
                    "name": page.get("pageName"),
                    "icon": page.get("icon", ""),
                    "default": page.get("isDefault", False),
                    "url_path": page.get("urlPathname", ""),
                }
                for page in nav.get("appPages") or []
            ]
            out.append({"kind": "navigation", "pages": pages, "position": nav.get("position"),
                        "current": nav.get("pageScriptHash"), "sections": nav.get("sections") or [],
                        "expanded": nav.get("expanded", False)})
        elif kind == "new_session":
            session = summary.get("new_session") or {}
            page = session.get("page_script_hash") or ""
            _need(session.get("main_script_hash") == main_hash, "the main script hash changed mid-observation")
            stripped = 0
            out.append({"kind": "new_session", "page": "<main>" if page == main_hash else page})
        elif kind == "rerun_script":
            rerun = summary.get("rerun_script") or {}
            states = [{**state, "id": _ID_SUB.sub("$$ID-", state.get("id") or "")} for state in rerun.get("widget_states") or []]
            page = rerun.get("page_script_hash") or ""
            out.append({"kind": "rerun", "page_script_hash": "<main>" if page == main_hash else page, "widget_states": states})
        elif kind == "page_info_changed":
            out.append({"kind": "page_info", "query_string": (summary.get("page_info") or {}).get("query_string")})
        elif kind == "script_finished":
            out.append({"kind": "finished", "status": (summary.get("script_finished") or {}).get("status")})
        elif kind == "session_status_changed":
            out.append({"kind": "session_status_changed"})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def navigation_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 navigation wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 navigation wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == NAVIGATION_CASE and observation.get("contract") == NAVIGATION_CONTRACT,
              "missing versioned navigation contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(NAVIGATION_STAGES),
              f"stages must be exactly the {len(NAVIGATION_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        main_hash = next((frame["summary"]["new_session"]["main_script_hash"]
                          for stage in stages for frame in stage["new_frames"]
                          if (frame["summary"].get("new_session") or {}).get("main_script_hash")), "")
        _need(bool(main_hash), "no NewSession main script hash")

        timelines = {stage["name"]: _timeline(stage, main_hash) for stage in stages}
        for name in NAVIGATION_STAGES:
            _need(timelines[name] == NAVIGATION_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        for name in NAVIGATION_STAGES:
            navs = [entry for entry in timelines[name] if entry["kind"] == "navigation"]
            runs = [entry for entry in timelines[name] if entry["kind"] == "new_session"]
            _need(len(navs) == len(runs) and len(navs) >= 1,
                  f"stage {name} must stream exactly one navigation message per run, got {len(navs)} for {len(runs)} runs")
        mark("nav_wire")

        # NewSession echoes the addressed page hash; the unaddressed load
        # runs the default page; every rerun addresses a page hash.
        load = timelines["01-load"]
        first_new_session = next(entry for entry in load if entry["kind"] == "new_session")
        _need(first_new_session["page"] == "<main>", "an unaddressed load must report the main script hash")
        load_nav = next(entry for entry in load if entry["kind"] == "navigation")
        _need(load_nav["current"] == load_nav["pages"][0]["hash"] and load_nav["pages"][0]["default"],
              "an unaddressed load must resolve the default page")
        for name in ("02-click-two", "03-back-main"):
            stage_frames = timelines[name]
            rerun = next(entry for entry in stage_frames if entry["kind"] == "rerun")
            new_session = next(entry for entry in stage_frames if entry["kind"] == "new_session")
            _need(rerun["page_script_hash"] == new_session["page"] and new_session["page"] != "<main>",
                  f"stage {name} NewSession must echo the browser-addressed page hash")
        mark("page_hash_wire")

        bodies = lambda frames: [entry.get("body") for entry in frames if entry["kind"] == "markdown"]
        _need(bodies(load) == ["page=main hits=1"], "the load runs the default page once")
        _need(bodies(timelines["03-back-main"]) == ["page=main hits=2"], "session state must survive the page round trip")
        mark("session_state_wire")

        # switch_page: early finish, empty page_info, then one server-only
        # run of the target page with no second browser request.
        switched = timelines["04-switch-button"]
        reruns = [entry for entry in switched if entry["kind"] == "rerun"]
        _need(len(reruns) == 1, "the switch stage must carry exactly one browser rerun")
        infos = [entry for entry in switched if entry["kind"] == "page_info"]
        finishes = [entry for entry in switched if entry["kind"] == "finished"]
        new_sessions = [entry for entry in switched if entry["kind"] == "new_session"]
        _need(infos == [{"kind": "page_info", "query_string": ""}], "st.switch_page must stream exactly one empty page_info")
        _need([finish["status"] for finish in finishes] == [2, 0], "the switch run finishes early, the next run finishes successfully")
        _need(len(new_sessions) == 2 and new_sessions[0]["page"] != new_sessions[1]["page"],
              "the server-started run addresses the target page")
        _need(bodies(switched) == ["page=main hits=3", "page=two"], "the switched run renders Main then the server runs Two")
        mark("switch_wire")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in NAVIGATION_DOMS[name]} == NAVIGATION_DOMS[name],
                  f"stage {name} resolved DOM projection differs from the measured page")
        mark("dom_projection")

        for stage in stages:
            _need(not ((stage["dom"] or {}).get("exceptions") or []), f"stage {stage['name']} renders an exception")
            for frame in stage["new_frames"]:
                delta = (frame.get("summary") or {}).get("delta") or {}
                _need(delta.get("element") != "exception", "the stream carries an exception element")
        mark("no_exceptions")

        for stage in stages:
            finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                        for frame in stage["new_frames"]
                        if (frame.get("summary") or {}).get("type") == "script_finished"]
            _need(finishes == [entry["status"] for entry in timelines[stage["name"]] if entry["kind"] == "finished"],
                  f"stage {stage['name']} finish statuses differ from the measured wire")
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
        for name in NAVIGATION_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def navigation_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = navigation_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(NAVIGATION_REQUIRED),
    }
