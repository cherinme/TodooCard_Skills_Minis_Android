---
name: today-eats
version: 1.1.0
description: >
  附近随机外卖「今天吃点啥」并推送到 TodooCard（土豆片）六色电子纸。
  用于用户说今天吃点啥、中午吃啥、晚饭吃什么、随机外卖、附近吃什么、推到土豆片时。
---

# today-eats · 今天吃点啥

附近随机一家外卖，生成卡片并推送到 TodooCard / 土豆片（528×792 六色电子纸）。

## 何时使用

- 「今天吃点啥」「中午吃啥」「晚饭吃什么」
- 「随机外卖」「附近吃什么」
- 「推到土豆片 / TodooCard」（在要推荐吃什么的语境下）

## 命令

本技能位于 monorepo 的 `today-eats/`。共享传输层在 `shared/`。

```bash
CLI="python3 today-eats/scripts/cli.py"

# 首次绑定设备（写入 /var/minis/shared/todoocard/config.json）
$CLI scan
$CLI probe --device-id <UUID> --save

# 今天吃点啥
$CLI eat
$CLI 今天吃点啥

# 只出图
$CLI eat --prepare-only
```

Minis 安装后路径示例：

```bash
python3 /var/minis/skills/today-eats/scripts/cli.py eat
```

## 流程

1. 确认本地 `device_id`（`scan` / `probe --save`）
2. `apple-location` 定位 + `apple-maps` 多品类搜索 → 随机 1 家
3. `meal_template.py` 渲染「今天吃点啥」卡片
4. 调用 `shared` 传输层：六色转换 + 整帧 BLE 推送

## 依赖

- Minis：`apple-bluetooth` `apple-location` `apple-maps`
- `py3-pillow`、`font-noto-cjk`
- 共享代码：仓库内 `shared/scripts`（或与本技能一并安装）

设备配置示例：`shared/config.example.json`  
协议：`shared/references/protocol.md`
