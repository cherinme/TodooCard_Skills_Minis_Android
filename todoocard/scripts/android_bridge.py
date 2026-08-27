#!/usr/bin/env python3
"""Call the TodooCard companion app from Android Minis over localhost."""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PACKAGE = "io.github.jiqimaooo.todoocard.androidbridge"
SCHEME = "todoocard-minis"
MAX_RESULT_BYTES = 1_000_000
DEVICE_PATTERN = r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$"
DEFAULT_TIMEOUTS = {
    "scan": 60,
    "pair": 140,
    "probe": 90,
    "send": 900,
    "location": 70,
}
SEND_IDLE_TIMEOUT = 240


class BridgeError(RuntimeError):
    pass


class _BridgeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, request: dict, payload: bytes | None):
        super().__init__(("127.0.0.1", 0), _BridgeHandler)
        self.token = secrets.token_hex(24)
        self.request_bytes = json.dumps(request, ensure_ascii=False).encode("utf-8")
        self.payload = payload
        self.result: dict | None = None
        self.result_event = threading.Event()
        self.progress: dict | None = None
        self.progress_event = threading.Event()
        self.last_activity_at = time.monotonic()


class _BridgeHandler(BaseHTTPRequestHandler):
    server: _BridgeServer

    def log_message(self, format: str, *args) -> None:
        return

    def _route(self, suffix: str) -> bool:
        return self.path == f"/{self.server.token}/{suffix}"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self._route("request"):
            self.server.last_activity_at = time.monotonic()
            self._send(200, self.server.request_bytes, "application/json; charset=utf-8")
            return
        if self._route("payload") and self.server.payload is not None:
            self.server.last_activity_at = time.monotonic()
            self._send(200, self.server.payload, "application/octet-stream")
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        is_result = self._route("result")
        is_progress = self._route("progress")
        if not is_result and not is_progress:
            self._send(404, b"not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        maximum = MAX_RESULT_BYTES if is_result else 64 * 1024
        if length <= 0 or length > maximum:
            self._send(413, b"invalid result length", "text/plain")
            return
        try:
            result = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, b"invalid json", "text/plain")
            return
        expected = json.loads(self.server.request_bytes)["request_id"]
        if result.get("request_id") != expected:
            self._send(409, b"request id mismatch", "text/plain")
            return
        if is_progress:
            percent = result.get("percent")
            block = result.get("block")
            if (
                result.get("mode") != "send"
                or not isinstance(percent, int)
                or not 0 <= percent <= 100
                or not isinstance(block, int)
                or block < -1
            ):
                self._send(400, b"invalid progress", "text/plain")
                return
            previous = self.server.progress
            if previous is None or percent >= previous.get("percent", -1):
                self.server.progress = result
            self.server.last_activity_at = time.monotonic()
            self.server.progress_event.set()
            self._send(200, b"ok", "text/plain")
            return
        self.server.result = result
        self.server.last_activity_at = time.monotonic()
        self.server.result_event.set()
        self._send(200, b"ok", "text/plain")


def _wait_for_result(server: _BridgeServer, mode: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_percent = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BridgeError(
                "companion timed out; no final result arrived before the operation deadline"
            )
        if server.result_event.wait(min(1.0, remaining)):
            return
        if mode != "send":
            continue
        progress = server.progress
        if progress is not None and progress.get("percent") != last_percent:
            last_percent = progress["percent"]
            print(
                f"TodooCard transfer {last_percent}% (block {progress['block']})",
                file=sys.stderr,
                flush=True,
            )
        server.progress_event.clear()
        if time.monotonic() - server.last_activity_at > SEND_IDLE_TIMEOUT:
            raise BridgeError(
                "companion stopped reporting transfer progress for 240 seconds"
            )


def _validate_device_id(device_id: str | None) -> str | None:
    if device_id is None:
        return None
    import re

    normalized = device_id.upper()
    if not re.fullmatch(DEVICE_PATTERN, normalized):
        raise BridgeError("device_id must be the exact BLE MAC address from scan")
    return normalized


def call_bridge(
    mode: str,
    *,
    companion_key: str,
    device_id: str | None = None,
    payload_path: Path | None = None,
    timeout: float | None = None,
    opener: str = "android-open",
) -> dict:
    """Run one companion operation and return its verified JSON result."""
    if shutil.which(opener) is None:
        raise BridgeError(
            f"{opener} is unavailable; run this skill inside Minis for Android"
        )
    if mode not in {"scan", "pair", "probe", "send", "location"}:
        raise BridgeError(f"unsupported bridge mode: {mode}")
    import re

    if not re.fullmatch(r"[0-9a-f]{64}", companion_key):
        raise BridgeError("a valid local companion_key is required")
    device_id = _validate_device_id(device_id)
    if mode in {"pair", "probe", "send"} and not device_id:
        raise BridgeError(f"{mode} requires an exact device_id")
    payload = None
    if mode == "send":
        if payload_path is None or not payload_path.is_file():
            raise BridgeError("send requires an existing payload file")
        payload = payload_path.read_bytes()

    request_id = f"{int(time.time())}-{secrets.token_hex(8)}"
    request = {
        "request_id": request_id,
        "mode": mode,
        "companion_key": companion_key,
    }
    if device_id:
        request["device_id"] = device_id
    server = _BridgeServer(request, payload)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        query = urllib.parse.urlencode({"port": port, "token": server.token})
        deep_link = f"{SCHEME}://bridge/run?{query}"
        opened = subprocess.run(
            [opener, deep_link], capture_output=True, text=True, timeout=20
        )
        if opened.returncode != 0:
            detail = (opened.stderr or opened.stdout or "").strip()
            raise BridgeError(
                "cannot open the TodooCard companion app; install the bundled APK"
                + (f": {detail}" if detail else "")
            )
        wait_seconds = timeout or DEFAULT_TIMEOUTS[mode]
        _wait_for_result(server, mode, wait_seconds)
        assert server.result is not None
        result = server.result
        if result.get("mode") != mode:
            raise BridgeError("companion returned a mismatched operation")
        if result.get("ok") is not True:
            raise BridgeError(str(result.get("message") or "companion operation failed"))
        return result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    subparsers.add_parser("scan")
    subparsers.add_parser("location")
    for mode in ("pair", "probe"):
        command = subparsers.add_parser(mode)
        command.add_argument("--device-id", required=True)
    send = subparsers.add_parser("send")
    send.add_argument("--device-id", required=True)
    send.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--companion-key", required=True)
    args = parser.parse_args()
    try:
        result = call_bridge(
            args.mode,
            companion_key=args.companion_key,
            device_id=getattr(args, "device_id", None),
            payload_path=getattr(args, "payload", None),
        )
    except BridgeError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
