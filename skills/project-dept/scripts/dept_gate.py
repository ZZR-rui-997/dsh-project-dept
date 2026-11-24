#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dept_gate.py — 开工闸门（通用版）

检查项目台账的结构完整性，据此决定能不能开工。配置来自 dept.config.json：
从当前工作目录向上逐级查找，找到为止；也可用 --config 显式指定。

退出码
    0 = 通过（可能有告警，告警不阻塞，但要写进本轮回复）
    1 = 阻塞：结构性问题（缺台账 / 没有当前板块）——不许开工
    2 = 需决策：有未处置的债务——必须逐条「做掉 / 豁免（理由+复查日期）/ 降级」
    3 = 未执行：四种情形——找不到配置文件 / 配置解析失败（JSON 解不开）/ 顶层不是 JSON 对象 /
        本目录有自己的台账但配置只在祖先目录找到（拿祖先配置审本项目会漏掉本项目债务）

设计约束
    - 只读，不改任何文件。
    - 不猜：所有结论都附位置（文件:行），PASS 与 FAIL 都能人工复核。
    - 路径一律相对项目根，项目根 = 配置文件所在目录。
"""
import argparse
import io
import json
import os
import re
import sys

EXIT_PASS = 0
EXIT_BLOCKED = 1
EXIT_DECISION = 2
EXIT_NOT_RUN = 3

CN_NUM = "一二三四五六七八九十"


def find_config(start, explicit=None):
    if explicit:
        return os.path.abspath(explicit) if os.path.isfile(explicit) else None
    cur = os.path.abspath(start)
    while True:
        cand = os.path.join(cur, "dept.config.json")
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def read_text(path):
    """读文本，容忍 BOM 与常见编码。文件不存在返回 None。"""
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def strip_fences(text):
    """把 Markdown 围栏代码块（``` 或 ~~~）的内容清空（保留行数，便于行号对得上）。

    为什么：看板/文档里常贴示例片段，示例里写 `## 当前板块` 或 `- [ ] D9` 会被当成真的
    小节/债务（X2 实测：围栏里的示例可以伪造"有当前板块"，也可以反过来误拦）。

    两种围栏都要认（Y2 实测：只认 ``` 时，~~~ 围栏里的示例照样能伪造 exit 0）；
    另外 fence 记号至少要 3 个字符、且用同一字符闭合（Markdown 的规则）。
    """
    out = []
    fence = None
    for line in text.splitlines():
        s = line.lstrip()
        marker = None
        for ch in ("`", "~"):
            n = len(s) - len(s.lstrip(ch))
            if n >= 3:
                marker = ch * n
                break
        if marker is not None:
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            out.append("")
            continue
        out.append("" if fence is not None else line)
    return "\n".join(out)


def section_lines(text, heading_re):
    """返回**所有**匹配 heading_re 的 `##` 小节正文行（可跨多个同名小节），带行号。

    两条修正（验证轮实证）：
    1. **大小写不敏感**（Lead L3 通用性实测）：以前 `re.search(heading_re, line)` 区分大小写，
       英文项目写 `## Open debts` / `## Pre-mortem`（自然写法）就完全匹配不上 ⇒ 未处置债务被漏查、
       闸门 exit 0 放行。加上 IGNORECASE 后 `Open debts` / `open debts` 都生效。
    2. **扫全部匹配小节**（V1/N4）：以前遇到下一个 `##` 就 break，看板里有
       「## 未完成事项」+「## 债务账本」两节时只看第一节，第二节的真债务被忽略。
    """
    lines = text.splitlines()
    out = []
    inside = False
    for i, line in enumerate(lines, 1):
        if re.match(r"^##\s", line):
            if re.search(heading_re, line, re.IGNORECASE):
                inside = True
                out.append((i, line))
                continue
            inside = False
            continue
        if inside:
            out.append((i, line))
    return out


def classify_gate(ok_structural, open_debts):
    if not ok_structural:
        return EXIT_BLOCKED
    if open_debts:
        return EXIT_DECISION
    return EXIT_PASS


def main(argv=None):
    ap = argparse.ArgumentParser(description="Project department pre-start gate")
    ap.add_argument("--config", help="path to dept.config.json (default: walk up from cwd)")
    ap.add_argument("--root", default=os.getcwd(), help="where to start looking for the config")
    ap.add_argument("--quiet", action="store_true", help="only print the verdict line")
    args = ap.parse_args(argv)

    cfg_path = find_config(args.root, args.config)
    if not cfg_path:
        print("[x] 未找到 dept.config.json（从 %s 向上查找）—— 闸门未执行" % args.root)
        print("    先按 references/project-scaffold.md 第 3 步建配置文件。")
        return EXIT_NOT_RUN
    try:
        cfg = json.loads(read_text(cfg_path) or "{}")
    except Exception as exc:  # noqa: BLE001 - 配置坏了要如实报告
        print("[x] 配置文件解析失败：%s（%s）—— 闸门未执行" % (cfg_path, exc))
        return EXIT_NOT_RUN
    if not isinstance(cfg, dict):
        # W1/N5：配置写成 `[]` 这类非对象时，后面 cfg.get 会抛 AttributeError（崩溃不是判定）。
        print("[x] 配置文件顶层必须是 JSON 对象（现在是 %s）：%s —— 闸门未执行"
              % (type(cfg).__name__, cfg_path))
        return EXIT_NOT_RUN

    root = os.path.dirname(cfg_path)
    # W1②/R3-P4：find_config 会一路向上找，于是「本目录是另一个项目（有自己的 _team\ 但漏了
    # 配置文件）」时会拿祖先项目的配置和台账来审 ⇒ 本项目的真债务一条都没看，却 exit 0。
    # 判据：本目录下存在 ledger_dir，但配置文件不在本目录 ⇒ 结构性阻断（要求显式 --config）。
    ledger_name = cfg.get("ledger_dir", "_team") if isinstance(cfg, dict) else "_team"
    here = os.path.abspath(args.root)
    if not args.config and os.path.abspath(root) != here \
            and os.path.isdir(os.path.join(here, ledger_name)):
        print("[x] 本目录（%s）有自己的 %s\\，但 dept.config.json 是在上层 %s 找到的"
              % (here, ledger_name, root))
        print("    —— 拿祖先项目的配置审本项目的台账，会漏掉本项目的未处置债务。")
        print("    请在 %s 建自己的 dept.config.json；若确实要审祖先那份，显式传 "
              "--config <path> 才会放行（这是有意为之的逃生口，不是自动行为）。" % here)
        return EXIT_NOT_RUN
    # R3-P4：配置里的 project_name 若与所在目录名明显不符，提示可能抓错项目配置。
    expected = os.path.basename(root)
    declared = cfg.get("project_name")
    if declared and expected not in str(declared) and str(declared) not in expected:
        print("[!] 警告：dept.config.json 的 project_name=「%s」与其所在目录「%s」不一致 —— 可能抓到了别的项目的配置，先核对再开工" % (declared, expected))
    ledger = os.path.join(root, cfg.get("ledger_dir", "_team"))
    files = {
        "board": os.path.join(ledger, cfg.get("board_file", "看板.md")),
        "flow": os.path.join(ledger, cfg.get("flow_file", "工作流.md")),
        "register": os.path.join(ledger, cfg.get("register_file", "交付登记簿.md")),
        "baseline": os.path.join(ledger, cfg.get("baseline_file", "基准清单.md")),
    }
    role_dir = os.path.join(ledger, cfg.get("role_dir", "岗位"))
    artefact_dir = os.path.join(ledger, cfg.get("artefact_dir", "out"))

    structural = True
    violations = []
    warnings = []
    ok = []

    def say(tag, msg):
        if not args.quiet:
            print("  [%s] %s" % (tag, msg))

    print("=" * 44)
    print("  DEPARTMENT GATE  —  %s" % cfg.get("project_name", os.path.basename(root)))
    print("=" * 44)

    # ---- 1 台账文件齐否（缺 = 结构性问题）
    missing = [k for k, p in files.items() if not os.path.isfile(p)]
    if missing:
        structural = False
        violations.append("缺台账文件：%s" % ", ".join(missing))
    else:
        ok.append("台账文件齐（流程/看板/登记簿/基准清单 四件套）")

    board_text = strip_fences(read_text(files["board"]) or "")

    # ---- 2 当前板块
    current = None
    for ln, line in enumerate(board_text.splitlines(), 1):
        low = line.lower()
        if re.match(r"^##\s", line) and ("当前板块" in line or "current package" in low):
            current = (ln, line.strip("# ").strip())
            break
    if not current:
        structural = False
        violations.append("看板里没有「## 当前板块」—— 不知道要做什么，不许开工")
    else:
        title = re.sub(r"^#+\s*", "", current[1])
        title = re.sub(r"^(当前板块|Current package)\s*[:：]\s*", "", title)
        ok.append("当前板块：%s" % title)

    # ---- 3 债务账本未处置条数
    open_debts = []
    sec = section_lines(board_text, r"未完成事项|债务账本|open debts|debt ledger|backlog")
    if not sec:
        # V1/N2 + V2/③：以前这里只 warning，于是「把标题改个名」就能让闸门放过未处置债务 ⇒ exit 0 开工。
        # 债务账本是开工闸门的存在理由之一，读不到就等于没核 —— 必须当结构性问题（exit 1）。
        structural = False
        violations.append("看板里找不到「未完成事项 / 债务账本」小节 —— 未处置债务无法核对，不许开工"
                          "（小节标题须含：未完成事项 / 债务账本 / open debts / debt ledger）")
    else:
        for ln, line in sec[1:]:
            s = line.strip()
            # W2/P1-a：Markdown 无序列表有 - / * / + 三种写法，只认 "-" 会把
            # `* [ ] D1` 这类未处置债务整条跳过（实测 exit 0「未处置 0 条」）。
            if not re.match(r"^[-*+]\s", s):
                continue
            # R3-P3 修复：只有显式 `- [ ]` 才算未处置。
            # 说明性 bullet（豁免记录、复查日期、纯文字）不算未处置债务 ——
            # 以前第二个正则把任何非 [x] 行都当未处置，导致按 workflow 写的
            # 「豁免（理由+复查日期）」记录永远被判未处置（死锁，唯一出路是删行销毁豁免证据）。
            # 处置状态只看勾选框：`- [ ]` 未处置 / `- [x]` 已处置 / 无框 = 说明文字不算。
            unchecked = re.match(r"^[-*+]\s*\[\s*\]", s) is not None
            if unchecked:
                open_debts.append((ln, s))
        ok.append("未完成事项：未处置 %d 条 / 已处置 %d 条"
                  % (len(open_debts), max(0, len([1 for _, l in sec[1:]
                                                  if re.match(r"^[-*+]\s*\[x\]", l.strip(), re.IGNORECASE)]))))
        for ln, s in open_debts:
            warnings.append("债务未处置 %s:%d  %s" % (os.path.basename(files["board"]), ln, s[:90]))

    # ---- 4 交付登记簿是否有记录
    reg_text = read_text(files["register"])
    if reg_text is None:
        pass
    else:
        rows = [l for l in reg_text.splitlines()
                if l.strip().startswith("|") and not re.match(r"^\|\s*-+", l)]
        ok.append("交付登记簿：%d 行表格记录（含表头）" % len(rows))

    # ---- 5 临时脚本散落
    patterns = cfg.get("scratch_patterns") or ["probe_*", "_scan*", "_summ*", "_tmp*"]
    stray = []
    if os.path.isdir(artefact_dir):
        for dirpath, dirnames, filenames in os.walk(artefact_dir):
            dirnames[:] = [d for d in dirnames if d.lower() != "scratch"]
            for fn in filenames:
                if not fn.lower().endswith((".py", ".ps1", ".sh", ".bat", ".cmd")):
                    continue
                for pat in patterns:
                    if _glob_match(fn, pat):
                        stray.append(os.path.relpath(os.path.join(dirpath, fn), root))
                        break
    if stray:
        warnings.append("%s\\ 下有 %d 个临时脚本没归到 scratch\\（例：%s）"
                        % (os.path.basename(artefact_dir), len(stray), stray[0]))
    else:
        ok.append("产物目录下无散落临时脚本")

    # ---- 6 岗位卡
    required = cfg.get("required_roles") or ["lead", "audit", "reviewer"]
    if not os.path.isdir(role_dir):
        structural = False
        violations.append("缺岗位卡目录 %s" % role_dir)
    else:
        have = [f[:-3] for f in os.listdir(role_dir) if f.lower().endswith(".md")]
        lacking = [r for r in required if r not in have]
        if lacking:
            structural = False
            violations.append("缺必备岗位卡：%s（现有：%s）" % (", ".join(lacking), ", ".join(sorted(have)) or "无"))
        else:
            ok.append("岗位卡：%d 张（%s）" % (len(have), " / ".join(sorted(have))))

    # ---- 7 基准清单里的 [未溯源]
    _raw_base = read_text(files["baseline"])
    base_text = strip_fences(_raw_base) if _raw_base is not None else None
    if base_text is not None:
        untraced = [(i, l.strip()) for i, l in enumerate(base_text.splitlines(), 1)
                    if "[未溯源]" in l or "[untraced]" in l.lower()]
        ok.append("基准清单：%d 行，其中标记未溯源 %d 处" % (len(base_text.splitlines()), len(untraced)))
        if untraced:
            warnings.append("未溯源基准 %d 处 —— 不能当验收基准，也不能写进正式交付物"
                            % len(untraced))
            if not args.quiet:
                for ln, l in untraced[:3]:
                    print("        %s:%d  %s" % (os.path.basename(files["baseline"]), ln, l[:110]))

    # ---- 8 方向复盘小节是否还是模板
    pre = section_lines(board_text, r"方向复盘|pre-?mortem")
    if pre:
        body = " ".join(l for _, l in pre)
        if re.search(r"待填|TODO|TBD|<填|待补充", body):
            warnings.append("「方向复盘」小节还是模板 —— 收口前必须填三问（见 references/self-skepticism.md）")

    # ---- 输出
    if not args.quiet:
        for m in ok:
            say("i", m)
        for m in warnings:
            say("!", m)
        for m in violations:
            say("x", m)
    code = classify_gate(structural, open_debts)
    print("-" * 44)
    # V1/P7：以前无论有没有告警都印「（有告警）」，零告警时是假话。按实际条数输出。
    verdicts = {
        EXIT_PASS: ("结论：可以开工（exit 0，%s）。"
                    % ("有 %d 条告警 —— 不阻塞，但要逐条记进本轮回复" % len(warnings) if warnings else "无告警")),
        EXIT_BLOCKED: "结论：禁止开工（exit 1）—— 先修结构性问题。",
        EXIT_DECISION: "结论：需先决策（exit 2）—— 逐条「做掉 / 豁免（理由+复查日期）/ 降级」后再开工。",
    }
    print(verdicts[code])
    return code


def _glob_match(name, pat):
    """极简 glob：只支持 * 与 ?。"""
    rx = "^" + re.escape(pat).replace(r"\*", ".*").replace(r"\?", ".") + "$"
    return re.match(rx, name, re.IGNORECASE) is not None


if __name__ == "__main__":
    sys.exit(main())
