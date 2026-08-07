#!/usr/bin/env python3
"""TodooCard skill CLI — prepare / push images & templates to e-paper card."""
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
SHARED = Path("/var/minis/shared/todoocard")
CFG_PATH = SHARED / "config.json"
ATTACH = Path("/var/minis/attachments")
WORK = Path("/var/minis/workspace/todoocard_run")

sys.path.insert(0, str(SCRIPTS))
from image_to_payload import convert  # noqa: E402


def load_cfg() -> dict:
    SHARED.mkdir(parents=True, exist_ok=True)
    if CFG_PATH.exists():
        return json.loads(CFG_PATH.read_text())
    cfg = {
        "device_id": "",
        "device_name": "",
        "screen_orientation": "rotate-180-then-flip-horizontal",
        "block_size": 240,
        "target": "t3",
        "size": "528x792",
        "send_policy": "full-frame-only-no-resume",
        "pace": 0.0,
        "wait_refresh": 40.0,
        "transport": "auto",
        "native_binary": "/var/minis/skills/todoocard/scripts/native_sender",
    }
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    return cfg


def save_cfg(cfg: dict) -> None:
    SHARED.mkdir(parents=True, exist_ok=True)
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))


def run(cmd: list[str], timeout: int = 120) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    out = (p.stdout or "").strip()
    if not out:
        raise RuntimeError(f"empty: {' '.join(cmd)}\n{p.stderr}")
    # may contain non-json prefix
    start = out.find("{")
    if start < 0:
        raise RuntimeError(out[:500])
    return json.loads(out[start:])


def bt(args: list[str], timeout: int = 60) -> dict:
    d = run(["apple-bluetooth", *args, "--compact"], timeout=timeout)
    if d.get("ok") is False:
        raise RuntimeError(str(d.get("error")))
    return d


def cmd_scan(args):
    print("scanning BLE…")
    d = bt(["scan", "--duration", str(args.duration)], timeout=args.duration + 30)
    devs = (d.get("data") or {}).get("devices") or []
    hits = []
    for x in devs:
        name = (x.get("name") or "")
        svcs = x.get("advertised_services") or []
        blob = (" ".join(map(str, svcs)) + " " + name).lower()
        if any(k in blob for k in ["fef0", "fdf0", "newstone", "todoo", "potato", "nemr", "picksmart"]):
            hits.append(x)
            print(
                f"HIT rssi={x.get('rssi')} name={name!r} uuid={x.get('uuid')} services={svcs}"
            )
    if not hits:
        print("no FEF0/NEWSTONE hits; named devices:")
        for x in sorted([z for z in devs if z.get("name")], key=lambda z: -(z.get("rssi") or -999))[:20]:
            print(f"  {x.get('rssi')} {x.get('name')!r} {x.get('uuid')}")
    return hits


def cmd_probe(args):
    cfg = load_cfg()
    dev = args.device_id or cfg.get("device_id")
    if not dev:
        raise SystemExit("need --device-id or config device_id")
    print("connect", dev)
    bt(["connect", "--uuid", dev], timeout=45)
    svc = bt(["services", "--uuid", dev])
    print(json.dumps(svc.get("data"), ensure_ascii=False, indent=2))
    try:
        info = bt(["read", "--uuid", dev, "--service", "FEF0", "--characteristic", "FEF3"])
        print("FEF3", info.get("data"))
    except Exception as e:
        print("FEF3", e)
    # block size via notify
    import threading

    box = {}

    def nworker():
        try:
            box["r"] = bt(
                [
                    "notify",
                    "--uuid",
                    dev,
                    "--service",
                    "FEF0",
                    "--characteristic",
                    "FEF1",
                    "--duration",
                    "8",
                ],
                timeout=40,
            )
        except Exception as e:
            box["e"] = str(e)

    t = threading.Thread(target=nworker)
    t.start()
    time.sleep(2)
    try:
        bt(["write", "--uuid", dev, "--service", "FEF0", "--characteristic", "FEF1", "--value", "01"])
    except Exception as e:
        print("write01", e)
    t.join(timeout=15)
    samples = ((box.get("r") or {}).get("data") or {}).get("samples") or []
    block = None
    for s in samples:
        hx = (s.get("value_hex") or "").replace(" ", "")
        if len(hx) >= 6 and hx.startswith("01") and hx.endswith("00"):
            block = int(hx[2:4], 16) - 4
            print("block_size", block, "raw", hx)
    name = (svc.get("data") or {}).get("name") or cfg.get("device_name")
    if args.save:
        cfg["device_id"] = dev
        if name:
            cfg["device_name"] = name
        if block:
            cfg["block_size"] = block
        save_cfg(cfg)
        print("saved", CFG_PATH)
    try:
        bt(["disconnect", "--uuid", dev])
    except Exception:
        pass


def prepare_image(src: Path, prefix: Path, orientation: str) -> dict:
    WORK.mkdir(parents=True, exist_ok=True)
    ATTACH.mkdir(parents=True, exist_ok=True)
    info = convert(str(src), str(prefix), orientation=orientation, make_preview=True)
    # copy preview to attachments
    prev = Path(info["preview"])
    if prev.exists():
        dest = ATTACH / f"{prefix.name}_preview.png"
        shutil.copy(prev, dest)
        info["preview_attach"] = str(dest)
    return info


def push_payload(payload: Path, cfg: dict, block_size: int | None = None, pace: float | None = None, transport: str | None = None):
    dev = cfg.get("device_id")
    if not dev:
        raise SystemExit("config missing device_id — run: todoocard_cli.py scan && probe --save")

    selected = transport or cfg.get("transport") or "auto"
    native_bin = Path(cfg.get("native_binary") or (SCRIPTS / "native_sender"))
    if selected in {"auto", "native"} and native_bin.exists() and native_bin.is_file() and native_bin.stat().st_mode & 0o111:
        cmd = [
            str(native_bin),
            "--payload",
            str(payload),
            "--compressed",
            "--id",
            dev,
        ]
        print("exec native CoreBluetooth:", " ".join(cmd), flush=True)
        subprocess.check_call(cmd)
        return
    if selected == "native":
        raise SystemExit(
            f"native sender not built: {native_bin}. Run build_native_sender.sh on macOS with Xcode/swiftc."
        )

    bs = str(block_size or cfg.get("block_size") or 240)
    pc = str(pace if pace is not None else cfg.get("pace") or 0.0)
    wait_refresh = str(float(cfg.get("wait_refresh") or 40.0))
    cmd = [
        sys.executable,
        str(SCRIPTS / "safe_send.py"),
        "--device-id",
        dev,
        "--payload",
        str(payload),
        "--block-size",
        bs,
        "--pace",
        pc,
        "--wait-refresh",
        wait_refresh,
    ]
    # Prefer instrumented/pipelined fast_send when pushing from a source image path
    # is not available here (payload already built). Keep safe_send as the
    # block-stream engine.
    print("exec CLI fallback:", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)


def cmd_push(args):
    cfg = load_cfg()
    src = Path(args.input)
    if not src.exists():
        raise SystemExit(f"missing image: {src}")
    orient = args.orientation or cfg.get("screen_orientation") or "rotate-180-then-flip-horizontal"
    WORK.mkdir(parents=True, exist_ok=True)
    prefix = WORK / (args.prefix or f"push_{datetime.now().strftime('%H%M%S')}")
    print("convert", src, "orient", orient)
    info = prepare_image(src, prefix, orient)
    print(json.dumps({k: info[k] for k in info if k != "codes"}, ensure_ascii=False, indent=2))
    # also copy source-ish card if png
    if src.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        shutil.copy(src, ATTACH / f"{prefix.name}_source{src.suffix.lower()}")
    if args.prepare_only:
        print("prepare-only done")
        return
    push_payload(Path(info["qlz"]), cfg, args.block_size, args.pace, args.transport)


def search_nearby_food(lat: float, lon: float, radius: int = 2500) -> list[dict]:
    queries = [
        "中餐厅",
        "火锅",
        "烧烤",
        "麻辣烫",
        "面条",
        "盖饭",
        "快餐",
        "日料",
        "韩式料理",
        "炸鸡",
        "汉堡",
        "披萨",
        "小吃",
        "米粉",
        "黄焖鸡",
        "冒菜",
        "饺子",
        "寿司",
    ]
    all_places: dict[str, dict] = {}
    for q in queries:
        try:
            d = run(
                [
                    "apple-maps",
                    "search",
                    "--query",
                    q,
                    "--lat",
                    str(lat),
                    "--lon",
                    str(lon),
                    "--radius",
                    str(radius),
                    "--limit",
                    "12",
                    "--compact",
                ],
                timeout=30,
            )
        except Exception as e:
            print("search fail", q, e)
            continue
        if not d.get("ok"):
            continue
        items = (d.get("data") or {}).get("places") or (d.get("data") or {}).get("results") or []
        if isinstance(d.get("data"), list):
            items = d["data"]
        if not isinstance(items, list):
            continue
        for it in items:
            name = it.get("name") or ""
            la = it.get("lat")
            lo = it.get("lon")
            key = f"{name}|{round(float(la or 0),5)}|{round(float(lo or 0),5)}"
            it = dict(it)
            it["_query"] = q
            all_places[key] = it
        print(f"{q} → {len(items)}")
    return list(all_places.values())


def pick_dinner(places: list[dict], max_m: float = 2800) -> dict:
    exclude = ["咖啡", "茶饮", "奶茶", "酒吧", "KTV", "酒店", "超市", "便利店", "加油站", "不对外开放"]
    cands = []
    for it in places:
        name = it.get("name") or ""
        if any(k in name for k in exclude):
            continue
        dist = it.get("distance_m")
        if dist is None:
            continue
        if dist > max_m:
            continue
        cands.append(it)
    # unique by name nearest first
    seen = set()
    uniq = []
    for it in sorted(cands, key=lambda x: x.get("distance_m") or 1e9):
        if it["name"] in seen:
            continue
        seen.add(it["name"])
        uniq.append(it)
    if not uniq:
        raise SystemExit("no nearby restaurants found")
    pool = uniq[:60]
    return random.choice(pool)


def cmd_dinner(args):
    cfg = load_cfg()
    print("location…")
    loc = run(["apple-location", "current", "--accuracy", "km", "--compact"])
    data = loc.get("data") or loc
    lat, lon = data["latitude"], data["longitude"]
    addr = data.get("address") or {}
    print("at", addr, lat, lon)

    places = search_nearby_food(lat, lon, radius=args.radius)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "food_places.json").write_text(json.dumps(places, ensure_ascii=False, indent=2))
    pick = pick_dinner(places, max_m=args.max_distance)
    pick_path = WORK / "food_pick.json"
    pick_path.write_text(json.dumps(pick, ensure_ascii=False, indent=2))
    print("PICK", pick.get("name"), pick.get("distance_m"), "m", pick.get("_query"))

    # render premium template
    from dinner_template import render

    card = ATTACH / "dinner_card.png"
    render(pick, card, meal_override=args.meal)
    print("card", card)

    if args.prepare_only or args.no_send:
        # still convert preview
        orient = cfg.get("screen_orientation") or "rotate-180-then-flip-horizontal"
        info = prepare_image(card, WORK / "dinner_push", orient)
        print("preview", info.get("preview_attach"))
        return

    # push via template helper path
    orient = cfg.get("screen_orientation") or "rotate-180-then-flip-horizontal"
    info = prepare_image(card, WORK / "dinner_push", orient)
    shutil.copy(info["preview"], ATTACH / "dinner_card_preview.png")
    push_payload(Path(info["qlz"]), cfg)


def cmd_weather(args):
    cfg = load_cfg()
    # weather_template has its own fetch+render; call functions
    import weather_template as wt

    print("fetch weather…")
    payload = wt.fetch_weather()
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "weather_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    card = ATTACH / "weather_card.png"
    wt.render(payload, card)
    print("card", card)
    if args.no_send or args.prepare_only:
        orient = cfg.get("screen_orientation") or "rotate-180-then-flip-horizontal"
        info = prepare_image(card, WORK / "weather_push", orient)
        print("preview", info.get("preview_attach"))
        return
    orient = cfg.get("screen_orientation") or "rotate-180-then-flip-horizontal"
    info = prepare_image(card, WORK / "weather_push", orient)
    shutil.copy(info["preview"], ATTACH / "weather_card_preview.png")
    push_payload(Path(info["qlz"]), cfg)


def cmd_config(args):
    cfg = load_cfg()
    if args.show or not any([args.device_id, args.orientation, args.block_size, args.pace is not None]):
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        print("path", CFG_PATH)
        return
    if args.device_id:
        cfg["device_id"] = args.device_id
    if args.orientation:
        cfg["screen_orientation"] = args.orientation
    if args.block_size:
        cfg["block_size"] = args.block_size
    if args.pace is not None:
        cfg["pace"] = args.pace
    if args.device_name:
        cfg["device_name"] = args.device_name
    save_cfg(cfg)
    print("updated", json.dumps(cfg, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(prog="todoocard", description="TodooCard / Potato e-paper skill CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan", help="scan nearby TodooCard-like BLE devices")
    p.add_argument("--duration", type=int, default=12)
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("probe", help="probe device services / block size")
    p.add_argument("--device-id")
    p.add_argument("--save", action="store_true")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("config", help="show/update shared config")
    p.add_argument("--show", action="store_true")
    p.add_argument("--device-id")
    p.add_argument("--device-name")
    p.add_argument("--orientation", choices=["normal", "rotate-180-then-flip-horizontal"])
    p.add_argument("--block-size", type=int)
    p.add_argument("--pace", type=float)
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("push", help="convert image and push to card")
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--orientation")
    p.add_argument("--prefix")
    p.add_argument("--prepare-only", action="store_true")
    p.add_argument("--block-size", type=int)
    p.add_argument("--pace", type=float)
    p.add_argument("--transport", choices=["auto", "native", "cli"], default=None)
    p.set_defaults(func=cmd_push)

    p = sub.add_parser("dinner", help="random nearby takeout meal → card → push")
    p.add_argument("--meal", choices=["早餐", "午餐", "晚餐"], default=None, help="override meal label")
    p.add_argument("--radius", type=int, default=2500)
    p.add_argument("--max-distance", type=float, default=2800)
    p.add_argument("--no-send", action="store_true")
    p.add_argument("--prepare-only", action="store_true")
    p.set_defaults(func=cmd_dinner)

    p = sub.add_parser("weather", help="current weather card → push")
    p.add_argument("--no-send", action="store_true")
    p.add_argument("--prepare-only", action="store_true")
    p.set_defaults(func=cmd_weather)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
