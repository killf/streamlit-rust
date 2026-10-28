"""Capture the request_context example page in a real browser.

One stage: load the page, read the rendered JSON code block (the whitelisted
handshake headers the official frontend's connection carried) plus the
st_embed variant via ?st_embed=true; screenshots for both. Caller-owned Rust
server.
"""
import argparse
import base64
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests/browser"), str(ROOT / "tests/reference")]
from componentv2_state_capture import Recorder, free_port
from componenttrigger_capture import CHROME_CANDIDATES, evaluate, http_json


def collect(args):
    if importlib.metadata.version("streamlit") != "1.66.1":
        raise RuntimeError("requires the pinned Streamlit 1.66.1 decoder environment")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    capture = {"runtime": "rust", "reference_decoder": "1.66.1", "url": args.url,
               "captured_at_utc": datetime.now(timezone.utc).isoformat(), "server_cleanup": "caller-owned", "stages": []}
    chrome = recorder = None
    profile = (out / "chrome-profile").resolve()
    profile.mkdir()
    try:
        chrome_path = next(path for path in CHROME_CANDIDATES if Path(path).is_file())
        port = free_port()
        chrome = subprocess.Popen([chrome_path, "--headless=new", "--disable-gpu", f"--remote-debugging-port={port}",
                                   f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check", "about:blank"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(2.5)
        assert chrome.poll() is None, "owned Chrome failed to start"
        deadline = time.monotonic() + 15
        while True:
            try:
                http_json(f"http://127.0.0.1:{port}/json/version")
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise RuntimeError("devtools unavailable")
                time.sleep(0.3)
        target = http_json(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")
        recorder = Recorder(target["webSocketDebuggerUrl"])
        recorder.start()
        for name, url in [("default", args.url), ("embedded", args.url.rstrip("/") + "/?embed=true")]:
            recorder.call("Page.navigate", {"url": url})
            time.sleep(4)
            code = evaluate(recorder, "document.querySelector('[data-testid=stCode]')?.innerText || ''")
            exceptions = evaluate(recorder, "JSON.stringify([...document.querySelectorAll('[data-testid=stException]')].map(e=>e.innerText))")
            caption = evaluate(recorder, "[...document.querySelectorAll('[data-testid=stCaption]')].map(e=>e.innerText).join('|')")
            metrics = recorder.call("Page.getLayoutMetrics")["result"]["cssContentSize"]
            png = recorder.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                               "clip": {"x": 0, "y": 0, "width": metrics["width"], "height": metrics["height"], "scale": 1}})["result"]["data"]
            (out / f"{name}.png").write_bytes(base64.b64decode(png))
            capture["stages"].append({"name": name, "code_text": code, "exceptions": exceptions, "caption": caption, "screenshot": f"{name}.png"})
            print(name, "code:", code.replace("\n", " ")[:160], "| exceptions:", exceptions, "| caption:", caption, flush=True)
        capture["browser"] = http_json(f"http://127.0.0.1:{port}/json/version")
        capture["successful"] = True
    except Exception as error:
        capture["producer_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        if recorder is not None:
            recorder.stop()
        if chrome is not None:
            chrome.terminate()
            chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
        (out / "trace.json").write_text(json.dumps(capture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="caller-owned request_context example server URL")
    parser.add_argument("--out", required=True)
    collect(parser.parse_args())
