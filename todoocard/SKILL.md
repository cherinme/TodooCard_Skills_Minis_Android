---
name: todoocard
version: 2.0.0
description: >
  Android Minis 上的 TodooCard（土豆片 / NEWSTONE）六色电子纸技能族。
  用户提到土豆片、TodooCard、电子纸推送、扫描或绑定卡片时使用。
  当前子技能 today-eats 可随机推荐附近餐厅并推送。
compatibility: >
  Minis for Android with android-open; Android 8.0+; bundled TodooCard companion;
  Python 3, py3-pillow, font-noto-cjk. today-eats needs network access.
---

# todoocard for Android Minis

这是 Android 专用父技能。图像编码在 Minis 的 Python 环境内完成；BLE 和
定位由同一台手机上的 `TodooCard BLE Bridge` companion 完成。两者只通过
`127.0.0.1` 上的一次性 token 通信，不需要电脑、ADB 或 Apple CLI。

## 子技能

| 子技能 | 目录 | 触发示例 |
|---|---|---|
| 今天吃点啥 | `today-eats/` | 今天吃点啥、中午吃啥、随机附近餐厅 |

匹配子技能意图时，先读取子技能的 `SKILL.md`。

## 首次设置

1. 确认 `android-open` 存在；不存在就停止，说明本技能只支持 Android Minis。
2. 安装 `assets/todoocard-android-bridge.apk`。APK 也提供完整源码于
   `android-bridge/`；Android 会要求用户确认安装来源。
3. 首次 `scan` 时 companion 显示 **Trust this Minis and continue**。只在用户
   刚发起命令时确认；之后用本地 256-bit key 认证每次请求。
4. 在 Android 设置中允许 companion 的“附近设备”和定位权限。不要要求
   Minis 无障碍服务，本技能不靠 UI 点击控制 BLE。
5. 依次执行：

```bash
CLI="python3 /var/minis/skills/todoocard/today-eats/scripts/cli.py"

$CLI scan
$CLI pair --device-id AA:BB:CC:DD:EE:FF
$CLI probe --device-id AA:BB:CC:DD:EE:FF --save
```

`device_id` 必须是 `scan` 返回的精确 Android BLE MAC 地址。首次配对前，让
用户按设备说明打开实体配对窗口，并在 Android 系统弹窗中确认配对。

## 设备操作约束

- `scan` 只扫描，不连接、不写入。
- `pair`、`probe`、`send` 是分离操作；不要把它们暗中合并。
- 配对窗口开启时拒绝 `probe` 和 `send`。
- 安全固件必须以加密 Battery Level 读取证明系统 bond 可用。
- 发送失败或断连后禁止从中间 block 续传，必须重新握手并整帧发送。
- 未收到卡片最终刷新确认，不能报告发送成功。
- 发送前说明目标 MAC 和将显示的内容，并取得用户确认。

## 依赖与隐私

- Android Minis 内置 `android-open`
- `python3`、Pillow、Noto CJK 字体
- companion 只申请蓝牙、定位和网络权限；无广域存储权限
- localhost RPC 只服务单次请求；payload 不上传
- `companion_key` 自动生成并存本地配置，展示配置时必须打码
- today-eats 使用 Android 定位，并把坐标发给公开的 OpenStreetMap Overpass
  服务查询附近餐饮；执行前向用户说明这一网络请求

协议详情：`references/protocol.md`。
