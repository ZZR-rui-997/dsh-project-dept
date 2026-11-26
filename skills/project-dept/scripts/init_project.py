#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stand up the contractor-style project department in a fresh project.

Creates ``dept.config.json`` plus a minimal ``_team/`` ledger that the gate
(``dept_gate.py``) accepts, so a new project can start the six-step flow
without hand-copying files from another project.

Design rules (learned the hard way, see references/project-scaffold.md):

* Only create what the project will actually maintain — every extra file is a
  future inconsistency, so the generated ledgers are short skeletons, not
  paper mountains.
* Do **not** fork the quality scripts. The generated ``_team/bin/README.md``
  tells the project to call the skill's scripts by path, because a per-project
  copy means the audit is measuring something different from what the skill
  describes.
* Be idempotent and conservative: never overwrite an existing file unless
  ``--force`` is given; print exactly what was created / skipped / left alone.
* A brand-new project has no open package. Writing a fake "current package"
  just to make the gate exit 0 would be lying to the gate, so by default the
  board says "no package open yet" and carries a single open debt ``D0`` that
  asks the Lead to decide the first package — the gate then exits ``2``
  (needs a decision), which is the honest answer. Pass ``--open-package``
  once you actually know the first package.

Usage::

    python init_project.py --root D:/some/project
    python init_project.py --root D:/some/project --open-package "板块 1：xxx"
    python init_project.py --root . --dry-run
    python init_project.py --root . --json

Exit codes: 0 = scaffold ready (or already complete), 1 = refused (see stderr),
2 = bad usage.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

VERSION = "1.3.10"

# --------------------------------------------------------------------------
# file templates
# --------------------------------------------------------------------------

DEFAULT_ENV_NOTES = [
    "Python 解释器：用项目自己的 venv（具体路径写进项目 `AGENTS.md`，不要写死在通用台账里）",
    "文档处理（docx / pptx / openpyxl）：用装了对应依赖的解释器（见项目 `AGENTS.md`）",
    "控制台中文按 GBK 输出会乱码：长文本写 UTF-8 文件再读",
]

CONFIG_TMPL = """{
  "project_name": %(name)s,
  "ledger_dir": "_team",
  "board_file": "看板.md",
  "flow_file": "工作流.md",
  "register_file": "交付登记簿.md",
  "baseline_file": "基准清单.md",
  "baseline_changelog": "基准变更记录.md",
  "role_dir": "岗位",
  "required_roles": %(roles)s,
  "artefact_dir": "out",
  "scratch_patterns": ["probe_*", "_scan*", "_summ*", "_tmp*", "_probe*", "_patch*", "_mut*"],
  "banned_terms": [],
  "environment": {
    "notes": %(env_notes)s
  }
}
"""

CHARTER_TMPL = """# %(name)s — 项目部章程

> 本文件是项目级台账的入口。通用规程在 skill `project-dept`；本文件只放**本项目**的值。

## 这个项目是什么

%(desc)s

## 硬规则（违反即返工）

0. **开工前先跑闸门**：`dept_gate.py --root .`（解释器见下）。`0`=通过（告警写进回复）／`1`=禁止开工／`2`=需 Lead 逐条「做掉／豁免（理由+复查日期）／降级」并更新债务账本／`3`=未执行（**不许当通过**）。
1. **一次只做一个板块**。开工前读本目录 `看板.md` 的「当前板块」；没有板块不要自行开工。
2. **多步任务先加载 skill `project-dept`**，再按需加载本项目自己的技能。
3. **交付 ≠ 完成**：L1 自检 → L2 独立盲审 → L3 终审，Lead 才能标完成并记入 `交付登记簿.md`。
4. **检查要独立，基准本身也要核**：正确锚点 = 独立重算 > 外部权威 > 自洽性；没出处的数字标 `[未溯源]`，不能当验收基准。
5. **不编数**：每个数字要有出处（文件:行 / 表号 / 页码 / 命令输出）。
6. **写盘有边界**：只读目录不经要求不改；新产物写 `_team/out/<role>/`。
7. **spawn 必须喂岗位卡全文**（`_team/岗位/<role>.md`），不许临场编职责。

## 路径表

| 东西 | 路径 |
|---|---|
| 章程（本文件） | `_team/README.md` |
| 流程细节 | `_team/工作流.md` |
| 当前板块 + 债务账本 | `_team/看板.md` |
| 交付登记簿 | `_team/交付登记簿.md` |
| 基准清单 / 变更记录 | `_team/基准清单.md` · `_team/基准变更记录.md` |
| 岗位卡 | `_team/岗位/` |
| 模板 | `_team/templates/` |
| 产物 | `_team/out/<role>/` |
| 盲审包 | `_team/review/blind/<task>/` |
| 跨窗口收件箱 | `_team/跨窗口收件箱.md`（多人/多窗口时再建） |

## 环境坑

%(env)s

## 质量工具（不复制，直接调用 skill 里的那一份）

```bash
# 闸门（开板块前 + 每次汇报前）
python "<skill>/scripts/dept_gate.py" --root "<项目根>"
# 文档断言器（交文档前）
python "<skill>/scripts/check_doc.py" --file "<docx>" --config "<项目根>/dept.config.json"
# 复核单结构校验（收到复核单后）
python "<skill>/scripts/check_review_form.py" "<复核单>"
```

`<skill>` = `C:\\Users\\<you>\\.dsh\\skills\\project-dept`（或本机实际安装路径）。
"""

FLOW_TMPL = """# 工作流

> 通用细节见 skill `project-dept`（`static/core/workflow.md`）。这里只留本项目执行时必须照着做的部分。

## 六步

- **Step 0 闸门**：`dept_gate.py --root .`，按退出码处置（见章程规则 0）。
- **Step 1 读底稿**：读 `dept.config.json` + `看板.md` + 相关产物；先确认「当前板块」是什么。
- **Step 2 写验收标准**：板块级验收标准（可判定、可复现），交用户确认后再拆任务。
- **Step 3 拆任务**：半天粒度，每个任务有产物路径与验收标准；写进共享任务板或 `_team/out/lead/`。
- **Step 4 派工**：spawn 时 prompt 开头必须是 `_team/岗位/<role>.md` 全文 + 任务单。
- **Step 5 循环**：执行 → L1 自检 → L2 盲审（见 `references/blind-review.md` 的三档节奏）→ 按必改项修 → 再审。
- **Step 6 收口**：更新登记簿 + 看板；填方向复盘三问；跑闸门；汇报。

## 债务记法（闸门只认这一种）

```
- [ ] **D1** 未处置的债（谁、什么、复查日期）
- [x] **D1** 已处置
- D1 waived until 2026-12-01: 豁免理由（无勾选框 = 说明文字，不算未处置）
```

小节标题必须含「未完成事项 / 债务账本 / open debts / debt ledger」之一，否则闸门直接 exit 1。
**勾选框是自报的**：闸门只读勾选框，不核证据；交叉核验是 L2 复核人的事，不要把 exit 0 读成「每条已处置债都核过」。

## 基准作废/替代（P-15-9）

基准清单里的条目**不删行**：行首加 `[已作废]` 或 `[superseded]`，并在 `_team/基准变更记录.md` 写
「旧值 → 新值或理由 / superseded_by / 哪些下游要重跑 / 哪些不重跑」。
只写在 reference 里、不挂在强制产出物上的规则，agent 不会稳定执行（实测）。

## 基准记法（marker 放在这里，不要写进 基准清单 的图例）

- 未溯源：行末加方括号标记 `[未溯源]`（闸门会把含该标记的行计入「未溯源基准」告警，且**图例行也会被计入**——所以标记词只写在本文档）
- 作废/替代：行首加 `[已作废]` 或 `[superseded]`（大小写不敏感、括号内允许空白），并在 `基准变更记录.md` 留记录

## 盲审节奏（三档，别按任务大小决定）

- **档 A 增量审**（每个可交付单元）：1 人，送审 = 产物 + 验收标准 + 上轮复核单 + 修正记录；只验「真修了吗 / 有无连带破坏 / 抽 3 个数字手算」。
- **档 B 全量 panel**（板块收口 / 数字要进正文 / 判据换了）：2 名异方法复核人，全量不抽样，从磁盘重读，不看作者自检。
- **档 C 触发式专项**（基准被改 / 结论反转 / 抓到自检漏检 / 同错第二次出现）：1 人攻一点。
- 不审：中间件（探针脚本、草稿、日志、只读盘点、格式微调）。
"""

BOARD_TMPL_NO_PKG = """# 看板

## 当前板块

（尚未开板块 —— 决定第一个板块后，把这一行换成板块名与目标，并勾掉 D0）

## 未完成事项（债务账本）

- [ ] **D0** 尚未决定第一个板块是什么（Lead 决定后再开工；按章程规则 1，没板块不许自行开工）

## 冻结清单

（没有任何东西被冻结；需要冻结时在这里列路径与原因）

## 需拍板项

（暂无）

## 方向复盘（收口时逐条回答，未回答不得标完成）

1. 若核心结论错，最可能错在哪（至少 3 条，至少一条指向方法/假设层面）
2. 每条的最小证伪动作
3. 沉没成本检查：有没有因为「已经做了很久」不敢回头
"""

BOARD_TMPL_OPENED = """# 看板

## 当前板块

%(pkg)s

## 未完成事项（债务账本）

- [x] **D0** 第一个板块已确定（%(pkg_short)s）

## 冻结清单

（没有任何东西被冻结；需要冻结时在这里列路径与原因）

## 需拍板项

（暂无）

## 方向复盘（收口时逐条回答，未回答不得标完成）

1. 若核心结论错，最可能错在哪（至少 3 条，至少一条指向方法/假设层面）
2. 每条的最小证伪动作
3. 沉没成本检查：有没有因为「已经做了很久」不敢回头
"""

REGISTER_TMPL = """# 交付登记簿

> 一行 = 一个收口的板块。**没走过 L2 的行不许写「通过」**；未完成的复核一律按未通过记。

## 已验收

| 日期 | 板块 / 任务 | 角色 | 产物 | L2 复核 | 结论 | Lead |
|---|---|---|---|---|---|---|

## 未验收（参考材料，**不得当作已核过的成果引用**）

| 日期 | 产物 | 为什么未验收 |
|---|---|---|

## 图例

- 结论列只允许：`通过` / `通过（范围限定：…）` / `未通过` / `待复核 —— 本行不得读作「通过」`
"""

BASELINE_TMPL = """# 基准清单

> 一条 = 一个被当基准用的东西。**没有出处的不能当基准**。

## 出处等级

- **A** 原始数据 / 原始文件 + 行号页码 —— 可以当验收基准
- **B** 原始文献报道值 / 解析解 / 规范条文 —— 可以当验收基准
- **C** 我们自己整理的稿子（对照表、矩阵 v1、记忆里的「已审计数值」）—— **只能当待验证说法**
- **D** 无出处（记忆、「之前说过」）—— 不可用；行末必须加未溯源标记（标记词见 `_team/工作流.md` §基准记法，
  写在本文件图例里会被闸门当成真实条目计数——这是已知假阳性，别在图例里写方括号标记）

## 使用规则

1. 每板块收口抽 ≥1/3 的基准回原件核（全查更好）。
2. 发现基准错：①立刻停下游 ②评估波及面 ③债务账本登记 ④修基准再重跑受影响部分。
3. 作废/替代**不删行**：行首加 `[已作废]` / `[superseded]`，并在 `基准变更记录.md` 写清楚。

## 清单

| # | 条目 | 值 | 等级 | 出处（文件:行 / 表号 / 页码） | 状态 | 备注 |
|---|---|---|---|---|---|---|
"""

CHANGELOG_TMPL = """# 基准变更记录

> 基准被作废/替代时**必须**在这里留一条，闸门会检查本文件非空（P-15-9）。
> 每条写：旧值 → 新值或理由 / `superseded_by` / 哪些下游要重跑 / 哪些不重跑。

## B-01 示例（用完删掉这一条，或改成本项目第一条真实记录）

- 旧值：
- 新值或理由：
- superseded_by：
- 下游要重跑：
- 不重跑及理由：
"""

ROLE_TMPL = """# 岗位卡 — %(role)s（通用骨架）

> 由 `init_project.py` 生成。**通用角色**（lead/audit/reviewer）可直接用；
> **领域角色**（sim/write/geom/…）必须由懂这个领域坑的人重写第 5 节，照抄通用文本等于把坑再踩一遍。

## 1. 定位
- 隶属：项目部（本项目）；向 Lead 汇报。
- 一句话：%(one_line)s

## 2. 职责（做什么 / 明确不做什么）
- 做：
- 不做：

## 3. 输入（开工前必须读）
- `_team/README.md`（章程）、`_team/工作流.md`（流程）
- `_team/看板.md` 的「当前板块」与债务账本
- 本任务的任务单（含验收标准）

## 4. 输出（产物与交接）
- 产物路径：`_team/out/%(role)s/…`
- 交接格式：产物路径 + 可复现命令 + 逐条自检 + 未解决项 + 未验证项

## 5. 已知环境坑（只写**真的踩过**的）
- （按项目实际填）

## 6. 验收标准（别人怎么判你）
- 可复现：结论能被第三方用你给的命令重跑出来
- 有出处：每个数字有 文件:行 / 表号 / 页码 / 命令输出
- 不越权：没改只读目录、没替 Lead 宣布完成

## 7. 交接
- 向 Lead 交：产物 + 证据 + 未解决项；不自己标「完成」。
- 收到复核单后：先按必改项修，再回填「怎么改的 + 证据」。

## 8. changelog
- %(today)s 由 init_project.py 生成。
"""

TASK_TMPL = """# 任务单 — <任务名>

## 目标（一句话，可判定）

## 范围
- 做：
- 不做（明确排除）：

## 输入
- 必须读：<路径>
- 可用环境：<解释器 / 命令>

## 产物
- 路径：
- 格式：

## 验收标准（每条都要能机械判定）
- [ ]
- [ ]

## 明确禁止
- 改：<只读路径>
- 不要：<跑重活 / commit / 删除文件>

## 交给谁 / 怎么交
- 产物路径 + 可复现命令 + 逐条自检 + 未解决项 + 未验证项
"""

REVIEW_TMPL = """# 复核单 — <task>

## 0. 被验快照
- 复核开始：`HASH <12位hex> FILES <n>`
- 复核结束：`HASH <12位hex> FILES <n>`
- 两次是否一致：<一致 / 不一致（说明）>
- 被验产物逐个 sha256：
  - `<产物路径>` — `<sha256 前 16 位>`

## 1. 我的独立结论（必须在打开作者自检之前写完）

- 判定：<通过 / 通过但要修 / 不通过>
- 必改项：

| # | 我重算/重跑/重查了什么 | 方法或命令 | 结果 |
|---|---|---|---|
| 1 | | | |
| 2 | | | |

- 独立性：§1 的独立结论写完之后，我才打开作者自检文件对照。

## 2. 对照作者自检（判完之后才写）

- 我判对的：
- 我判错的：
- 作者自检漏掉的：

## 3. 问题表

| # | 位置（文件:行/节） | 问题 | 为什么是问题（证据） | 严重度 |
|---|---|---|---|---|
| 1 | | | | |

## 4. 判不了的东西（说清楚为什么判不了）
"""

BIN_README_TMPL = """# 质量工具（不在这里放副本）

本项目**不复制** skill 里的质量脚本——一份项目内的 fork 意味着审核标准已经和 skill 描述的不一样了。
直接用安装好的那一份：

```bash
SKILL="C:/Users/<you>/.dsh/skills/project-dept"
python "$SKILL/scripts/dept_gate.py" --root "<项目根>"        # 闸门
python "$SKILL/scripts/check_doc.py" --file "<docx>" --config "<项目根>/dept.config.json"
python "$SKILL/scripts/check_review_form.py" "<复核单>"
python "$SKILL/scripts/run_evals.py" --mode static --evals "$SKILL/evals/evals.json"
```

第一次接线后要**各跑一次**确认退出码行为符合文档（尤其：台账被破坏时闸门必须 exit 1、断言器能被故意弄成 exit 1）。
"""

PROJECT_AGENTS_TMPL = """# AGENTS.md — %(name)s 的工作规则（自动生效）

> 项目级指令文件：工作目录在本项目之下的会话会自动加载。
> 通用规程在 skill `project-dept`；完整台账在 `_team/`。

## 六条硬规则

0. **开工前先跑闸门**：`dept_gate.py --root "<项目根>"`。`0`=通过（告警写进回复）／`1`=禁止开工／`2`=需 Lead 逐条决策并更新债务账本／`3`=未执行（不许当通过）。
1. **一次只做一个板块**。开工前读 `_team/看板.md` 的「当前板块」；没有板块不要自行开工，先问用户。
2. **多步任务先加载 skill `project-dept`**（不必等用户点名）。
3. **交付 ≠ 完成**：L1 自检 → L2 独立盲审 → L3 终审，Lead 才能标完成并记入 `_team/交付登记簿.md`。
4. **检查独立 + 基准要核**：独立重算 > 外部权威 > 自洽性；无出处标 `[未溯源]`。
5. **不编数**；**写盘有边界**（只读目录不经要求不改）；**spawn 必须喂岗位卡全文**。

## 状态文件

`_team/README.md`（章程）· `_team/工作流.md`（流程）· `_team/看板.md`（当前板块 + 债务账本）· `_team/交付登记簿.md` · `_team/基准清单.md` · `_team/岗位/` · `_team/templates/`
"""


# --------------------------------------------------------------------------
# scaffolding
# --------------------------------------------------------------------------

def _one_line(role):
    return {
        "lead": "主持板块、写验收标准、拆任务、派工、终审、收口。",
        "audit": "只读审计：独立重算关键数字、核对出处等级、找「声明与实体不符」。",
        "reviewer": "局外人盲审：只看产物 + 验收标准，先写独立结论再看作者自检。",
    }.get(role, "本项目的领域角色（按实际职责重写本节）。")


def build_payload(name, desc, env_notes, roles, open_package):
    """Return {relpath: content}. Pure function: easy to unit-test."""
    today = datetime.date.today().isoformat()
    pkg = (open_package or "").strip()
    board = BOARD_TMPL_OPENED % {
        "pkg": pkg,
        "pkg_short": pkg[:40],
    } if pkg else BOARD_TMPL_NO_PKG
    notes = list(DEFAULT_ENV_NOTES) + [n for n in (env_notes or []) if n and n not in DEFAULT_ENV_NOTES]
    env = "\n".join("- %s" % e for e in notes)
    files = {
        "dept.config.json": CONFIG_TMPL % {
            "name": json.dumps(name, ensure_ascii=False),
            "roles": json.dumps(roles, ensure_ascii=False),
            "env_notes": json.dumps(notes, ensure_ascii=False),
        },
        "_team/README.md": CHARTER_TMPL % {"name": name, "desc": desc or "（一句话说明本项目在做什么）", "env": env},
        "_team/工作流.md": FLOW_TMPL,
        "_team/看板.md": board,
        "_team/交付登记簿.md": REGISTER_TMPL,
        "_team/基准清单.md": BASELINE_TMPL,
        "_team/基准变更记录.md": CHANGELOG_TMPL,
        "_team/templates/任务单.md": TASK_TMPL,
        "_team/templates/复核单.md": REVIEW_TMPL,
        "_team/bin/README.md": BIN_README_TMPL,
        "AGENTS.md": PROJECT_AGENTS_TMPL % {"name": name},
    }
    for role in roles:
        files["_team/岗位/%s.md" % role] = ROLE_TMPL % {
            "role": role, "one_line": _one_line(role), "today": today,
        }
    return files


DIRS = ["_team", "_team/岗位", "_team/templates", "_team/bin", "_team/out", "_team/out/scratch", "_team/review/blind"]


def scaffold(root, name=None, desc=None, env_notes=None, roles=None, open_package=None, force=False):
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        raise SystemExit("[x] 不是目录：%s" % root)
    name = name or os.path.basename(os.path.normpath(root))
    roles = roles or ["lead", "audit", "reviewer"]
    env_notes = env_notes or []
    plan = build_payload(name, desc, env_notes, roles, open_package)

    created, skipped, overwritten = [], [], []
    for d in DIRS:
        p = os.path.join(root, d)
        if not os.path.isdir(p):
            os.makedirs(p)
            created.append(d + "/")
    for rel, content in plan.items():
        p = os.path.join(root, rel)
        if os.path.exists(p):
            if not force:
                skipped.append(rel)
                continue
            overwritten.append(rel)
        else:
            parent = os.path.dirname(p)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            created.append(rel)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
    return {"root": root, "name": name, "created": created,
            "skipped": skipped, "overwritten": overwritten, "open_package": bool(open_package)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="在空项目里搭起项目部台账（dept.config.json + _team/）")
    ap.add_argument("--root", default=".", help="项目根目录（默认当前目录）")
    ap.add_argument("--name", default=None, help="项目名（默认取目录名；建议与目录名一致，否则闸门会告警）")
    ap.add_argument("--desc", default=None, help="一句话说明本项目在做什么")
    ap.add_argument("--roles", default="lead,audit,reviewer", help="岗位卡列表，逗号分隔")
    ap.add_argument("--env-note", action="append", default=None, metavar="TEXT",
                    help="追加一条环境提示到 dept.config.json 的 environment.notes（可重复；默认给三条通用提示，不含本机路径）")
    ap.add_argument("--open-package", default=None, help="第一个板块名（给了才把看板「当前板块」写成它；否则留 D0 待决）")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的同名文件（默认跳过）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要做什么")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--version", action="version", version="init_project " + VERSION)
    args = ap.parse_args(argv)

    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    if not roles:
        print("[x] --roles 不能为空", file=sys.stderr)
        return 2
    if args.dry_run:
        plan = build_payload(args.name or os.path.basename(os.path.abspath(args.root)), args.desc,
                             args.env_note or [], roles, args.open_package)
        out = {"root": os.path.abspath(args.root), "dry_run": True,
               "dirs": DIRS, "files": sorted(plan)}
        print(json.dumps(out, ensure_ascii=False, indent=2) if args.json else
              "将创建目录：%s\n将创建文件：\n  %s" % (", ".join(DIRS), "\n  ".join(sorted(plan))))
        return 0

    res = scaffold(args.root, args.name, args.desc, args.env_note or [], roles, args.open_package, args.force)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    print("项目部台账：%s（项目名 %s）" % (res["root"], res["name"]))
    for d in res["created"]:
        print("  [+] %s" % d)
    for f in res["overwritten"]:
        print("  [~] %s（已覆盖）" % f)
    for f in res["skipped"]:
        print("  [=] %s（已存在，跳过）" % f)
    board_just_created = "_team/看板.md" in res["created"]
    if board_just_created and not res["open_package"]:
        print("\n下一步：决定第一个板块后，把 `_team/看板.md` 的「当前板块」写实，并勾掉 D0；")
        print("        然后跑闸门确认 exit 0：python <skill>/scripts/dept_gate.py --root %s" % res["root"])
    else:
        print("\n下一步：跑闸门确认 exit 0：python <skill>/scripts/dept_gate.py --root %s" % res["root"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
