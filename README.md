# TodooCard Skills for Minis

[Minis](https://github.com/OpenMinis) 上的 **TodooCard / 土豆片** 技能包。

## 设计：父技能 + 子技能

| 层级 | 路径 | 职责 |
|------|------|------|
| **父技能** | [`todoocard/`](todoocard/) | 设备配置、协议、六色转换、BLE 发送、子技能路由 |
| **子技能** | [`todoocard/today-eats/`](todoocard/today-eats/) | 今天吃点啥 |

安装时拷贝整个 `todoocard/` 到 `/var/minis/skills/todoocard/`。  
仓库不含设备 UUID / Token / 个人数据。

## 目录结构

```text
TodooCard_Skills_Minis/
├── README.md
├── LICENSE
├── .gitignore
└── todoocard/                 # 父技能（也可作为 MinisSkills 单目录提交）
    ├── SKILL.md
    ├── config.example.json
    ├── references/protocol.md
    ├── scripts/               # 共享传输层
    │   ├── image_to_payload.py
    │   ├── safe_send.py
    │   ├── fast_send.py
    │   ├── native_sender.swift
    │   └── build_native_sender.sh
    └── today-eats/            # 子技能
        ├── SKILL.md
        ├── scripts/
        │   ├── cli.py
        │   └── meal_template.py
        ├── references/
        └── assets/
```

## 快速开始

```bash
git clone https://github.com/jiqimaooo/TodooCard_Skills_Minis.git
ln -sfn "$PWD/todoocard" /var/minis/skills/todoocard

mkdir -p /var/minis/shared/todoocard
cp todoocard/config.example.json /var/minis/shared/todoocard/config.json
apk add py3-pillow font-noto-cjk

CLI="python3 /var/minis/skills/todoocard/today-eats/scripts/cli.py"
$CLI scan && $CLI probe --device-id <UUID> --save
$CLI eat
```

## 子技能索引

| 子技能 | 路径 | 说明 |
|--------|------|------|
| 今天吃点啥 | `todoocard/today-eats/` | 附近随机外卖并推到土豆片 |

## 扩展

在 `todoocard/` 下新增子目录 + `SKILL.md`，复用 `todoocard/scripts/` 推屏，并更新父技能子技能表与本索引。

## 传输层

见 `todoocard/references/protocol.md`。可选 macOS 原生加速：

```bash
./todoocard/scripts/build_native_sender.sh ./todoocard/scripts/native_sender
```

## License

MIT
