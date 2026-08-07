# TodooCard Skills for Minis

[Minis](https://github.com/OpenMinis) 上的 **TodooCard / 土豆片** 技能包。

## 设计：父技能 + 子技能

| 层级 | 路径 | 职责 |
|------|------|------|
| **父技能** | [`todoocard/`](todoocard/) | 设备配置、协议、六色转换、BLE 发送、子技能路由 |
| **子技能** | [`todoocard/today-eats/`](todoocard/today-eats/) | 今天吃点啥 |

- **导入 / 安装单位**永远是整个 `todoocard/` 目录（不要只导 `today-eats/`）。
- 子技能负责「做什么内容」；推屏与编码一律走父级 `todoocard/scripts/`。
- 仓库**不含**设备 UUID、Token、Cookie 或个人数据。

---

## 在 Minis 里安装（推荐）

用 App 的「导入技能」从 GitHub 安装**父技能目录**：

```text
https://github.com/jiqimaooo/TodooCard_Skills_Minis/tree/main/todoocard
```

### 操作步骤

#### 步骤 1 — 打开「技能」

进入 Minis **设置**，在「智能体运行时」中点击 **技能**。

![步骤1：设置 → 技能](docs/images/step1-settings-skills.png)

#### 步骤 2 — 导入技能

在技能页打开右上角菜单，点击 **导入技能**。

![步骤2：导入技能](docs/images/step2-import-entry.png)

#### 步骤 3 — 粘贴 GitHub 链接并导入

1. 选择 **URL**
2. 粘贴：

```text
https://github.com/jiqimaooo/TodooCard_Skills_Minis/tree/main/todoocard
```

3. 点右上角 **导入**

![步骤3：粘贴链接并导入](docs/images/step3-github-url.png)

成功后列表中应出现 **todoocard**。

---

## 首次绑定设备

```bash
CLI="python3 /var/minis/skills/todoocard/today-eats/scripts/cli.py"

$CLI scan
$CLI probe --device-id <你的UUID> --save
```

本地配置（自动生成，**勿提交**）：

```text
/var/minis/shared/todoocard/config.json
```

或：

```bash
mkdir -p /var/minis/shared/todoocard
cp /var/minis/skills/todoocard/config.example.json /var/minis/shared/todoocard/config.json
```

## 使用「今天吃点啥」

对话示例：

- 「今天吃点啥」
- 「中午吃啥，推到土豆片」
- 「随机附近外卖」

命令行：

```bash
$CLI eat
$CLI 今天吃点啥
$CLI eat --prepare-only   # 只出图不发送
```

---

## 目录结构

```text
TodooCard_Skills_Minis/
├── README.md                      # 本文件
├── LICENSE
├── .gitignore
├── docs/images/                   # 安装示意图
└── todoocard/                     # 父技能（Minis 导入这个目录）
    ├── SKILL.md                   # 父技能：路由 + 公共能力
    ├── config.example.json        # 配置模板（无隐私）
    ├── references/
    │   └── protocol.md            # BLE / 图像协议
    ├── scripts/                   # 共享传输层
    │   ├── image_to_payload.py
    │   ├── safe_send.py
    │   ├── fast_send.py
    │   ├── native_sender.swift
    │   └── build_native_sender.sh
    └── today-eats/                # 子技能
        ├── SKILL.md
        ├── scripts/
        │   ├── cli.py
        │   └── meal_template.py
        ├── references/            # 可选
        └── assets/                # 可选
```

---

## 依赖

```bash
apk add py3-pillow font-noto-cjk
```

Minis 需提供：`apple-bluetooth`、`apple-location`、`apple-maps`。

传输与协议细节：[`todoocard/references/protocol.md`](todoocard/references/protocol.md)。

可选：在 **macOS** 编译原生发送器（加速主要对 Mac 侧有效；Minis 内仍受 `apple-bluetooth` CLI 能力限制）：

```bash
./todoocard/scripts/build_native_sender.sh ./todoocard/scripts/native_sender
```

---

## 本仓库提交规范（Contributing）

面向向 **本仓库**（`jiqimaooo/TodooCard_Skills_Minis`）提交代码或文档的约定。  
若同时向上游 [OpenMinis/MinisSkills](https://github.com/OpenMinis/MinisSkills) 贡献，见文末「与官方技能库的关系」。

### 1. 架构约定（必须遵守）

| 规则 | 说明 |
|------|------|
| 父技能唯一入口 | 可安装目录只有 `todoocard/`；不要把子技能拆成仓库根下第二个可导入包 |
| 子技能只放内容 | 新场景建 `todoocard/<sub-skill>/`，自带 `SKILL.md` + 可选 `scripts/` |
| 传输层不复制 | 转换 / BLE / 协议只放在 `todoocard/scripts/` 与 `todoocard/references/` |
| 子技能引用父脚本 | 通过父目录 `scripts/` 做 `sys.path` 或相对路径引用，禁止再拷一份 `safe_send.py` |
| 配置本地化 | 真实 `config.json`、设备 UUID 只存在用户机器上 |

### 2. 可以提交 / 不可以提交

**可以：**

- `todoocard/` 下源码、`SKILL.md`、`config.example.json`
- `docs/` 文档与示意图（注意打码隐私 UI）
- README / LICENSE / .gitignore 的改进

**不可以（已由 .gitignore 拦截，PR 中也禁止）：**

```text
**/config.json              # 真实设备配置
**/*token* **/*secret* **/*cookie* **/*.env
**/*.bin **/*.protocol.qlz **/*.log
**/native_sender            # 预编译二进制（源码 .swift 可提交）
**/__pycache__/
```

以及任何 API Key、账号 Cookie、手机号、精确到个人的定位轨迹等。

### 3. 新增子技能的步骤

1. **建目录**（kebab-case）：

   ```text
   todoocard/my-skill/
   ├── SKILL.md
   └── scripts/          # 可选
   ```

2. **写 `SKILL.md`**
   - frontmatter 必填：`name`、`description`
   - `description` = **做什么 + 何时触发**（写上用户原话）
   - 正文用祈使句；说明如何调用父级传输层
   - 在文件开头标明：**父技能为 `todoocard`**

3. **需要推电子纸时**，在子技能脚本中引用父级：

   ```python
   PARENT_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
   # today-eats/scripts/cli.py → parents[2] == todoocard/
   sys.path.insert(0, str(PARENT_SCRIPTS))
   from image_to_payload import convert
   ```

4. **更新索引**
   - 父技能 [`todoocard/SKILL.md`](todoocard/SKILL.md) 的「子技能」表
   - 本 README 的设计表 / 目录树（若对外可见）

5. **自测**
   - 语法：`python3 -m py_compile …`
   - 尽量 `prepare-only` 出图；有设备再整帧推送
   - 确认失败路径**不会**断点续传半帧

### 4. Commit 与 PR（本仓库）

```bash
git clone https://github.com/jiqimaooo/TodooCard_Skills_Minis.git
cd TodooCard_Skills_Minis
git checkout -b feat/my-change

# … 修改 …

git add -A
git status   # 确认没有 config.json / 密钥 / 二进制产物
git commit -m "简述：做了什么、为什么"
git push -u origin feat/my-change
# 再在 GitHub 上开 PR 打到 main
```

**Commit message 建议：**

- 用现在时、说清意图：`Add weather sub-skill skeleton`
- 避免无意义的 `update` / `fix`

**PR 描述建议包含：**

```markdown
## Summary
- 改了什么
- 为什么

## 影响范围
- [ ] 仅文档
- [ ] 父技能传输层（需更谨慎测试）
- [ ] 子技能 xxx

## 检查
- [ ] 无密钥 / 无真实 config.json / 无 .bin.qlz
- [ ] 未复制传输层脚本
- [ ] 已更新父 SKILL 子技能表（若新增子技能）
- [ ] 本地 py_compile / 关键路径 smoke test
```

### 5. 代码与文档风格

- 父 / 子 `SKILL.md`：触发语写全；流程可执行；细节进 `references/`
- Python：标准库 + 已声明依赖；路径不要写死个人机器目录（Minis 约定路径除外，如 `/var/minis/shared/todoocard`）
- 注释中文或英文均可，以说清协议与安全边界为准（尤其：**禁止半帧 resume**）
- 不在 README 主文堆长篇排障；协议与限制写在 `references/protocol.md`

### 6. 与官方技能库 OpenMinis/MinisSkills 的关系

| | 本仓库 | [OpenMinis/MinisSkills](https://github.com/OpenMinis/MinisSkills) |
|--|--------|------------------------------------------------------------------|
| 形态 | 父+子 monorepo，可演进多个子场景 | **一技能一顶层目录**，flat 安装 |
| 导入 | 导入 `…/tree/main/todoocard` | 合并后出现在官方列表 |
| 提交 | 按**上文本仓库规范** | 另遵[官方 README Checklist](https://github.com/OpenMinis/MinisSkills) |

向上游贡献时：

1. Fork `OpenMinis/MinisSkills`，从 `main` 开分支  
2. **只新增一个**顶层目录（一般为 `todoocard/`，内含子目录 `today-eats/` 等实现）  
3. 满足官方：`name` + `description`、kebab-case、无密钥、`scripts/` / `references/` / 可选 `evals/`  
4. **不要**在官方仓根目录塞本仓库的 monorepo 说明或无关文件  
5. PR 附 Summary + Layout + Checklist + Test plan  

本仓库可以比官方仓更「产品化」（父+子文档）；上游 PR 以 **可被 Minis 单目录安装** 为第一约束。

### 7. 安全与传输底线（贡献时勿破坏）

- 推屏必须 **整帧**；失败即中止，禁止索引半帧续传（会导致花屏/竖纹）
- 不引入未验证的 payload 格式作为默认路径
- 不在默认依赖里要求用户提交任何密钥

---

## 开源声明

### 许可证

本仓库以 **[MIT License](LICENSE)** 发布。

```text
Copyright (c) 2026 TodooCard Skill Contributors
```

在遵守 MIT 条款的前提下，你可以自由地：

- 使用、复制、修改、合并本软件
- 公开发布、再分发
- 用于商业或非商业项目
- 进行再许可（sublicense）与销售副本

**条件：** 再分发时须保留版权声明与 MIT 许可全文（见根目录 [`LICENSE`](LICENSE)）。

**免责：** 软件按「现状」提供，不附带任何明示或暗示担保；作者不对使用本软件造成的损失承担责任（含推送错误导致的设备显示异常等）。

### 本仓库开源范围

| 包含 | 不包含 |
|------|--------|
| 父/子技能说明（`SKILL.md`） | 真实设备 `config.json` / UUID |
| 转换与 BLE 发送脚本源码 | API Key、Cookie、Token |
| 协议说明文档 | 运行日志、`.bin` / `.protocol.qlz` 产物 |
| 安装示意图、示例配置 | 预编译 `native_sender` 二进制（仅提供 `.swift` 源码） |

### 第三方与致谢

本项目在实现过程中参考或依赖以下内容（权利归各方所有；本仓库代码除非另有说明，仍以 MIT 授权）：

| 项目 / 组件 | 说明 |
|-------------|------|
| [Minis](https://github.com/OpenMinis) / [MinisSkills](https://github.com/OpenMinis/MinisSkills) | 技能运行环境与社区技能规范（官方库为 Apache-2.0） |
| [Sunbelife/TodooCard_Skills](https://github.com/Sunbelife/TodooCard_Skills) | TodooCard 六色转换与 BLE 传输思路参考（macOS skill） |
| Apple CoreBluetooth / 相关系统框架 | 仅通过 Minis 的 `apple-*` 接口或可选 Swift 源码调用；非本仓库再授权对象 |
| Pillow 等开源库 | 由用户环境自行安装，遵循其各自许可证 |

协议逆向/兼容实现基于公开 skill 与设备侧可观察行为，用于个人设备互联；**不包含**任何厂商未公开固件镜像或密钥。

### 商标与品牌

「TodooCard」「土豆片」「NEWSTONE」「Minis」等名称与标识归其各自权利人所有。  
本项目为**非官方**社区技能，与上述品牌权利人**无隶属或背书关系**，不声称代表官方产品。

### 使用与安全提示

- 仅建议在**你拥有或已获授权**的电子纸设备上推送画面。
- 错误的半帧/续传推送可能导致花屏；默认实现要求整帧发送。
- 贡献代码即表示你确认有权以 MIT 贡献该内容，且未夹带密钥或他人专有代码。

### 贡献

欢迎 Issue / PR。向本仓库贡献请遵循上文「本仓库提交规范」；向上游 MinisSkills 贡献请额外遵循官方 checklist。

---

## License

[MIT](LICENSE) © 2026 TodooCard Skill Contributors
