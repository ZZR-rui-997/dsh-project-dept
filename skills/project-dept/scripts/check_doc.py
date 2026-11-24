#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_doc.py — 文档机械断言器（通用版）

只查「编号与引用是否自洽」，不查内容对不对。内容正确性归独立复核与基准核对。

八条断言
    A1 图编号连续
    A2 表编号连续
    A3 公式编号连续
    A4 图注↔正文双向（每个图注都被引用，每个正文引用都有图注）
    A5 表注↔正文双向
    A6 参考文献双向（编号制 [n] 与作者-年份制两制都支持）
    A7 章节编号连续（只认 Word 标题样式，绝不用表格文字）
    A8 术语写法（禁用词表来自项目配置，绝不写死在脚本里）

退出码
    0 = 已执行的断言全部通过（未执行的断言会在文案里列明）
    1 = 有 FAIL
    2 = 检查未执行 —— 文件不存在 / 缺 python-docx / 缺配置 / 所有断言都不适用（**不是通过**）

用法
    python check_doc.py <docx> [--chapter 2] [--config dept.config.json] [--json]

设计约束
    - 只读；不改文档。
    - 缺依赖返回 2 而不是 0：把「没跑」当成「通过」是最坏的结果。
    - 表格文字与正文段落分两条流处理：表格里的 `1.6 mm` 不是小节号。
"""
import argparse
import json
import os
import re
import sys

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_NOT_RUN = 2

CN_NUM = "一二三四五六七八九十"


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


# ----------------------------------------------------------------- 配置

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


def load_banned_terms(config_path):
    """从配置读禁用词表。

    配置**不存在或解不开**时不再静默返回 []（V1/N2 + V2/N6 实测：坏 JSON 会让
    A8 静默失效却仍 PASS）。这里抛 ValueError，由 run_checks 转成 exit 2。
    字段缺失/为空是合法的"没有禁用词"，返回 []。
    """
    if not config_path:
        raise ValueError("没有传入 dept.config.json 路径")
    if not os.path.isfile(config_path):
        raise ValueError("dept.config.json 不存在：%s" % config_path)
    with open(config_path, "rb") as fh:
        raw = fh.read()
    cfg = None
    last = None
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            cfg = json.loads(raw.decode(enc))
            break
        except UnicodeDecodeError as exc:
            last = exc
            continue
        except json.JSONDecodeError as exc:
            raise ValueError("dept.config.json 不是合法 JSON（%s）" % exc)
    if cfg is None:
        raise ValueError("dept.config.json 编码无法识别（%s）" % last)
    if not isinstance(cfg, dict):
        raise ValueError("dept.config.json 顶层必须是 JSON 对象（现在是 %s）" % type(cfg).__name__)
    raw_terms = cfg.get("banned_terms")
    if isinstance(raw_terms, str):
        # W2/P2-d：写成字符串时 for 会逐字拆开，每个汉字都变成"禁用词"⇒ 全文假 FAIL。
        raise ValueError("banned_terms 必须是数组（现在是字符串，会被逐字符当成禁用词）")
    terms = []
    for item in raw_terms or []:
        if isinstance(item, str):
            terms.append({"pattern": item, "reason": "禁用写法", "flags": ""})
        elif isinstance(item, dict) and item.get("pattern"):
            terms.append({
                "pattern": item["pattern"],
                "reason": item.get("reason", "禁用写法"),
                "flags": item.get("flags", ""),
            })
    return terms


# ----------------------------------------------------------------- 读取

def load_docx(path):
    """返回 (body, table_text)。

    body: [(text, style_name)] 段落文本 + 段落样式名
    table_text: 表格单元格文字拼成的长字符串（单独存放，避免误判小节号）
    """
    from docx import Document  # 延迟导入，缺库时给出明确的「未执行」

    doc = Document(path)
    body = []
    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if not text:
            continue
        style = ""
        try:
            style = (p.style.name or "") if p.style is not None else ""
        except Exception:  # noqa: BLE001
            style = ""
        body.append((text, style, "p"))

    table_text_parts = []
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    t = (p.text or "").strip()
                    if t:
                        table_text_parts.append(t)
                        body.append((t, "", "table"))
    return body, "\n".join(table_text_parts)


# ----------------------------------------------------------------- 辅助

def heading_texts(body):
    """只认 Word 标题样式，绝不用正文或表格文字判章节。"""
    out = []
    for text, style, kind in body:
        if kind != "p":
            continue
        s = (style or "").lower()
        if s.startswith("heading") or s.startswith("标题") or re.match(r"^(title|subtitle)$", s):
            out.append(text)
    return out


def head_number(text):
    """抓节号：`2.3` / `2.3.1`（点分），也抓裸章号 `2 绪论`（行首单数字+空格）。"""
    m = re.match(r"^\s*(\d+(?:\.\d+)+)\s*", text)
    if m:
        return m.group(1)
    # 裸章号：行首一个 1-2 位数字后跟空格/全角空格（如 "3 结论"），防止 "3 结论"→"5 结论" 跳号漏报。
    # 只认标题文本（调用方只喂标题样式行），且不吞多级点分号。
    m = re.match(r"^\s*(\d{1,2})(?:[\s\u3000]+|$)", text)
    if m:
        return m.group(1)
    return None


def dedup_sorted(nums):
    return sorted(set(nums))


def contiguity(nums):
    """返回缺失的编号（从最小值到最大值，两端取实际出现的最小/最大）。

    从最小值起算而不是从 1 起算：单章文档里只出现 2.x 是正常的，
    从 1 起算会把「这是一章」误报成跳号。
    """
    if not nums:
        return []
    have = set(nums)
    return [i for i in range(min(have), max(have) + 1) if i not in have]


# ----------------------------------------------------------------- 断言

def _pairs(alltext, ch_pat, global_pat):
    """抓编号，返回 (制式, [(ch, n), ...])。

    制式：
      "chapter" —— 文档用「章-号」（图 2-3）；ch 为字符串章号
      "global"  —— 文档用全局编号（图 1、图 2 …）；ch 为 None
      "mixed"   —— 同一文档两种制式并存（本身就是要报的缺陷）
      None      —— 一种都没匹配到

    为什么必须区分（V1/V2 验证轮实证）：旧实现只写「章-号」一种正则，
    全局编号制的文档会被判成「没有找到任何编号」→ 未执行 → 仍然 PASS，
    即"支持一种输入方言、把另一种当没事"的假 PASS（包内 code.md 明确列为最坏形态）。
    """
    ch_hits = [(m.group("ch"), int(m.group("n")))
               for m in re.finditer(ch_pat, alltext) if m.group("n")]
    if ch_hits:
        glob_hits = [(None, int(m.group("n")))
                     for m in re.finditer(global_pat, alltext) if m.group("n")]
        # 全局正则可能把「图 2-3」的前半截也算进来，先剔除与章-号命中重叠的那些
        ch_texts = set()
        for m in re.finditer(ch_pat, alltext):
            ch_texts.add((m.start(), m.end()))
        glob_extra = []
        for m in re.finditer(global_pat, alltext):
            if any(s <= m.start() < e for s, e in ch_texts):
                continue
            glob_extra.append((None, int(m.group("n"))))
        kind = "mixed" if glob_extra else "chapter"
        return kind, ch_hits
    glob_hits = [(None, int(m.group("n")))
                 for m in re.finditer(global_pat, alltext) if m.group("n")]
    if glob_hits:
        return "global", glob_hits
    return None, []


def _report_series(label, kind, groups, chapter):
    """按制式报连续性。groups: {章号 or None: set(n)}"""
    problems = []
    if chapter is not None:
        key = str(chapter)
        if key not in groups:
            return None, "%s：第 %d 章没有找到%s编号（本断言未执行）" % (label, chapter, label)
        nums = sorted(groups[key])
        miss = contiguity(nums)
        if miss:
            return False, "%s 编号不连续（第 %d 章）：出现 %d..%d 中的 %d 个，缺 %s" % (
                label, chapter, min(nums), max(nums), len(nums), miss)
        return True, "%s 编号连续（第 %d 章 %d..%d）" % (label, chapter, min(nums), max(nums))
    for key in sorted(groups, key=lambda k: (k is None, k)):
        nums = sorted(groups[key])
        miss = contiguity(nums)
        if miss:
            where = "全局编号" if key is None else "第 %s 章" % key
            problems.append("%s %s 编号不连续：出现 %d..%d 中的 %d 个，缺 %s" % (
                where, label, min(nums), max(nums), len(nums), miss))
    if problems:
        return False, "%s 编号不连续：%s" % (label, "；".join(problems))
    if kind == "global":
        nums = sorted(groups[None])
        return True, "%s 编号连续（全局编号制 %d..%d）" % (label, min(nums), max(nums))
    return True, "%s 逐章连续（%d 章：%s）" % (label, len(groups), "、".join(sorted(groups)))


def check_series(body, table_text, label, ch_pat, global_pat, chapter=None):
    """A1/A2/A3 通用：抓编号，按制式报不连续（章-号逐章核 / 全局编号核）。"""
    alltext = "\n".join(t for t, _, _ in body)
    kind, pairs = _pairs(alltext, ch_pat, global_pat) if global_pat else (None, [])
    if not global_pat:
        # A3 只认「章-号」形式（年份括号无法与公式号区分），单独处理
        pairs = [(m.group("ch"), int(m.group("n")))
                 for m in re.finditer(ch_pat, alltext) if m.group("n")]
        kind = "chapter" if pairs else None
    if not pairs:
        return None, "%s：没有找到任何编号" % label
    if kind == "mixed":
        return False, "%s：同一文档混用「章-号」与全局编号两种制式 —— 编号不可机械核对，先统一制式" % label
    groups = {}
    for ch, n in pairs:
        key = str(ch) if ch is not None else (str(chapter) if chapter is not None else None)
        groups.setdefault(key, set()).add(n)
    return _report_series(label, kind, groups, chapter)


CAPTION_MAX_LEN = 80          # 无分隔符：图2-1示意图 这种写法，整段必须很短才算图注
CAPTION_MAX_LEN_SEP = 300     # 有分隔符：允许长图注（(a)(b) 子图说明），但仍设上限
# 编号后面**紧接着**这些词 ⇒ 这一段是行文，不是图注。
# 为什么只判开头、不判全段（第一版判全段，把真实图注全毙了）：
#   真实图注里常出现「对应」「说明」等词（如「R1 与 R5 对应的正态曲线」），
#   只有**紧接编号**的「所示的…」「表明了…」才必定是句子。Y2 反例：「图 2-1 所示的裂隙开度场是…」。
# 只保留「几乎不可能出现在图注开头」的固定词。「所示 / 所示为 / 中给出的分布」这类是**名词短语式图注**
# （"图 2-1 所示的裂隙开度场"），当标志会误杀真图注（第七轮 P1 实测 exit 1）；「动词 + 了」的形态
# 交给下面的正则判，不再逐一穷举（穷举必然"补一个漏一个"：收了「展示了」就漏「显示了」）。
CAPTION_PROSE_PREFIXES = ("可以看出", "可知", "因此")
CAPTION_PROSE_VERB_RE = re.compile(r"^(?:中)?[\u4e00-\u9fa5]{1,8}了")
# 图注（中文 GB 体例）不以句末标点结尾；以 。！？ 结尾的段落是行文。
CAPTION_SENTENCE_ENDS = ("。", "！", "？")


def _caption_match(text, cap_re):
    """图注 = 段落开头就是「图/表 + 编号」，且不像正文。

    两条判据（都被验证轮打回过，别再改回去）：
    1. **不像正文**：两种情况判为行文而不是图注——
       (i) **紧接编号**出现动词性标志：**「动词 + 了」形态**（展示了 / 显示了 / 给出了 / 描绘了 /
           记录了 / 中给出了 …，用正则 `^(?:中)?[\u4e00-\u9fa5]{1,8}了` 判，不穷举），以及
           可以看出 / 可知 / 因此。**「所示 / 所示为 / 中给出的分布」不算标志**——它们是名词短语式
           图注（"图 2-1 所示的裂隙开度场"），第七轮实测把它们当标志会误杀真图注；行文里的
           "图 2-1 所示的…" 由 (ii) 句末标点规则兜住；
       (ii) 整段以句末标点（。！？）结尾（中文图注体例不以句号收尾）。
       实测依据：86 字正文「图 2-1 所示的…」、98 字「图 2-1 展示了…」都曾被当成图注 ⇒
       A4 报「双向一致」exit 0；而「图 2-1 对应的开度分布」是真图注，不能误杀（所以
       "对应/显示/给出" 这类**不带「了」**的词不进标志表）。
    2. **长度**：编号后有分隔符（空白/全角空格/制表符/冒号）⇒ 放宽到 CAPTION_MAX_LEN_SEP
       （真实图注常带 (a)(b) 子图说明，很长）；无分隔符（图2-1示意图）⇒ 限 CAPTION_MAX_LEN。
       注意分隔符必须是**真的**空格/制表符/全角空格/冒号，不能写字面 `\t`（Y1 实测：
       写字的转义串导致制表符分隔的长图注被判 FAIL）。
    """
    m = re.match(cap_re, text)
    if not m:
        return None
    rest = text[m.end():]
    tail = rest[:1]
    has_sep = tail == "" or tail in (" ", "\t", "\u3000", ":", "：")
    bare = rest.strip()
    if bare.startswith(CAPTION_PROSE_PREFIXES) or CAPTION_PROSE_VERB_RE.match(bare):
        return None
    if text.rstrip().endswith(CAPTION_SENTENCE_ENDS):
        return None
    if has_sep:
        return m if len(text) <= CAPTION_MAX_LEN_SEP else None
    return m if len(text) <= CAPTION_MAX_LEN else None


def _pair_label(label, ch, n):
    """给 (章号, 编号) 二元组一个人话标签；章号为 None 表示全局编号制。"""
    if ch is None or str(ch) == "None":
        return "%s %s" % (label, n)
    return "%s %s-%s" % (label, ch, n)


def check_captions(body, label, cap_re, ref_re, chapter=None):
    """A4/A5 通用：图注↔正文双向，**按章分组比较**（不许跨章并集）。

    跨章并集是上一版最严重的假 PASS：第 2 章缺图 2-2、第 3 章有 3-2，
    并集 1..3 看来连续，A1 报 PASS；A4 也用同一个 n 集合，缺号被两章互相抵消。
    """
    caps = {}   # key -> set(n)
    refs = {}
    for text, style, kind in body:
        m = _caption_match(text, cap_re)
        if m:
            ch = m.groupdict().get("ch")
            # 图注没有章号 ⇒ 全局编号制，key 记 None；不许硬塞当前章，否则文案会伪造「第 2 章 图 7」
            key = str(ch) if ch is not None else None
            caps.setdefault(key, set()).add(int(m.group("n")))
    for text, style, kind in body:
        if _caption_match(text, cap_re):
            continue  # 跳过图注本身
        for m in re.finditer(ref_re, text):
            g = m.groupdict()
            try:
                n = int(g.get("n"))
            except (TypeError, ValueError):
                continue
            ch = g.get("ch")
            # 省略章号的引用（「图 9」）不硬塞给当前章：那样会把「图 9」报成「图 3-9」（第九轮 U1 抓到）。
            # 这类引用按"任一章有同号图注即算被满足"处理（见下面的 missing 判定）。
            key = str(ch) if ch is not None else None
            refs.setdefault(key, set()).add(n)

    # 全篇一条图注都没有、而正文引用了图 ⇒ 悬空引用，直接 FAIL。
    # 这条必须在 --chapter 分支之前判：否则 `--chapter 3` 时（引的是第 2 章的图、
    # 全篇又没有任何图注）会被记成"未执行"放过（Z2 实测 exit 0）。
    if not caps:
        if any(refs.values()):
            return False, "正文引用了%s，但文档里一条%s注都没有" % (label, label)
        return None, "%s：没有%s注" % (label, label)

    # 跨章比较必须按 (章号, 编号) 二元组：只比数字会把「正文引 图 9-9」与「图 2-9 有图注」
    # 当成同一编号 —— 第八轮 Q1/Q2 实测：`--chapter 3` 引 图 9-9、全篇有 图 2-9 ⇒ 旧实现 exit 0 假 PASS。
    caps_pairs = {(k, n) for k, s in caps.items() for n in s}
    refs_pairs = {(k, n) for k, s in refs.items() for n in s}
    caps_ns = {n for (_k, n) in caps_pairs}
    if chapter is not None:
        keep = str(chapter)
        # 带章号的引用按 (章号, 编号) 精确比；省略章号的引用（key is None）只要任一章有同号图注就算满足。
        missing = sorted({(k, n) for (k, n) in refs_pairs
                          if (k, n) not in caps_pairs and not (k is None and n in caps_ns)},
                         key=lambda p: (str(p[0]), p[1]))
        if missing:
            return False, "正文引用了%s，但全篇没有对应%s注：%s" % (
                label, label,
                "、".join(_pair_label(label, k, n) for k, n in missing))
        caps = {k: v for k, v in caps.items() if k == keep}
        # 章内引用：带章号的同章引用 + 省略章号的引用都算
        # 裸编号（key=None）只有在**本章确实有这个图号**时才能算作本章的引用；
        # 指向别章的裸编号不并入本章集合（否则会在 A4 里被报成「第 2 章 图 7」，而它其实是第 3 章的图；
        # 第十一轮 A1/T1 实测抓到）。真正无人满足的裸编号已由上面的 missing 判定按「图 7」报过。
        merged = set(refs.get(keep, set()))
        merged |= {n for n in refs.get(None, set()) if n in caps.get(keep, set())}
        refs = {keep: merged}
        if not caps:
            # 走到这里，本章一条图注都没有，而正文引用全部**在别章有图注**（否则上面的 missing 已判 FAIL）。
            # 那不是悬空引用，也不属本章核对范围 ⇒ 如实记未执行并说明，不许谎报"没有任何引用"
            # （第八轮 Q1 抓到的文案不实）。此前的「本章引本章号⇒FAIL」分支实际不可达（第九轮 U1 证明），已删。
            other = sorted({(k, n) for (k, n) in refs_pairs if k != keep},
                           key=lambda p: (str(p[0]), p[1]))
            if other:
                return None, ("%s：第 %d 章没有%s注；正文引用的%s属于其他章节，不在本章核对范围（本断言未执行）"
                              % (label, chapter, label,
                                 "、".join(_pair_label(label, k, n) for k, n in other)))
            return None, "%s：第 %d 章既没有%s注也没有引用（本断言未执行）" % (label, chapter, label)

    problems = []
    if not caps:            # 走到这里只可能是 --chapter 过滤后该章没有图注（全篇为空已在上面处理）
        return None, "%s：第 %s 章没有%s注（本断言未执行）" % (label, chapter, label)
    if chapter is None and any(k is None for k in caps) and any(k is not None for k in caps):
        return False, "%s：图注混用「章-号」与全局编号两种制式 —— 先统一制式再核" % label
    for key in sorted(caps, key=lambda k: (k is None, k)):
        where = "全局编号" if key is None else "第 %s 章" % key
        # 章号省略的引用（「图 9」）可能指向任一章：只有当初**本章有这个图号**时才算本章的引用；
        # 指向别章的裸编号不在这里报，也不许在文案里给它安上本章章号（第十一轮 A1/T1 抓到
        # 「图 7」被报成「第 2 章 图 7」——而 图 7 实际是第 3 章的图）。未能被任何章满足的裸编号
        # 已在上面 missing 判定里按「图 7」报过。
        ref_n = set(refs.get(key, set()))
        if key is not None:
            ref_n |= {n for n in refs.get(None, set()) if n in caps[key]}
        uncited = sorted(caps[key] - ref_n)
        orphans = sorted(ref_n - caps[key])
        if uncited:
            problems.append("%s %s 有图注，但正文没有引用它" % (where, uncited))
        if orphans:
            problems.append("正文引用了 %s %s，但文档里找不到对应的图注" % (where, orphans))
    if problems:
        return False, "；".join(problems)
    total = sum(len(v) for v in caps.values())
    scope = "（第 %d 章）" % chapter if chapter is not None else ""
    return True, "%s 双向一致%s（%d 个，全部被引用且有注）" % (label, scope, total)


def check_references(body, table_text):
    """A6：参考文献双向，两制都支持。

    只用正文段落（kind == "p"）：表格里的符号说明不是文献条目。
    """
    para_texts = [t for t, _, kind in body if kind == "p"]
    lines = "\n".join(para_texts).splitlines()

    # 找参考文献小节：标题可能带前缀（「第二章参考文献」「第 3 章 参考文献」）或英文
    start = None
    for i, line in enumerate(lines):
        if re.search(r"(参\s*考\s*文\s*献|References)\s*[:：]?\s*$", line, re.IGNORECASE) \
                and len(line) <= 30:
            start = i
            break
    if start is None:
        return None, ("参考文献：文档里没有识别到参考文献小节"
                      "（接受的写法：「参考文献」/「参 考 文 献」/「References」，可带冒号）")

    # W2/P2-c：以前把「参考文献」之后的全文都当条目，于是「致谢」「附录」里的句子
    # 被当成文献条目 ⇒ 报「清单有 N 条正文从未引用」的假 FAIL。遇到下一个大节就停。
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^\s*(致\s*谢|附\s*录|Acknowledg|Appendix|作者简介|攻读)", lines[j], re.IGNORECASE):
            end = j
            break
    entry_lines = [l.strip() for l in lines[start + 1:end] if l.strip()]
    entries = [l for l in entry_lines if re.match(r"^(\[\d+\]|\d+[\.\)]|[A-Z\u4e00-\u9fff])", l)]
    if not entries:
        return None, "参考文献：小节内没有识别到条目"

    # 编号制：清单里是 [1] 形式
    numbered = [e for e in entries if re.match(r"^\[\d+\]", e)]
    if numbered:
        listed = set()
        for e in numbered:
            m = re.match(r"^\[(\d+)\]", e)
            if m:
                listed.add(int(m.group(1)))
        cited = set()
        body_without_refs = "\n".join(
            l for l in lines[:start] if l.strip())
        for m in re.finditer(r"\[(\d+)\]", body_without_refs):
            cited.add(int(m.group(1)))
        missing = sorted(listed - cited)
        extra = sorted(cited - listed)
        problems = []
        if missing:
            problems.append("清单有 %d 条正文从未引用（编号 %s）" % (len(missing), missing))
        if extra:
            problems.append("正文引用了 %d 个清单里没有的编号（%s）" % (len(extra), extra))
        if problems:
            return False, "参考文献%s" % ("；".join(problems))
        return True, "参考文献双向一致（编号制，%d 条）" % len(listed)

    # 作者-年份制：只取第一个词当姓，登记全部作者别名
    names = {}
    for e in entries:
        tok = e.split(",")[0].split(".")[0].strip()
        if not tok:
            continue
        first = tok.split()[0].strip("*· ")
        if not first:
            continue
        # 处理 "Tse 与 Cruden" / "A and B" / "A & B" 这类多作者
        alias_parts = re.split(r"\s*(?:与|和|&|and|,)\s*", tok)
        aliases = set()
        for part in alias_parts:
            part = part.strip().strip(".").strip()
            if not part:
                continue
            aliases.add(part.split()[0].strip("*· "))
        aliases.add(first)
        for a in aliases:
            if len(a) > 1:
                names.setdefault(a, os.path.basename(str(e))[:60])

    if not names:
        return None, "参考文献：无法从条目里解析出作者姓名"

    body_without_refs = "\n".join(l for l in lines[:start] if l.strip())
    uncited = [n for n in names if n not in body_without_refs]
    problems = []
    if uncited:
        problems.append("清单有 %d 条正文从未引用（%s）" % (len(uncited), uncited[:8]))
    if problems:
        return False, "参考文献单向核对（清单 → 正文）：%s" % "；".join(problems)
    # W2/P1-b：作者-年份制只机械核了"清单里的每条是否在正文出现"；
    # 反方向（正文引用是否都在清单里）无法可靠识别（"王某 (2025)" 之类形式太多），
    # 所以这里只能报单向通过，不能说"双向一致"。
    return True, ("参考文献清单条目均被正文引用（作者-年份制，%d 条）；"
                  "反方向（正文是否引用了清单外文献）未机械核对" % len(names))


def check_sections(body):
    """A7：章节编号连续，只认标题样式。"""
    heads = heading_texts(body)
    if not heads:
        return None, "章节：没有文字使用 Word 标题样式，无法判断（不用正文硬猜）"
    numbered = [(h, head_number(h)) for h in heads]
    numbered = [(h, n) for h, n in numbered if n]
    if not numbered:
        return None, "章节：标题样式里没有带数字编号的标题"

    # 只看二级（x.y）连续性与一级（x）连续性
    level1 = dedup_sorted(int(n.split(".")[0]) for _, n in numbered if n.count(".") >= 0)
    missing1 = contiguity(level1)
    problems = []
    if missing1:
        problems.append("章号跳号：%s" % missing1)

    by_chapter = {}
    for _, n in numbered:
        parts = n.split(".")
        if len(parts) == 2:
            by_chapter.setdefault(int(parts[0]), []).append(int(parts[1]))
    for ch, subs in sorted(by_chapter.items()):
        miss = contiguity(dedup_sorted(subs))
        if miss:
            problems.append("%d.x 小节号跳号：%s" % (ch, miss))
    if problems:
        return False, "章节编号不连续：%s" % "；".join(problems)
    return True, "章节编号连续（%d 个带号标题，来源标题样式）" % len(numbered)


def check_terms(body, table_text, banned):
    """A8：术语写法。禁用词表来自配置。"""
    if not banned:
        return None, "术语：项目配置里没有 banned_terms，本断言未执行"
    hits = []
    for term in banned:
        flags = 0
        f = term.get("flags") or ""
        if "i" in f:
            flags |= re.IGNORECASE
        try:
            rx = re.compile(term["pattern"], flags)
        except re.error:
            hits.append("配置里的正则有误：%r" % term["pattern"])
            continue
        for text, style, kind in body:
            for m in rx.finditer(text):
                hits.append("%r（应为 %s）" % (m.group(0), term.get("reason", "")))
    if hits:
        uniq = sorted(set(hits))
        return False, "术语：出现 %d 处禁用写法 —— %s" % (len(uniq), "；".join(uniq[:6]))
    return True, "术语：无禁用写法（检查了 %d 条规则）" % len(banned)


# ----------------------------------------------------------------- 主流程

def run_checks(docx_path, config_path, chapter=None, quiet=False):
    try:
        body, table_text = load_docx(docx_path)
    except ImportError:
        print("[x] 缺 python-docx —— 检查未执行（exit 2，不是通过）")
        return EXIT_NOT_RUN, []
    except Exception as exc:  # noqa: BLE001
        print("[x] 读不了文档：%s —— 检查未执行（exit 2）" % exc)
        return EXIT_NOT_RUN, []

    if not body:
        print("[x] 文档里没有可读文字 —— 检查未执行（exit 2）")
        return EXIT_NOT_RUN, []

    try:
        banned = load_banned_terms(config_path)
    except ValueError as exc:
        print("[x] 配置读不了：%s —— 检查未执行（exit 2，不是通过）" % exc)
        return EXIT_NOT_RUN, []
    results = []

    # 图注形如「图 2-3 xxx」「图 3 xxx」「图2.3 xxx」
    # W1/N1：编号前后只允许**行内空白**（空格/制表/全角空格），不许跨行。
    # 以前用 `\s*` 会把上一段末尾的「图」和下一段开头的「3」拼成一个编号 ⇒ 合法文档假报"混用"。
    SP = r"[ \t\u3000]*"
    fig_cap = r"^" + SP + r"图" + SP + r"(?:(?P<ch>\d+)" + SP + r"[-–.]" + SP + r")?(?P<n>\d+)"
    tab_cap = r"^" + SP + r"表" + SP + r"(?:(?P<ch>\d+)" + SP + r"[-–.]" + SP + r")?(?P<n>\d+)"
    fig_ref = r"图" + SP + r"(?:(?P<ch>\d+)" + SP + r"[-–.]" + SP + r")?(?P<n>\d+)"
    tab_ref = r"表" + SP + r"(?:(?P<ch>\d+)" + SP + r"[-–.]" + SP + r")?(?P<n>\d+)"
    # A1/A2 两套制式各自的正则：章-号制 与 全局编号制（不许只支持一种）
    fig_ch = r"图" + SP + r"(?P<ch>\d+)" + SP + r"[-–.]" + SP + r"(?P<n>\d+)"
    tab_ch = r"表" + SP + r"(?P<ch>\d+)" + SP + r"[-–.]" + SP + r"(?P<n>\d+)"
    fig_glob = r"图" + SP + r"(?P<n>\d+)(?!" + SP + r"[-–.]" + SP + r"\d)"
    tab_glob = r"表" + SP + r"(?P<n>\d+)(?!" + SP + r"[-–.]" + SP + r"\d)"

    # A3 的公式编号：有章号时只认「(2-3)」形式（含全角括号），避免把年份 (2026) 当公式号
    if chapter is not None:
        formula_pat = (r"[（(]" + SP + r"(?P<ch>\d+)" + SP + r"[-–.]" + SP
                       + r"(?P<n>\d+)" + SP + r"[）)]")
    else:
        # 无 --chapter 时不猜公式号：年份括号 (2026)、数值括号 (3) 都会被当编号，
        # 产生成百条假缺号（R1-P10 实测：真实文档误报缺 600 项）。
        # 未给章号 ⇒ A3 拒绝执行（返回 None，记为「未执行」而不是误报）。
        formula_pat = None

    # A1/A2/A3
    for code, label, ch_pat, glob_pat in (
        ("A1", "图", fig_ch, fig_glob),
        ("A2", "表", tab_ch, tab_glob),
        ("A3", "公式", formula_pat, None),
    ):
        if ch_pat is None:
            results.append((code, None, "%s：未给 --chapter，公式号形如 (2026) 的括号无法与年份区分，本断言未执行（给出 --chapter N 后只认 (N-m) 形式）" % code))
            continue
        ok, msg = check_series(body, table_text, label, ch_pat, glob_pat, chapter)
        results.append((code, ok, msg))

    # A1/A2 的兜底闸门（V1/N2 + V2/N2）：文档里明明有「图 3」「表 2」这类编号，
    # 但两条断言都没匹配到 ⇒ 说明编号制不被支持，**必须判 FAIL 而不是未执行**。
    # 否则"支持一种方言、另一种当没事"就会变成 exit 0 假 PASS。
    alltext = "\n".join(t for t, _, _ in body)
    # W1/N2：给了 --chapter 时，本章没图是正常的（图在别的章），不能套这个兜底，
    # 否则「只查第 2 章」会把合法的第 2 章判 FAIL。
    if chapter is None:
        for code, label, marker in (("A1", "图", r"图[ \t\u3000]*[（(\[【]?[ \t\u3000]*\d"),
                                    ("A2", "表", r"表[ \t\u3000]*[（(\[【]?[ \t\u3000]*\d")):
            got = [r for r in results if r[0] == code]
            if got and got[0][1] is None and re.search(marker, alltext):
                results = [(c,
                            (False if c == code else o),
                            ("%s：正文里出现了%s编号，但一条都没被识别 —— 编号制式不在支持范围，"
                             "按失败处理（以前会记成「未执行」而整体 PASS）" % (code, label))
                            if c == code else m)
                           for c, o, m in results]

    # A4/A5
    ok, msg = check_captions(body, "图", fig_cap, fig_ref, chapter)
    results.append(("A4", ok, msg))
    ok, msg = check_captions(body, "表", tab_cap, tab_ref, chapter)
    results.append(("A5", ok, msg))

    # A6
    ok, msg = check_references(body, table_text)
    results.append(("A6", ok, msg))

    # A7
    ok, msg = check_sections(body)
    results.append(("A7", ok, msg))

    # A8
    ok, msg = check_terms(body, table_text, banned)
    results.append(("A8", ok, msg))

    # 未执行（None）不算通过：executed = 有明确 True/False 结果的断言。
    # 全部未执行 ⇒ exit 2（检查未运行）；部分未执行 ⇒ exit 0/1 但文案明说哪些没跑。
    any_fail = any(r[1] is False for r in results)
    executed = [r for r in results if r[1] is not None]
    not_run = [r[0] for r in results if r[1] is None]
    structural = [r for r in executed if r[0] in ("A1", "A2", "A3", "A4", "A5", "A6", "A7")]
    # 已经确定的 FAIL 优先于「未执行」：文档结构太少时确实没法判，但若已有断言明确失败，
    # 就该报 FAIL（exit 1）而不是 NOT RUN（exit 2）——两者都拦交付，但 FAIL 信息更多。
    if len(structural) < 3 and not any_fail:
        if not quiet:
            for code, ok, msg in results:
                tag = "ok" if ok else ("x" if ok is False else "-")
                print("  [%s] %s" % (tag, msg if msg.startswith(code) else "%s %s" % (code, msg)))
            print("-" * 44)
            print("结论：NOT RUN（exit 2）—— 结构性断言（A1-A7）只执行了 %d 条（<3）：文档几乎没有编号/引用结构，" % len(structural))
            print("      机械断言没有真正起作用。未执行不是通过；若文档本应含图表/公式/文献，先修文档来源。")
        return EXIT_NOT_RUN, results
    if not quiet:
        for code, ok, msg in results:
            tag = "ok" if ok else ("x" if ok is False else "-")
            print("  [%s] %s" % (tag, msg if msg.startswith(code) else "%s %s" % (code, msg)))
        print("-" * 44)
        if any_fail:
            print("结论：FAIL（exit 1）—— 修完再交付。断言只查编号/引用是否自洽，不查内容对不对。")
        else:
            ran = "、".join(r[0] for r in executed)
            tail = ("；未执行：%s" % "、".join(not_run)) if not_run else ""
            print("结论：PASS（exit 0）—— 已执行 %d 条（%s）通过%s。**这不证明科学正确**，内容仍归独立复核。" % (len(executed), ran, tail))
    return (EXIT_FAIL if any_fail else EXIT_PASS), results


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mechanical assertions for a document artefact")
    ap.add_argument("docx", help="path to the .docx")
    ap.add_argument("--chapter", type=int, default=None, help="limit numbering to this chapter number")
    ap.add_argument("--config", default=None, help="path to dept.config.json")
    ap.add_argument("--root", default=None,
                    help="where to start looking for dept.config.json (default: cwd)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.docx):
        if args.json:
            print(json.dumps({"error": "file not found", "path": args.docx}, ensure_ascii=False))
        else:
            print("[x] 文件不存在：%s —— 检查未执行（exit 2）" % args.docx)
        return EXIT_NOT_RUN

    cfg = find_config(args.root or os.getcwd(), args.config)
    if cfg is None:
        # R1-P9 的漏口（V1/N2 + V2/N6 实测）：只拦"没给 --config"是不够的——
        # 显式给了不存在的路径/坏 JSON 时曾照样跑完并报 PASS，而 A8 静默失效。
        # 现在：配置拿不到就 exit 2，文案分清三种原因。
        if args.config:
            why = "给定的 --config 路径不存在：%s" % os.path.abspath(args.config)
        else:
            why = "在 %s 及其上级目录都没找到 dept.config.json（也未给 --config）" % os.path.abspath(
                args.root or os.getcwd())
        if args.json:
            print(json.dumps({"error": "config not available", "detail": why,
                              "hint": "pass --config <path> or put dept.config.json in the project root"},
                             ensure_ascii=False))
        else:
            print("[x] %s" % why)
            print("    —— 检查未执行（exit 2，不是通过）。A8 禁用词依赖它（本脚本不做项目身份校验；身份核对只在 dept_gate.py 的 project_name 告警里）。")
        return EXIT_NOT_RUN
    # X1-1/② 链2：与 dept_gate 同等的祖先配置判定。子目录有自己的台账却没有配置文件时，
    # 从祖先拿到的 banned_terms 是**别的项目**的词表 ⇒ A8 拿错词典报假 FAIL。
    if not args.config:
        start = os.path.abspath(args.root or os.getcwd())
        if os.path.abspath(os.path.dirname(cfg)) != start:
            try:
                with open(cfg, encoding="utf-8-sig") as _fh:
                    _raw = json.load(_fh)
                _ledger = _raw.get("ledger_dir", "_team") if isinstance(_raw, dict) else "_team"
            except Exception:  # noqa: BLE001 - 配置坏了下面 load_banned_terms 会报
                _ledger = "_team"
            if os.path.isdir(os.path.join(start, _ledger)):
                msg = ("本目录（%s）有自己的 %s\\，但 dept.config.json 是在上层 %s 找到的\n"
                       "    —— 禁用词表会用错项目的配置。请在本地建 dept.config.json，"
                       "或显式传 --config 指明用哪份。" % (start, _ledger, os.path.dirname(cfg)))
                if args.json:
                    print(json.dumps({"error": "ancestor config", "detail": msg}, ensure_ascii=False))
                else:
                    print("[x] %s" % msg)
                    print("    —— 检查未执行（exit 2，不是通过）。")
                return EXIT_NOT_RUN
    if not args.json:
        print("=" * 44)
        print("  DOC CHECK  —  %s" % os.path.basename(args.docx))
        print("  config: %s" % cfg)
        print("=" * 44)

    code, results = run_checks(args.docx, cfg, args.chapter, quiet=args.json)
    if args.json:
        print(json.dumps({
            "file": args.docx,
            "exit": code,
            "checks": [{"id": c, "pass": ok, "message": m} for c, ok, m in results],
        }, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
