"""Unit tests of the strict query-params contract (journey-queryparams-v1)."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "browser"))

from queryparams_contract import (  # noqa: E402
    QUERYPARAMS_DOMS,
    QUERYPARAMS_PAGE_INFOS,
    QUERYPARAMS_REQUIRED,
    QUERYPARAMS_RERUNS,
    QUERYPARAMS_SOURCE_FILES,
    QUERYPARAMS_STAGES,
    QUERYPARAMS_TIMELINE,
    queryparams_result,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not-a-real-image-but-magic-and-hash-are-checked"


TEXT_LENGTH_PHASES = ("load", "ascii", "unicode", "same-prefix", "joiner", "empty", "assign", "retain", "recover")
TEXT_LENGTH_INPUTS = {"ascii": "abcdef🧊", "unicode": "中文🧊e\u0301TAIL", "same-prefix": "中文🧊e\u0301OTHER",
                      "joiner": "👨\u200d👩\u200d👧\u200d👦!", "empty": "", "recover": "line1\nline2🧊"}
TEXT_LENGTH_VALUES = (
    ("abcde", "abcde", "中文🧊e\u0301", "中文🧊e\u0301", "👨\u200d👩\u200d👧", "", "code長🧊extra", "code長🧊extra", "line1"),
    ("", "", "", "", "", "", "code長🧊extra", "code長🧊extra", ""),
    ("abcdef🧊", "abcdef🧊", "中文🧊e\u0301TAIL", "中文🧊e\u0301OTHER", "👨\u200d👩\u200d👧\u200d👦!", "", "code長🧊extra", "code長🧊extra", "line1\nline2🧊"),
    (None, "abcde", "中文🧊e\u0301", "中文🧊e\u0301", "👨\u200d👩\u200d👧", "", "code長🧊extra", "code長🧊extra", "line1"),
)

TEXT_RESET_STEPS = (("5", "long", "load"), ("5", "long", "edit"), ("3", "long", "shrink"), ("3", "long", "edit-short"),
                    ("5", "long", "grow"), ("0", "long", "zero"), ("none", "long", "unlimited"), ("none", "long", "same-none"),
                    ("none", "long", "retain"), ("none", "none", "same-default"), ("5", "long", "return-five"), ("5", "long", "edit-five"))
TEXT_RESET_INPUTS = {"edit": "é🧊zUPPER", "edit-short": "XYZtail", "same-none": "retained🧊text", "edit-five": "END🧊ok"}
TEXT_RESET_VALUES = ("abcde", "é🧊zUP", "abc", "XYZ", "abcde", "", "abcdef🧊", "retained🧊text", "retained🧊text", "retained🧊text", "abcde", "END🧊o")

TEXT_SOURCE_STEPS = (("5", "load", None), ("5", "edit", "OLDstate🧊"), ("3", "shrink", "ABCDEtail"), ("0", "assign", "xyzTAIL"),
                     ("0", "retain", None), ("5", "grow", "ignored"), ("3", "assign", "newvalue"), ("3", "edit-short", "AFTERtail"),
                     ("5", "assign", None), ("5", "retain", None))
TEXT_SOURCE_VALUES = ("abcde", "OLDst", "abc", "code長🧊extra", "code長🧊extra", "abcde", "code長🧊extra", "AFT", "code長🧊extra", "code長🧊extra")
TEXT_SOURCE_CALLBACKS = (None, "OLDst", "ABCDE", "xyz", None, "", "newva", "AFT", None, None)

TEXT_BOUND_STEPS = (("load", "中文🧊e\u0301TAIL", None, False), ("url-only", "UVWXYZ", None, False),
                    ("same-default", "abcdefTAIL", None, False), ("frontend", "URLlonger", "EDITED", False),
                    ("history", "HISTORY🧊", "OTHERtail", True), ("assign", "NATIVEURL", None, False),
                    ("assign", "HISTORYTOO", None, True), ("history-missing", None, "staleTEXT", True),
                    ("empty-url", "", None, False), ("short", "ok", None, False),
                    ("repeat", ["ABCDExyz", "中文🧊e\u0301TAIL"], None, False), ("recover", "ok", "recover🧊", False))
TEXT_BOUND_VALUES = ("中文🧊e\u0301", "UVWXY", "UVWXY", "EDITE", "HISTO", "code長🧊extra", "HISTO", "abcde", "", "ok", "中文🧊e\u0301", "recov")


QUERY_ENCODING_CASES = (('tag=%+1&%+f=key&keep=ok', ['% 1'], [['tag', '% 1'], ['% f', 'key'], ['keep', 'ok']]),
 ('tag=%+0&tag=%+9&tag=%+A&tag=%+F&tag=%+a&tag=%+f', ['% 0', '% 9', '% A', '% F', '% a', '% f'], [['tag', '% f']]),
 ('tag=%1&tag=%&tag=%%&tag=%GG&tag=%1G&tag=%G1&tag=%-1&tag=%+G',
  ['%1', '%', '%%', '%GG', '%1G', '%G1', '%-1', '% G'],
  [['tag', '% G']]),
 ('tag=%20&tag=+&tag=%2B&tag=%2520&tag=a%26b%3Dc', [' ', ' ', '+', '%20', 'a&b=c'], [['tag', 'a&b=c']]),
 ('tag=%00&tag=%0A&tag=%0D&tag=%09&tag=%7F', ['\x00', '\n', '\r', '\t', '\x7f'], [['tag', '\x7f']]),
 ('tag=%E4%B8%AD%E6%96%87&tag=%e4%b8%ad&tag=%F0%9F%A7%8A', ['中文', '中', '🧊'], [['tag', '🧊']]),
 ('tag=%FF&tag=%C0%AF&tag=%ED%A0%80&tag=%F4%90%80%80', ['�', '��', '���', '����'], [['tag', '����']]),
 ('tag=%E2%82&tag=%E2%28%A1&tag=%F0%9F%28%8A&tag=%C3%A9%FF', ['�', '�(�', '�(�', 'é�'], [['tag', 'é�']]),
 ('=empty&bare&blank=&tag=first&tag=last&&', ['first', 'last'], [['', 'empty'], ['bare', ''], ['blank', ''], ['tag', 'last']]),
 ('tag=a;b&tag=a=b&tag=%23part&tag=%3Fquestion&tag=%2Fpath', ['a;b', 'a=b', '#part', '?question', '/path'], [['tag', '/path']]),
 ('tag=literal中文+🧊&tag=literal%中文', ['literal中文 🧊', 'literal%中文'], [['tag', 'literal%中文']]),
 ('tag=%2b&tag=%2B&tag=%2f&tag=%2F&tag=%7e&tag=~', ['+', '+', '/', '/', '~', '~'], [['tag', '~']]),
 ('tag=%+1&tag=%2B1&%+1=invalid-key&%2B1=valid-key',
  ['% 1', '+1'],
  [['tag', '+1'], ['% 1', 'invalid-key'], ['+1', 'valid-key']]),
 ('%E4%B8%AD=x&中=y&tag=a&%74ag=b&tag=c', ['a', 'b', 'c'], [['中', 'y'], ['tag', 'c']]),
 ('tag=&tag&=one&=two', ['', ''], [['tag', ''], ['', 'two']]),
 ('tag=%+A%+f%2B+%25', ['% A% f+ %'], [['tag', '% A% f+ %']]))


DISABLED_JSON_INPUTS = ('',
 '{',
 '[',
 '{"x":}',
 '{"x":1,}',
 '[1,]',
 '{"x" 1}',
 '["\\q"]',
 '"a\nb"',
 '{"x":1} tail',
 '中文',
 '{"🧊":\n }',
 '["\\uZZZZ"]',
 'true false',
 '01',
 '-',
 '1.',
 'NaN',
 'Infinity',
 '-Infinity',
 '"\\ud800"',
 '1e9999',
 '[NaN]',
 '{"x":Infinity}')

DISABLED_JSON_ERRORS = {0: ('json.decoder.JSONDecodeError', 'Expecting value: line 1 column 1 (char 0)'),
 1: ('json.decoder.JSONDecodeError', 'Expecting property name enclosed in double quotes: line 1 column 2 (char 1)'),
 2: ('json.decoder.JSONDecodeError', 'Expecting value: line 1 column 2 (char 1)'),
 3: ('json.decoder.JSONDecodeError', 'Expecting value: line 1 column 6 (char 5)'),
 4: ('json.decoder.JSONDecodeError', 'Illegal trailing comma before end of object: line 1 column 7 (char 6)'),
 5: ('json.decoder.JSONDecodeError', 'Illegal trailing comma before end of array: line 1 column 3 (char 2)'),
 6: ('json.decoder.JSONDecodeError', "Expecting ':' delimiter: line 1 column 6 (char 5)"),
 7: ('json.decoder.JSONDecodeError', 'Invalid \\escape: line 1 column 3 (char 2)'),
 8: ('json.decoder.JSONDecodeError', 'Invalid control character at: line 1 column 3 (char 2)'),
 9: ('json.decoder.JSONDecodeError', 'Extra data: line 1 column 9 (char 8)'),
 10: ('json.decoder.JSONDecodeError', 'Expecting value: line 1 column 1 (char 0)'),
 11: ('json.decoder.JSONDecodeError', 'Expecting value: line 2 column 2 (char 7)'),
 12: ('json.decoder.JSONDecodeError', 'Invalid \\uXXXX escape: line 1 column 4 (char 3)'),
 13: ('json.decoder.JSONDecodeError', 'Extra data: line 1 column 6 (char 5)'),
 14: ('json.decoder.JSONDecodeError', 'Extra data: line 1 column 2 (char 1)'),
 15: ('json.decoder.JSONDecodeError', 'Expecting value: line 1 column 1 (char 0)'),
 16: ('json.decoder.JSONDecodeError', 'Extra data: line 1 column 2 (char 1)'),
 22: ('TypeError', "cannot use 'list' as a dict key (unhashable type: 'list')"),
 23: ('TypeError', "cannot use 'dict' as a dict key (unhashable type: 'dict')")}


def read_query_param_capture(scenario, capture=None):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    if capture is None:
        capture = json.loads((HERE / f"reference-browser/queryparams/{scenario}/trace.json").read_text(encoding="utf-8-sig"))
    assert capture["runtime"] == "python" and capture["reference_version"] == "1.66.1"
    assert capture["successful"] and "producer_error" not in capture
    assert capture["cleanup"] == {"websocket_closed": True, "server_stopped": True}
    snapshots, urls, finishes, requests, histories, errors = [], [], [], [], [], []
    sessions, error_phases, input_types, byte_payloads, json_payloads = [], [], [], [], []
    length_inputs, length_widgets, length_ids = [], [], []
    slot = 0
    for frame in capture["frames"]:
        assert frame["direction"] in ("client->server", "server->client")
        raw = base64.b64decode(frame["base64"], validate=True)
        assert len(raw) == frame["bytes"]
        message = BackMsg() if frame["direction"] == "client->server" else ForwardMsg()
        message.ParseFromString(raw)
        assert MessageToDict(message, preserving_proto_field_name=True) == frame["message"]
        if isinstance(message, BackMsg):
            requests.append(message.rerun_script.query_string)
            histories.append(message.rerun_script.is_history_navigation)
            slot = 0
            if scenario == "text-repeat":
                assert not message.rerun_script.widget_states.widgets
            if scenario in ("text-length", "text-reset", "text-source"):
                widgets = message.rerun_script.widget_states.widgets
                phase = requests[-1].rsplit("phase=", 1)[-1]
                if scenario == "text-source":
                    submitted = TEXT_SOURCE_STEPS[(len(requests) - 1) % 10][2]
                    assert len(widgets) == (1 if submitted is not None else 0)
                    if widgets:
                        assert widgets[0].id == length_ids[-1]
                else:
                    inputs = TEXT_LENGTH_INPUTS if scenario == "text-length" else TEXT_RESET_INPUTS
                    assert len(widgets) == (1 if phase in inputs else 0)
                if widgets:
                    assert widgets[0].id.endswith("-cjk_note") and widgets[0].WhichOneof("value") == "string_value"
                    length_inputs.append((phase, widgets[0].string_value))
            if scenario == "disabled-json" and len(requests) % 3 == 2:
                widgets = message.rerun_script.widget_states.widgets
                assert len(widgets) == 2 and widgets[0].id.endswith("-bound") and widgets[1].id.endswith("-live")
                assert widgets[0].WhichOneof("value") == "json_value"
                json_payloads.append(widgets[0].json_value)
            if scenario in ("disabled-types-isolated", "disabled-types-more", "disabled-types-bytes") and len(requests) % 3 == 2:
                widgets = message.rerun_script.widget_states.widgets
                input_types.append((widgets[0].id.rsplit("-", 1)[-1], widgets[0].WhichOneof("value")))
                assert len(widgets) == 2 and widgets[1].id.endswith("-live")
                if widgets[0].WhichOneof("value") == "bytes_value":
                    byte_payloads.append(widgets[0].bytes_value)
        elif message.WhichOneof("type") == "new_session":
            sessions.append(message.new_session.initialize.session_id)
            if scenario in ("disabled-json", "encoding", "text-length", "text-reset", "text-source", "text-bound", "text-bound-peer", "text-repeat", "text-empty", "text-validation", "text-unkeyed", "text-unkeyed-area", "text-area-height"):
                environment = message.new_session.initialize.environment_info
                assert environment.streamlit_version == "1.66.1" and environment.python_version == "3.14.7.final.0"
        elif message.WhichOneof("type") == "script_finished":
            finishes.append(message.script_finished)
        elif message.WhichOneof("type") == "page_info_changed":
            urls.append(message.page_info_changed.query_string)
        elif message.WhichOneof("type") == "delta" and message.delta.WhichOneof("type") == "new_element":
            element = message.delta.new_element
            if scenario in ("text-length", "text-reset", "text-source") and element.WhichOneof("type") in ("text_input", "text_area"):
                kind = element.WhichOneof("type")
                widget = getattr(element, kind)
                length_ids.append(widget.id)
                length_widgets.append((kind, widget.default if widget.HasField("default") else None, widget.max_chars,
                                       widget.set_value, widget.value if widget.HasField("value") else None))
            if scenario.startswith("disabled-types") or scenario in ("disabled-json", "encoding"):
                assert list(message.metadata.delta_path) == [0, slot]
                slot += 1
            if element.WhichOneof("type") == "exception":
                errors.append(element.exception)
                phase = requests[-1].split("phase=")[1].split("&")[0]
                error_phases.append(phase)
                if scenario == "disabled-json":
                    number = int(phase.rsplit("-", 1)[1])
                    expected_type, expected_message = DISABLED_JSON_ERRORS[number]
                    assert element.exception.type == expected_type and element.exception.message == expected_message
                    assert list(message.metadata.delta_path) == [0, 0]
                elif scenario.startswith("disabled-types"):
                    assert element.exception.type == "TypeError"
                    number = int(phase.rsplit("-", 1)[1])
                    expected = {0: "'str' object cannot be interpreted as an integer", 1: "'str' object cannot be interpreted as an integer",
                                2: "must be real number, not str", 14: "expected bytes, str found",
                                15: "'str' object cannot be interpreted as an integer",
                                16: "expected bytes, str found", 17: "expected bytes, str found", 18: "expected bytes, str found"}.get(number)
                    if scenario == "disabled-types-isolated":
                        assert number in (0, 1, 2, 3) and (phase.startswith("malformed-") or number == 3)
                    if expected is None:
                        kind = {8: "list", 9: "dict"}.get(number, "google._upb._message.RepeatedScalarContainer") if scenario in ("disabled-types-more", "disabled-types-bytes") else "google._upb._message.RepeatedScalarContainer"
                        expected = f"cannot use '{kind}' as a dict key (unhashable type: '{kind}')"
                    assert element.exception.message == expected
                    assert list(message.metadata.delta_path) == [0, 1 if number in (0, 1, 2, 14, 15, 16, 17, 18) else 0]
                else:
                    assert scenario == "disabled", "reference must not contain an unexpected exception"
                    assert element.exception.type == "TypeError"
                    assert element.exception.message == "'str' object cannot be interpreted as an integer"
                assert not element.exception.message_is_markdown and not element.exception.is_streamlit_exception
                if scenario.startswith("disabled-types") or scenario == "disabled-json":
                    assert element.exception.stack_trace
                else:
                    assert len(element.exception.stack_trace) == 2
            if element.WhichOneof("type") == "json":
                snapshots.append(json.loads(element.json.body))
    expected_errors = {"disabled": 1, "disabled-types": 13, "disabled-types-isolated": 5, "disabled-types-more": 15, "disabled-types-bytes": 18, "disabled-json": 38}.get(scenario, 0)
    assert len(errors) == expected_errors
    if scenario == "disabled-json":
        metadata = json.loads((HERE / "reference-browser/queryparams/disabled-json/runtime.json").read_text(encoding="utf-8-sig"))
        assert metadata["streamlit_version"] == "1.66.1" and metadata["python_version"] == "3.14.7"
        assert metadata["scope"].startswith("Post-capture")
        assert len(set(sessions)) == 24 and len(sessions) == 72
        assert all(len(set(sessions[index:index + 3])) == 1 for index in range(0, 72, 3))
        assert histories == [False] * 72 and finishes == [0] * 72
        assert json_payloads == list(DISABLED_JSON_INPUTS)
        assert [query.split("phase=")[1].split("&")[0] for query in requests] == [phase for number in range(24) for phase in ("load", f"malformed-{number}", f"recovery-{number}")]
        assert error_phases == [phase for number in DISABLED_JSON_ERRORS for phase in (f"malformed-{number}", f"recovery-{number}")]
        assert len(snapshots) == 34
        assert urls == [query for number in range(17, 22) for query in (f"case=disabled&phase=malformed-{number}&text=base", f"case=disabled&phase=malformed-{number}")]
        for report in snapshots:
            phase = report["phase"]
            assert [report[key] for key in ("plain", "bound", "text", "check")] == ["safe", "y", "url", False]
            if phase == "load":
                assert report["callbacks"] == [] and report["live"] == "ready"
            else:
                number = int(phase.rsplit("-", 1)[1])
                assert 17 <= number <= 21
                recovery = phase.startswith("recovery-")
                assert report["callbacks"] == ["live"] * (2 if recovery else 1)
                assert report["live"] == f"step-{number * 3 + (2 if recovery else 1)}"
    elif scenario in ("disabled-types-isolated", "disabled-types-more", "disabled-types-bytes"):
        case_count = {"disabled-types-isolated": 8, "disabled-types-more": 16, "disabled-types-bytes": 19}[scenario]
        assert len(set(sessions)) == case_count and len(sessions) == case_count * 3
        assert all(len(set(sessions[index:index + 3])) == 1 for index in range(0, case_count * 3, 3))
        assert histories == [False] * (case_count * 3) and finishes == [0] * (case_count * 3)
        assert [query.split("phase=")[1].split("&")[0] for query in requests] == [phase for number in range(case_count) for phase in ("load", f"malformed-{number}", f"recovery-{number}")]
        expected_types = [("bound", kind) for kind in ("bool_value", "int_value", "double_value", "string_array_value", "json_value")] + [("plain", "bool_value"), ("text", "bool_value"), ("check", "string_value")]
        expected_phases = ["malformed-0", "malformed-1", "malformed-2", "malformed-3", "recovery-3"]
        if case_count >= 16:
            expected_types += [("bound", kind) for kind in ("json_value", "json_value", "json_value", "json_value", "int_array_value", "double_array_value", "bytes_value", "trigger_value")]
            expected_phases += [phase for number in (8, 9, 12, 13) for phase in (f"malformed-{number}", f"recovery-{number}")] + ["malformed-14", "malformed-15"]
        if case_count == 19:
            expected_types += [("bound", "bytes_value")] * 3
            expected_phases += [f"malformed-{number}" for number in (16, 17, 18)]
            assert byte_payloads == [b"", b"x", b"'\0\\\r\n", bytes(range(256))]
        assert input_types == expected_types and error_phases == expected_phases
        assert len(snapshots) == {8: 19, 16: 33, 19: 39}[case_count]
        for report in snapshots:
            phase = report["phase"]
            assert [report[key] for key in ("plain", "bound", "text", "check")] == ["safe", "y", "url", False]
            if phase == "load":
                assert report["callbacks"] == [] and report["live"] == "ready"
            else:
                number = int(phase.rsplit("-", 1)[1])
                recovery = phase.startswith("recovery-")
                assert report["callbacks"] == ["live"] * (2 if recovery else 1)
                assert report["live"] == f"step-{number * 3 + (2 if recovery else 1)}"
    elif scenario == "disabled-types":
        assert len(set(sessions)) == 1 and len(sessions) == 17
        assert len(snapshots) == 4 and histories == [False] * 17 and finishes == [0] * 17
        assert error_phases[:4] == ["malformed-0", "malformed-1", "malformed-2", "malformed-3"]
        assert error_phases[4:] == ["recovery-3", *[phase for number in range(4, 8) for phase in (f"malformed-{number}", f"recovery-{number}")]]
    elif scenario == "navigation-rerun":
        assert requests == ["probe=load", "probe=switch"] and histories == [False, False]
        assert finishes == [0, 2, 0]
    elif scenario == "rerun-queue":
        assert requests == ["case=queue&phase=warm", "case=queue&phase=queue"] and histories == [False, False]
        assert finishes == [0, 2, 0]
    elif scenario == "rerun-messages":
        assert requests == [capture["query_string"]] and histories == [False]
        assert finishes == [2, 0]
    elif scenario == "rerun":
        assert len(requests) == 5 and requests[0] == capture["query_string"]
        assert histories == [False] * 4 + [True] and finishes == [2, 0] * 5
        assert [query.split("phase=")[1].split("&")[0] for query in requests] == ["load", "frontend", "early", "assign", "history"]
    elif scenario in ("disabled", "disabled-valid"):
        assert len(requests) == 9 and requests[0] == capture["query_string"]
        assert histories == [False] * 9 and finishes == [0] * 9
        assert [query.split("phase=")[1].split("&")[0] for query in requests] == [
            "load", "forge", "malformed" if scenario == "disabled" else "invalid-url", "code", "hidden", "remount", "enabled", "interactive", "redisable"]
    elif scenario == "text-length":
        configurations = [(kind, limit, default) for kind in ("input", "area") for limit, default in (("5", "long"), ("0", "long"), ("none", "long"), ("5", "none"))]
        assert requests == [f"case=form-max-chars-cjk&probe=length&kind={kind}&limit={limit}&default={default}&phase={phase}"
                            for kind, limit, default in configurations for phase in TEXT_LENGTH_PHASES]
        assert histories == [False] * 72 and finishes == [0] * 72 and urls == []
        assert len(sessions) == 72 and len(set(sessions)) == 8
        assert all(len(set(sessions[index:index + 9])) == 1 for index in range(0, 72, 9))
        assert len(snapshots) == 72 and len(length_widgets) == 72
        assert length_inputs == list(TEXT_LENGTH_INPUTS.items()) * 8
        for number, (kind, limit, default) in enumerate(configurations):
            calls = []
            values = TEXT_LENGTH_VALUES[number % 4]
            for stage, (phase, value) in enumerate(zip(TEXT_LENGTH_PHASES, values, strict=True)):
                if phase in TEXT_LENGTH_INPUTS and value != values[stage - 1]:
                    calls.append(value)
                assert snapshots[number * 9 + stage] == {"phase": phase, "value": value, "state": value, "callbacks": calls}
                assert length_widgets[number * 9 + stage] == ("text_input" if kind == "input" else "text_area",
                    None if default == "none" else "abcdef🧊", 5 if limit == "5" else 0, phase == "assign", "code長🧊extra" if phase == "assign" else None)
    elif scenario == "text-reset":
        assert requests == [f"case=form-max-chars-cjk&probe=length&kind={kind}&limit={limit}&default={default}&phase={phase}"
                            for kind in ("input", "area") for limit, default, phase in TEXT_RESET_STEPS]
        assert histories == [False] * 24 and finishes == [0] * 24 and urls == []
        assert len(sessions) == 24 and len(set(sessions)) == 2
        assert len(set(sessions[:12])) == len(set(sessions[12:])) == 1
        assert len(snapshots) == len(length_widgets) == len(length_ids) == 24
        assert length_inputs == list(TEXT_RESET_INPUTS.items()) * 2
        for number, kind in enumerate(("text_input", "text_area")):
            calls = []
            for stage, ((limit, default, phase), value) in enumerate(zip(TEXT_RESET_STEPS, TEXT_RESET_VALUES, strict=True)):
                if phase in TEXT_RESET_INPUTS:
                    calls.append(value)
                assert snapshots[number * 12 + stage] == {"phase": phase, "value": value, "state": value, "callbacks": calls}
                assert length_widgets[number * 12 + stage] == (kind, None if default == "none" else "abcdef🧊", 0 if limit == "none" else int(limit), False, None)
            identities = length_ids[number * 12:(number + 1) * 12]
            assert [identities.index(identity) for identity in identities] == [0, 0, 2, 2, 0, 5, 6, 6, 6, 6, 0, 0]
        assert set(length_ids[:12]).isdisjoint(length_ids[12:])
    elif scenario == "text-source":
        assert requests == [f"case=form-max-chars-cjk&probe=length&kind={kind}&limit={limit}&default=long&phase={phase}"
                            for kind in ("input", "area") for limit, phase, _ in TEXT_SOURCE_STEPS]
        assert histories == [False] * 20 and finishes == [0] * 20 and urls == []
        assert len(sessions) == 20 and len(set(sessions)) == 2
        assert len(set(sessions[:10])) == len(set(sessions[10:])) == 1
        assert len(snapshots) == len(length_widgets) == len(length_ids) == 20
        assert length_inputs == [(phase, value) for _, phase, value in TEXT_SOURCE_STEPS if value is not None] * 2
        for number, kind in enumerate(("text_input", "text_area")):
            calls = []
            for stage, ((limit, phase, _), value, callback) in enumerate(zip(TEXT_SOURCE_STEPS, TEXT_SOURCE_VALUES, TEXT_SOURCE_CALLBACKS, strict=True)):
                if callback is not None:
                    calls.append(callback)
                assert snapshots[number * 10 + stage] == {"phase": phase, "value": value, "state": value, "callbacks": calls}
                assert length_widgets[number * 10 + stage] == (kind, "abcdef🧊", int(limit), phase == "assign", "code長🧊extra" if phase == "assign" else None)
            identities = length_ids[number * 10:(number + 1) * 10]
            assert [identities.index(identity) for identity in identities] == [0, 0, 2, 3, 3, 0, 2, 2, 0, 0]
        assert set(length_ids[:10]).isdisjoint(length_ids[10:])
    elif scenario == "text-area-height":
        heights = (-2147483648, -1, 0, 1, 67, 68, 94, 96, 2147483647)
        phases = ("load", "submit", "recover")
        prefix = "case=form-max-chars-cjk&probe=length&kind=area&limit=5&default=long&height_errors=on&height="
        assert requests == [prefix + str(height if phase == "submit" else 122) + "&phase=" + phase for height in heights for phase in phases]
        assert histories == [False] * 27 and finishes == [0] * 27 and len(sessions) == 27 and len(set(sessions)) == 9
        assert [sessions.index(session) for session in sessions] == [number // 3 * 3 for number in range(27)]
        assert not urls and not errors
        locked = {"type": "StreamlitWidgetAlreadyInstantiatedError", "message": (
            "`st.session_state['cjk_note']` cannot be modified after the widget with that key is instantiated. "
            "Assign `st.session_state['cjk_note']` before creating the widget, or update it from an `on_change` or `on_click` callback, "
            "which runs before the widget is instantiated. If this is a read-only session state key "
            "(buttons, file and media inputs, `st.data_editor`, forms, chart or `ButtonColumn` selections), "
            "store the value under a different session state key.")}
        duplicate = {"type": "StreamlitDuplicateElementKey", "message": (
            "There are multiple elements with the same `key='cjk_note'`. To fix this, "
            "please make sure that the `key` argument is unique for each element you create.")}
        expected = []
        widget_heights = []
        for height in heights:
            for phase in phases:
                invalid = phase == "submit" and height <= 0
                value = "abcde" if phase == "load" else "EDITE"
                expected.append({"phase": phase, "value": None if invalid else value, "state": value,
                                 "callbacks": [] if phase == "load" else ["EDITE"],
                                 "error": {"type": "StreamlitInvalidHeightError", "message": (
                                     f"Invalid height value: {height}. Height must be either a positive integer (pixels), 'stretch', or 'content'.")} if invalid else None,
                                 "locked": locked if invalid else None, "duplicate": duplicate if invalid else None})
                if not invalid:
                    widget_heights.append(height if phase == "submit" else 122)
        assert snapshots == expected
        run = -1
        ordered = []
        for frame in capture["frames"]:
            if frame["direction"] == "client->server":
                run += 1
            element = frame["message"].get("delta", {}).get("new_element", {})
            if "text_area" in element:
                ordered.append((run, "widget"))
            if "json" in element:
                ordered.append((run, "report"))
        expected_order = []
        for number in range(27):
            if not (number % 3 == 1 and heights[number // 3] <= 0):
                expected_order.append((number, "widget"))
            expected_order.append((number, "report"))
        assert len(ordered) == 51 and ordered == expected_order
        elements = [frame["message"]["delta"]["new_element"] for frame in capture["frames"]
                    if "text_area" in frame["message"].get("delta", {}).get("new_element", {})]
        assert len(elements) == 24 and [element["height_config"]["pixel_height"] for element in elements] == widget_heights
        ids = [element["text_area"]["id"] for element in elements]
        assert len(set(ids)) == 1 and ids[0].endswith("-cjk_note")
        for element in elements:
            widget = element["text_area"]
            assert widget["default"] == "abcdef🧊" and widget["max_chars"] == 5
            assert not widget.get("set_value", False) and "value" not in widget
            assert element["width_config"] == {"use_stretch": True}
        clients = [frame["message"]["rerun_script"] for frame in capture["frames"] if frame["direction"] == "client->server"]
        for number, client in enumerate(clients):
            assert client.get("widget_states", {}).get("widgets", []) == ([{"id": ids[0], "string_value": "EDITEDtail"}] if number % 3 == 1 else [])
    elif scenario in ("text-unkeyed", "text-unkeyed-area"):
        area = scenario == "text-unkeyed-area"
        kind = "area" if area else "input"
        phases = ("load", "edit", "disabled", "none", "hidden", "ignore", "collapsed", "width", "edit-wide", "help", "restore-help", "restore-width")
        policies = ("normal", "normal", "disabled", "none", "hidden", "ignore", "collapsed") + ("normal",) * 5
        prefix = f"case=form-max-chars-cjk&probe=length&kind={kind}&limit=5&default=long&unkeyed=on&policy="
        expected_requests = [prefix + policy + ("&pixels=320" if 7 <= number <= 10 else "") + ("&help=new" if number == 9 else "") + "&phase=" + phase
                             for number, (phase, policy) in enumerate(zip(phases, policies, strict=True))]
        if area:
            extra = (("height", 120, None), ("edit-tall", 120, None), ("resize", 240, None), ("placeholder", 240, "hint"),
                     ("edit-placeholder", 240, "hint"), ("change-placeholder", 240, "next"), ("restore-placeholder", 240, None),
                     ("restore-height", 120, None), ("restore-default", None, None))
            expected_requests.extend(prefix + "normal" + (f"&height={height}" if height is not None else "")
                                     + (f"&placeholder={placeholder}" if placeholder is not None else "") + "&phase=" + phase
                                     for phase, height, placeholder in extra)
            phases += tuple(phase for phase, _, _ in extra)
        count = 21 if area else 12
        assert requests == expected_requests
        assert histories == [False] * count and finishes == [0] * count and len(sessions) == count and len(set(sessions)) == 1
        assert not urls
        values = ("abcde",) + ("KEEP🧊",) * 6 + ("abcde", "EDIT🧊") + ("abcde",) * 3
        if area:
            values += ("abcde", "TALL🧊", "abcde", "abcde", "PLACE", "abcde", "abcde", "abcde", "abcde")
        assert snapshots == [{"phase": phase, "value": value, "state": None, "has_key": False,
                              "callbacks": ["changed"] * (0 if number == 0 else 1 if number < 8 else 2 if number < 13 else 3 if number < 16 else 4)}
                             for number, (phase, value) in enumerate(zip(phases, values, strict=True))]
        element_kind = "text_area" if area else "text_input"
        elements = [frame["message"]["delta"]["new_element"] for frame in capture["frames"]
                    if element_kind in frame["message"].get("delta", {}).get("new_element", {})]
        widgets = [element[element_kind] for element in elements]
        assert len(widgets) == count
        ids = [widget["id"] for widget in widgets]
        assert all(identity.endswith("-None") for identity in ids)
        classes = [0] * 7 + [7, 7, 9, 7, 0]
        if area:
            classes += [12, 12, 14, 15, 15, 17, 14, 12, 0]
        assert [ids.index(identity) for identity in ids] == classes
        for number, (element, widget) in enumerate(zip(elements, widgets, strict=True)):
            assert widget["default"] == "abcdef🧊" and widget["max_chars"] == 5
            assert not widget.get("set_value", False) and "value" not in widget and "query_param_key" not in widget
            assert widget.get("disabled", False) == (number == 2)
            assert widget.get("ignore_rerun", False) == (number == 5)
            assert widget["label_visibility"].get("value", "VISIBLE") == {4: "HIDDEN", 6: "COLLAPSED"}.get(number, "VISIBLE")
            assert widget.get("help", "") == ("new" if number == 9 else "")
            assert element.get("width_config") == ({"pixel_width": 320} if 7 <= number <= 10 else {"use_stretch": True})
            if area:
                height = 120 if number in (12, 13, 19) else 240 if 14 <= number <= 18 else 94 if number == 6 else 122
                assert element.get("height_config") == {"pixel_height": height}
                assert widget.get("placeholder", "") == {15: "hint", 16: "hint", 17: "next"}.get(number, "")
        clients = [frame["message"]["rerun_script"] for frame in capture["frames"] if frame["direction"] == "client->server"]
        for number, client in enumerate(clients):
            value = {1: "KEEP🧊tail", 8: "EDIT🧊tail", 13: "TALL🧊tail", 16: "PLACEextra"}.get(number)
            assert client.get("widget_states", {}).get("widgets", []) == ([] if value is None else [{"id": ids[number - 1], "string_value": value}])
    elif scenario == "text-validation":
        kinds = ("default", "default", "email", "url", "phone", "search", "password", "default", "default", "email", "url", "email", "email", "default")
        rules = ("inherit",) * 7 + ("pattern-a", "pattern-a", "pattern-b", "off", "off", "inherit", "inherit")
        phases = ("load", "edit", "email", "url", "phone", "search", "password", "rule", "edit-rule", "message", "off", "type-off", "restore", "ordinary")
        prefix = "case=form-max-chars-cjk&probe=length&kind=input&limit=5&default=long&input_type="
        assert requests == [prefix + kind + "&validation=" + rule + "&phase=" + phase for kind, rule, phase in zip(kinds, rules, phases, strict=True)]
        assert histories == [False] * 14 and finishes == [0] * 14 and len(sessions) == 14 and len(set(sessions)) == 1
        assert not urls
        values = ("abcde",) + ("KEEP🧊",) * 6 + ("abcde", "AAAAA", "AAAAA") + ("abcde",) * 4
        assert snapshots == [{"phase": phase, "value": value, "state": value,
                              "callbacks": ([] if number == 0 else ["KEEP🧊"] if number < 8 else ["KEEP🧊", "AAAAA"])}
                             for number, (phase, value) in enumerate(zip(phases, values, strict=True))]
        widgets = [frame["message"]["delta"]["new_element"]["text_input"] for frame in capture["frames"]
                   if "text_input" in frame["message"].get("delta", {}).get("new_element", {})]
        assert len(widgets) == 14
        ids = [widget["id"] for widget in widgets]
        assert [ids.index(identity) for identity in ids] == [0] * 7 + [7] * 3 + [10] * 2 + [0] * 2
        defaults = {"email": (r"^[^\s@]+@[^\s@]+\.[^\s@]+$", "Enter a valid email address."),
                    "url": (r"^([Hh][Tt][Tt][Pp][Ss]?://)?[^\s/.]+\.[^\s]+$", "Enter a valid URL.")}
        for widget, kind, rule in zip(widgets, kinds, rules, strict=True):
            expected = ("", None) if rule == "off" else (("^A+$", "First message" if rule == "pattern-a" else "Second message")
                        if rule.startswith("pattern-") else defaults.get(kind, (None, None)))
            assert (widget.get("validate_regex"), widget.get("validate_message")) == expected
            assert widget.get("type", "DEFAULT") == kind.upper()
            assert widget["default"] == "abcdef🧊" and widget["max_chars"] == 5
            assert not widget.get("set_value", False) and "value" not in widget and "query_param_key" not in widget
        clients = [frame["message"]["rerun_script"] for frame in capture["frames"] if frame["direction"] == "client->server"]
        for number, client in enumerate(clients):
            value = {1: "KEEP🧊tail", 8: "AAAAAextra"}.get(number)
            assert client.get("widget_states", {}).get("widgets", []) == ([] if value is None else [{"id": ids[number - 1], "string_value": value}])
    elif scenario == "text-empty":
        prefix = "case=form-max-chars-cjk&probe=length&kind=input&bind=on&limit=5&default=long&phase="
        phases = ("load", "assign-none", "assign-none", "url-only", "empty-url", "frontend", "assign-none", "history-missing", "history-empty", "recover")
        tails = ("seed", "seed", "None", "None", "", "", "abcde", None, "", "ok")
        assert requests == [prefix + phase + ("&cjk_note=" + value if value is not None else "") for phase, value in zip(phases, tails, strict=True)]
        assert histories == [False] * 7 + [True, True, False]
        assert finishes == [0] * 10 and len(sessions) == 10 and len(set(sessions)) == 1
        values = ("seed", None, None, "None", "", "abcde", None, None, "", "")
        assert snapshots == [{"phase": phase, "value": value, "state": value, "callbacks": [] if number < 5 else ["abcde"]}
                             for number, (phase, value) in enumerate(zip(phases, values, strict=True))]
        assert urls == [prefix + "assign-none"] * 3
        widgets = [frame["message"]["delta"]["new_element"]["text_input"] for frame in capture["frames"]
                   if "text_input" in frame["message"].get("delta", {}).get("new_element", {})]
        assert len(widgets) == 10 and len({widget["id"] for widget in widgets}) == 1
        for number, widget in enumerate(widgets):
            assert widget.get("default") == (None if number in (1, 2, 3, 6, 7, 8) else "abcdef🧊")
            assert widget["max_chars"] == 5 and widget["query_param_key"] == "cjk_note"
            assert widget.get("set_value", False) == (number not in (5, 9))
            assert widget.get("value") == (values[number] if number not in (5, 9) else None)
        submitted = (None, None, None, None, None, "abcdef🧊", None, "staleTEXT", "staleTEXT", "")
        clients = [frame["message"]["rerun_script"] for frame in capture["frames"] if frame["direction"] == "client->server"]
        for client, value in zip(clients, submitted, strict=True):
            inputs = client.get("widget_states", {}).get("widgets", [])
            assert inputs == ([] if value is None else [{"id": widgets[0]["id"], "string_value": value}])
    elif scenario == "text-repeat":
        prefix = "case=form-max-chars-cjk&probe=length&kind=input&bind=on&limit=5&default=long&phase="
        assert requests == [prefix + "load&cjk_note=first&cjk_note=ok", prefix + "repeat-unchanged&cjk_note=again&cjk_note=ok",
                            prefix + "repeat-truncated&cjk_note=first&cjk_note=LONGEST"]
        assert histories == [False] * 3 and finishes == [0] * 3 and len(sessions) == 3 and len(set(sessions)) == 1
        assert snapshots == [{"phase": phase, "value": value, "state": value, "callbacks": []}
                             for phase, value in (("load", "ok"), ("repeat-unchanged", "ok"), ("repeat-truncated", "LONGE"))]
        assert urls == [prefix + "repeat-truncated&cjk_note=LONGE"]
        widgets = [frame["message"]["delta"]["new_element"]["text_input"] for frame in capture["frames"]
                   if "text_input" in frame["message"].get("delta", {}).get("new_element", {})]
        assert len(widgets) == 3 and len({widget["id"] for widget in widgets}) == 1
        for widget, value in zip(widgets, ("ok", "ok", "LONGE"), strict=True):
            assert widget["default"] == "abcdef🧊" and widget["max_chars"] == 5 and widget["query_param_key"] == "cjk_note"
            assert widget["set_value"] and widget["value"] == value
    elif scenario in ("text-bound", "text-bound-peer"):
        assert len(requests) == 12 and requests[0] == capture["query_string"]
        assert finishes == [0] * 12 and len(sessions) == 12 and len(set(sessions)) == 1
    elif scenario == "encoding":
        assert requests == [case[0] for case in QUERY_ENCODING_CASES]
        assert histories == [False] * 16 and finishes == [0] * 16
        assert len(sessions) == 16 and len(set(sessions)) == 1
        assert len(snapshots) == 128
        for number, (_, values, pairs) in enumerate(QUERY_ENCODING_CASES):
            assert snapshots[number * 8] == {"stage": "load", "value": values[-1], "all": values, "pairs": pairs, "empty": None}
    elif scenario == "binding":
        assert capture["query_string"] == requests[0]
        assert requests == ["case=binding&phase=load", "case=binding&phase=active&bound=y&text=hello",
                            "case=binding&phase=hidden&bound=y&text=hello&BOUND=case-sensitive",
                            "case=binding&phase=released&BOUND=case-sensitive"]
        assert finishes == [0, 0, 0, 0]
    elif scenario == "seed":
        assert len(requests) == 8 and requests[0] == capture["query_string"]
        assert [query.split("phase=")[1].split("&")[0] for query in requests] == ["initial", "frontend", "again", "invalid", "empty", "assign", "history", "history-missing"]
        assert histories == [False] * 6 + [True, True] and finishes == [0] * 8
    elif scenario == "seed-code":
        assert len(requests) == 2 and requests[0] == capture["query_string"]
        assert histories == [False, True] and finishes == [0, 0]
    else:
        assert requests == [capture["query_string"]] and finishes == [0]
    return snapshots, urls


def test_query_param_values_oracle_is_complete_and_backed_by_wire():
    snapshots, urls = read_query_param_capture("values")
    assert [state["stage"] for state in snapshots] == ["load", "replace", "append", "empty-list", "remove-empty", "remove-tag", "clear", "restore"]
    assert snapshots[0]["value"] == "second" and snapshots[0]["all"] == ["first", "second"]
    assert snapshots[3]["empty"] == "" and snapshots[3]["pairs"][-1] == ["empty", ""]
    assert snapshots[4]["empty"] is None and snapshots[5]["value"] is None
    assert snapshots[6]["pairs"] == [] and snapshots[7]["value"] == "last"
    assert len(urls) == 7 and urls[2] == urls[3] == urls[1]
    assert urls[0].startswith("z=last&tag=replacement&tag=tail&a=first&blank=")
    assert urls[1].endswith("&new=%E4%B8%AD%E6%96%87+%2B+text")
    assert urls[-2:] == ["", "tag=again&tag=last"]


def test_query_param_encoding_oracle_keeps_exact_values_and_writes():
    from urllib.parse import parse_qsl, urlencode

    snapshots, urls = read_query_param_capture("encoding")
    assert len(snapshots) == 128 and len(urls) == 112
    for number, (query, _, _) in enumerate(QUERY_ENCODING_CASES):
        states = snapshots[number * 8:(number + 1) * 8]
        assert [state["stage"] for state in states] == ["load", "replace", "append", "empty-list", "remove-empty", "remove-tag", "clear", "restore"]
        assert states[1]["all"] == ["replacement", "tail"] and states[1]["value"] == "tail"
        assert states[3]["empty"] == "" and states[4]["empty"] is None
        assert states[5]["all"] == [] and states[5]["value"] is None
        assert states[6]["pairs"] == [] and states[7]["all"] == ["again", "last"]

        # 标准库只构造写回 URL；初始解码内容另由固定字面量约束。
        parameters = {}
        for key, value in parse_qsl(query, keep_blank_values=True):
            parameters.setdefault(key, []).append(value)
        parameters["tag"] = ["replacement", "tail"]
        expected = [urlencode(parameters, doseq=True)]
        parameters["new"] = ["中文 + text"]
        expected += [urlencode(parameters, doseq=True)] * 3
        del parameters["tag"]
        expected += [urlencode(parameters, doseq=True), "", "tag=again&tag=last"]
        assert urls[number * 7:(number + 1) * 7] == expected
    assert urls[0] == "tag=replacement&tag=tail&%25+f=key&keep=ok"


def test_text_length_reference_separates_wire_defaults_and_native_assignments():
    snapshots, urls = read_query_param_capture("text-length")
    assert not urls
    assert snapshots[3]["callbacks"] == snapshots[2]["callbacks"]
    assert snapshots[6]["value"] == snapshots[7]["value"] == "code長🧊extra"
    assert snapshots[9]["value"] == "" and snapshots[18]["value"] == "abcdef🧊" and snapshots[27]["value"] is None


def test_text_reset_reference_preserves_keyed_identity_equivalence_and_state():
    snapshots, urls = read_query_param_capture("text-reset")
    assert not urls and snapshots[:12] == snapshots[12:]


def test_text_source_reference_keeps_previous_codec_callback_then_native_assignment():
    snapshots, urls = read_query_param_capture("text-source")
    assert not urls and snapshots[:10] == snapshots[10:]
    assert snapshots[2]["value"] == "abc" and snapshots[2]["callbacks"][-1] == "ABCDE"
    assert snapshots[3]["value"] == snapshots[4]["value"] == "code長🧊extra"
    assert snapshots[5]["callbacks"][-1] == ""


def read_bound_text_capture(peer, capture=None):
    from urllib.parse import urlencode

    # 1. 原始 PB/摘要和生命周期先由已有读取器绑定。
    scenario = "text-bound-peer" if peer else "text-bound"
    if capture is None:
        capture = json.loads((HERE / f"reference-browser/queryparams/{scenario}/trace.json").read_text(encoding="utf-8"))
    assert capture["scenario"] == scenario
    snapshots, urls = read_query_param_capture(scenario, capture)
    runs = []
    for frame in capture["frames"]:
        message = frame["message"]
        if "rerun_script" in message:
            runs.append({"request": message["rerun_script"], "events": []})
        if "page_info_changed" in message:
            runs[-1]["events"].append(("url", message["page_info_changed"]["query_string"]))
        element = message.get("delta", {}).get("new_element", {})
        if "text_input" in element:
            runs[-1]["events"].append(("widget", element["text_input"]))
        if "json" in element:
            runs[-1]["events"].append(("state", json.loads(element["json"]["body"])))
    assert len(runs) == 12 and len(snapshots) == 12
    first_widgets = [value for kind, value in runs[0]["events"] if kind == "widget"]
    ids = {widget["id"].rsplit("-", 1)[-1]: widget["id"] for widget in first_widgets}
    assert set(ids) == ({"cjk_note", "live"} if peer else {"cjk_note"})
    corrections = {0: TEXT_BOUND_VALUES[0], 1: "UVWXY", 2: None, 4: "HISTO", 5: "code長🧊extra", 6: "HISTO", 10: TEXT_BOUND_VALUES[10]}
    expected_urls, calls, peer_calls, live = [], [], [], "ready"

    # 2. 固定输入、来源优先级、URL 修正时机和两个控件各自的同步字段。
    for index, ((phase, url_value, incoming, history), value) in enumerate(zip(TEXT_BOUND_STEPS, TEXT_BOUND_VALUES, strict=True)):
        prefix = "case=form-max-chars-cjk&probe=length&kind=input&bind=on&limit=5&default=long" + ("&peer=on" if peer else "") + f"&phase={phase}"
        request = runs[index]["request"]
        assert request["query_string"] == prefix + ("&" + urlencode({"cjk_note": url_value}, doseq=True) if url_value is not None else "")
        assert request.get("is_history_navigation", False) == history
        expected_input = [] if incoming is None else [{"id": ids["cjk_note"], "string_value": incoming}]
        if peer and history:
            live = f"peer-{index}"
            peer_calls.append(live)
            expected_input.append({"id": ids["live"], "string_value": live})
        assert request.get("widget_states", {}).get("widgets", []) == expected_input
        if index == 3:
            calls.append("EDITE")
        if index == 11:
            calls.append("recov")
        report = {"phase": phase, "value": value, "state": value, "callbacks": calls.copy()}
        if peer:
            report.update(live=live, peer_callbacks=peer_calls.copy())
        expected = []
        if index in corrections:
            corrected = corrections[index]
            corrected_url = prefix + ("&" + urlencode({"cjk_note": corrected}) if corrected is not None else "")
            expected.append(("url", corrected_url))
            expected_urls.append(corrected_url)
        set_value = index not in (2, 3, 11)
        widgets = [value for kind, value in runs[index]["events"] if kind == "widget"]
        assert len(widgets) == (2 if peer else 1)
        for slot, widget in enumerate(widgets):
            key = "cjk_note" if slot == 0 else "live"
            assert widget["id"] == ids[key]
            assert widget.get("default") == ("abcdef🧊" if slot == 0 else "ready")
            assert widget.get("max_chars", 0) == (5 if slot == 0 else 0)
            assert widget.get("query_param_key") == ("cjk_note" if slot == 0 else None)
            assert widget.get("set_value", False) == (set_value if slot == 0 else False)
            assert widget.get("value") == (value if slot == 0 and set_value else None)
            expected.append(("widget", widget))
        expected.append(("state", report))
        assert runs[index]["events"] == expected
    assert urls == expected_urls and len(urls) == 7
    return snapshots


def test_bound_text_reference_corrects_urls_and_preserves_only_unbound_history_callbacks():
    single = read_bound_text_capture(False)
    peer = read_bound_text_capture(True)
    assert single == [{key: value for key, value in report.items() if key not in ("live", "peer_callbacks")} for report in peer]


def test_area_height_reference_preserves_registration_errors_and_recovery():
    read_query_param_capture("text-area-height")


@pytest.mark.parametrize("mutation", ["early-state", "early-release", "error-type", "error-message", "recovery", "positive-rejected"])
def test_area_height_gate_rejects_coherent_wrong_wire(mutation):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / "reference-browser/queryparams/text-area-height/trace.json").read_text(encoding="utf-8"))
    target = 2 if mutation == "recovery" else 10 if mutation == "positive-rejected" else 1
    run = -1
    remove = []
    for position, frame in enumerate(capture["frames"]):
        if frame["direction"] == "client->server":
            run += 1
            continue
        if run != target:
            continue
        message = ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        element = message.delta.new_element
        if mutation == "positive-rejected" and element.WhichOneof("type") == "text_area":
            remove.append(position)
        if element.WhichOneof("type") != "json":
            continue
        report = json.loads(element.json.body)
        if mutation == "early-state":
            report.update(state="abcde", callbacks=[])
        elif mutation == "early-release":
            report.update(locked=None, duplicate=None)
        elif mutation == "error-type":
            report["error"]["type"] = "StreamlitAPIException"
        elif mutation == "error-message":
            report["error"]["message"] = report["error"]["message"].replace("-2147483648", "-1")
        elif mutation == "recovery":
            report.update(value="abcde", state="abcde")
        else:
            report.update(value=None, error={"type": "StreamlitInvalidHeightError", "message": "Invalid height value: 1."})
        element.json.body = json.dumps(report)
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    for position in reversed(remove):
        del capture["frames"][position]
    with pytest.raises(AssertionError):
        read_query_param_capture("text-area-height", capture)


@pytest.mark.parametrize("scenario", ["text-unkeyed", "text-unkeyed-area"])
def test_unkeyed_text_policy_identity_reference(scenario):
    read_query_param_capture(scenario)


@pytest.mark.parametrize("scenario", ["text-unkeyed", "text-unkeyed-area"])
@pytest.mark.parametrize("mutation", ["disabled-reset", "callback-reset", "ignore-flag", "width-retain", "layout-wire"])
def test_unkeyed_text_policy_gate_rejects_coherent_wrong_wire(scenario, mutation):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / f"reference-browser/queryparams/{scenario}/trace.json").read_text(encoding="utf-8"))
    target = {"disabled-reset": 2, "callback-reset": 3, "ignore-flag": 5, "width-retain": 7, "layout-wire": 6}[mutation]
    run = -1
    for frame in capture["frames"]:
        if frame["direction"] == "client->server":
            run += 1
            continue
        if run != target:
            continue
        message = ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        element = message.delta.new_element
        widget_kind = "text_area" if scenario == "text-unkeyed-area" else "text_input"
        if mutation == "layout-wire" and element.WhichOneof("type") == widget_kind:
            element.ClearField("height_config" if scenario == "text-unkeyed-area" else "width_config")
        elif mutation == "ignore-flag" and element.WhichOneof("type") == widget_kind:
            getattr(element, widget_kind).ignore_rerun = False
        elif mutation not in ("ignore-flag", "layout-wire") and element.WhichOneof("type") == "json":
            report = json.loads(element.json.body)
            report["value"] = "KEEP🧊" if mutation == "width-retain" else "abcde"
            element.json.body = json.dumps(report)
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    with pytest.raises(AssertionError):
        read_query_param_capture(scenario, capture)


def test_keyed_text_validation_reference_distinguishes_raw_and_type_defaults():
    read_query_param_capture("text-validation")


@pytest.mark.parametrize("mutation", ["type-reset", "message-reset", "regex-wire"])
def test_keyed_text_validation_gate_rejects_coherent_wrong_wire(mutation):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / "reference-browser/queryparams/text-validation/trace.json").read_text(encoding="utf-8"))
    target = {"type-reset": 2, "message-reset": 9, "regex-wire": 12}[mutation]
    run = -1
    for frame in capture["frames"]:
        if frame["direction"] == "client->server":
            run += 1
            continue
        if run != target:
            continue
        message = ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        element = message.delta.new_element
        if mutation == "regex-wire" and element.WhichOneof("type") == "text_input":
            element.text_input.ClearField("validate_regex")
        elif mutation != "regex-wire" and element.WhichOneof("type") == "json":
            report = json.loads(element.json.body)
            report["value"] = report["state"] = "abcde"
            element.json.body = json.dumps(report)
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    with pytest.raises(AssertionError):
        read_query_param_capture("text-validation", capture)


def test_bound_text_none_empty_and_history_reference():
    read_query_param_capture("text-empty")


@pytest.mark.parametrize("mutation", ["default", "missing-clear", "literal-none", "history-value"])
def test_bound_text_none_empty_gate_rejects_coherent_wrong_wire(mutation):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / "reference-browser/queryparams/text-empty/trace.json").read_text(encoding="utf-8"))
    if mutation == "missing-clear":
        position = next(index for index, frame in enumerate(capture["frames"]) if "page_info_changed" in frame["message"])
        del capture["frames"][position]
    else:
        run = -1
        target = {"default": 1, "literal-none": 3, "history-value": 7}[mutation]
        for frame in capture["frames"]:
            if frame["direction"] == "client->server":
                run += 1
                continue
            if run != target:
                continue
            message = ForwardMsg()
            message.ParseFromString(base64.b64decode(frame["base64"]))
            element = message.delta.new_element
            if element.WhichOneof("type") == "text_input":
                if mutation == "default":
                    element.text_input.default = "abcdef🧊"
                elif mutation == "literal-none":
                    element.text_input.ClearField("value")
                else:
                    element.text_input.value = "abcde"
            elif element.WhichOneof("type") == "json" and mutation != "default":
                report = json.loads(element.json.body)
                report["value"] = report["state"] = None if mutation == "literal-none" else "abcde"
                element.json.body = json.dumps(report)
            else:
                continue
            raw = message.SerializeToString()
            frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    with pytest.raises(AssertionError):
        read_query_param_capture("text-empty", capture)


def test_bound_text_repeat_reference_preserves_raw_pairs_until_correction():
    read_query_param_capture("text-repeat")


@pytest.mark.parametrize("mutation", ["rewrite-unchanged", "first-value"])
def test_bound_text_repeat_gate_rejects_coherent_wrong_wire(mutation):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / "reference-browser/queryparams/text-repeat/trace.json").read_text(encoding="utf-8"))
    if mutation == "rewrite-unchanged":
        extra = copy.deepcopy(next(frame for frame in capture["frames"] if "page_info_changed" in frame["message"]))
        message = ForwardMsg()
        message.ParseFromString(base64.b64decode(extra["base64"]))
        message.page_info_changed.query_string = message.page_info_changed.query_string.replace("repeat-truncated", "repeat-unchanged").replace("LONGE", "ok")
        raw = message.SerializeToString()
        extra.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
        client = next(index for index, frame in enumerate(capture["frames"]) if frame["message"].get("rerun_script", {}).get("query_string", "").endswith("cjk_note=again&cjk_note=ok"))
        position = next(index for index, frame in enumerate(capture["frames"]) if index > client and "text_input" in frame["message"].get("delta", {}).get("new_element", {}))
        capture["frames"].insert(position, extra)
    else:
        run = -1
        for frame in capture["frames"]:
            if frame["direction"] == "client->server":
                run += 1
                continue
            if run != 1:
                continue
            message = ForwardMsg()
            message.ParseFromString(base64.b64decode(frame["base64"]))
            element = message.delta.new_element
            if element.WhichOneof("type") == "text_input":
                element.text_input.value = "again"
            elif element.WhichOneof("type") == "json":
                report = json.loads(element.json.body)
                report["value"] = report["state"] = "again"
                element.json.body = json.dumps(report)
            else:
                continue
            raw = message.SerializeToString()
            frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
    with pytest.raises(AssertionError):
        read_query_param_capture("text-repeat", capture)


@pytest.mark.parametrize("mutation", ["url", "history-callback", "history-value", "peer-lost"])
def test_bound_text_gate_rejects_coherent_wrong_wire(mutation):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / "reference-browser/queryparams/text-bound-peer/trace.json").read_text(encoding="utf-8"))
    run, changed = -1, False
    for frame in capture["frames"]:
        if frame["direction"] == "client->server":
            run += 1
            continue
        if run != (0 if mutation == "url" else 4):
            continue
        message = ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        element = message.delta.new_element
        if mutation == "url" and message.WhichOneof("type") == "page_info_changed":
            message.page_info_changed.query_string += "TAIL"
        elif mutation == "history-value" and element.WhichOneof("type") == "text_input" and element.text_input.query_param_key == "cjk_note":
            element.text_input.value = "OTHER"
        elif mutation != "url" and element.WhichOneof("type") == "json":
            report = json.loads(element.json.body)
            if mutation == "history-callback":
                report["callbacks"].append("OTHER")
            elif mutation == "history-value":
                report["value"] = report["state"] = "OTHER"
            else:
                report["live"] = "ready"
                report["peer_callbacks"] = []
            element.json.body = json.dumps(report)
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
        changed = True
    assert changed
    with pytest.raises(AssertionError):
        read_bound_text_capture(True, capture)


@pytest.mark.parametrize("mutation", ["callback-source", "assigned-value", "retention", "sync"])
def test_text_source_gate_rejects_coherent_wrong_wire(mutation):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / "reference-browser/queryparams/text-source/trace.json").read_text(encoding="utf-8"))
    target = {"callback-source": 2, "assigned-value": 3, "retention": 4, "sync": 3}[mutation]
    run, changed = -1, False
    for frame in capture["frames"]:
        incoming = frame["direction"] == "client->server"
        if incoming:
            run += 1
        if incoming or run != target:
            continue
        message = ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        element = message.delta.new_element
        if element.WhichOneof("type") == "text_input" and mutation in ("assigned-value", "sync"):
            if mutation == "assigned-value":
                element.text_input.value = ""
            else:
                element.text_input.set_value = False
        elif element.WhichOneof("type") == "json" and mutation != "sync":
            report = json.loads(element.json.body)
            if mutation == "callback-source":
                report["callbacks"][-1] = "ABC"
            else:
                report["value"] = report["state"] = ""
            element.json.body = json.dumps(report)
        else:
            continue
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
        changed = True
    assert changed, "missing text-source mutation target"
    with pytest.raises(AssertionError):
        read_query_param_capture("text-source", capture)


@pytest.mark.parametrize("mutation", ["identity", "stale-state", "callback", "default-only"])
def test_text_reset_gate_rejects_coherent_wrong_wire(mutation):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / "reference-browser/queryparams/text-reset/trace.json").read_text(encoding="utf-8"))
    run, phase, changed = -1, None, False
    for frame in capture["frames"]:
        incoming = frame["direction"] == "client->server"
        message = BackMsg() if incoming else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if incoming:
            run += 1
            phase = message.rerun_script.query_string.rsplit("phase=", 1)[-1]
        if run < 12:
            continue
        if mutation == "identity":
            if incoming and message.rerun_script.widget_states.widgets:
                message.rerun_script.widget_states.widgets[0].id = "$$ID-collapsed-cjk_note"
            elif not incoming and message.delta.new_element.WhichOneof("type") == "text_area":
                message.delta.new_element.text_area.id = "$$ID-collapsed-cjk_note"
            else:
                continue
        else:
            if incoming or phase != ("same-default" if mutation == "default-only" else "grow") or message.delta.new_element.WhichOneof("type") != "json":
                continue
            report = json.loads(message.delta.new_element.json.body)
            if mutation == "callback":
                report["callbacks"].append(report["value"])
            else:
                report["value"] = report["state"] = None if mutation == "default-only" else "XYZ"
            message.delta.new_element.json.body = json.dumps(report)
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
        changed = True
        if mutation != "identity":
            break
    assert changed, "missing text-reset mutation target"
    with pytest.raises(AssertionError):
        read_query_param_capture("text-reset", capture)


@pytest.mark.parametrize("mutation", ["unicode", "callback", "code-assignment", "widget-sync"])
def test_text_length_gate_rejects_coherent_wrong_wire(mutation):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / "reference-browser/queryparams/text-length/trace.json").read_text(encoding="utf-8"))
    phase = None
    for frame in capture["frames"]:
        if frame["direction"] == "client->server":
            phase = frame["message"]["rerun_script"]["query_string"].rsplit("phase=", 1)[-1]
            continue
        if phase != {"unicode": "unicode", "callback": "same-prefix", "code-assignment": "assign", "widget-sync": "assign"}[mutation]:
            continue
        message = ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        element = message.delta.new_element
        if mutation == "widget-sync":
            if element.WhichOneof("type") != "text_input":
                continue
            element.text_input.set_value = False
        else:
            if element.WhichOneof("type") != "json":
                continue
            report = json.loads(element.json.body)
            if mutation == "callback":
                report["callbacks"].append(report["value"])
            else:
                report["value"] = report["state"] = "中文" if mutation == "unicode" else "code長"
            element.json.body = json.dumps(report)
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
        break
    else:
        pytest.fail("missing text-length mutation target")
    with pytest.raises(AssertionError):
        read_query_param_capture("text-length", capture)


@pytest.mark.parametrize("mutation", ["percent-value", "percent-key", "utf8-replacement", "input"])
def test_query_encoding_gate_rejects_coherent_wrong_wire(mutation):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / "reference-browser/queryparams/encoding/trace.json").read_text(encoding="utf-8"))
    run = -1
    for frame in capture["frames"]:
        incoming = frame["direction"] == "client->server"
        message = BackMsg() if incoming else ForwardMsg()
        message.ParseFromString(base64.b64decode(frame["base64"]))
        if incoming:
            run += 1
            if mutation != "input" or run != 0:
                continue
            message.rerun_script.query_string = message.rerun_script.query_string.replace("tag=%+1", "tag=%2B1")
        else:
            if run != (6 if mutation == "utf8-replacement" else 0) or message.delta.new_element.WhichOneof("type") != "json":
                continue
            report = json.loads(message.delta.new_element.json.body)
            if report["stage"] != "load" or mutation == "input":
                continue
            if mutation == "percent-value":
                report["all"] = ["\x01"]
                report["value"] = "\x01"
                report["pairs"][0][1] = "\x01"
            elif mutation == "percent-key":
                report["pairs"][1][0] = "\x0f"
            else:
                report["all"][2] = "�"
            message.delta.new_element.json.body = json.dumps(report)
        raw = message.SerializeToString()
        frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
        break
    else:
        pytest.fail("missing encoding mutation target")
    with pytest.raises(AssertionError):
        read_query_param_capture("encoding", capture)


def test_query_param_reserved_oracle_is_complete_and_backed_by_wire():
    snapshots, urls = read_query_param_capture("reserved")
    assert len(snapshots) == 9 and len(urls) == 4
    reports = [item for item in snapshots if "stage" in item]
    assert [item["stage"] for item in reports] == ["reserved-load", "after-rejections", "empty-key-set", "empty-key-remove", "reserved-clear", "reserved-restore"]
    assert snapshots[1:4] == [
        {"operation": "set:embed", "rejected": True},
        {"operation": "set:EmBeD_OpTiOnS", "rejected": True},
        {"operation": "remove:embed", "rejected": True},
    ]
    assert reports[1] | {"stage": "reserved-load"} == reports[0]
    assert all(item["embed"] is None and item["options"] == [] for item in reports)
    assert reports[0]["ordinary"] == "ordinary" and reports[0]["empty_key"] == "empty-key-value"
    assert reports[2]["empty_key"] == "updated empty key" and reports[3]["empty_key"] is None
    assert reports[4]["pairs"] == [] and reports[5]["pairs"] == [["restored", "ok"]]
    assert urls[0].endswith("&=updated+empty+key")
    assert urls[-2:] == ["embed=true&EMBED_OPTIONS=light_theme", "embed=true&EMBED_OPTIONS=light_theme&restored=ok"]


def test_query_param_binding_lifecycle_oracle():
    reports, urls = read_query_param_capture("binding")
    assert len(reports) == 18 and len(urls) == 5
    assert reports[0] == {"phase": "load", "selected": "x", "text": ""}
    assert reports[6] == {"phase": "active", "selected": "y", "text": "hello"}
    assert reports[4] == {"operation": "clear", "rejected": False}, "absent bound params do not block clear"
    assert all(report["rejected"] for report in reports[7:11])
    assert all(report["rejected"] for report in reports[12:16]), "hidden widgets stay bound until run-end cleanup"
    assert urls[2] == "case=binding&phase=hidden&BOUND=case-sensitive"
    assert urls[-2:] == ["case=binding&phase=released&BOUND=case-sensitive&bound=manual", ""]
    assert reports[-1] == {"phase": "released", "pairs": []}


def test_query_param_url_seed_priority_and_correction_oracle():
    reports, urls = read_query_param_capture("seed")
    assert len(reports) == 8 and len(urls) == 9
    values = {report["phase"]: (report["bound"], report["text"], report["optional"], report["creation"]) for report in reports}
    assert values == {
        "initial": ("y", "hello", "y", "new"),
        "frontend": ("x", "edited", "x", "typed"),
        "again": ("y", "fresh", "y", "another"),
        "invalid": ("y", "fresh", "y", "another"),
        "empty": ("y", "", "y", "another"),
        "assign": ("x", "code", "y", "url"),
        "history": ("y", "url-history", "y", "history"),
        "history-missing": ("x", "base", None, "x"),
    }
    assert "bound" not in dict(reports[1]["pairs"]), "frontend default collapses the stored query without a URL broadcast"
    assert reports[3]["pairs"] == [["case", "seed"], ["phase", "invalid"]]
    assert reports[4]["pairs"] == [["case", "seed"], ["phase", "empty"], ["text", ""]]
    assert urls[3] == "case=seed&phase=invalid"
    assert urls[-1] == "case=seed&phase=assign&text=code&optional=y&creation=url"


def test_query_param_url_overrides_invalid_code_types_oracle():
    reports, urls = read_query_param_capture("seed-code")
    assert urls == [] and len(reports) == 2
    assert (reports[0]["phase"], reports[0]["bound"], reports[0]["text"]) == ("bad-initial", "y", "hello")
    assert (reports[1]["phase"], reports[1]["bound"], reports[1]["text"]) == ("bad-history", "y", "code-history")


@pytest.mark.parametrize("scenario", ["disabled", "disabled-valid"])
def test_disabled_input_callbacks_and_error_recovery_oracle(scenario):
    reports, urls = read_query_param_capture(scenario)
    assert len(reports) == (8 if scenario == "disabled" else 9)
    assert len(urls) == (3 if scenario == "disabled" else 5)
    values = {report["phase"]: tuple(report[key] for key in ("plain", "bound", "text", "check", "live")) for report in reports}
    assert values["load"] == ("safe", "y", "url", False, "ready")
    assert values["forge"] == ("safe", "y", "url", False, "one")
    assert values["code"] == ("code", "x", "code", True, "three")
    assert values["hidden"] == (None, "y", "url", True, "four")
    assert values["remount"] == ("safe", "y", "url", True, "five")
    assert values["enabled"] == ("edited", "x", "edited", False, "six")
    assert values["interactive"] == ("edited2", "y", "edited2", True, "seven")
    assert values["redisable"] == ("edited2", "y", "edited2", True, "eight")
    callbacks = {report["phase"]: report["callbacks"] for report in reports}
    assert callbacks["load"] == [] and callbacks["forge"] == ["live"]
    assert callbacks["code"] == ["live"] * 3, "malformed run already executed the live callback"
    assert callbacks["enabled"] == ["live"] * 6
    assert callbacks["interactive"] == ["live"] * 6 + ["plain", "bound", "text", "check", "live"]
    assert callbacks["redisable"] == ["live"] * 6 + ["plain", "bound", "text", "check", "live"] * 2
    if scenario == "disabled-valid":
        assert values["invalid-url"] == ("safe", "y", "url", False, "two")
        assert callbacks["invalid-url"] == ["live"] * 2


def test_bound_server_reruns_keep_state_callbacks_and_url_oracle():
    reports, urls = read_query_param_capture("rerun")
    assert len(reports) == 15 and len(urls) == 12
    assert [(report["phase"], report["iteration"], report["stage"]) for report in reports] == [
        (phase, 1, stage) for phase in ("load", "frontend", "early", "assign", "history") for stage in ("before", "values", "complete")]
    complete = {report["phase"]: report for report in reports if report["stage"] == "complete"}
    assert [(report["bound"], report["text"]) for report in complete.values()] == [
        ("y", "url"), ("x", "edited"), ("y", "fresh"), ("x", "code"), ("x", "base")]
    assert complete["load"]["callbacks"] == []
    assert all(report["callbacks"] == ["bound", "text"] for report in reports[3:]), "internal reruns must not replay callbacks"
    assert reports[6]["bound"] == "x" and reports[6]["text"] == "edited", "early rerun keeps unseen widget state"
    assert reports[3]["pairs"] == [["case", "rerun"], ["phase", "frontend"], ["bound", "y"], ["text", "ignored"], ["marker", "frontend-1"]]
    assert complete["frontend"]["pairs"] == [["case", "rerun"], ["phase", "frontend"], ["text", "ignored"], ["marker", "frontend-1"]]
    assert urls[7:10] == ["case=rerun&phase=assign&text=url&marker=assign-0",
                          "case=rerun&phase=assign&text=code&marker=assign-0",
                          "case=rerun&phase=assign&text=code&marker=assign-1"]


def selected_rerun_events(scenario):
    capture = json.loads((HERE / f"reference-browser/queryparams/{scenario}/trace.json").read_text())
    events = []
    for frame in capture["frames"]:
        message = frame["message"]
        element = message.get("delta", {}).get("new_element", {})
        events.extend(element.keys() & {"toast", "markdown", "balloons", "json", "selectbox", "text_input", "button"})
        for kind in ("page_config_changed", "page_info_changed", "navigation", "script_finished"):
            if kind in message:
                events.append(kind + (":" + message[kind] if kind == "script_finished" else ""))
    return events


def test_native_navigation_rerun_discards_queued_navigation_and_deltas():
    reports, urls = read_query_param_capture("navigation-rerun")
    assert reports == [] and urls == [""]
    assert selected_rerun_events("navigation-rerun") == [
        "navigation", "markdown", "button", "script_finished:FINISHED_SUCCESSFULLY",
        "page_info_changed", "script_finished:FINISHED_EARLY_FOR_RERUN",
        "navigation", "markdown", "script_finished:FINISHED_SUCCESSFULLY"]


def test_warm_rerun_keeps_toast_url_and_lifecycle_but_drops_other_queued_messages():
    reports, urls = read_query_param_capture("rerun-queue")
    assert reports == [{"phase": "warm", "iteration": 0}, {"phase": "queue", "iteration": 1}]
    assert urls == ["case=queue&phase=queue&marker=retained"]
    assert selected_rerun_events("rerun-queue") == [
        "page_config_changed", "toast", "markdown", "balloons", "json", "script_finished:FINISHED_SUCCESSFULLY",
        "toast", "page_info_changed", "script_finished:FINISHED_EARLY_FOR_RERUN", "json", "script_finished:FINISHED_SUCCESSFULLY"]


def test_cold_rerun_capture_retains_its_already_sent_prefix():
    reports, urls = read_query_param_capture("rerun-messages")
    assert len(reports) == 4 and len(urls) == 2
    assert [(report["iteration"], report["stage"]) for report in reports] == [(0, "before"), (1, "before"), (1, "values"), (1, "complete")]
    assert selected_rerun_events("rerun-messages")[:7] == ["page_config_changed", "toast", "markdown", "balloons", "page_info_changed", "json", "selectbox"]


URL = "http://127.0.0.1:8616"


def build_frame(entry):
    entry = copy.deepcopy(entry)
    kind = entry["kind"]
    if kind == "page_info":
        return {"direction": "server->client", "timestamp": 0.3, "summary": {"type": "page_info_changed", "page_info": {"query_string": entry["query_string"]}}}
    if kind == "rerun":
        states = []
        for state in entry["widget_states"]:
            real = state["id"]
            if real.endswith("-None"):
                real = "$$ID-79b26fd5542f64b238f6f878327b6b00-None"
            elif real.endswith("-bound"):
                real = "$$ID-85e592e7f7a3c4baeb8416bed8b755e6-bound"
            states.append({**state, "id": real})
        return {"direction": "client->server", "timestamp": 0.0, "summary": {"type": "rerun_script", "rerun_script": {"query_string": entry["query_string"], "widget_states": states}}}
    if kind == "selectbox":
        select = copy.deepcopy(entry["selectbox"])
        digest = "79b26fd5542f64b238f6f878327b6b00" if select["id"] == "$$ID-None" else "85e592e7f7a3c4baeb8416bed8b755e6"
        select["id"] = select["id"].replace("$$ID-", f"$$ID-{digest}-")
        return {"direction": "server->client", "timestamp": 0.4, "summary": {"type": "delta", "delta": {"type": "new_element", "element": "selectbox", "path": [0, 0], "element_full": {"selectbox": select}}}}
    if kind in ("new_session", "session_status_changed", "script_finished"):
        if kind == "script_finished":
            return {"direction": "server->client", "timestamp": 9.0, "summary": {"type": "script_finished", "script_finished": {"status": 0}}}
        return {"direction": "server->client", "timestamp": 0.1, "summary": {"type": kind, kind: {}}}
    return {"direction": "server->client", "timestamp": 0.5, "summary": {"type": "delta", "delta": {"type": "new_element", "element": kind, "path": entry.get("path"), "body": entry.get("body")}}}


def stage_frames(name, *, leading_main_blocks=0):
    frames = []
    for _ in range(leading_main_blocks):
        frames.append({"direction": "server->client", "timestamp": 0.2,
                       "summary": {"type": "delta", "delta": {"type": "add_block", "block_id": "main_container", "block_type": "vertical",
                                                              "block": {"vertical": {}, "id": "main_container"}, "path": [0]}}})
    frames.extend(build_frame(entry) for entry in QUERYPARAMS_TIMELINE[name])
    return frames


def dom(name):
    return json.loads(json.dumps(copy.deepcopy(QUERYPARAMS_DOMS[name]), ensure_ascii=False))


def observation(tmp_path, **faults):
    leading = faults.pop("leading_main_blocks", 0)
    stages = []
    for name in QUERYPARAMS_STAGES:
        stages.append({"name": name, "new_frames": stage_frames(name, leading_main_blocks=leading), "http": [], "dom": dom(name)})
    observation = {
        "journey": "queryparams-page",
        "contract": "journey-queryparams-v1",
        "scope": "PYTHON SIDE ONLY",
        "url": f"{URL}/",
        "source": {"file": QUERYPARAMS_SOURCE_FILES["python"]},
        "capture_sources": {},
        "stages": stages,
        "ipc_dir": str(tmp_path),
    }
    for stage in stages:
        png = f"{stage['name']}.png"
        (tmp_path / png).write_bytes(PNG_BYTES)
        stage["screenshot"] = {"file": png, "sha256": hashlib.sha256(PNG_BYTES).hexdigest()}
    mutation = faults.pop("mutation", None)
    target = stages[0]

    def find(kind):
        return next(frame for frame in target["new_frames"] if (frame["summary"].get(kind) if kind != "page_info_changed" else None) or frame["summary"].get("type") == kind)

    def page_info_frame(stage):
        return next(frame for frame in stage["new_frames"] if frame["summary"].get("type") == "page_info_changed")

    if mutation == "query_string_changed":
        page_info_frame(stages[0])["summary"]["page_info"]["query_string"] = "mode=other"
    elif mutation == "page_info_missing":
        target["new_frames"] = [frame for frame in target["new_frames"] if frame["summary"].get("type") != "page_info_changed"]
    elif mutation == "page_info_duplicated":
        target["new_frames"].insert(4, copy.deepcopy(page_info_frame(target)))
    elif mutation == "accept_new_options_off":
        for stage in stages:
            select = next(frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == "selectbox")
            box = select["summary"]["delta"]["element_full"]["selectbox"]
            if box.get("acceptNewOptions") is True:
                box["acceptNewOptions"] = False
                break
    elif mutation == "filter_mode_changed":
        for stage in stages:
            select = next(frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == "selectbox")
            box = select["summary"]["delta"]["element_full"]["selectbox"]
            if box.get("filterMode") == "FILTER_MODE_CONTAINS":
                box["filterMode"] = "FILTER_MODE_FUZZY"
                break
    elif mutation == "query_param_key_missing":
        for stage in stages:
            select = [frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == "selectbox"]
            box = select[1]["summary"]["delta"]["element_full"]["selectbox"]
            if "queryParamKey" in box:
                del box["queryParamKey"]
                break
    elif mutation == "bound_label_changed":
        for stage in stages:
            select = [frame for frame in stage["new_frames"] if (frame["summary"].get("delta") or {}).get("element") == "selectbox"]
            box = select[1]["summary"]["delta"]["element_full"]["selectbox"]
            if box.get("queryParamKey") == "bound":
                box["label"] = "Other"
                break
    elif mutation == "typed_value_lost":
        rerun = next(frame for frame in stages[1]["new_frames"] if frame["summary"].get("type") == "rerun_script")
        rerun["summary"]["rerun_script"]["widget_states"] = []
    elif mutation == "browser_query_string_changed":
        rerun = next(frame for frame in stages[2]["new_frames"] if frame["summary"].get("type") == "rerun_script")
        rerun["summary"]["rerun_script"]["query_string"] = "mode=demo"
    elif mutation == "markdown_changed":
        for frame in stages[2]["new_frames"]:
            delta = frame["summary"].get("delta") or {}
            if delta.get("element") == "markdown" and delta.get("body") == "bound=y":
                delta["body"] = "bound=x"
    elif mutation == "dom_url_missing_sync":
        stages[2]["dom"]["url"] = "?mode=demo"
    elif mutation == "dom_markdown_missing":
        stages[1]["dom"]["markdowns"] = ["pick=a", "bound=x"]
    elif mutation == "exception_element":
        target["new_frames"].insert(6, {"direction": "server->client", "timestamp": 2.9,
                                        "summary": {"type": "delta", "delta": {"type": "new_element", "element": "exception", "path": [0, 4]}}})
    elif mutation == "wrong_finish":
        for frame in stages[0]["new_frames"]:
            if frame["summary"]["type"] == "script_finished":
                frame["summary"]["script_finished"]["status"] = 2
    elif mutation == "missing_png":
        (tmp_path / f"{target['name']}.png").unlink()
    elif mutation == "png_sha":
        target["screenshot"]["sha256"] = "0" * 64
    elif mutation == "wrong_contract":
        observation["contract"] = "journey-queryparams-v0"
    elif mutation == "missing_stage":
        observation["stages"] = []
    assert not faults, faults
    return observation


def result(tmp_path, **faults):
    return queryparams_result(observation=observation(tmp_path, **faults))


def test_complete_synthetic_model_passes_every_check(tmp_path):
    outcome = result(tmp_path)
    assert outcome["ok"], outcome["failures"]
    assert outcome["counts"] == {"expected": 10, "executed": 10, "asserted": 10}
    assert tuple(check["check"] for check in outcome["checks"]) == QUERYPARAMS_REQUIRED


def test_the_rust_leading_main_block_is_the_one_allowed_divergence(tmp_path):
    outcome = result(tmp_path, leading_main_blocks=1)
    assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("leading", [2, 3])
def test_more_than_one_leading_main_block_fails(tmp_path, leading):
    outcome = result(tmp_path, leading_main_blocks=leading)
    assert not outcome["ok"], (leading, outcome["counts"])


@pytest.mark.parametrize("mutation", [
    "query_string_changed", "page_info_missing", "page_info_duplicated",
    "accept_new_options_off", "filter_mode_changed", "query_param_key_missing",
    "bound_label_changed", "typed_value_lost", "browser_query_string_changed",
    "markdown_changed", "dom_url_missing_sync", "dom_markdown_missing",
    "exception_element", "wrong_finish", "missing_png", "png_sha",
    "wrong_contract", "missing_stage",
])
def test_known_mutations_fail(tmp_path, mutation):
    outcome = result(tmp_path, mutation=mutation)
    assert not outcome["ok"], (mutation, outcome["counts"])


def test_degenerate_observations_fail_closed():
    for observation in (None, {}, [], {"journey": "queryparams-page"}):
        outcome = queryparams_result(observation=observation)
        assert not outcome["ok"] and outcome["counts"]["expected"] == len(QUERYPARAMS_REQUIRED)


def test_the_constants_pin_the_measured_semantics():
    assert QUERYPARAMS_STAGES == ["01-load", "02-new-option", "03-bound-pick"]
    assert QUERYPARAMS_PAGE_INFOS["01-load"]["query_string"] == "mode=demo"
    assert QUERYPARAMS_PAGE_INFOS["03-bound-pick"]["query_string"] == "bound=y&mode=demo"
    creation = QUERYPARAMS_SELECTBOXES_FIRST()
    assert creation["acceptNewOptions"] is True
    assert creation["filterMode"] == "FILTER_MODE_CONTAINS"
    assert "queryParamKey" not in creation
    bound = QUERYPARAMS_SELECTBOXES_SECOND()
    assert bound["queryParamKey"] == "bound"
    assert bound["acceptNewOptions"] is False
    # The measured wire omits the default filterMode (proto3 FUZZY = 0).
    assert "filterMode" not in bound
    assert QUERYPARAMS_RERUNS["01-load"]["query_string"] is None
    assert QUERYPARAMS_RERUNS["03-bound-pick"]["query_string"] == "bound=y&mode=demo"
    assert QUERYPARAMS_DOMS["01-load"]["url"] == "?mode=demo"
    assert QUERYPARAMS_DOMS["03-bound-pick"]["url"] == "?bound=y&mode=demo"
    assert QUERYPARAMS_DOMS["03-bound-pick"]["markdowns"] == ["pick=c", "bound=y"]
    assert all(not dom["exceptions"] for dom in QUERYPARAMS_DOMS.values())


def QUERYPARAMS_SELECTBOXES_FIRST():
    from queryparams_contract import QUERYPARAMS_SELECTBOXES
    return QUERYPARAMS_SELECTBOXES["01-load"][0]


def QUERYPARAMS_SELECTBOXES_SECOND():
    from queryparams_contract import QUERYPARAMS_SELECTBOXES
    return QUERYPARAMS_SELECTBOXES["01-load"][1]


def test_source_fingerprints_do_not_gate_functional_evidence(tmp_path):
    for source in ({"file": "historical-app.py", "sha256": "changed"}, {"file": "historical-app.py"}, None):
        observed = observation(tmp_path)
        observed["source"] = source
        outcome = queryparams_result(observation=observed)
        assert outcome["ok"], outcome["failures"]


@pytest.mark.parametrize("scenario", ["disabled-types", "disabled-types-isolated", "disabled-types-more", "disabled-types-bytes", "disabled-json"])
def test_disabled_type_oracles_keep_recovery_and_persistent_array_errors(scenario):
    read_query_param_capture(scenario)


@pytest.mark.parametrize("mutation", ["exception", "position", "callback", "json-list", "json-dict", "bytes", "byte-value", "json-error-kind", "json-error-offset", "json-input"])
def test_disabled_type_gate_rejects_coherent_wrong_wire(mutation):
    import base64
    from google.protobuf.json_format import MessageToDict
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    if mutation in ("json-error-kind", "json-error-offset", "json-input"):
        scenario = "disabled-json"
    elif mutation == "byte-value":
        scenario = "disabled-types-bytes"
    elif mutation in ("json-list", "json-dict", "bytes"):
        scenario = "disabled-types-more"
    else:
        scenario = "disabled-types-isolated"
    capture = json.loads((HERE / f"reference-browser/queryparams/{scenario}/trace.json").read_text(encoding="utf-8-sig"))
    phase = ""
    for frame in capture["frames"]:
        if frame["direction"] == "client->server":
            phase = frame["message"]["rerun_script"]["query_string"].split("phase=")[1].split("&")[0]
            if (mutation == "byte-value" and phase == "malformed-18") or (mutation == "json-input" and phase == "malformed-17"):
                message = BackMsg()
                message.ParseFromString(base64.b64decode(frame["base64"]))
                if mutation == "byte-value":
                    message.rerun_script.widget_states.widgets[0].bytes_value = bytes(reversed(range(256)))
                else:
                    message.rerun_script.widget_states.widgets[0].json_value = "null"
                raw = message.SerializeToString()
                frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
                break
            continue
        element = frame["message"].get("delta", {}).get("new_element", {})
        target_phase = {"json-list": "malformed-8", "json-dict": "malformed-9", "bytes": "malformed-14", "json-error-kind": "malformed-0", "json-error-offset": "malformed-11"}.get(mutation, "malformed-2")
        if (mutation not in ("callback", "byte-value", "json-input") and phase == target_phase and "exception" in element) or (mutation == "callback" and phase == "recovery-1" and "json" in element):
            message = ForwardMsg()
            message.ParseFromString(base64.b64decode(frame["base64"]))
            if mutation == "json-error-kind":
                message.delta.new_element.exception.type = "TypeError"
            elif mutation == "json-error-offset":
                message.delta.new_element.exception.message = "Expecting value: line 2 column 2 (char 10)"
            elif mutation in ("exception", "json-list", "json-dict", "bytes"):
                message.delta.new_element.exception.message = "'str' object cannot be interpreted as an integer"
            elif mutation == "position":
                message.metadata.delta_path[-1] = 0
            else:
                report = json.loads(message.delta.new_element.json.body)
                report["callbacks"] = ["live"]
                message.delta.new_element.json.body = json.dumps(report)
            raw = message.SerializeToString()
            frame.update(base64=base64.b64encode(raw).decode(), bytes=len(raw), message=MessageToDict(message, preserving_proto_field_name=True))
            break
    else:
        pytest.fail("missing disabled type mutation target")
    with pytest.raises(AssertionError):
        read_query_param_capture(scenario, capture)


def read_browser_history_capture(runtime, capture=None):
    import base64
    import re
    from urllib.parse import urlsplit
    from PIL import Image
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
    from streamlit.proto.SelectWidgetFilterMode_pb2 import FILTER_MODE_CONTAINS

    # 1. 读取原始记录；运行时、清理和截图均使用本次采集的数据。
    directory = (HERE / "reference-browser/queryparams/history-ui" if runtime == "python"
                 else HERE.parent / "browser/rust-queryparams/history-ui")
    if capture is None:
        capture = json.loads((directory / "trace.json").read_text(encoding="utf-8"))
    assert capture["runtime"] == runtime and capture["reference_version"] == "1.66.1"
    assert capture["cleanup"] == {"owned_tabs_closed": True, "owned_servers_stopped": True, "ports_free": [8515, 18515]}
    assert set(capture["scenarios"]) == {"replacement-and-document", "same-document"}

    # 2. 解码原始帧，分别验证页面重载和同页历史的状态、URL 与 DOM。
    projections = {}
    for name, scenario in capture["scenarios"].items():
        events = scenario["events"]
        sequences = [event["sequence"] for event in events]
        assert sequences == sorted(set(sequences))
        if name == "same-document":
            assert not any("truncated" in note for note in scenario["notes"])
        else:
            # 跨文档记录有缓冲淘汰，只校验保留下来的完整执行，不推断全部请求数。
            assert "CDP event buffer truncated" in scenario["notes"]
        runs = []
        for event in events:
            assert event["method"] in ("Network.webSocketFrameSent", "Network.webSocketFrameReceived")
            response = event["params"]["response"]
            assert response["opcode"] == 2
            message = BackMsg() if event["method"].endswith("Sent") else ForwardMsg()
            message.ParseFromString(base64.b64decode(response["payloadData"], validate=True))
            if isinstance(message, BackMsg):
                assert message.WhichOneof("type") == "rerun_script"
                runs.append({"request": message.rerun_script, "messages": [], "sequences": [event["sequence"]]})
            else:
                assert runs
                runs[-1]["messages"].append(message)
                runs[-1]["sequences"].append(event["sequence"])

        same_document = name == "same-document"
        requests = (["bound=y", "bound=y&mode=demo", "mode=demo", "bound=y", "mode=demo"] if same_document else
                    ["mode=demo", "mode=demo", "bound=y&mode=demo", "mode=demo", "mode=demo", "mode=demo&bound=y"]
                    + (["mode=demo&bound=y"] if runtime == "python" else []))
        assert [run["request"].query_string for run in runs] == requests
        assert [run["request"].is_history_navigation for run in runs] == ([False, False, False, True, True] if same_document else [False] * len(runs))
        expected_text = ([("a", "y"), ("c", "y"), ("c", "x"), ("c", "y"), ("c", "x")] if same_document else
                         [("a", "x"), ("c", "x"), ("c", "y"), ("c", "x"), ("a", "x"), ("a", "y")]
                         + ([("a", "y")] if runtime == "python" else []))
        sessions, projection = [], []
        for number, (run, (pick, bound)) in enumerate(zip(runs, expected_text, strict=True)):
            messages = run["messages"]
            assert [message.WhichOneof("type") for message in messages] == [
                "new_session", "session_status_changed", "page_info_changed", "delta", "delta", "delta", "delta", "script_finished", "session_status_changed"]
            sessions.append(messages[0].new_session.initialize.session_id)
            if runtime == "python":
                environment = messages[0].new_session.initialize.environment_info
                assert environment.streamlit_version == "1.66.1" and environment.python_version == "3.14.7.final.0"
            assert messages[1].session_status_changed.script_is_running
            assert not messages[-1].session_status_changed.script_is_running
            assert messages[-2].script_finished == 0
            assert messages[2].page_info_changed.query_string == ("bound=y&mode=demo" if same_document and bound == "y" else
                                                                "mode=demo&bound=y" if not same_document and number >= 5 else
                                                                "bound=y&mode=demo" if bound == "y" else "mode=demo")
            deltas = messages[3:7]
            assert [list(message.metadata.delta_path) for message in deltas] == [[0, index] for index in range(4)]
            elements = [message.delta.new_element for message in deltas]
            assert [element.WhichOneof("type") for element in elements] == ["selectbox", "markdown", "selectbox", "markdown"]
            assert [elements[1].markdown.body, elements[3].markdown.body] == [f"pick={pick}", f"bound={bound}"]
            assert elements[0].selectbox.label == "Pick" and list(elements[0].selectbox.options) == ["a", "b"]
            assert elements[0].selectbox.accept_new_options
            assert elements[0].selectbox.filter_mode == FILTER_MODE_CONTAINS
            assert elements[2].selectbox.label == "Bound" and list(elements[2].selectbox.options) == ["x", "y"]
            assert elements[2].selectbox.query_param_key == "bound" and not elements[2].selectbox.accept_new_options
            if same_document:
                assert elements[2].selectbox.set_value == (number in (0, 3, 4))
                assert elements[2].selectbox.raw_value == (bound if number in (0, 3, 4) else "")
                widgets = run["request"].widget_states.widgets
                assert len(widgets) == (0 if number == 0 else 2)
                if widgets:
                    assert [widget.WhichOneof("value") for widget in widgets] == ["string_value", "string_value"]
                    assert [widget.string_value for widget in widgets] == ["c", ["y", "x", "x", "y"][number - 1]]
                    assert [widget.id for widget in widgets] == [elements[0].selectbox.id, elements[2].selectbox.id]
            projection.append((run["request"].query_string, run["request"].is_history_navigation, pick, bound))
        assert sessions[0] and len(set(sessions[:4])) == 1
        if same_document:
            assert len(set(sessions)) == 1 and not scenario["logs"]
            stages = [("initial", "bound=y&mode=demo", "a", "y"), ("pick-c", "bound=y&mode=demo", "c", "y"),
                      ("bound-x", "mode=demo", "c", "x"), ("back-y", "bound=y&mode=demo", "c", "y"), ("forward-x", "mode=demo", "c", "x")]
            assert [item["label"] for item in scenario["observations"]] == [stage[0] for stage in stages]
        else:
            assert len(set(sessions)) == len(runs) - 3
            stages = [("initial", "mode=demo", "a", "x"), ("pick-c", "mode=demo", "c", "x"),
                      ("bound-y", "bound=y&mode=demo", "c", "y"), ("bound-x", "mode=demo", "c", "x"),
                      ("forward-return", "mode=demo", "a", "x"), ("navigate-y", "mode=demo&bound=y", "a", "y"),
                      ("back-x-document", "mode=demo", "a", "x"), ("forward-y-document", "mode=demo&bound=y", "a", "y")]
            blank = next(item for item in scenario["observations"] if item["label"] == "back-blank")
            assert blank["url"] == "about:blank" and blank["dom"] == "" and blank["eventCursor"] is None
            assert scenario["logs"] and all(log["message"] == "Client Error: WebSocket onerror" for log in scenario["logs"])
        for label, query, pick, bound in stages:
            observation = next(item for item in scenario["observations"] if item["label"] == label)
            assert urlsplit(observation["url"]).query == query
            assert f"paragraph: pick={pick}" in observation["dom"] and f"paragraph: bound={bound}" in observation["dom"]
            for control, expected in (("Pick", pick), ("Bound", bound)):
                selected = re.search(rf'^  - combobox "{control}"(?: \[[^\]]+\])*: "?([^"\n]+)"?$', observation["dom"], re.MULTILINE)
                assert selected and selected.group(1) == expected
            assert "stException" not in observation["dom"]
        if same_document:
            previous = -1
            for observation, run in zip(scenario["observations"], runs, strict=True):
                assert previous < min(run["sequences"]) <= max(run["sequences"]) <= observation["eventCursor"]
                previous = observation["eventCursor"]
        final = scenario["finalDom"]
        expected_final = ["pick=c", "bound=x"] if same_document else ["pick=a", "bound=y"]
        assert final["markdowns"] == expected_final
        assert [(control["name"], control["value"]) for control in final["comboboxes"]] == [("Pick", "c" if same_document else "a"), ("Bound", "x" if same_document else "y")]
        assert not final["exceptions"] and not any(control["disabled"] for control in final["comboboxes"])
        projections[name] = projection

    # 3. 截图必须存在且可解码，不能只信 manifest 中的摘要。
    assert {shot["file"] for shot in capture["screenshots"]} == {"forward-return.jpg", "forward-y.jpg", "history-back-y.jpg", "history-forward-x.jpg"}
    for shot in capture["screenshots"]:
        image_path = directory / shot["file"]
        raw = image_path.read_bytes()
        assert len(raw) == shot["bytes"] and hashlib.sha256(raw).hexdigest() == shot["sha256"]
        with Image.open(image_path) as image:
            assert image.format == "JPEG" and list(image.size) == shot["size"] and min(image.size) > 700
            image.verify()
    return projections


def test_real_browser_query_history_matches_reference():
    python = read_browser_history_capture("python")
    rust = read_browser_history_capture("rust")
    assert rust["same-document"] == python["same-document"]
    assert rust["replacement-and-document"] == python["replacement-and-document"][:6]


@pytest.mark.parametrize("mutation", ["history-flag", "retained-pick", "dom-bound", "url", "screenshot"])
def test_browser_history_gate_rejects_wrong_evidence(mutation):
    import base64
    from streamlit.proto.BackMsg_pb2 import BackMsg
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    capture = json.loads((HERE / "reference-browser/queryparams/history-ui/trace.json").read_text(encoding="utf-8"))
    scenario = capture["scenarios"]["same-document"]
    if mutation in ("history-flag", "retained-pick"):
        run = -1
        for event in scenario["events"]:
            message = BackMsg() if event["method"].endswith("Sent") else ForwardMsg()
            message.ParseFromString(base64.b64decode(event["params"]["response"]["payloadData"]))
            if isinstance(message, BackMsg):
                run += 1
            if run == 3 and mutation == "history-flag" and isinstance(message, BackMsg):
                message.rerun_script.is_history_navigation = False
            elif run == 3 and mutation == "retained-pick" and isinstance(message, ForwardMsg) and message.delta.new_element.markdown.body == "pick=c":
                message.delta.new_element.markdown.body = "pick=a"
                scenario["observations"][3]["dom"] = scenario["observations"][3]["dom"].replace("pick=c", "pick=a")
            else:
                continue
            event["params"]["response"]["payloadData"] = base64.b64encode(message.SerializeToString()).decode()
            break
        else:
            pytest.fail("missing browser history mutation target")
    elif mutation == "dom-bound":
        scenario["observations"][3]["dom"] = scenario["observations"][3]["dom"].replace('combobox "Bound" [active]: "y"', 'combobox "Bound" [active]: x')
    elif mutation == "url":
        scenario["observations"][3]["url"] = "http://127.0.0.1:18515/?mode=demo"
    else:
        capture["screenshots"][0]["sha256"] = "0" * 64
    with pytest.raises(AssertionError):
        read_browser_history_capture("python", capture)
