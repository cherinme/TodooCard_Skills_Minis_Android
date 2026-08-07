# TodooCard Skills for Minis

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Minis](https://img.shields.io/badge/Minis-Skill-blue)](https://github.com/OpenMinis)
[![GitHub](https://img.shields.io/badge/repo-TodooCard__Skills__Minis-green)](https://github.com/jiqimaooo/TodooCard_Skills_Minis)

在 [Minis](https://github.com/OpenMinis) 里把内容推到 **TodooCard / 土豆片** 六色电子纸（528×792）。

当前内置子技能：**今天吃点啥** — 附近随机一家外卖 → 生成卡片 → BLE 整帧推送。

> **非官方**社区项目，与 TodooCard / NEWSTONE / Minis 品牌方无隶属关系。  
> 仓库不含设备 UUID、Token、Cookie 或个人数据。

---

## 目录

- [特性](#特性)
- [安装](#安装)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [配置](#配置)
- [扩展子技能](#扩展子技能)
- [传输说明](#传输说明)
- [贡献](#贡献)
- [开源声明](#开源声明)
- [License](#license)

---

## 特性

| | |
|--|--|
| **今天吃点啥** | 定位 + 附近餐饮搜索 → 随机 1 家 → 出卡 → 推屏 |
| **父 / 子技能** | `todoocard` 管设备与传输；场景能力做成子目录，便于扩展 |
| **整帧推送** | 失败即中止，禁止半帧续传（避免花屏） |
| **Minis 一键导入** | 支持从 GitHub URL 安装 |

**导入链接（请指向父技能目录）：**

```text
https://github.com/jiqimaooo/TodooCard_Skills_Minis/tree/main/todoocard
```

---

## 安装

### 方式 A — Minis App（推荐）

1. **设置 → 技能**  
   ![步骤1](docs/images/step1-settings-skills.png)

2. **右上角菜单 → 导入技能**  
   ![步骤2](docs/images/step2-import-entry.png)

3. 选择 **URL**，粘贴上方导入链接，点 **导入**  
   ![步骤3](docs/images/step3-github-url.png)

成功后列表中出现 **todoocard** 并保持开启。

### 方式 B — 命令行

```bash
git clone https://github.com/jiqimaooo/TodooCard_Skills_Minis.git
ln -sfn "$PWD/todoocard" /var/minis/skills/todoocard

apk add py3-pillow font-noto-cjk
mkdir -p /var/minis/shared/todoocard
cp todoocard/config.example.json /var/minis/shared/todoocard/config.json
```

---

## 快速开始

```bash
CLI="python3 /var/minis/skills/todoocard/today-eats/scripts/cli.py"

# 1. 绑定设备（首次）
$CLI scan
$CLI probe --device-id <UUID> --save

# 2. 今天吃点啥
$CLI eat
# 或对话：「今天吃点啥」「中午吃啥，推到土豆片」
```

| 命令 | 说明 |
|------|------|
| `eat` / `今天吃点啥` | 定位 → 随机外卖 → 推屏 |
| `eat --prepare-only` | 只生成卡片，不发送 |
| `scan` / `probe --save` | 扫描 / 探测并写入本地配置 |
| `config --show` | 查看本地配置 |

依赖：Minis 的 `apple-bluetooth`、`apple-location`、`apple-maps`。

---

## 项目结构

```text
TodooCard_Skills_Minis/
├── README.md
├── LICENSE
├── docs/images/                 # 安装示意图
└── todoocard/                   # ← Minis 导入此目录
    ├── SKILL.md                 # 父技能
    ├── config.example.json
    ├── references/protocol.md   # BLE / 六色协议
    ├── scripts/                 # 共享：转换 + 发送
    └── today-eats/              # 子技能：今天吃点啥
        ├── SKILL.md
        └── scripts/
```

| 层级 | 路径 | 职责 |
|------|------|------|
| 父技能 | `todoocard/` | 配置、协议、转换、BLE、路由 |
| 子技能 | `todoocard/today-eats/` | 推荐吃什么 + 出卡 |

推屏与编码只放在父级 `scripts/`，子技能不要复制传输实现。

---

## 配置

| 项 | 说明 |
|----|------|
| 模板 | [`todoocard/config.example.json`](todoocard/config.example.json) |
| 本地路径 | `/var/minis/shared/todoocard/config.json`（**勿提交**） |
| 常用字段 | `device_id`、`screen_orientation`、`block_size`（240）、`transport` |

`screen_orientation` 按实机校准：`normal` 或 `rotate-180-then-flip-horizontal`。

---

## 扩展子技能

1. 新建 `todoocard/<name>/`（kebab-case）+ `SKILL.md`（`name` + `description` = 做什么 & 何时触发）  
2. 脚本放 `todoocard/<name>/scripts/`，需要推屏时引用父级：

```python
PARENT_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(PARENT_SCRIPTS))
from image_to_payload import convert
```

3. 更新 [`todoocard/SKILL.md`](todoocard/SKILL.md) 子技能表  
4. 自测：`py_compile`；失败路径不得半帧 resume  

---

## 传输说明

协议细节见 [`todoocard/references/protocol.md`](todoocard/references/protocol.md)。

- 服务 `FEF0`，数据块 payload **240** 字节  
- 六色 SE0368 + QuickLZ stored 帧  
- **整帧发送**；失败整图重来  

**性能（务实预期）：**

| 环境 | 数据段量级 |
|------|------------|
| Minis `apple-bluetooth`（`with_response`） | 约 60–80s / 帧 |
| 原生 CoreBluetooth `withoutResponse`（如 macOS） | 约 20s 量级 |

Minis 内变快取决于宿主是否提供 withoutResponse / 批量写；**不是**把 Mac 编译产物放进仓库就能加速 iPhone。

可选 macOS 原生发送器（源码在仓，二进制不进 Git）：

```bash
./todoocard/scripts/build_native_sender.sh ./todoocard/scripts/native_sender
```

---

## 贡献

欢迎 Issue / PR。

```bash
git clone https://github.com/jiqimaooo/TodooCard_Skills_Minis.git
cd TodooCard_Skills_Minis
git checkout -b feat/my-change
# … 修改 …
git add -A && git status   # 确认无 config.json / 密钥 / .bin.qlz
git commit -m "Add …"
git push -u origin HEAD
```

### 提交检查

- [ ] 未提交真实 `config.json`、token、cookie、`.bin` / `.qlz`、预编译二进制  
- [ ] 未复制父级传输脚本到子技能  
- [ ] 新增子技能已更新父 `SKILL.md` 索引  
- [ ] 推屏路径保持整帧、禁止半帧 resume  

### 不要提交

```text
**/config.json
**/*token* **/*secret* **/*cookie* **/*.env
**/*.bin **/*.protocol.qlz **/*.log
**/native_sender
**/__pycache__/
```

### 与 OpenMinis/MinisSkills

| | 本仓库 | [MinisSkills](https://github.com/OpenMinis/MinisSkills) |
|--|--------|--------|
| 形态 | 父+子，便于扩展 | 一技能一顶层目录 |
| 导入 | `…/tree/main/todoocard` | 合并后进官方列表 |
| 规范 | 本文贡献一节 | 官方 README Checklist |

上游 PR：Fork → 只新增可安装的 `todoocard/` 包 → 无密钥 → Summary + Checklist + Test plan。

---

## 开源声明

**许可证：** [MIT](LICENSE)  
Copyright (c) 2026 TodooCard Skill Contributors  

允许使用、修改、再分发与商用；再分发须保留版权与许可声明。软件按「现状」提供，不作担保。

**开源范围：** 技能说明、脚本源码、协议文档、示例配置、安装图。  
**不包含：** 真实设备配置、密钥、运行产物、预编译 `native_sender`。

**致谢：** [Minis](https://github.com/OpenMinis) / [MinisSkills](https://github.com/OpenMinis/MinisSkills)（Apache-2.0）；[TodooCard_Skills](https://github.com/Sunbelife/TodooCard_Skills)（传输思路参考）；Pillow 等依赖遵循其各自许可证。

**商标：** TodooCard、土豆片、NEWSTONE、Minis 等归各自权利人；本项目为非官方社区技能，不代表官方背书。

**使用：** 仅在你拥有或已获授权的设备上推送；贡献即表示你有权以 MIT 提交且未夹带专有代码或密钥。

---

## License

[MIT](LICENSE) © 2026 TodooCard Skill Contributors
