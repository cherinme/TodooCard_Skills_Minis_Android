# TodooCard Skills for Minis

[Minis](https://github.com/OpenMinis) 上的 **TodooCard / 土豆片** 技能包。

## 设计：父技能 + 子技能

| 层级 | 路径 | 职责 |
|------|------|------|
| **父技能** | [`todoocard/`](todoocard/) | 设备配置、协议、六色转换、BLE 发送、子技能路由 |
| **子技能** | [`todoocard/today-eats/`](todoocard/today-eats/) | 今天吃点啥 |

仓库不含设备 UUID / Token / 个人数据。

---

## 在 Minis 里安装（推荐）

用 App 的「导入技能」从 GitHub 安装父技能目录：

**导入链接（请用这个，指向 `todoocard` 目录）：**

```text
https://github.com/jiqimaooo/TodooCard_Skills_Minis/tree/main/todoocard
```

### 操作步骤

#### 步骤 1 — 打开「技能」

进入 Minis **设置**，在「智能体运行时」中点击 **技能**。

![步骤1：设置 → 技能](docs/images/step1-settings-skills.png)

#### 步骤 2 — 导入技能

在技能页点击 **右上角 ＋**，再点 **导入技能**。

![步骤2：右上角 ＋ → 导入技能](docs/images/step2-import-entry.png)

#### 步骤 3 — 粘贴 GitHub 链接并导入

1. 选择 **URL**
2. 在输入框粘贴：

```text
https://github.com/jiqimaooo/TodooCard_Skills_Minis/tree/main/todoocard
```

3. 点右上角 **导入**

![步骤3：粘贴链接并导入](docs/images/step3-github-url.png)

导入成功后，技能列表中应出现 **todoocard**（可开关启用）。

---

## 首次绑定设备

```bash
CLI="python3 /var/minis/skills/todoocard/today-eats/scripts/cli.py"

$CLI scan
$CLI probe --device-id <你的UUID> --save
```

本地配置（自动生成，勿提交）：

```text
/var/minis/shared/todoocard/config.json
```

也可从示例复制：

```bash
mkdir -p /var/minis/shared/todoocard
cp /var/minis/skills/todoocard/config.example.json /var/minis/shared/todoocard/config.json
```

## 使用「今天吃点啥」

在对话里直接说：

- 「今天吃点啥」
- 「中午吃啥，推到土豆片」
- 「随机附近外卖」

或命令行：

```bash
$CLI eat
$CLI 今天吃点啥
$CLI eat --prepare-only   # 只出图不发送
```

## 目录结构

```text
TodooCard_Skills_Minis/
├── README.md
├── LICENSE
├── docs/images/                 # 安装示意图
└── todoocard/                   # 父技能（导入这个目录）
    ├── SKILL.md
    ├── config.example.json
    ├── references/protocol.md
    ├── scripts/                 # 共享传输层
    └── today-eats/              # 子技能：今天吃点啥
        ├── SKILL.md
        └── scripts/
```

## 依赖

```bash
apk add py3-pillow font-noto-cjk
```

Minis 需提供：`apple-bluetooth`、`apple-location`、`apple-maps`。

## 扩展子技能

在 `todoocard/` 下新增目录（如 `weather/`），编写独立 `SKILL.md` 与脚本，复用父级 `scripts/` 做推屏，并更新父技能子技能表。

传输协议见 [`todoocard/references/protocol.md`](todoocard/references/protocol.md)。

## License

MIT
