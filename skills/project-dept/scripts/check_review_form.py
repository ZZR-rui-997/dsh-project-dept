#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_review_form.py — L2 复核单结构校验器（只查结构，不判技术结论）

七条规则
    R1 §0 锚哈希  两次快照取值 + 「一致 / 不一致」结论；取值不同还要写限定语
    R2 §1 判定    只允许 通过 / 通过但要修 / 不通过 三者之一（判定附近 3 行内）
    R3 判定矛盾   判「通过」却留着未标「已修 / 已关闭」的必改项 ⇒ 缺陷
    R4 独立性     出现「自检」且其附近有「未看 / 没看 / 先写 / 之后才 / 之前」之类限定
    R5 机械证据   §1 里要有表格，且至少 1 个数据行带 命令 / 路径 / 行号 痕迹
    R6 禁用证据   和旧版一致 / 与旧版一致 / 和 MEMORY / 与 MEMORY /
                  作者说 / 看起来合理 / 量级差不多 / 文件存在就算
    R7 真问题     「问题」表格（有数据行），或「我重算了…确实没问题」豁免句

用法
    python check_review_form.py <复核单路径> [--json]

退出码
    0 = 合规
    1 = 有缺陷
    2 = 文件不存在 / 读不了（**不是通过**）

设计约束
    - 只读；不改被校验的复核单。
    - 只做结构断言，不判「复核结论本身对不对」——那是人的事。
    - 缺文件返回 2 而不是 0：把「没跑」当「通过」是最坏的结果。
    - --json 时 stdout 上只有一段 JSON，不混 banner / 分隔线。
"""
import argparse
import json
import os
import re
import sys

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_NOT_RUN = 2

# 规则键 -> 报告里的规则名（顺序即输出顺序）
RULES = [
    ("snapshot", "§0 锚哈希两次快照"),
    ("verdict", "§1 判定唯一且合法"),
    ("verdict_mustfix", "§1 判定与必改项不矛盾"),
    ("independence", "独立性：先独立结论再看自检"),
    ("evidence", "§1 机械证据表格"),
    ("banned", "禁用证据短语"),
    ("problem", "至少一条真问题"),
]
RULE_NAMES = dict(RULES)

# 规则 5/6 判据里点名的禁用短语（只查这些字面量，不扩展）
BANNED_PHRASES = (
    "和旧版一致",
    "与旧版一致",
    "和 MEMORY",
    "与 MEMORY",
    "作者说",
    "看起来合理",
    "量级差不多",
    "文件存在就算",
)

# 判定只认这三种；顺序重要：长的在前，避免「通过」抢先匹配「通过但要修」
VERDICT_ALT = r"(通过但要修|不通过|通过)"

# 独立性限定语：出现「自检」时，附近至少要有其中一个
INDEPENDENCE_MARKERS = re.compile(
    r"未看|没看|未读|没读|未打开|没打开|先写|先出|先给|之后才|之后|之前|独立于|后看|不看"
)

# 标题行与模板说明行不算独立性的证据（它们本来就长在模板里）。
INDEPENDENCE_SKIP_HINTS = ("模板", "必填", "示例", "说明", "要求", "提示")


def _strip_lead_markers(line):
    """反复剥掉行首的引用标记、括号、列表符号与强调符，直到不再变化。

    v1.3.4（A1 必改）：复核人实测 `> **提示**：…`、`>**提示**`、`（**提示**）`、
    `> - **提示**`、`> **说明**` 五例骨架行都被判成"不是模板痕迹"而白送 exit 0——
    因为此前只剥一层标记，遇到 `> ` + `**` + `提示` 这种叠加形态就剥不干净。
    """
    prev = None
    out = line
    while out != prev:
        prev = out
        out = out.lstrip()
        out = out.lstrip(">（(")
        out = out.lstrip()
        out = out.lstrip("-*+")
        out = out.lstrip()
        out = out.lstrip("*_`“\"\'")
    return out


def _independence_candidate(line):
    """只认正文里的声明句：标题行、模板提示行一律不算。

    演进（四条都是复核逼出来的）：
    - v1.3.1：标题行与模板提示行不算证据（模板标题自己写着「在打开自检之前完成」，等于白送）。
    - v1.3.2：跳过规则收窄到**行首形态**（此前「行内任意位置出现提示词就整句跳过」，
      正文里一句「我按要求先写…」会被误丢，假缺陷）。
    - v1.3.3：行首是 `>` / `（` / `(` 时，去掉标记后必须以提示词开头才算模板痕迹。
    - v1.3.4：标记可能**叠加**（`> **提示**`、`> - 提示`、`（**提示**）`），改为循环剥到稳定。
    """
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return False
    body = _strip_lead_markers(stripped)
    return not any(body.startswith(hint) for hint in INDEPENDENCE_SKIP_HINTS)

# §1 表格行里的机械证据痕迹（按验收标准点名的六类）
EVIDENCE_RE = re.compile(r"python|\.py\b|:\d+|--mode|sha256|HASH\s")

# 判定已修 / 已关闭的标注
FIXED_RE = re.compile(r"已修|已修复|已关闭|已闭合|已处理")

# 两次取值不同时，允许的「结论适用范围」限定语（「只对 start 版有效」之类）
LIMIT_RE = re.compile(
    r"只对\s*start|只对\s*开始|只对\s*起始|仅对\s*start|start\s*版|"
    r"start[^\n]{0,16}(?:有效|成立|适用)|本轮[^\n]{0,16}(?:有效|成立|适用)",
    re.IGNORECASE,
)


def _force_utf8_stdout():
    """Windows 控制台默认 GBK，中文输出会乱码或炸。尽量切到 UTF-8。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


_force_utf8_stdout()


# ------------------------------------------------------------------ 基础工具


def make_defect(rule, line, message, excerpt=""):
    return {
        "rule": rule,
        "line": int(line),
        "message": message,
        "excerpt": excerpt,
    }


def excerpt_of(line, limit=60):
    s = (line or "").strip()
    if len(s) > limit:
        return s[:limit] + "…"
    return s


def read_text(path):
    """读 UTF-8（容忍 BOM）。返回 (text, error)；error 为 None 表示成功。"""
    if not os.path.exists(path):
        return None, f"文件不存在: {path}"
    if os.path.isdir(path):
        return None, f"路径是目录不是文件: {path}"
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read(), None
    except UnicodeDecodeError as exc:
        return None, f"不是 UTF-8 文本，读不出来: {path}（{exc}）"
    except OSError as exc:
        return None, f"文件读取失败: {path}（{exc}）"


HEADING_RE = re.compile(r"^##(?!#)\s*(\d+)\s*[.、．]?")


def find_sections(lines):
    """只按二级标题切节：{节号: (start_idx, end_idx)}，0-based 半开区间。"""
    heads = []
    for idx, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            heads.append((idx, int(m.group(1))))
    sections = {}
    for pos, (idx, num) in enumerate(heads):
        end = heads[pos + 1][0] if pos + 1 < len(heads) else len(lines)
        if num not in sections:
            sections[num] = (idx, end)
    return sections


def _is_separator(line):
    s = line.strip()
    if not s.startswith("|"):
        return False
    core = s.strip("|").replace(" ", "")
    return bool(core) and set(core) <= set("-:")


def iter_table_blocks(lines, start, end):
    """产出表块 (header_idx, data_idx_list)。数据行 = 表头与分隔行之后的行。"""
    i = start
    while i < end:
        if not lines[i].strip().startswith("|"):
            i += 1
            continue
        j = i
        while j < end and lines[j].strip().startswith("|"):
            j += 1
        block = list(range(i, j))
        if len(block) >= 2 and _is_separator(lines[block[1]]):
            data = block[2:]
        else:
            data = block[1:]
        yield block[0], data
        i = j


def _row_has_content(line):
    return bool(re.sub(r"[|\s\-:]", "", line))


# ------------------------------------------------------------------ R1 快照

MISSING_SNAPSHOT_MSG = "§0 缺被验快照：复核人无法证明期间文件没被改过"


def _snapshot_readings(lines, start, end):
    """收集两次法则的「取值」：

    - kind='hash': `HASH <12hex> FILES <n>` 行，value=(hash, files)
    - kind='tuple': 一行里 ≥2 个 8+ 位十六进制串（锚哈希 / sha256 行常见形态）
    """
    readings = []
    for idx in range(start, end):
        line = lines[idx]
        hashes = re.findall(r"HASH\s+([0-9a-fA-F]{12})\b", line)
        if hashes:
            files = None
            fm = re.search(r"FILES\s*[=:]?\s*(\d+)", line)
            if fm:
                files = int(fm.group(1))
            for value in hashes:
                readings.append((idx + 1, "hash", value.lower(), files))
            continue
        tokens = re.findall(r"\b[0-9a-fA-F]{8,}\b", line)
        if len(tokens) >= 2:
            readings.append((idx + 1, "tuple", tuple(t.lower() for t in tokens), None))
    return readings


def check_snapshot(lines, sections):
    defects = []
    if 0 not in sections:
        return [make_defect("snapshot", 1, MISSING_SNAPSHOT_MSG, "")]

    start, end = sections[0]
    body = "\n".join(lines[start:end])
    readings = _snapshot_readings(lines, start, end)

    hash_count = sum(1 for r in readings if r[1] == "hash")
    word_hits = len(re.findall(r"(?i)\banchor\b|\bsha256\b", body))
    hex_tokens = re.findall(r"\b[0-9a-fA-F]{8,}\b", body)
    has_snapshot = hash_count >= 2 or (word_hits >= 2 and len(hex_tokens) >= 2)
    if not has_snapshot:
        return [make_defect("snapshot", start + 1, MISSING_SNAPSHOT_MSG, excerpt_of(lines[start]))]

    # 结论：必须写「一致 / 不一致」
    if "不一致" not in body and "一致" not in body:
        defects.append(
            make_defect(
                "snapshot",
                start + 1,
                "§0 未给出「一致 / 不一致」结论：两次快照取值没有机械比对结果",
                excerpt_of(lines[start]),
            )
        )

    # 两次取值是否可比
    mismatch_line = None
    hash_vals = {r[2] for r in readings if r[1] == "hash"}
    if len(hash_vals) > 1:
        first = readings[0][2]
        mismatch_line = next((r[0] for r in readings if r[2] != first), readings[0][0])
    files_vals = {r[3] for r in readings if r[1] == "hash" and r[3] is not None}
    if len(files_vals) > 1 and mismatch_line is None:
        first_files = next(r[3] for r in readings if r[3] is not None)
        mismatch_line = next((r[0] for r in readings if r[3] not in (None, first_files)), readings[0][0])
    tuples = [r[2] for r in readings if r[1] == "tuple"]
    if len(set(tuples)) > 1 and mismatch_line is None:
        mismatch_line = next(r[0] for r in readings if r[1] == "tuple" and r[2] != tuples[0])

    if mismatch_line is not None:
        has_inconsistent = "不一致" in body
        has_limit = bool(LIMIT_RE.search(body))
        if not (has_inconsistent and has_limit):
            defects.append(
                make_defect(
                    "snapshot",
                    mismatch_line,
                    "两次快照取值不同，但没同时写明「不一致」与「只对 start 版有效」之类"
                    "的限定语（否则等于拿两次不同的快照下同一个结论）",
                    excerpt_of(lines[mismatch_line - 1]),
                )
            )
    return defects


# ------------------------------------------------------------------ R2 判定


def _verdict_in_line(line):
    """从一行里认出 通过 / 通过但要修 / 不通过；认不出返回 None。"""
    # 形态一：判定：X   /   **判定**：**X**
    m = re.search(
        r"判定(?:\*\*)?\s*[：:]\s*(?:\*\*)?"
        + VERDICT_ALT
        + r"(?=\s*(?:\*\*)?\s*(?:[（(，,。；;、）)]|$))",
        line,
    )
    if m:
        return m.group(1)
    # 形态二：整行（可带列表符号 / 加粗）就是一个判定
    text = line.strip()
    m = re.match(r"(?:[-*>]\s+)?\*\*" + VERDICT_ALT + r"\*\*", text)
    if m:
        return m.group(1)
    m = re.match(r"(?:[-*>]\s+)?" + VERDICT_ALT + r"(?=$|[\s（(：:，,。；;、)）])", text)
    if m:
        return m.group(1)
    return None


def check_verdict(lines, sections):
    if 1 not in sections:
        return None, [
            make_defect(
                "verdict",
                1,
                "缺 §1「我的独立结论」节：判定无处可查（只允许 通过 / 通过但要修 / 不通过）",
                "",
            )
        ]

    start, end = sections[1]
    candidates = []  # (line_idx0, verdict)
    for idx in range(start, end):
        if "判定" not in lines[idx]:
            continue
        for j in range(idx, min(idx + 4, end)):  # 判定字样附近 3 行内
            value = _verdict_in_line(lines[j])
            if value:
                candidates.append((j, value))

    candidates = sorted(set(candidates))
    if not candidates:
        return None, [
            make_defect(
                "verdict",
                start + 1,
                "§1 未给出合法判定：只允许 通过 / 通过但要修 / 不通过 三者之一"
                "（且须写在「判定」字样附近 3 行内）",
                excerpt_of(lines[start]),
            )
        ]

    values = []
    for _, value in candidates:
        if value not in values:
            values.append(value)
    if len(values) > 1:
        detail = " / ".join(f"「{v}」" for v in values)
        lines_txt = "、".join(f"第 {i + 1} 行" for i, _ in candidates[:4])
        return None, [
            make_defect(
                "verdict",
                candidates[0][0] + 1,
                f"§1 判定不唯一：同时出现 {detail}（{lines_txt}），只能是一个",
                excerpt_of(lines[candidates[0][0]]),
            )
        ]

    return candidates[0][1], []


def check_verdict_mustfix(lines, verdict):
    if verdict != "通过":
        return []
    pending = []
    for header_idx, data in iter_table_blocks(lines, 0, len(lines)):
        for idx in data:
            row = lines[idx]
            if "必改" not in row:
                continue
            if FIXED_RE.search(row):
                continue
            if not _row_has_content(row):
                continue
            pending.append(idx + 1)
    if not pending:
        return []
    return [
        make_defect(
            "verdict_mustfix",
            pending[0],
            "判定为「通过」，但正文仍有未标注「已修 / 已关闭」的必改项——"
            "判通过与必改项矛盾",
            excerpt_of(lines[pending[0] - 1]),
        )
    ]


# ------------------------------------------------------------------ R4 独立性


def check_independence(lines):
    hits = [i for i, line in enumerate(lines) if "自检" in line]
    if not hits:
        return [
            make_defect(
                "independence",
                1,
                "无法确认独立性：全文没有「自检」相关表述"
                "（复核人必须先写独立结论、后看作者自检）",
                "",
            )
        ]
    first_candidate = None
    for idx in hits:
        line = lines[idx]
        if not _independence_candidate(line):
            continue
        if first_candidate is None:
            first_candidate = idx
        pos = line.find("自检")
        window = line[max(0, pos - 40): pos + 40]
        if INDEPENDENCE_MARKERS.search(window):
            return []
    # v1.3.2（A1 必改 ②）：报第一个真正的正文候选行，别把被跳过的标题行当违规原文。
    ref = first_candidate if first_candidate is not None else hits[0]
    return [
        make_defect(
            "independence",
            ref + 1,
            "无法确认独立性：正文里出现「自检」但附近没有「未看 / 没看 / 先写 / "
            "之后才」之类限定（标题行与模板提示行不算证据）",
            excerpt_of(lines[ref]),
        )
    ]


# ------------------------------------------------------------------ R5 证据


def check_evidence(lines, sections):
    if 1 not in sections:
        return [
            make_defect(
                "evidence",
                1,
                "§1 缺机械证据：没有独立的 §1 节，无法核对表格",
                "",
            )
        ]
    start, end = sections[1]
    blocks = list(iter_table_blocks(lines, start, end))
    if not blocks:
        return [
            make_defect(
                "evidence",
                start + 1,
                "§1 缺机械证据：没有表格（至少要列出重跑 / 重算的命令与结果）",
                excerpt_of(lines[start]),
            )
        ]
    evidence_header_hints = ("重算", "重跑", "重查", "方法", "命令")
    best_rows = 0
    for header_idx, data in blocks:
        header = lines[header_idx]
        if not any(hint in header for hint in evidence_header_hints):
            continue
        good = 0
        for idx in data:
            row = lines[idx]
            if not _row_has_content(row):
                continue
            if "<" in row:  # 模板占位符行不算证据
                continue
            if EVIDENCE_RE.search(row):
                good += 1
        best_rows = max(best_rows, good)
    if best_rows >= 2:
        return []
    return [
        make_defect(
            "evidence",
            blocks[0][0] + 1,
            "§1 缺机械证据：需要「重算 / 重跑 / 重查」表里至少 2 行真实数据，"
            "每行带 命令 / 路径 / 行号 痕迹（python、.py、:数字、--mode、sha256、HASH）；"
            "只写一行、或拿问题表凑数都不算",
            excerpt_of(lines[blocks[0][0]]),
        )
    ]


# ------------------------------------------------------------------ R6 禁用证据


def check_banned(lines):
    defects = []
    for idx, line in enumerate(lines):
        for phrase in BANNED_PHRASES:
            if phrase in line:
                defects.append(
                    make_defect(
                        "banned",
                        idx + 1,
                        f"禁用证据短语「{phrase}」：这类说法不能作为正确性依据"
                        "（正确锚点是独立重算 > 外部权威 > 自洽性）",
                        excerpt_of(line),
                    )
                )
    return defects


# ------------------------------------------------------------------ R7 真问题


def check_problem(lines):
    for header_idx, data in iter_table_blocks(lines, 0, len(lines)):
        header = lines[header_idx]
        if "问题" not in header:
            continue
        if any(_row_has_content(lines[idx]) for idx in data):
            return []
    for idx, line in enumerate(lines):
        if "我重算了" not in line:
            continue
        if re.search(r"找不到真问题|要写|模板|必填|示例", line):
            continue
        if re.search(r"为什么|没问题|没有真问题|确实没问题|认为", line):
            return []
    return [
        make_defect(
            "problem",
            1,
            "找不到「问题」表（含数据行），也没有「我重算了哪几项、为什么认为确实"
            "没问题」的豁免句——无法证明复核人真找了问题",
            "",
        )
    ]


# ------------------------------------------------------------------ 汇总


def check_text(text):
    lines = text.splitlines()
    sections = find_sections(lines)
    defects = []
    defects.extend(check_snapshot(lines, sections))
    verdict, verdict_defects = check_verdict(lines, sections)
    defects.extend(verdict_defects)
    defects.extend(check_verdict_mustfix(lines, verdict))
    defects.extend(check_independence(lines))
    defects.extend(check_evidence(lines, sections))
    defects.extend(check_banned(lines))
    defects.extend(check_problem(lines))
    defects.sort(key=lambda d: (d["line"], d["rule"]))
    return defects


def build_payload(path, exit_code, defects, error=None):
    hit_rules = {d["rule"] for d in defects}
    rules = []
    for key, name in RULES:
        count = sum(1 for d in defects if d["rule"] == key)
        rules.append(
            {
                "rule": key,
                "name": name,
                "ok": count == 0,
                "defect_count": count,
            }
        )
    return {
        "ok": exit_code == EXIT_PASS,
        "file": os.path.abspath(path),
        "exit_code": exit_code,
        "defects": defects,
        "warnings": [],
        "rules": rules,
        "error": error,
        "rule_keys_hit": sorted(hit_rules),
    }


def print_human(path, defects, exit_code):
    print(f"REVIEW FORM CHECK · {os.path.abspath(path)}")
    by_rule = {}
    for d in defects:
        by_rule.setdefault(d["rule"], []).append(d)
    for key, name in RULES:
        items = by_rule.get(key, [])
        print(f"[{'x' if items else 'ok'}] {name}")
        for d in items:
            excerpt = d.get("excerpt") or ""
            suffix = f"｜原文：{excerpt}" if excerpt else ""
            print(f"      - 第 {d['line']} 行：{d['message']}{suffix}")
    total = len(defects)
    if exit_code == EXIT_PASS:
        print("结论：合规（exit 0）")
    else:
        print(f"结论：有缺陷（exit 1，{total} 条）")


def run(path, as_json):
    text, error = read_text(path)
    if text is None:
        if as_json:
            payload = build_payload(path, EXIT_NOT_RUN, [], error)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"REVIEW FORM CHECK · {os.path.abspath(path)}")
            print(f"[x] 无法执行：{error}")
            print("结论：未执行（exit 2）")
        return EXIT_NOT_RUN

    defects = check_text(text)
    exit_code = EXIT_FAIL if defects else EXIT_PASS
    if as_json:
        print(json.dumps(build_payload(path, exit_code, defects), ensure_ascii=False, indent=2))
    else:
        print_human(path, defects, exit_code)
    return exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="L2 复核单结构校验器（只查结构，不判技术结论）"
    )
    parser.add_argument("path", help="复核单 markdown 路径")
    parser.add_argument("--json", action="store_true", help="机器可读输出（stdout 只有 JSON）")
    args = parser.parse_args(argv)
    return run(args.path, args.json)


if __name__ == "__main__":
    sys.exit(main())
