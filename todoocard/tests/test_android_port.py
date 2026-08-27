#!/usr/bin/env python3

from __future__ import annotations

import json
import io
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "today-eats" / "scripts"))

from android_bridge import BridgeError, _BridgeServer, _validate_device_id  # noqa: E402
from places import haversine_m, parse_places  # noqa: E402
import cli  # noqa: E402


class BridgeServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = {"request_id": "request-1", "mode": "send"}
        self.server = _BridgeServer(self.request, b"payload")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = (
            f"http://127.0.0.1:{self.server.server_address[1]}/{self.server.token}"
        )

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_request_and_payload_are_token_scoped(self) -> None:
        with urllib.request.urlopen(self.base + "/request") as response:
            self.assertEqual(json.load(response), self.request)
        with urllib.request.urlopen(self.base + "/payload") as response:
            self.assertEqual(response.read(), b"payload")
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(
                f"http://127.0.0.1:{self.server.server_address[1]}/wrong/request"
            )
        self.assertEqual(context.exception.code, 404)
        context.exception.close()

    def test_matching_result_wakes_waiter(self) -> None:
        body = json.dumps(
            {"request_id": "request-1", "mode": "send", "ok": True}
        ).encode()
        request = urllib.request.Request(
            self.base + "/result", data=body, method="POST"
        )
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status, 200)
        self.assertTrue(self.server.result_event.wait(1))
        self.assertTrue(self.server.result["ok"])


class ValidationTests(unittest.TestCase):
    def test_device_address_is_normalized(self) -> None:
        self.assertEqual(
            _validate_device_id("aa:bb:cc:dd:ee:ff"), "AA:BB:CC:DD:EE:FF"
        )
        with self.assertRaises(BridgeError):
            _validate_device_id("not-a-mac")

    def test_config_generates_and_redacts_companion_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_dir, original_path = cli.CFG_DIR, cli.CFG_PATH
            cli.CFG_DIR = Path(directory)
            cli.CFG_PATH = cli.CFG_DIR / "config.json"
            try:
                cfg = cli.load_cfg()
                self.assertRegex(cfg["companion_key"], r"^[0-9a-f]{64}$")
                output = io.StringIO()
                args = type("Args", (), {
                    "show": True,
                    "device_id": None,
                    "device_name": None,
                    "orientation": None,
                })()
                with redirect_stdout(output):
                    cli.cmd_config(args)
                self.assertNotIn(cfg["companion_key"], output.getvalue())
                self.assertIn("***configured***", output.getvalue())
            finally:
                cli.CFG_DIR, cli.CFG_PATH = original_dir, original_path

    def test_android_source_keeps_trust_and_no_resume_guards(self) -> None:
        source = (
            ROOT
            / "android-bridge/app/src/main/java/io/github/jiqimaooo/todoocard/androidbridge/MainActivity.java"
        ).read_text(encoding="utf-8")
        self.assertIn("MessageDigest.isEqual", source)
        self.assertIn("requestedStart != 0", source)
        self.assertIn("refusing a mid-frame resume", source)

    def test_android_12_plus_keeps_location_permission(self) -> None:
        manifest = ET.parse(
            ROOT / "android-bridge/app/src/main/AndroidManifest.xml"
        ).getroot()
        android = "{http://schemas.android.com/apk/res/android}"
        permissions = {
            element.attrib.get(android + "name"): element.attrib
            for element in manifest.findall("uses-permission")
        }
        for name in (
            "android.permission.ACCESS_COARSE_LOCATION",
            "android.permission.ACCESS_FINE_LOCATION",
        ):
            self.assertIn(name, permissions)
            self.assertNotIn(android + "maxSdkVersion", permissions[name])


class PlacesTests(unittest.TestCase):
    def test_haversine_distance(self) -> None:
        self.assertAlmostEqual(haversine_m(0, 0, 0, 0.001), 111.2, delta=0.5)

    def test_parse_places_maps_osm_shape_and_filters_cafes(self) -> None:
        document = {
            "elements": [
                {
                    "type": "node",
                    "id": 1,
                    "lat": 31.2305,
                    "lon": 121.4738,
                    "tags": {
                        "name": "测试面馆",
                        "amenity": "restaurant",
                        "cuisine": "noodle;chinese",
                        "addr:street": "测试路",
                        "addr:housenumber": "8",
                    },
                },
                {
                    "type": "node",
                    "id": 2,
                    "lat": 31.2306,
                    "lon": 121.4739,
                    "tags": {"name": "咖啡店", "amenity": "cafe"},
                },
            ]
        }
        places = parse_places(document, 31.2304, 121.4737)
        self.assertEqual(len(places), 1)
        self.assertEqual(places[0]["name"], "测试面馆")
        self.assertEqual(places[0]["_query"], "面条")
        self.assertEqual(places[0]["address"], "测试路 8")


if __name__ == "__main__":
    unittest.main()
