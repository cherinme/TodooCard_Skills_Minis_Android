# TodooCard Skill

向 **TodooCard / 土豆片 / NEWSTONE** 六色电子纸（528×792）推送画面的开源工具集。

适用于：

- Minis / iSH 上的 AI Agent Skill
- 命令行直接推图
- 天气卡、附近外卖随机推荐卡
- macOS 原生 CoreBluetooth 加速发送（可选）

> 本仓库**不包含**任何设备 UUID、账号 Cookie、API Key 或个人位置数据。  
> 设备相关配置请放在本地 `config.json`（已被 `.gitignore` 忽略）。

---

## 功能

| 能力 | 说明 |
|------|------|
| 任意图推送 | PNG/JPG → 六色抖动 → BLE 整帧发送 |
| 天气卡 | 读取定位 + WeatherKit 风格数据源（Minis `apple-weather`） |
| 早午晚餐随机推荐 | 搜索附近餐饮并生成高级模板卡片 |
| 安全发送 | **禁止断点续传**（半帧/乱序会导致花屏竖纹） |
| 原生加速（可选） | macOS `CoreBluetooth` 长连接 + `writeWithoutResponse` |

---

## 目录结构

```text
todoocard/
├── README.md
├── LICENSE
├── SKILL.md                 # Agent Skill 说明（Minis 可直接安装）
├── config.example.json      # 本地配置模板（无隐私）
├── references/
│   └── protocol.md          # BLE / 图像协议
└── scripts/
    ├── todoocard_cli.py     # 统一 CLI
    ├── image_to_payload.py  # 六色转换 + SE0368 + QuickLZ stored
    ├── safe_send.py         # 顺序整帧 BLE 发送（CLI）
    ├── fast_send.py         # 转换∥连接 流水线计时发送
    ├── dinner_template.py   # 早/午/晚餐卡片
    ├── weather_template.py  # 天气卡片
    ├── native_sender.swift  # 原生 CoreBluetooth 发送器源码
    ├── build_native_sender.sh
    └── qlz1.py              # 实验性压缩（默认未启用）
```

---

## 快速开始（Minis）

### 1. 安装为 Skill

把本仓库放到：

```text
/var/minis/skills/todoocard/
```

或在 Minis 中导入 Skill。

### 2. 本地配置（不要提交）

```bash
mkdir -p /var/minis/shared/todoocard
cp config.example.json /var/minis/shared/todoocard/config.json
```

扫描并写入自己的设备 ID：

```bash
CLI="python3 /var/minis/skills/todoocard/scripts/todoocard_cli.py"
$CLI scan
$CLI probe --device-id <你的UUID> --save
$CLI config --show
```

### 3. 常用命令

```bash
# 推任意图
$CLI push -i /path/to.png

# 只转换不发送
$CLI push -i /path/to.png --prepare-only

# 附近随机外卖（自动早/午/晚文案）
$CLI dinner
$CLI dinner --meal 午餐

# 天气卡
$CLI weather
```

### 依赖（Minis / Alpine）

```bash
apk add py3-pillow py3-numpy font-noto-cjk
# 以及 Minis 提供的：
# apple-bluetooth / apple-location / apple-maps / apple-weather
```

---

## 协议要点（务必读）

- 服务：`FEF0`  
  - 控制 `FEF1`（write / notify）  
  - 数据 `FEF2`（write / write_without_response / notify）  
  - 信息 `FEF3`（read，固件时间戳字符串）
- 块大小：设备返回 `01 F4 00` → ATT 244 字节 → **payload 240 字节**
- 图像：528×792，六色（黑/白/黄/红/蓝/绿 = 0/1/2/3/5/6）
- 控制器变换：SE0368
- 封装：QuickLZ **stored** 帧（官方兼容；`74 43 40` + 64B）
- **整帧发送，失败即中止，禁止 resume**（否则横纹/竖纹花屏）

完整说明见 [`references/protocol.md`](references/protocol.md)。

---

## 性能说明

在 Minis `apple-bluetooth` CLI 路径上（实测）：

| 阶段 | 大约耗时 |
|------|----------|
| 图片转换 | 视实现，纯 Python FS 可到约 1 分钟；可再优化 |
| 连接 + 握手 | ~1–3 s |
| 数据写入 | **~60 s**（≈65ms/块 × 913 块，CLI 强制 `with_response`） |
| 面板刷新等待 | 可配置，默认示例 8 s |

**端到端 30s 目标**在 CLI 路径通常不可达：仅数据段下限约 59s。  
要明显加速，请在 **macOS** 编译原生发送器：

```bash
./scripts/build_native_sender.sh ./scripts/native_sender
```

然后将本地配置：

```json
{
  "transport": "auto",
  "native_binary": "/absolute/path/to/native_sender"
}
```

`transport=auto` 时：有可执行原生二进制就用 CoreBluetooth，否则回退 CLI。

---

## 花屏 / 竖纹排查

常见原因：

1. **半帧或断点续传**（最常见）
2. **并发乱序写 FEF2**
3. 转换/SE0368 实现与设备不兼容

处理：

1. 只用顺序 `safe_send` 整帧重推  
2. 不要对索引数据块做多线程乱序写入  
3. 用校准图（纯色块 + TL/TR）验证方向

---

## 隐私与安全

本仓库刻意排除：

- 设备 UUID / 绑定信息
- 定位轨迹、外卖订单
- Cookie / Token / API Key
- 运行日志、`.bin` / `.protocol.qlz` 产物

请勿把以下本地文件打进公开仓库：

```text
**/config.json
**/cookies/**
**/*.env
**/*token*
**/*.protocol.qlz
**/*.bin
**/*.log
```

脚本具备真实 BLE 写屏能力：只在你自己的设备上使用，或明确授权后使用。

---

## 配置示例

见 [`config.example.json`](config.example.json)：

```json
{
  "device_id": "",
  "device_name": "",
  "screen_orientation": "rotate-180-then-flip-horizontal",
  "block_size": 240,
  "pace": 0.0,
  "wait_refresh": 8.0,
  "transport": "auto",
  "native_binary": "",
  "send_policy": "full-frame-only-no-resume"
}
```

`screen_orientation` 需按你的屏幕安装方向实测：

- `normal`
- `rotate-180-then-flip-horizontal`

---

## Agent 话术映射（SKILL）

- 「推到土豆片 / TodooCard」→ `push` / 对应模板
- 「中午/今晚吃什么」→ `dinner --meal …`
- 「天气推送到卡」→ `weather`
- 「花了/条纹」→ 说明禁止 resume，整帧重推

更完整的 Agent 说明见 [`SKILL.md`](SKILL.md)。

---

## 致谢

- 图像/BLE 协议参考了公开的 [TodooCard_Skills](https://github.com/Sunbelife/TodooCard_Skills) 思路
- 面板为 528×792 六色 T3 / SE0368 类设备

---

## License

MIT — 见 [LICENSE](LICENSE)
