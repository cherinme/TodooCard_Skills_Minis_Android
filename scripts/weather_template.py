#!/usr/bin/env python3
"""
TodooCard · Weather Template (高级简约)

528×792 e-paper card:
  - large temperature hero
  - one-line condition + location
  - 4 metric chips (体感 / 湿度 / 风速 / 气压)
  - 5-day strip
  - sunrise / sunset footer

Designed for 6-color Spectra panel (B/W/Y/R/Blue/G).
Uses high-contrast layout, generous whitespace, minimal chrome.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 528, 792

# Layout palette — pure enough to survive 6-color dither cleanly
BLACK = (18, 20, 24)
WHITE = (248, 246, 240)
CREAM = (242, 238, 228)
MUTED = (90, 92, 98)
YELLOW = (220, 185, 40)
RED = (175, 48, 42)
BLUE = (48, 78, 155)
GREEN = (52, 125, 78)
LINE = (28, 30, 36)

FONT_DIR = Path("/usr/share/fonts/noto")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (
        ["NotoSansCJK-Bold.ttc", "NotoSansCJK-Regular.ttc"]
        if bold
        else ["NotoSansCJK-Regular.ttc", "NotoSansCJK-Bold.ttc"]
    )
    for n in names:
        p = FONT_DIR / n
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def run_json(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    out = (p.stdout or "").strip()
    if not out:
        raise RuntimeError(f"empty output: {' '.join(cmd)}\n{p.stderr}")
    d = json.loads(out[out.find("{") :])
    if d.get("ok") is False:
        raise RuntimeError(d.get("error"))
    return d.get("data", d)


def fetch_weather() -> dict:
    loc = run_json(["apple-location", "current", "--accuracy", "km", "--compact"])
    weather = run_json(["apple-weather", "report", "--hours", "6", "--days", "5", "--compact"])
    return {"location": loc, "weather": weather, "fetched_at": datetime.now().isoformat(timespec="seconds")}


def cond_short(text: str) -> str:
    if not text:
        return "—"
    # keep it quiet
    t = text.replace("无云", "").replace("大部", "").replace("局部", "").strip()
    mapping = {
        "晴朗": "晴",
        "晴": "晴",
        "多云": "多云",
        "阴": "阴",
        "雨": "雨",
        "雷暴雨": "雷雨",
        "雷暴": "雷雨",
        "雪": "雪",
        "雾": "雾",
        "霾": "霾",
    }
    for k, v in mapping.items():
        if k in text:
            return v
    return text[:6]


def cond_accent(text: str, is_day: bool) -> tuple[int, int, int]:
    if any(k in text for k in ("雷", "暴", "雨", "雪")):
        return BLUE
    if any(k in text for k in ("晴",)):
        return YELLOW if is_day else BLUE
    if "云" in text or "阴" in text:
        return MUTED
    return GREEN


def weekday_cn(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
    except Exception:
        return ""
    return "一二三四五六日"[dt.weekday()]


def rrect(d: ImageDraw.ImageDraw, box, r=16, fill=None, outline=None, width=2):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def hline(d, y, x0=32, x1=W - 32, fill=LINE, width=2):
    d.line([(x0, y), (x1, y)], fill=fill, width=width)


def render(payload: dict, out_path: Path) -> Path:
    loc = payload["location"]
    w = payload["weather"]
    cur = w.get("current") or {}
    daily = w.get("daily") or []
    addr = loc.get("address") or {}

    city = addr.get("locality") or ""
    district = addr.get("sub_locality") or ""
    place = district or addr.get("name") or city or "当前位置"
    if city and district and district not in city:
        place_line = f"{city} · {district}"
    else:
        place_line = place

    temp = cur.get("temperature_c")
    feels = cur.get("apparent_temperature_c")
    humidity = cur.get("humidity")
    wind = cur.get("wind_speed_kmh")
    wind_dir = cur.get("wind_direction") or ""
    pressure = cur.get("pressure_hpa")
    condition = cur.get("condition") or "—"
    is_day = bool(cur.get("is_daylight"))
    uv = cur.get("uv_index")
    updated = datetime.now().strftime("%H:%M")

    temp_i = int(round(temp)) if temp is not None else "—"
    feels_i = int(round(feels)) if feels is not None else "—"
    hum_i = int(round((humidity or 0) * 100))
    wind_i = int(round(wind or 0))
    pressure_i = int(round(pressure or 0))

    accent = cond_accent(condition, is_day)

    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    f_brand = font(15, True)
    f_place = font(20)
    f_temp = font(148, True)
    f_unit = font(36, True)
    f_cond = font(32, True)
    f_label = font(16, True)
    f_value = font(28, True)
    f_small = font(18)
    f_day = font(18, True)
    f_tiny = font(14)

    # top thin accent
    d.rectangle([0, 0, W, 6], fill=BLACK)

    # brand + time
    d.text((36, 28), "WEATHER", font=f_brand, fill=MUTED)
    d.text((W - 36, 28), updated, font=f_brand, fill=MUTED, anchor="ra")
    d.text((36, 54), place_line, font=f_place, fill=BLACK)

    # hero temperature
    d.text((40, 210), f"{temp_i}", font=f_temp, fill=BLACK, anchor="lm")
    # degree mark
    tw = d.textlength(f"{temp_i}", font=f_temp)
    d.text((48 + tw, 145), "°", font=f_unit, fill=BLACK)
    d.text((48 + tw + 18, 200), "C", font=f_label, fill=MUTED)

    # condition pill
    short = cond_short(condition)
    pill_text = short
    pt_w = d.textlength(pill_text, font=f_cond)
    pill = [36, 290, 36 + pt_w + 36, 340]
    rrect(d, pill, r=22, fill=accent)
    fg = BLACK if accent == YELLOW else WHITE
    d.text(((pill[0] + pill[2]) / 2, (pill[1] + pill[3]) / 2), pill_text, font=f_cond, fill=fg, anchor="mm")

    # full condition under pill if different
    if condition and condition != short:
        d.text((36 + pt_w + 52, 315), condition, font=f_small, fill=MUTED, anchor="lm")

    hline(d, 370)

    # metric grid 2x2
    metrics = [
        ("体感", f"{feels_i}°", RED),
        ("湿度", f"{hum_i}%", BLUE),
        ("风速", f"{wind_i} km/h", GREEN),
        ("气压", f"{pressure_i}", YELLOW),
    ]
    # wind dir subtitle on wind cell via label
    if wind_dir:
        metrics[2] = (f"风速 · {wind_dir}", f"{wind_i}", GREEN)

    grid_top = 392
    cell_w, cell_h = 220, 88
    gap_x, gap_y = 20, 16
    origin_x = 36
    for i, (label, value, color) in enumerate(metrics):
        col, row = i % 2, i // 2
        x = origin_x + col * (cell_w + gap_x)
        y = grid_top + row * (cell_h + gap_y)
        rrect(d, [x, y, x + cell_w, y + cell_h], r=18, fill=CREAM, outline=None)
        # left accent bar
        d.rounded_rectangle([x + 10, y + 18, x + 16, y + cell_h - 18], radius=3, fill=color)
        d.text((x + 28, y + 22), label, font=f_label, fill=MUTED)
        d.text((x + 28, y + 52), value, font=f_value, fill=BLACK, anchor="lm")

    # 5-day strip
    strip_top = 612
    d.text((36, strip_top - 28), "五日", font=f_label, fill=MUTED)
    hline(d, strip_top - 8, x0=80)

    n = min(5, len(daily))
    if n:
        slot_w = (W - 72) / n
        for i in range(n):
            day = daily[i]
            cx = 36 + slot_w * i + slot_w / 2
            date = day.get("date") or ""
            wd = "今" if i == 0 else weekday_cn(date)
            hi = int(round(day.get("high_c") or 0))
            lo = int(round(day.get("low_c") or 0))
            c = cond_short(day.get("condition") or "")
            precip = day.get("precip_chance") or 0
            d.text((cx, strip_top + 8), wd, font=f_day, fill=BLACK, anchor="mt")
            d.text((cx, strip_top + 36), c, font=f_tiny, fill=MUTED, anchor="mt")
            d.text((cx, strip_top + 58), f"{hi}°", font=f_day, fill=BLACK, anchor="mt")
            d.text((cx, strip_top + 82), f"{lo}°", font=f_tiny, fill=MUTED, anchor="mt")
            if precip and precip >= 0.3:
                d.ellipse([cx - 3, strip_top + 104, cx + 3, strip_top + 110], fill=BLUE)

    # footer sunrise/sunset from today
    today = daily[0] if daily else {}
    sr, ss = today.get("sunrise") or "—", today.get("sunset") or "—"
    hline(d, H - 58)
    d.text((36, H - 34), f"日出 {sr}", font=f_small, fill=MUTED, anchor="lm")
    d.text((W / 2, H - 34), f"UV {uv if uv is not None else '—'}", font=f_small, fill=MUTED, anchor="mm")
    d.text((W - 36, H - 34), f"日落 {ss}", font=f_small, fill=MUTED, anchor="ra")

    # left spine
    d.rectangle([0, 0, 5, H], fill=BLACK)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="TodooCard weather template")
    ap.add_argument("--out", default="/var/minis/attachments/weather_card.png")
    ap.add_argument("--json-out", default="/var/minis/workspace/todoocard_run/weather_payload.json")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--device-id", default=None)
    args = ap.parse_args()

    print("fetching location + weather...")
    payload = fetch_weather()
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    out = render(payload, Path(args.out))
    print(f"rendered {out}")

    # also save as named template artifact
    tmpl_dir = Path("/var/minis/shared/todoocard/templates")
    tmpl_dir.mkdir(parents=True, exist_ok=True)
    out_copy = tmpl_dir / "weather.png"
    Image.open(out).save(out_copy)
    meta = {
        "name": "weather",
        "title": "高级简约天气",
        "size": "528x792",
        "script": str(Path(__file__).resolve()),
        "last_render": datetime.now().isoformat(timespec="seconds"),
        "place": (payload.get("location") or {}).get("address"),
    }
    (tmpl_dir / "weather.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("template saved", out_copy)

    if args.send:
        import subprocess

        here = Path(__file__).resolve().parent
        sys.path.insert(0, str(here))
        from image_to_payload import convert

        cfg_path = Path("/var/minis/shared/todoocard/config.json")
        cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
        device = args.device_id or cfg.get("device_id")
        if not device:
            raise SystemExit("missing device_id in config")
        orient = cfg.get("screen_orientation") or "rotate-180-then-flip-horizontal"
        block = int(cfg.get("block_size") or 240)
        if block > 240:
            block = 240
        out_dir = Path("/var/minis/workspace/todoocard_run")
        out_dir.mkdir(parents=True, exist_ok=True)
        print("converting…")
        info = convert(out, str(out_dir / "weather_push"), orientation=orient, make_preview=True)
        Path("/var/minis/attachments/weather_card_preview.png").write_bytes(Path(info["preview"]).read_bytes())
        print(f"payload {info['qlz_bytes']} bytes → {device}")
        native = Path(cfg.get("native_binary") or (here / "native_sender"))
        if (cfg.get("transport") or "auto") in {"auto", "native"} and native.exists() and native.is_file() and native.stat().st_mode & 0o111:
            cmd = [str(native), "--payload", info["qlz"], "--compressed", "--id", device]
        elif cfg.get("transport") == "native":
            raise SystemExit(f"native sender not built: {native}")
        else:
            cmd = [
                "python3", str(here / "safe_send.py"), "--device-id", device,
                "--payload", info["qlz"], "--block-size", str(block),
                "--pace", str(float(cfg.get("pace") or 0.0)),
                "--wait-refresh", str(float(cfg.get("wait_refresh") or 40.0)),
            ]
        subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
