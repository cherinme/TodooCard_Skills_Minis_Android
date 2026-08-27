---
name: today-eats
version: 2.3.0
description: >
  在 Android Minis 中获取当前位置，从 OpenStreetMap 随机选择附近餐厅，
  生成“今天吃点啥”卡片并推送到 TodooCard。用户问今天吃什么、附近吃什么、
  随机餐厅或要求把推荐推到土豆片时使用。
compatibility: Android Minis; parent skill todoocard; network access required
---

# today-eats · 今天吃点啥

## 流程

1. 读取父技能配置，确认已保存 `device_id`；未保存时回到父技能的
   `scan` → `pair` → `probe --save`。
2. 通过 companion 获取 Android 当前坐标。首次运行由用户确认定位权限。
3. 明确告知用户：坐标将发送到公开 OpenStreetMap Overpass 服务用于附近
   餐饮查询；用户拒绝时停止联网，可改用 `--prepare-only` 配合手工地点数据。
4. 从请求半径内最多 60 个最近候选中随机一家，生成 528x792 卡片和预览。
5. `--prepare-only` 到此停止。正式推送前再次确认目标 MAC 与推荐餐厅，然后
   使用父技能 Android companion 整帧发送。

## 命令

```bash
CLI="python3 /var/minis/skills/todoocard/today-eats/scripts/cli.py"

$CLI eat
$CLI 今天吃点啥
$CLI eat --prepare-only
$CLI eat --radius 3500 --max-distance 3200
```

输出文件：

- `/var/minis/attachments/eat_card.png`
- `/var/minis/attachments/eat_push_preview.png`
- `/var/minis/workspace/todoocard_run/food_pick.json`

附近数据来自 OpenStreetMap 社区数据，可能不完整或过期。不要把“附近餐厅”
表述成“可外卖”，除非返回数据明确包含外卖属性。
