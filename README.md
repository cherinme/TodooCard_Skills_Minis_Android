感谢原项目 https://github.com/Sunbelife/TodooCard_Skills 、
小玩具挺好玩。
本项目纯基于Codex，这货道德感挺强应该没有雷，欢迎大家审查

# TodooCard Skills for Android Minis

在 Android 版 [Minis](https://github.com/OpenMinis) 中扫描、绑定并整帧推送内容到
TodooCard / 土豆片 T3 六色电子纸（528x792）。当前包含“今天吃点啥”子技能。

> 非官方社区项目，与 TodooCard、NEWSTONE 或 Minis 品牌方无隶属关系。

## Android 版变化

原仓库依赖 iOS 的 `apple-bluetooth`、`apple-location`、`apple-maps` 和可选
CoreBluetooth 发送器。本版本已完整移除这些依赖：

- Android Minis 用 `android-open` 唤起同机 companion APK
- companion 直接使用 Android BLE GATT 和系统 bond
- 完成首次信任和权限授权后，companion 自动退回 Minis 并在前台服务中处理请求
- 传输时请求高优先级 BLE 连接和 247+ MTU，优先使用逐块确认写入并回传进度心跳
- `probe/send` 直接连接已绑定 MAC，不要求卡片重新进入配对广播模式
- Minis 与 companion 只通过 `127.0.0.1` 一次性 token 通信
- Android 系统定位替代 Apple Location
- OpenStreetMap Overpass 替代 Apple Maps 餐饮搜索
- 保留六色抖动、SE0368、QuickLZ stored 和整帧禁止续传策略

不需要电脑、ADB、Termux 无线调试、Xcode 或 Swift。

## 安装

### 1. 发布到自己的 GitHub 仓库

Android Minis 从 URL 导入技能。把本目录推到你自己的公开仓库后，导入父技能的
`SKILL.md` 文件：

```text
https://github.com/<你的账号>/<仓库名>/blob/main/todoocard/SKILL.md
```

在 Minis 中打开：**设置 → 技能 → 导入技能 → URL**。

### 2. 安装 companion APK

在同一台 Android 手机上打开仓库中的：

```text
todoocard/assets/todoocard-android-bridge.apk
```

下载并安装。Android 会要求确认“安装未知应用”；这是不可绕过的用户安全操作。
APK 的完整源码在 `todoocard/android-bridge/`，可自行审计和重建。

首次操作时允许：

- **附近设备**：扫描、连接和发送 TodooCard
- **定位**：仅“今天吃点啥”使用

companion 不申请通讯录、相册或广域存储权限。

首次信任、运行时权限和 Android 系统配对必须显示界面。完成这些设置后，扫描、
定位、探测和发送不会停留在 companion 界面；执行期间只显示一条静音的低优先级
前台服务通知，任务结束后自动消失。Android 不允许可靠的后台 BLE 完全隐藏通知。

`send` 默认最长等待 15 分钟，但不是盲等：APK 每 5% 向 Minis 回传一次进度；
连续 240 秒没有进度才判定桥接停滞。成功结果包含 MTU、写入模式、数据写入耗时、
刷新等待耗时和吞吐率，便于定位不同手机 ROM 的 BLE 性能。

FEF2 同时支持确认写和无响应写时默认选择确认写，确保每个块已被 GATT 接收后才
发送下一块。只有不支持确认写时才使用 12 ms 限速的无响应写。卡片若通过 FEF1
要求非零块续传，仍会终止整帧；不会为了速度放开可能导致错位花屏的中间续传。

卡片可能在上一次失败后保留续传位置。若新握手在 `0%`、尚未写入数据时返回旧的
非零块号，companion 会忽略该位置并强制从 block 0 顺序覆盖全部 913 个块；这不是
中间续传。传输开始后若再次要求非零块，仍立即终止。

第一次运行 `scan` 时 companion 会显示 **Trust this Minis and continue**。
只在你刚刚发起命令时点一次；此后 companion 用本地 256-bit key 验证请求。
要更换 Minis 运行环境，在 Android 设置中清除 companion 的应用数据后重新信任。

### 3. Minis 运行依赖

```sh
apk add py3-pillow font-noto-cjk
```

Android Minis 必须提供 `/usr/local/bin/android-open`。若不存在，说明当前不是受支持
的 Android Minis 运行环境。

## 快速开始

```bash
CLI="python3 /var/minis/skills/todoocard/today-eats/scripts/cli.py"

# 1. 扫描，只读
$CLI scan

# 2. 打开土豆片实体配对窗口，再绑定精确 MAC
$CLI pair --device-id AA:BB:CC:DD:EE:FF

# 3. 验证加密 bond 和图像 GATT，保存设备
$CLI probe --device-id AA:BB:CC:DD:EE:FF --save

# 4. 测试定位
$CLI location

# 5. 生成预览，不发送
$CLI eat --prepare-only

# 6. 随机附近餐厅并推送
$CLI eat
```

`scan` 和 `pair` 用于首次发现及绑定，因此卡片需要进入实体配对广播窗口。
完成 `probe --save` 后，日常 `probe/send/eat` 直接使用 Android 已绑定设备连接，
不再先扫描厂商广播，也不需要重复开启配对模式。

`eat` 会把当前位置坐标发送给公开的 OpenStreetMap Overpass 服务。社区数据可能
不完整或过期，本技能只称“附近餐厅”，不保证外卖可用性。

## 安全模型

- `scan`、`pair`、`probe`、`send` 分离，不暗中创建 bond 或写屏
- 目标必须是扫描返回的精确 Android BLE MAC
- 安全固件以加密 Battery Level 读取验证 bond，连接成功本身不算验证
- 若用户主动开启了实体配对窗口，先完成 `pair` 或等待窗口关闭，再执行 probe/send
- payload 在 Minis 内生成和校验，不接受任意 `.bin` / `.qlz` 外部输入
- 任一写失败或断连后整帧重来，禁止中间 block resume
- 只有收到最终刷新 acknowledgement 才报告成功
- localhost 服务采用每次随机 48 位十六进制 token，请求完成立即关闭
- companion 另用本地 256-bit key 认证 Minis，`config --show` 永不显示明文

## 项目结构

```text
todoocard/
├── SKILL.md
├── assets/todoocard-android-bridge.apk
├── android-bridge/                 # Java 17 / Android SDK 35 源码
├── config.example.json
├── references/protocol.md
├── scripts/
│   ├── android_bridge.py           # Minis 侧 localhost RPC
│   ├── build_android_bridge.sh
│   └── image_to_payload.py
├── tests/test_android_port.py
└── today-eats/
    ├── SKILL.md
    └── scripts/
        ├── cli.py
        ├── meal_template.py
        └── places.py
```

## 配置

本地配置位于 `/var/minis/shared/todoocard/config.json`，不要提交。模板：
[`todoocard/config.example.json`](todoocard/config.example.json)。

允许的屏幕方向只有：

- `normal`
- `rotate-180-then-flip-horizontal`（默认）

```bash
$CLI config --show
$CLI config --orientation normal
```

## 从源码构建 APK

需要 JDK 17、Gradle、Android SDK platform 35：

```bash
./todoocard/scripts/build_android_bridge.sh \
  ./todoocard/assets/todoocard-android-bridge.apk
```

仓库内 APK 是方便安装的 debug-signed 构建。若你用不同 debug key 重建，Android
可能要求先卸载旧 companion；卸载不会影响 Minis 的 `config.json`。

## 验证

```bash
python3 -m unittest discover -s todoocard/tests -v
python3 -m py_compile todoocard/scripts/*.py todoocard/today-eats/scripts/*.py
./todoocard/scripts/build_android_bridge.sh /tmp/todoocard-android-bridge.apk
```

真实 BLE、系统 bond、Android 定位和面板刷新仍需在 Android 手机 + TodooCard 实机
上完成端到端测试。

## License

[MIT](LICENSE)
