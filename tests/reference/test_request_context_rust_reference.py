"""Frozen rust request_context browser evidence (M4 first slice)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1] / "browser/rust-request-context"


def test_frozen_files_and_manifest():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8-sig"))
    assert manifest["scope"] == "frozen rust capture data only; the caller-owned rust server is not archived"
    names = set()
    for item in manifest["files"]:
        data = (ROOT / item["file"]).read_bytes()
        assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
        names.add(item["file"])
    assert {"trace.json", "default.png", "embedded.png"} <= names


def test_whitelisted_headers_and_embedded_flag_render_in_the_official_frontend():
    raw = json.loads((ROOT / "trace.json").read_text(encoding="utf-8-sig"))
    assert raw["runtime"] == "rust" and raw["successful"] and "producer_error" not in raw
    assert [stage["name"] for stage in raw["stages"]] == ["default", "embedded"]
    for stage, embedded in zip(raw["stages"], [False, True]):
        report = json.loads(stage["code_text"])
        headers = report["headers"]
        # The real Chrome connection: whitelisted headers only, lowercase names.
        assert set(headers) == {"accept-language", "host", "origin", "user-agent"}, f"{stage['name']}: {sorted(headers)}"
        assert headers["user-agent"].startswith("Mozilla/5.0") and "HeadlessChrome" in headers["user-agent"]
        assert headers["host"] and headers["origin"].startswith("http://127.0.0.1")
        # No credential or transport header leaks through the default whitelist.
        assert not any(name.startswith(("cookie", "sec-websocket", "authorization", "x-")) for name in headers)
        # The page context rides the frontend's per-rerun context_info, the
        # same carriage the frozen python browser reference measured.
        assert report["url"] == "http://127.0.0.1:8590/"
        assert report["locale"] == "zh-CN" and report["timezone"] == "Asia/Shanghai" and report["timezone_offset"] == -480
        assert report["theme"] == "dark"
        # ?embed=true flips the browser-reported flag; ?st_embed=true does not
        # (measured on both runtimes).
        assert report["is_embedded"] is embedded
        assert stage["exceptions"] == "[]"
