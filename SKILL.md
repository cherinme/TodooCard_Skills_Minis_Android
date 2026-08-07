---
name: todoocard
version: 1.0.0
description: 将图片/天气/附近外卖晚餐推荐推送到 TodooCard（土豆片）六色电子纸。用于用户说推送到土豆片/TodooCard/NEWSTONE、刷新天气卡、随机外卖晚餐、电子纸传图、修复花屏重推时。通过 BLE FEF0 协议整帧发送（禁止断点续传）。
---

# TodooCard Skill

向 **TodooCard / 土豆片 / NEWSTONE** 六色电子纸（528×792）推送画面。

## 何时使用

- 「推到土豆片 / TodooCard / 电子纸」
- 「随机附近外卖当晚餐并推送」
- 「天气推送到土豆片」
- 「传这张图到卡」
- 花屏后需要**整帧重推**

## 快速命令

脚本根目录：`/var/minis/skills/todoocard/scripts`  
配置：`/var/minis/shared/todoocard/config.json`

```bash
CLI="python3 /var/minis/skills/todoocard/scripts/todoocard_cli.py"

# 首次 / 换设备
$CLI scan
$CLI probe --device-id <UUID> --save

# 看配置
$CLI config --show

# 推任意图片（默认用配置里的方向）
$CLI push -i /path/to.png

# 只出图不发送
$CLI push -i /path/to.png --prepare-only

# 在 macOS 上编译原生 CoreBluetooth 长连接发送器（需 Xcode Command Line Tools）
/var/minis/skills/todoocard/scripts/build_native_sender.sh /var/minis/skills/todoocard/scripts/native_sender
# 编译成功后，`transport: auto` 会自动优先使用原生发送器；否则回退 CLI

# 附近随机外卖晚餐 → 高级模板 → 推送
$CLI dinner

# 实时天气卡 → 推送
$CLI weather
```

## 标准工作流

1. **确认配置**有 `device_id`；没有则 `scan` → `probe --save`。
2. **出图**：模板脚本或用户图片 → 528×792 PNG。
3. **转换**：`image_to_payload.py`（六色 Floyd–Steinberg + SE0368 + QuickLZ）。
4. **发送**：`safe_send.py` / `fast_send.py` **整帧**；任一 block 失败立刻中止，**禁止 resume**。block=240；pace=0。
5. 聊天里用 Markdown 展示 `minis://attachments/*_preview.png` 与源卡。

### 当前实测（iSH + apple-bluetooth CLI）

| 阶段 | 优化后 |
|------|--------|
| 转换 | **~0.5–2s**（Pillow C 抖动，原 ~65s） |
| 连接+握手 | **~1.5–2s**（与转换流水线重叠） |
| 数据写入 | **~58–62s**（硬瓶颈：CLI `with_response` ≈65ms/块 ×913） |
| 刷新等待 | **8s**（可配，原 40s） |
| 端到端 | **~70s**（流水线后） |

**30s 目标在本机 CLI 路径不可达**：仅数据段下限 ≈ 913×0.065s ≈ 59s。必须启用 macOS 原生 `native_sender`（`withoutResponse` 流控）才能把数据段打进 30s。

## 硬性规则

| 项 | 值 |
|----|-----|
| 分辨率 | 528×792 |
| 色数 | 6（黑白黄红蓝绿，码 0/1/2/3/5/6） |
| block payload | **240**（设备 `01f400` → 244−4） |
| 方向（本机已校准） | `rotate-180-then-flip-horizontal` |
| 发送策略 | full-frame only，pace=0；设备 CLI 当前强制 `with_response`；macOS 原生 sender 使用 `withoutResponse` |
| 单块耗时 | 实测约 90ms（含一次 apple-bluetooth CLI 调用） |
| 数据耗时 | 约 80–90s / 218893B；另有面板刷新等待约 40s |
| 断线 | 整图重来，绝不续传 |

## 性能

- 当前每个 240B 数据块都由独立的 `apple-bluetooth` CLI 调用发送；工具报告 `write_type=with_response`，所以约 0.09s/块是主要瓶颈。
- 已移除脚本额外 `pace`，并跳过已知 block size 的 notify 探测；正常数据段目标约 80–90s。
- `wait_refresh` 只是等待面板刷新，不是传输速度；可在配置中调整，但过短可能在屏幕尚未完成刷新时断开。
- 真正降到几秒需要原生 CoreBluetooth 长连接，`scripts/native_sender.swift` 已实现：`writeValue(..., type: .withoutResponse)` + `canSendWriteWithoutResponse` 流控。macOS 编译出 `native_sender` 后，CLI `transport=auto` 会优先使用它；本机 iSH/Linux 无法编译，自动回退 CLI。


| 命令 | 模板 | 输出 |
|------|------|------|
| `dinner` | 高级晚餐随机卡 | `dinner_card.png` |
| `weather` | 简约天气卡 | `weather_card.png` |
| `push -i` | 任意图 | 调用方提供 |

模板定义也在 `/var/minis/shared/todoocard/templates/`。

## 用户话术映射

- 「随机外卖/今晚吃什么/附近推荐」→ `dinner`
- 「天气/气温」→ `weather`
- 「推这张图」→先存 attachments，再 `push -i …`
- 「花了/条纹」→说明是续传错位；`push`/`dinner`/`weather` 整帧重推
- 「方向反了」→ `config --orientation …` 后重推

## 依赖

- `apple-bluetooth`, `apple-location`, `apple-weather`, `apple-maps`
- macOS 原生加速：Xcode Command Line Tools / `swiftc`，CoreBluetooth 权限
- Python：`Pillow`（`apk add py3-pillow`）
- 字体：`font-noto-cjk`（中文模板）

## 详情

协议与故障见 [references/protocol.md](references/protocol.md)。
