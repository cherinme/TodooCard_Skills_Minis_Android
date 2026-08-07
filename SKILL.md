---
name: todoocard
version: 1.1.0
description: 附近随机外卖「今天吃点啥」并推送到 TodooCard（土豆片）六色电子纸。用于用户说今天吃点啥/中午吃啥/晚饭吃什么/随机外卖/推到土豆片时。通过 BLE FEF0 整帧发送（禁止断点续传）。
---

# TodooCard · 今天吃点啥

附近随机一家外卖，生成卡片并推送到 **TodooCard / 土豆片 / NEWSTONE**（528×792 六色电子纸）。

## 何时使用

- 「今天吃点啥」「中午吃啥」「晚饭吃什么」
- 「随机外卖」「附近吃什么」
- 「推到土豆片 / TodooCard」

## 命令

```bash
CLI="python3 /var/minis/skills/todoocard/scripts/todoocard_cli.py"

# 首次
$CLI scan
$CLI probe --device-id <UUID> --save

# 今天吃点啥
$CLI eat
$CLI 今天吃点啥

# 只出图不发送
$CLI eat --prepare-only
```

配置：`/var/minis/shared/todoocard/config.json`（参考 `config.example.json`）

## 流程

1. 确认 `device_id`
2. 定位 + 附近餐饮搜索 → 随机 1 家
3. `meal_template.py` 渲染「今天吃点啥」
4. 六色转换 + 整帧 BLE 推送

## 依赖

- `apple-bluetooth` `apple-location` `apple-maps`
- `py3-pillow`、`font-noto-cjk`

协议：`references/protocol.md`
