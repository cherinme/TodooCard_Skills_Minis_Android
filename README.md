# TodooCard Skills for Minis

面向 [Minis](https://github.com/OpenMinis) 的 **TodooCard / 土豆片** 技能集合。

当前提供「今天吃点啥」；目录按**可扩展多技能**设计，后续可继续加天气卡、任意图推送等，而不改动已有技能的对外接口。

本仓库**不含**设备 UUID、Token、Cookie 或个人数据。

---

## 技能目录

| 技能 | 目录 | 一句话 |
|------|------|--------|
| **今天吃点啥** | [`today-eats/`](today-eats/) | 附近随机一家外卖 → 生成卡片 → 推送到土豆片 |

每个技能都是独立目录（含 `SKILL.md`），可单独拷贝进 [OpenMinis/MinisSkills](https://github.com/OpenMinis/MinisSkills) 或本地 `/var/minis/skills/`。

---

## 仓库结构

```text
TodooCard_Skills_Minis/
├── README.md                 # 本文件：集合说明 + 技能索引
├── LICENSE
├── .gitignore
├── shared/                   # 跨技能公共层（不是 skill）
│   ├── config.example.json
│   ├── references/
│   │   └── protocol.md       # BLE / 六色图像协议
│   └── scripts/
│       ├── image_to_payload.py
│       ├── safe_send.py
│       ├── fast_send.py
│       ├── native_sender.swift
│       └── build_native_sender.sh
└── today-eats/               # 技能：今天吃点啥
    ├── SKILL.md
    ├── scripts/
    │   ├── cli.py
    │   └── meal_template.py
    ├── references/           # 可选：技能专属文档
    └── assets/               # 可选：模板素材
```

设计约定：

- **一个技能 = 一个顶级目录**，目录名 kebab-case，内含必填 `SKILL.md`
- **传输 / 协议 / 设备配置模板**放 `shared/`，避免每个技能复制一份 BLE 实现
- 新增技能时：新建 `your-skill/SKILL.md` + `scripts/`，复用 `shared/scripts`
- 本地 Minis：把技能目录放到 `/var/minis/skills/<name>/`，并保证能解析到 `shared/`（monorepo 同级，或拷贝/链接 `shared`）

---

## 快速开始（今天吃点啥）

```bash
git clone https://github.com/jiqimaooo/TodooCard_Skills_Minis.git
cd TodooCard_Skills_Minis

# Minis：链接技能与共享层
ln -sfn "$PWD/today-eats" /var/minis/skills/today-eats
ln -sfn "$PWD/shared" /var/minis/skills/todoocard-shared

mkdir -p /var/minis/shared/todoocard
cp shared/config.example.json /var/minis/shared/todoocard/config.json

CLI="python3 /var/minis/skills/today-eats/scripts/cli.py"
$CLI scan
$CLI probe --device-id <UUID> --save
$CLI eat
```

依赖：

```bash
apk add py3-pillow font-noto-cjk
# Minis 内置：apple-bluetooth / apple-location / apple-maps
```

更完整的触发语与流程见 [`today-eats/SKILL.md`](today-eats/SKILL.md)。

---

## 新增一个技能（约定）

1. 复制结构：

```text
my-skill/
├── SKILL.md
└── scripts/
```

2. `SKILL.md` 必须含 frontmatter：`name`、`description`（写清做什么 + 何时触发）
3. 需要推电子纸时，复用：

```python
sys.path.insert(0, str(repo_root / "shared" / "scripts"))
from image_to_payload import convert
# 再调用 safe_send / native_sender
```

4. 在本 README 的「技能目录」表中加一行  
5. 不要把 `config.json`、日志、`.bin` / `.qlz`、Token 提交进库

---

## 公共层说明

`shared/` 不是技能，不会被 Minis 当作 skill 加载。

| 内容 | 用途 |
|------|------|
| `scripts/image_to_payload.py` | 图 → 六色 528×792 payload |
| `scripts/safe_send.py` | BLE 整帧顺序发送（CLI） |
| `scripts/fast_send.py` | 转换与连接流水线（可选） |
| `scripts/native_sender.swift` | macOS CoreBluetooth 长连接（可选加速） |
| `references/protocol.md` | FEF0 协议与编码说明 |
| `config.example.json` | 本地设备配置模板 |

可选原生加速（macOS）：

```bash
./shared/scripts/build_native_sender.sh ./shared/scripts/native_sender
```

---

## 配置与隐私

- 设备配置写在本地：`/var/minis/shared/todoocard/config.json`
- 仓库只提供：`shared/config.example.json`
- `.gitignore` 已排除 token、cookie、日志与二进制产物

---

## License

MIT
