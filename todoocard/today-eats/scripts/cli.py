#!/usr/bin/env python3
"""TodooCard Android Minis CLI: device setup and today's nearby meal card."""

from __future__ import annotations

import argparse
import json
import random
import secrets
import shutil
import sys
from pathlib import Path

SUBSKILL_ROOT = Path(__file__).resolve().parent.parent
PARENT_ROOT = SUBSKILL_ROOT.parent
SCRIPTS = Path(__file__).resolve().parent
PARENT_SCRIPTS = PARENT_ROOT / "scripts"
CFG_DIR = Path("/var/minis/shared/todoocard")
CFG_PATH = CFG_DIR / "config.json"
ATTACH = Path("/var/minis/attachments")
WORK = Path("/var/minis/workspace/todoocard_run")

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(PARENT_SCRIPTS))

from android_bridge import BridgeError, call_bridge  # noqa: E402
from image_to_payload import convert  # noqa: E402
from meal_template import render  # noqa: E402
from places import search_nearby_food  # noqa: E402

DEFAULT_CONFIG = {
    "device_id": "",
    "device_name": "",
    "companion_key": "",
    "screen_orientation": "rotate-180-then-flip-horizontal",
    "target": "t3",
    "size": "528x792",
    "places_provider": "openstreetmap-overpass",
    "send_policy": "full-frame-only-no-resume",
}


def load_cfg() -> dict:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    if CFG_PATH.exists():
        loaded = json.loads(CFG_PATH.read_text(encoding="utf-8"))
        cfg = {**DEFAULT_CONFIG, **loaded}
    else:
        cfg = dict(DEFAULT_CONFIG)
    if not cfg.get("companion_key"):
        cfg["companion_key"] = secrets.token_hex(32)
        save_cfg(cfg)
    return cfg


def save_cfg(cfg: dict) -> None:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    CFG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def print_result(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_scan(_args) -> None:
    cfg = load_cfg()
    print_result(call_bridge("scan", companion_key=cfg["companion_key"]))


def cmd_pair(args) -> None:
    cfg = load_cfg()
    print_result(
        call_bridge(
            "pair", companion_key=cfg["companion_key"], device_id=args.device_id
        )
    )


def cmd_probe(args) -> None:
    cfg = load_cfg()
    device_id = args.device_id or cfg.get("device_id")
    if not device_id:
        raise SystemExit("probe requires --device-id or a saved device_id")
    result = call_bridge(
        "probe", companion_key=cfg["companion_key"], device_id=device_id
    )
    if args.save:
        cfg["device_id"] = device_id.upper()
        if result.get("device_name"):
            cfg["device_name"] = result["device_name"]
        save_cfg(cfg)
        print(f"saved {CFG_PATH}")
    print_result(result)


def cmd_location(_args) -> None:
    cfg = load_cfg()
    print_result(call_bridge("location", companion_key=cfg["companion_key"]))


def prepare_image(source: Path, prefix: Path, orientation: str) -> dict:
    WORK.mkdir(parents=True, exist_ok=True)
    ATTACH.mkdir(parents=True, exist_ok=True)
    info = convert(
        str(source), str(prefix), orientation=orientation, make_preview=True
    )
    preview = Path(info["preview"])
    if preview.exists():
        destination = ATTACH / f"{prefix.name}_preview.png"
        shutil.copy(preview, destination)
        info["preview_attach"] = str(destination)
    return info


def push_payload(payload: Path, cfg: dict) -> None:
    device_id = cfg.get("device_id")
    if not device_id:
        raise SystemExit("config missing device_id; run scan, pair, then probe --save")
    print_result(
        call_bridge(
            "send",
            companion_key=cfg["companion_key"],
            device_id=device_id,
            payload_path=payload,
        )
    )


def pick_place(places: list[dict], maximum_m: float) -> dict:
    candidates = [
        place
        for place in places
        if 0 < float(place.get("distance_m") or 0) <= maximum_m
    ]
    if not candidates:
        raise SystemExit("no nearby restaurants found within the requested distance")
    return random.choice(candidates[:60])


def cmd_eat(args) -> None:
    cfg = load_cfg()
    location = call_bridge("location", companion_key=cfg["companion_key"])
    latitude = float(location["latitude"])
    longitude = float(location["longitude"])
    print(
        f"location accuracy={location.get('accuracy_m')}m "
        f"provider={location.get('provider')}"
    )
    places = search_nearby_food(latitude, longitude, radius=args.radius)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "food_places.json").write_text(
        json.dumps(places, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    selected = pick_place(places, args.max_distance)
    (WORK / "food_pick.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"PICK {selected.get('name')} {selected.get('distance_m')}m "
        f"{selected.get('_query')}"
    )

    ATTACH.mkdir(parents=True, exist_ok=True)
    card = render(selected, ATTACH / "eat_card.png")
    orientation = cfg.get("screen_orientation") or DEFAULT_CONFIG["screen_orientation"]
    info = prepare_image(card, WORK / "eat_push", orientation)
    print(f"preview {info.get('preview_attach')}")
    if not args.prepare_only:
        push_payload(Path(info["qlz"]), cfg)


def cmd_config(args) -> None:
    cfg = load_cfg()
    def visible_config() -> dict:
        visible = dict(cfg)
        visible["companion_key"] = "***configured***"
        return visible

    if args.show or not any([args.device_id, args.device_name, args.orientation]):
        print_result(visible_config())
        print(f"path {CFG_PATH}")
        return
    if args.device_id:
        cfg["device_id"] = args.device_id.upper()
    if args.device_name:
        cfg["device_name"] = args.device_name
    if args.orientation:
        cfg["screen_orientation"] = args.orientation
    save_cfg(cfg)
    print_result(visible_config())


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="today-eats", description="TodooCard for Android Minis"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="scan compatible TodooCard devices")
    scan.set_defaults(func=cmd_scan)
    pair = subparsers.add_parser("pair", help="create the Android system bond")
    pair.add_argument("--device-id", required=True)
    pair.set_defaults(func=cmd_pair)
    probe = subparsers.add_parser(
        "probe", help="verify advertisement, bond, and image GATT"
    )
    probe.add_argument("--device-id")
    probe.add_argument("--save", action="store_true")
    probe.set_defaults(func=cmd_probe)
    location = subparsers.add_parser("location", help="test Android location access")
    location.set_defaults(func=cmd_location)

    config = subparsers.add_parser("config", help="show or update local config")
    config.add_argument("--show", action="store_true")
    config.add_argument("--device-id")
    config.add_argument("--device-name")
    config.add_argument(
        "--orientation",
        choices=["normal", "rotate-180-then-flip-horizontal"],
    )
    config.set_defaults(func=cmd_config)

    def add_eat_parser(name: str) -> None:
        eat = subparsers.add_parser(name, help="nearby random restaurant to TodooCard")
        eat.add_argument("--radius", type=int, default=2500)
        eat.add_argument("--max-distance", type=float, default=2800)
        eat.add_argument("--prepare-only", action="store_true")
        eat.set_defaults(func=cmd_eat)

    add_eat_parser("eat")
    add_eat_parser("今天吃点啥")
    args = parser.parse_args()
    try:
        args.func(args)
    except BridgeError as error:
        print(f"Android bridge error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
