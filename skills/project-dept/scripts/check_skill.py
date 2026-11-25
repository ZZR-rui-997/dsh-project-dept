#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_skill.py — project-dept skill 包静态自检器（作者自查工具，不是验收工具）。

只查「机械可判的腐化」，不判断内容好坏:
    1. frontmatter      name / description / metadata.version 存在且合法
    2. 版本一致         SKILL.md / manifest.yaml / README.md / README_EN.md 的当前版本号一致
    3. 声明资产存在     manifest 与 SKILL.md 正文里声明的相对路径必须真实存在
    4. 禁出现文件名     VERIFICATION.md / 修复进度.md / 看板.md / 交付登记簿.md 不得出现在入口文档里
    5. 上下文预算       SKILL.md ≤ 3000 tokens（**硬上限：超了算缺陷**）；
                        SKILL.md + always_load ≤ 9000 tokens（超限只警告）
    6. evals 可读       evals/evals.json 合法 JSON、evals 数组、每例字段齐全、id 不重复
    7. 包完整性         manifest/SKILL/README* /static /references /质量脚本 /tests /evals 都在
    8. manifest 语法    manifest.yaml 必须能被解析（有 PyYAML 就 safe_load，无则启发式抓断行）

用法:
    python scripts/check_skill.py                  # 检查脚本所在包（上两级目录）
    python scripts/check_skill.py --root <dir>     # 检查指定包目录
    python scripts/check_skill.py --json           # 机器可读输出（stdout 上只有 JSON）

退出码:
    0 = 无缺陷（可有警告）
    1 = 有缺陷
    2 = 无法执行（目录不存在 / SKILL.md 缺失 / 文件读不出来）

已知局限（见 README 里的说明）:
    - manifest 与 SKILL.md 正文用「前缀 + 文件扩展名」识别相对路径；不带扩展名的裸目录
      （例如正文里写 static/core 而不是 static/core/xxx.md）不参与存在性核对，避免把
      「tests/evals」这类散文词误判成路径。
    - README 的「当前版本」取文内出现的最高版本号（变更记录按倒序排列，旧版本号不计）。
    - 禁出现文件名是纯文本匹配：入口文档里即使只是「历史记录里提到该文件名」也会被判 [x]，
      这是宽严取舍 —— 对「不随包分发」的承诺做机械约束，宁可多报。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------- 常量

EXPECTED_NAME = "project-dept"

FORBIDDEN_FILENAMES = ("VERIFICATION.md", "修复进度.md", "看板.md", "交付登记簿.md")

REQUIRED_PATHS = (
    "manifest.yaml",
    "SKILL.md",
    "README.md",
    "README_EN.md",
    "static/",
    "references/",
    "scripts/dept_gate.py",
    "scripts/check_doc.py",
    "tests/",
    "evals/evals.json",
)

TOKEN_LIMIT_SKILL_MD = 3000
TOKEN_LIMIT_ALWAYS_LOAD = 9000
# v1.2.1：真实单次开工成本还包括命中的轴片段（static/fragments/<轴>/<值>.md，每轴取最大那份）。
# 以前只算 SKILL.md + always_load，往片段里塞几万字也不会报警（R2 实测 +15,311 字符仍 exit 0）。
TOKEN_LIMIT_PER_RUN_WARN = 9000
TOKEN_LIMIT_PER_RUN_DEFECT = 14000

# 「写死脚本个数」这类陈述会随实体变化腐化（R1 抓到 README 还写"两个脚本/两个质量工具"，实体已 4 个）。
STALE_TWO_SCRIPTS_PHRASES = ("两个脚本", "两个质量工具", "two scripts", "two quality tools")
QUALITY_TOOL_SCRIPT_RE = re.compile(
    r"(?m)^\s+(?:gate_script|audit_script|skill_lint_script|eval_runner)\s*:\s*(\S+)\s*$"
)

PATH_PREFIXES = ("static", "references", "scripts", "agents", "tests", "evals")
FILE_EXTS = {
    "md", "markdown", "py", "json", "yaml", "yml", "txt", "rst",
    "ps1", "sh", "bat", "cmd", "csv", "tsv", "toml", "ini", "cfg",
}

# 「声明处」出现的相对路径 token（前缀 + 至少一段）
PATH_TOKEN_RE = re.compile(
    r"(?<![\w./\\-])"
    r"((?:%s)/[A-Za-z0-9_.\-/]*)" % "|".join(PATH_PREFIXES)
)

VERSION_RE = re.compile(r"(?<![\d.])(\d+\.\d+\.\d+)(?![\d.])")

TAGS = {"ok": "[ok]", "warn": "[!]", "defect": "[x]"}

# CJK 码位区间：按 1 token/字计，其余按 3.5 字符/token
CJK_RANGES = (
    (0x3000, 0x303F),   # CJK 标点
    (0x3040, 0x30FF),   # 日文假名（v1.2.1 补：此前漏掉，纯假名文本按 3.5 字符/token 估算，可绕过预算上限）
    (0x3400, 0x4DBF),   # 扩展 A
    (0x4E00, 0x9FFF),   # 基本区
    (0xAC00, 0xD7A3),   # 谚文音节（v1.2.1 补：同上）
    (0xF900, 0xFAFF),   # 兼容表意
    (0xFF00, 0xFFEF),   # 全角形式
    (0x1F300, 0x1FAFF), # emoji（v1.2.1 补：按 1 token/字保守计，避免用表情凑体积逃检）
    (0x20000, 0x2A6DF), # 扩展 B（v1.2.1 补）
)


# ---------------------------------------------------------------- 结果容器


@dataclass
class CheckResult:
    number: int
    title: str
    details: list = field(default_factory=list)
    defects: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.defects:
            return "defect"
        if self.warnings:
            return "warn"
        return "ok"


class Ctx:
    def __init__(self, root: Path, skill_text: str, manifest_text, fm, body,
                 body_line_offset: int, fm_error, allow_dirname_mismatch: bool = False):
        self.root = root
        self.skill_text = skill_text
        self.manifest_text = manifest_text      # str | None
        self.fm = fm                            # dict | None
        self.body = body or ""
        self.body_line_offset = body_line_offset
        self.fm_error = fm_error
        self.allow_dirname_mismatch = allow_dirname_mismatch
        self.budget = {}


# ---------------------------------------------------------------- 通用工具


def is_cjk(cp: int) -> bool:
    for lo, hi in CJK_RANGES:
        if lo <= cp <= hi:
            return True
    return False


def estimate_tokens(text: str) -> int:
    cjk = sum(1 for ch in text if is_cjk(ord(ch)))
    other = len(text) - cjk
    return int(math.ceil(cjk + other / 3.5))


def read_text(path: Path):
    """按 UTF-8（容忍 BOM）读文本；读不出来返回 None。"""
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    # 去掉 YAML 行尾注释（只处理「空格 + #」）
    m = re.search(r"\s+#", value)
    if m:
        value = value[:m.start()].rstrip()
    return value


def classify_token(token: str):
    """把 path token 分成 ('file', path) / ('dir', path) / None（不核对）。

    - 以 / 结尾 → 目录
    - 最后一段带已知文件扩展名 → 文件
    - 其余（如 static/core、tests/evals 这类散文词/裸目录）→ None，不核对
    """
    token = token.rstrip(".,;:!?)]}'\"").strip()
    if not token:
        return None
    if token.endswith("/"):
        return "dir", token
    last = token.rsplit("/", 1)[-1]
    if "." in last:
        ext = last.rsplit(".", 1)[-1].lower()
        if ext in FILE_EXTS:
            return "file", token
    return None


def exists_with_kind(root: Path, kind: str, token: str) -> bool:
    target = root / token
    return target.is_dir() if kind == "dir" else target.is_file()


def version_key(version: str):
    return tuple(int(part) for part in version.split("."))


def extract_versions(text: str):
    return [m.group(1) for m in VERSION_RE.finditer(text)]


# ---------------------------------------------------------------- frontmatter 解析


def parse_frontmatter(text: str):
    """极简 YAML frontmatter 解析（不依赖 PyYAML）。

    返回 (data, body, body_line_offset, error)。
    data 只支持一层嵌套（metadata: 下的键），足够本包使用。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None, 0, "SKILL.md 首行不是 YAML frontmatter 分隔符 '---'"

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, None, 0, "frontmatter 缺少结束分隔符 '---'"

    data: dict = {}
    current = data
    i = 1
    while i < end:
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        indent = len(raw) - len(raw.lstrip(" \t"))
        m = re.match(r"^([A-Za-z0-9_][A-Za-z0-9_.\-]*)\s*:\s*(.*)$", stripped)
        if not m:
            i += 1
            continue

        key, value = m.group(1), m.group(2).strip()
        if value == "" and indent == 0:
            # 进入嵌套块（例如 metadata:）
            current = {}
            data[key] = current
        elif value[:1] in ("|", ">"):
            # 块标量
            block = []
            j = i + 1
            while j < end:
                nxt = lines[j]
                nindent = len(nxt) - len(nxt.lstrip(" \t"))
                if nxt.strip() and nindent <= indent:
                    break
                block.append(nxt.strip())
                j += 1
            sep = "\n" if value.startswith("|") else " "
            joined = sep.join(block).strip()
            if indent == 0:
                data[key] = joined
                current = data
            else:
                current[key] = joined
            i = j
            continue
        else:
            parsed = unquote(value)
            if indent == 0:
                data[key] = parsed
                current = data
            else:
                current[key] = parsed
        i += 1

    body = "\n".join(lines[end + 1:])
    return data, body, end + 1, None


# ---------------------------------------------------------------- 各项检查


def check_frontmatter(ctx: Ctx) -> CheckResult:
    r = CheckResult(1, "frontmatter")
    if ctx.fm_error:
        r.defects.append(f"SKILL.md: {ctx.fm_error}")
        return r

    fm = ctx.fm or {}
    name = fm.get("name")
    desc = fm.get("description")
    meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
    ver = meta.get("version")

    if not isinstance(name, str) or not name.strip():
        r.defects.append("frontmatter 缺少 name")
        name = ""
    else:
        name = name.strip().rstrip("/")
        if name != ctx.root.name:
            msg = (f"frontmatter name='{name}' 与目录名 '{ctx.root.name}' 不符")
            if ctx.allow_dirname_mismatch:
                r.warnings.append(msg + "（--allow-dirname-mismatch 已放开：只用于验证被改名的副本）")
            else:
                r.defects.append(msg)

    if not isinstance(desc, str) or not desc.strip():
        r.defects.append("frontmatter 缺少 description")
    elif len(desc) > 1024:
        r.defects.append(f"description 长度 {len(desc)} 字符 > 上限 1024")

    if not isinstance(ver, str) or not ver.strip():
        r.defects.append("frontmatter 缺少 metadata.version")
        ver = ""

    if not r.defects:
        r.details.append(
            f"name={name} · description={len(desc)} 字符（上限 1024） · metadata.version={ver}"
        )
    return r


def parse_manifest_version(manifest_text) -> str | None:
    if not manifest_text:
        return None
    m = re.search(r"(?m)^version\s*:\s*['\"]?(\d+\.\d+\.\d+)", manifest_text)
    return m.group(1) if m else None


def check_version_consistency(ctx: Ctx) -> CheckResult:
    r = CheckResult(2, "版本一致")
    values = {}

    if ctx.fm and isinstance(ctx.fm.get("metadata"), dict):
        v = ctx.fm["metadata"].get("version")
        values["SKILL.md metadata.version"] = str(v).strip() if v else None
    else:
        values["SKILL.md metadata.version"] = None

    values["manifest.yaml version"] = parse_manifest_version(ctx.manifest_text)

    readme_notes = {}
    for doc in ("README.md", "README_EN.md"):
        path = ctx.root / doc
        if not path.is_file():
            values[doc] = None
            continue
        text = read_text(path)
        if text is None:
            values[doc] = None
            continue
        tokens = extract_versions(text)
        if not tokens:
            values[doc] = None
            continue
        best = max(tokens, key=version_key)
        values[doc] = best
        readme_notes[doc] = len(set(tokens))

    missing = [key for key, val in values.items() if not val]
    if missing:
        r.defects.append("缺少版本号: " + "、".join(missing))

    present = {key: val for key, val in values.items() if val}
    if len(set(present.values())) > 1:
        r.defects.append(
            "版本不一致: " + ", ".join(f"{key}={values[key]}" for key in values)
        )

    if not r.defects:
        r.details.append("一致: " + "、".join(f"{key}={val}" for key, val in values.items()))
        for doc, count in readme_notes.items():
            if count > 1:
                r.details.append(
                    f"{doc} 文内另有 {count - 1} 个更旧的版本号（变更记录），不计入"
                )
    return r


def parse_always_load(manifest_text):
    """解析 manifest.yaml 的 always_load 列表（只取 `- ` 条目）。"""
    if not manifest_text:
        return []
    items = []
    in_block = False
    for line in manifest_text.splitlines():
        if re.match(r"^always_load\s*:\s*$", line):
            in_block = True
            continue
        if not in_block:
            continue
        if not line.strip():
            continue
        stripped = line.lstrip()
        if stripped.startswith("- "):
            item = unquote(stripped[2:].strip())
            if item:
                items.append(item)
            continue
        if not line[0].isspace():
            break
    return items


def resolve_declared(root: Path, rel: str):
    """把声明里的相对路径落到实体：先按原样，找不到且无扩展名时按「同 stem + 任意扩展名」唯一匹配。"""
    p = root / rel
    if p.is_file() or p.is_dir():
        return p
    last = rel.rsplit("/", 1)[-1]
    if "." not in last:
        hits = sorted(p.parent.glob(last + ".*"))
        if len(hits) == 1:
            return hits[0]
    return None


def parse_fragment_groups(manifest_text):
    """从 manifest 的 axes.values 抽出片段，按轴分组：{轴名: [片段相对路径, ...]}。"""
    groups = {}
    if not manifest_text:
        return groups
    for line in manifest_text.splitlines():
        m = re.match(
            r"^\s+[A-Za-z_][\w-]*:\s+(static/fragments/([A-Za-z0-9_.\-]+)/[A-Za-z0-9_.\-]+\.md)\s*$",
            line,
        )
        if m:
            groups.setdefault(m.group(2), []).append(m.group(1))
    return groups


def check_declared_assets(ctx: Ctx) -> CheckResult:
    r = CheckResult(3, "声明资产存在")
    checked = 0
    seen = set()

    def scan(text, label, line_offset):
        nonlocal checked
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in PATH_TOKEN_RE.finditer(line):
                kind_token = classify_token(m.group(1))
                if not kind_token:
                    continue
                kind, token = kind_token
                checked += 1
                if exists_with_kind(ctx.root, kind, token):
                    continue
                if label == "manifest.yaml":
                    where = f"manifest.yaml:{lineno}"
                else:
                    file_lineno = line_offset + lineno
                    where = f"SKILL.md:{file_lineno}"
                key = (where, token)
                if key in seen:
                    continue
                seen.add(key)
                r.defects.append(f"{where} → {token}")

    if ctx.manifest_text is None:
        r.defects.append("manifest.yaml 缺失，无法核对声明资产")
    else:
        scan(ctx.manifest_text, "manifest.yaml", 0)

    if ctx.body:
        scan(ctx.body, "SKILL.md", ctx.body_line_offset)

    # v1.2.1：结构化的脚本声明必须落到实体。以前只认「前缀 + 带扩展名」的路径 token，
    # 写成 `scripts/check_skill`（无扩展名）就整条逃检 —— 与 manifest 的
    # missing_asset_policy「declared 缺失即 DEFECT」相冲突（R2 的 M6 实测）。
    tool_scripts = []
    if ctx.manifest_text:
        for m in QUALITY_TOOL_SCRIPT_RE.finditer(ctx.manifest_text):
            rel = m.group(1).strip().rstrip(",;")
            tool_scripts.append(rel)
            if resolve_declared(ctx.root, rel) is None:
                r.defects.append(
                    f"manifest.yaml quality_tools → {rel}（找不到实体；无扩展名的声明也必须有对应文件）"
                )
            else:
                checked += 1

        for rel in parse_always_load(ctx.manifest_text):
            if resolve_declared(ctx.root, rel) is None:
                r.defects.append(f"manifest.yaml always_load → {rel}（找不到实体）")

    # v1.2.1：写死「两个脚本 / 两个质量工具」这类计数会随实体变化腐化。
    if len(tool_scripts) and len(tool_scripts) != 2:
        # v1.2.2：以前只扫三份"入口"文档，references/ 里同一条旧措辞就逃过了检查（复核人实抓）。
        # 规则要么全包生效、要么等于没有——所以扫包内所有 .md。
        docs = sorted(
            p for p in ctx.root.rglob("*.md")
            if "__pycache__" not in p.parts and p.is_file()
        )
        for path in docs:
            text = read_text(path)
            if text is None:
                # v1.3.0（P-15-5）：以前这里静默 continue —— 一个 GBK/UTF-16 的 .md
                # 就能让「陈旧计数措辞」这条规则对它永不生效（复核人实测逃检）。
                r.defects.append(
                    path.relative_to(ctx.root).as_posix()
                    + " 不是 UTF-8 文本，读不出来 —— 陈旧措辞扫描对它没有生效"
                    "（GBK/UTF-16 会静默逃过；请统一转成 UTF-8）"
                )
                continue
            doc = path.relative_to(ctx.root).as_posix()
            for lineno, line in enumerate(text.splitlines(), 1):
                for phrase in STALE_TWO_SCRIPTS_PHRASES:
                    if phrase in line:
                        r.defects.append(
                            f"{doc}:{lineno} 写「{phrase}」，但 manifest 声明了 {len(tool_scripts)} 个脚本"
                            "（计数已腐化：改成指向 manifest.yaml 的 quality_tools，不要写死个数）"
                        )

    if not r.defects:
        r.details.append(f"全部存在（核对 {checked} 处声明）")
    return r


def check_forbidden_names(ctx: Ctx) -> CheckResult:
    r = CheckResult(4, "不随包分发文件名")
    hits = 0
    for doc in ("SKILL.md", "README.md", "README_EN.md", "manifest.yaml"):
        path = ctx.root / doc
        if not path.is_file():
            continue
        text = read_text(path)
        if text is None:
            # v1.3.0（P-15-5）：同样不许静默跳过
            r.defects.append(
                doc + " 不是 UTF-8 文本，读不出来 —— 禁名检查对它没有生效"
                "（GBK/UTF-16 会静默逃过；请统一转成 UTF-8）"
            )
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for name in FORBIDDEN_FILENAMES:
                if name in line:
                    hits += 1
                    r.defects.append(f"{doc}:{lineno} 出现「{name}」")
    if not hits:
        r.details.append(
            "入口文档均未出现: " + "、".join(FORBIDDEN_FILENAMES)
        )
    return r


def check_budget(ctx: Ctx) -> CheckResult:
    r = CheckResult(5, "上下文预算")
    skill_tokens = estimate_tokens(ctx.skill_text)
    skill_lines = len(ctx.skill_text.splitlines())
    files = [{"path": "SKILL.md", "lines": skill_lines, "tokens": skill_tokens}]
    warnings = []

    if skill_tokens > TOKEN_LIMIT_SKILL_MD:
        # v1.2.0：入口正文改成硬上限。理由：入口每个 token 都挤掉真实工作的上下文，
        # 它涨上去没人拦，实际后果是"加载一个 skill 就吃掉几 K 预算"。下沉到 references/README 即可。
        r.defects.append(
            f"SKILL.md 估算 {skill_tokens} tokens > 硬上限 {TOKEN_LIMIT_SKILL_MD}"
            "（把细节下沉到 references/ 或 README.md；入口只留路由与不可协商项）"
        )

    always_total = 0
    always_missing = []
    for rel in parse_always_load(ctx.manifest_text):
        path = ctx.root / rel
        if not path.is_file():
            always_missing.append(rel)
            continue
        text = read_text(path)
        if text is None:
            always_missing.append(rel)
            continue
        tokens = estimate_tokens(text)
        always_total += tokens
        files.append({"path": rel, "lines": len(text.splitlines()), "tokens": tokens})

    total = skill_tokens + always_total
    groups = parse_fragment_groups(ctx.manifest_text)
    per_run = total
    per_run_parts = []
    for axis in sorted(groups):
        best = None
        for rel in groups[axis]:
            text = read_text(ctx.root / rel)
            if text is None:
                r.defects.append(f"manifest.yaml 轴片段 → {rel}（找不到实体）")
                continue
            tokens = estimate_tokens(text)
            if best is None or tokens > best[1]:
                best = (rel, tokens, len(text.splitlines()))
        if best:
            per_run += best[1]
            files.append(
                {"path": f"{best[0]}  [{axis} 轴最大]", "lines": best[2], "tokens": best[1]}
            )
            per_run_parts.append(f"{axis}={best[1]}")
    if per_run > TOKEN_LIMIT_PER_RUN_DEFECT:
        r.defects.append(
            f"单次开工实际加载（SKILL.md + always_load + 每轴最大片段）估算 {per_run} tokens"
            f" > 硬上限 {TOKEN_LIMIT_PER_RUN_DEFECT}（片段膨胀同样挤占真实工作上下文）"
        )
    elif per_run > TOKEN_LIMIT_PER_RUN_WARN:
        warnings.append(
            f"单次开工实际加载估算 {per_run} tokens > 警戒 {TOKEN_LIMIT_PER_RUN_WARN}"
        )

    if total > TOKEN_LIMIT_ALWAYS_LOAD:
        warnings.append(
            f"SKILL.md + always_load 合计 {total} tokens > 上限 {TOKEN_LIMIT_ALWAYS_LOAD}"
        )

    r.details.append("文件明细（行数 / 估算 tokens；SKILL.md 含 frontmatter，保守口径）：")
    for item in files:
        r.details.append(f"{item['path']}  {item['lines']} 行  {item['tokens']} tokens")
    r.details.append(
        f"合计: SKILL.md {skill_tokens} + always_load {always_total} = {total} tokens"
        f"（上限 {TOKEN_LIMIT_SKILL_MD} / {TOKEN_LIMIT_ALWAYS_LOAD}）"
    )
    if per_run_parts:
        r.details.append(
            "单次开工实际加载: %d tokens"
            "（+ 每轴最大片段 %s；警戒 %d / 硬上限 %d）"
            % (per_run, "、".join(per_run_parts), TOKEN_LIMIT_PER_RUN_WARN, TOKEN_LIMIT_PER_RUN_DEFECT)
        )
    if always_missing:
        r.details.append("always_load 缺失，未计入: " + "、".join(always_missing))
    if not warnings:
        r.details.insert(0, "预算内")

    r.warnings.extend(warnings)
    ctx.budget = {
        "skill_md_tokens": skill_tokens,
        "always_load_tokens": always_total,
        "total_tokens": total,
        "skill_md_limit": TOKEN_LIMIT_SKILL_MD,
        "total_limit": TOKEN_LIMIT_ALWAYS_LOAD,
        "per_run_tokens": per_run,
        "per_run_limit_warn": TOKEN_LIMIT_PER_RUN_WARN,
        "per_run_limit_defect": TOKEN_LIMIT_PER_RUN_DEFECT,
        "files": files,
    }
    return r


def check_evals(ctx: Ctx) -> CheckResult:
    r = CheckResult(6, "evals 可读")
    path = ctx.root / "evals" / "evals.json"
    if not path.is_file():
        r.defects.append("evals/evals.json 缺失")
        return r

    text = read_text(path)
    if text is None:
        r.defects.append("evals/evals.json 无法按 UTF-8 读取")
        return r
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        r.defects.append(f"evals/evals.json 不是合法 JSON: {exc}")
        return r

    if not isinstance(data, dict):
        r.defects.append("evals/evals.json 顶层不是 JSON 对象")
        return r

    cases = data.get("evals")
    if not isinstance(cases, list):
        r.defects.append("evals/evals.json 顶层缺少 evals 数组")
        return r

    seen = set()
    for idx, case in enumerate(cases, 1):
        if not isinstance(case, dict):
            r.defects.append(f"case #{idx} 不是 JSON 对象")
            continue
        for field_name in ("id", "prompt", "expected_output"):
            value = case.get(field_name)
            if not isinstance(value, str) or not value.strip():
                r.defects.append(
                    f"case #{idx}（id={case.get('id')!r}）缺少或为空: {field_name}"
                )
        cid = case.get("id")
        if isinstance(cid, str) and cid.strip():
            if cid in seen:
                r.defects.append(f"case id 重复: {cid}")
            seen.add(cid)

    if not r.defects:
        r.details.append(f"{len(cases)} 个用例，id 唯一，字段齐全")
    return r


def _yaml_suspicion(text: str):
    """没有 PyYAML 时的保守启发式：找出「父键是 plain scalar、子行却像 key: value」的断行。

    这一族错误本包已犯两次（都是把带冒号的说明写成续行），而当时 PyYAML 恰好又不在
    运行环境里，于是没有任何检查能抓到。所以即使装了 PyYAML 也保留这条兜底。
    """
    lines = text.splitlines()
    hits = []
    for idx, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent < 4:
            continue
        # 找最近的、缩进更小的非空父行
        parent = None
        for j in range(idx - 1, -1, -1):
            pl = lines[j]
            if not pl.strip() or pl.lstrip().startswith("#"):
                continue
            if len(pl) - len(pl.lstrip()) < indent:
                parent = pl.rstrip()
                break
        if parent is None:
            continue
        if parent.lstrip().startswith("- "):
            continue  # 序列项（- key: value）的子键，合法
        if parent.endswith(":") or parent.endswith((">-", "|", "|-", ">", "|+")):
            continue  # 容器或块标量，子行合法
        m = re.match(r"^\s*([A-Za-z_][\w .\-]{0,40}):\s+\S", line)
        if m:
            hits.append((idx + 1, line.strip()[:70]))
    return hits


def _duplicate_top_level_keys(text):
    """返回重复的顶层键名列表（PyYAML 会用后者静默覆盖前者，不报错）。"""
    seen = {}
    for line in text.splitlines():
        if not line or line[0] in (" ", "\t", "#", "-"):
            continue
        match = re.match(r"^([A-Za-z_][\w-]*)\s*:", line)
        if match is None:
            continue
        seen[match.group(1)] = seen.get(match.group(1), 0) + 1
    return sorted(key for key, count in seen.items() if count > 1)


def check_manifest_syntax(ctx: Ctx) -> CheckResult:
    r = CheckResult(8, "manifest 语法")
    if ctx.manifest_text is None:
        r.defects.append("manifest.yaml 缺失或无法按 UTF-8 读取 —— 后面几项检查都失去依据")
        return r
    duplicates = _duplicate_top_level_keys(ctx.manifest_text)
    for key in duplicates:
        r.defects.append(
            "manifest.yaml 顶层键 %r 出现多次 —— YAML 解析时后者会静默覆盖前者" % key
        )
    try:
        import yaml  # type: ignore
    except Exception:
        hits = _yaml_suspicion(ctx.manifest_text)
        for line_no, snippet in hits:
            r.defects.append(
                "疑似 YAML 断行（父键是 plain scalar，续行却含 'key: '）第 %d 行：%s"
                " —— 本机没有 PyYAML，用的是保守启发式；装 PyYAML 后应复核" % (line_no, snippet)
            )
        if not hits:
            r.details.append("本机无 PyYAML，仅做保守启发式检查（未发现断行）")
        return r
    try:
        data = yaml.safe_load(ctx.manifest_text)
    except Exception as exc:  # noqa: BLE001 - 报告原始解析错误最有用
        r.defects.append("manifest.yaml 不是合法 YAML：%s" % str(exc).replace("\n", " "))
        return r
    if not isinstance(data, dict):
        r.defects.append("manifest.yaml 顶层不是映射（YAML 解析得到 %s）" % type(data).__name__)
        return r
    hits = _yaml_suspicion(ctx.manifest_text)
    for line_no, snippet in hits:
        r.defects.append("疑似 YAML 断行（PyYAML 能过但语义多半不对）第 %d 行：%s" % (line_no, snippet))
    r.details.append("PyYAML 解析通过，顶层键 %d 个" % len(data))
    return r


def check_package_completeness(ctx: Ctx) -> CheckResult:
    r = CheckResult(7, "包完整性")
    for rel in REQUIRED_PATHS:
        path = ctx.root / rel
        ok = path.is_dir() if rel.endswith("/") else path.is_file()
        if not ok:
            r.defects.append(f"缺失: {rel}")
    if not r.defects:
        r.details.append(f"{len(REQUIRED_PATHS)} 项齐全")
    return r


# ---------------------------------------------------------------- 输出


def emit_fatal(root: Path, reason: str, as_json: bool) -> int:
    if as_json:
        payload = {
            "ok": False,
            "defects": [],
            "warnings": [],
            "budget": {},
            "checks": [],
            "root": str(root),
            "error": reason,
            "exit_code": 2,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"SKILL CHECK · {root}")
        print(f"[x] 无法执行：{reason}")
        print("结论：未执行（exit 2）")
    return 2


def print_report(root: Path, results) -> int:
    defects = [d for r in results for d in r.defects]
    warnings = [w for r in results for w in r.warnings]
    ok = not defects
    exit_code = 0 if ok else 1

    print(f"SKILL CHECK · {root}")
    for r in results:
        print(f"[{r.number}/{len(results)}] {r.title}  {TAGS[r.status]}")
        for item in r.details:
            print(f"      - {item}")
        for item in r.defects:
            print(f"      [x] {item}")
        for item in r.warnings:
            print(f"      [!] {item}")
    print(f"缺陷 {len(defects)} 项，警告 {len(warnings)} 项")
    print(f"结论：{'通过' if ok else '有缺陷'}（exit {exit_code}）")
    return exit_code


def build_payload(root: Path, results, exit_code: int, error=None):
    defects = [d for r in results for d in r.defects]
    warnings = [w for r in results for w in r.warnings]
    budget = {}
    for r in results:
        if r.number == 5 and getattr(r, "_budget", None):
            budget = r._budget
    return {
        "ok": not defects and error is None,
        "defects": defects,
        "warnings": warnings,
        "budget": budget,
        "checks": [
            {
                "id": r.number,
                "title": r.title,
                "status": r.status,
                "details": r.details,
                "defects": r.defects,
                "warnings": r.warnings,
            }
            for r in results
        ],
        "root": str(root),
        "exit_code": exit_code,
        "error": error,
    }


# ---------------------------------------------------------------- main


def run(root: Path, as_json: bool, allow_dirname_mismatch: bool = False) -> int:
    skill_path = root / "SKILL.md"
    if not root.is_dir():
        return emit_fatal(root, f"包目录不存在: {root}", as_json)
    if not skill_path.is_file():
        return emit_fatal(root, f"SKILL.md 缺失: {skill_path}", as_json)

    skill_text = read_text(skill_path)
    if skill_text is None:
        return emit_fatal(root, f"SKILL.md 无法按 UTF-8 读取: {skill_path}", as_json)

    manifest_path = root / "manifest.yaml"
    manifest_text = read_text(manifest_path) if manifest_path.is_file() else None

    fm, body, body_offset, fm_error = parse_frontmatter(skill_text)
    ctx = Ctx(root, skill_text, manifest_text, fm, body, body_offset, fm_error,
              allow_dirname_mismatch=allow_dirname_mismatch)

    results = [
        check_frontmatter(ctx),
        check_version_consistency(ctx),
        check_declared_assets(ctx),
        check_forbidden_names(ctx),
        check_budget(ctx),
        check_evals(ctx),
        check_package_completeness(ctx),
        check_manifest_syntax(ctx),
    ]
    # 预算结果挂到对应 CheckResult 上，供 --json 使用
    results[4]._budget = ctx.budget

    if not as_json:
        return print_report(root, results)

    exit_code = 0 if not any(r.defects for r in results) else 1
    print(json.dumps(build_payload(root, results, exit_code), ensure_ascii=False, indent=2))
    return exit_code


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except Exception:  # pragma: no cover - 旧解释器/非常规 stdout
        pass

    parser = argparse.ArgumentParser(
        description="project-dept skill 包静态自检器（只查机械可判的腐化）"
    )
    parser.add_argument(
        "--root",
        default=None,
        help="包目录；缺省为脚本所在包（脚本上两级目录）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出机器可读 JSON（stdout 上只有 JSON）",
    )
    parser.add_argument(
        "--allow-dirname-mismatch",
        action="store_true",
        help="把「frontmatter name 与目录名不符」降级为警告（只用于验证被改名的副本；"
             "正式包必须让目录名等于 name）",
    )
    args = parser.parse_args(argv)

    if args.root:
        root = Path(args.root).expanduser().resolve()
    else:
        root = Path(__file__).resolve().parent.parent

    return run(root, args.json, args.allow_dirname_mismatch)


if __name__ == "__main__":
    sys.exit(main())