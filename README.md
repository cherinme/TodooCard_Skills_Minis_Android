# TodooCard · 今天吃点啥

附近随机一家外卖，生成卡片并推送到 **TodooCard / 土豆片** 六色电子纸（528×792）。

面向 Minis / OpenMinis 的 Skill。仓库不含设备 UUID、Token 或个人数据。

## 技能介绍

当你说：

- 「今天吃点啥」
- 「中午吃啥 / 晚饭吃什么」
- 「随机外卖 / 附近吃什么」

Skill 会：

1. 读取当前位置
2. 搜索附近多品类餐饮
3. 随机推荐 **一家**
4. 生成「今天吃点啥」卡片
5. 推送到 TodooCard 电子纸

## 安装（Minis）

放到：

```text
/var/minis/skills/todoocard/
```

```bash
CLI="python3 /var/minis/skills/todoocard/scripts/todoocard_cli.py"

# 首次绑定设备
$CLI scan
$CLI probe --device-id <UUID> --save

# 今天吃点啥
$CLI eat
$CLI 今天吃点啥

# 只生成卡片，不发送
$CLI eat --prepare-only
```

本地配置（**不要提交**）：

```bash
mkdir -p /var/minis/shared/todoocard
cp config.example.json /var/minis/shared/todoocard/config.json
```

## 目录结构

```text
todoocard/
├── SKILL.md
├── README.md
├── LICENSE
├── config.example.json
├── references/
│   └── protocol.md
└── scripts/
    ├── todoocard_cli.py
    ├── meal_template.py
    ├── image_to_payload.py
    ├── safe_send.py
    ├── fast_send.py
    ├── native_sender.swift
    └── build_native_sender.sh
```

## 依赖

```bash
apk add py3-pillow font-noto-cjk
```

需要 Minis 提供：`apple-bluetooth`、`apple-location`、`apple-maps`。

## 配置

见 [`config.example.json`](config.example.json)。

| 字段 | 说明 |
|------|------|
| `device_id` | 设备 UUID（`probe --save`） |
| `screen_orientation` | `normal` 或 `rotate-180-then-flip-horizontal` |
| `block_size` | 默认 `240` |
| `transport` | `auto` / `cli` / `native` |

## 传输与协议

发送与图像编码细节见 [`references/protocol.md`](references/protocol.md)。

- 服务 `FEF0`，数据块 payload **240** 字节
- 六色 SE0368 + QuickLZ stored 帧
- **整帧发送**；中途失败整图重来

可选：在 macOS 编译原生发送器以加速传输：

```bash
./scripts/build_native_sender.sh ./scripts/native_sender
```

配置 `transport: auto` 后，若存在可执行的 `native_sender` 会优先使用。

## License

MIT
