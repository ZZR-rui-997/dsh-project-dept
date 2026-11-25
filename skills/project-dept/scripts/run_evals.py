#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""project-dept evals runner — schema check, deterministic keyword grading, A/B compare.

The eval cases in ``evals/evals.json`` are frozen judge criteria (prompt + expected_output)
plus machine-checkable assertions.  This runner never calls a model: it checks the assertions
file itself, prints a ready-to-paste grading brief for a judge sub-agent, and scores an answer
deterministically so the same answer always gets the same verdict.

Modes
-----
static (default)
    Validate ``evals/evals.json`` against the v2 schema (fields present, ids unique,
    assertions non-empty and not tautological, must_include literally derivable from
    expected_output, must_exclude not present in expected_output, axes real, steps real,
    budgets positive).  On success print, for every case, a complete grading brief that can
    be pasted verbatim to a judge sub-agent, plus the case's token budget.

grade --case <id> --answer <path>
    DEPRECATED as an acceptance criterion.  Deterministic keyword grading: every
    must_include must appear verbatim; any must_exclude appearing is an immediate FAIL.
    Reason: verbatim matching rejects answers that state the right point in different
    words; measured on 12 real answers it produced 12/12 false FAILs (backlog P-15-8).
    Use ``judge`` + ``tally`` instead.  The mode still prints its per-assertion
    ``[ok]``/``[x]`` report and last line ``CASE <id> PASS`` or ``CASE <id> FAIL`` with
    unchanged exit codes.

compare --with <dir> --without <dir>
    Run grade over the answer files of two directories and print an A/B table (per-case
    verdict, total passes, naive difference) with an explicit small-sample warning.

judge --answers <dir> --out <dir> [--seed 7] [--case <id>]
    Blind-judge harness.  Scan ``<case>-<arm>-r<rep>.txt`` answer files (arm is one of
    with/without, rep a positive integer); any other file in the directory is a hard error.
    For every case, shuffle the answers with a reproducible seed, replace identities by
    A/B/C..., and write three files:
      * ``judge_prompt_<case>.md``      - grading instructions + 4 rubric items + the
        anonymised answer texts.  Safe to hand to a judge: no arm name and no arm-revealing
        hint appears anywhere in it.
      * ``scores_template_<case>.json`` - the case id, the 4 rubric items, and a
        null-filled 0/1 slot per anonymous answer for the judge to fill in.
      * ``map_<case>.json``             - anonymous label -> real answer key
        (``with-r1`` / ``without-r1`` ...).  FOR STATISTICS ONLY; never give it to a judge.
    Rubric source: the case's optional ``rubric`` field (a list of exactly 4 strings) when
    present; otherwise 4 groups split evenly out of ``assertions.must_include``.  The
    expected_output text is never injected into the rubric.

tally --out <dir> [--json]
    Read ``scores_*.json`` + ``map_*.json`` pairs written by judge, then print: per-case
    two-arm totals and full marks (items x reps), per-rubric two-arm hit counts, paired
    ``(case, rep)`` with-better / worse / tie counts, the paired win rate with a Wilson 95%
    confidence interval (with a directional-only warning for small n), and the grand total
    row.  Any null score, unequal arm counts, an answer missing from one arm or an unpaired
    file is a hard error (exit 2), never a silent skip.  ``--json`` makes stdout a single
    JSON document (payload keys: cases, items, pairs, per_arm, wilson, warnings).

Exit codes
----------
static : 0 valid | 2 invalid
grade  : 0 PASS | 1 FAIL | 2 cannot execute (bad args, case missing, answer unreadable)
compare: 0 both sides graded (NOT "both passed") | 1 a case FAILed on the --with side |
         2 evals invalid or a directory unreadable
judge  : 0 prompt/template/map written | 2 cannot execute (bad answer naming, unequal arms)
tally  : 0 statistics printed | 2 cannot execute (null score, mismatch, missing pair)

Why the deprecation: keyword matching rejects answers that state the right point in
different words.  Measured on 12 real answers it produced 12/12 false FAILs, so it is not
an acceptance criterion (backlog P-15-8); use judge + tally for verdicts.

Standard library only.  Paths resolve relative to this script, never to the user's cwd.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
DEFAULT_EVALS = os.path.join(SKILL_ROOT, "evals", "evals.json")
MANIFEST_PATH = os.path.join(SKILL_ROOT, "manifest.yaml")
WORKFLOW_PATH = os.path.join(SKILL_ROOT, "static", "core", "workflow.md")
RUNS_HINT_DIR = os.path.join("evals", "runs")

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_CANNOT = 2

# A string that any answer would contain proves nothing.  must_include may not be one of these.
TRUE_STRINGS = frozenset({u"的", u"是", u"了", u"和", u"与", u"在", u"一个",
                          u"a", u"the", u"and"})
MIN_INCLUDE = 5
MIN_EXCLUDE = 2

# Slugs are derived from static/core/workflow.md headings; the label is what the heading says.
STEP_VOCAB = {
    "0-gate": u"Step 0 \u2014 Run the gate",
    "1-read-base": u"Step 1 \u2014 Read the base",
    "2-scope": u"Step 2 \u2014 Scope the package (\u7acb\u9879)",
    "3-split": u"Step 3 \u2014 Break into tasks",
    "4-staff": u"Step 4 \u2014 Staff it",
    "5-run-loop": u"Step 5 \u2014 Run the loop",
    "6-closeout": u"Step 6 \u2014 Close and archive",
}

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001  (older Python / redirected streams)
        pass


class EvalError(Exception):
    """A condition that makes the requested mode impossible to execute (exit 2)."""


# --------------------------------------------------------------------------- #
# loading / small utilities
# --------------------------------------------------------------------------- #
def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        raise EvalError("读不到 %s：%s" % (path, exc)) from exc


def load_json_file(path, label="evals.json"):
    raw = read_bytes(path)
    if raw.startswith(b"\xef\xbb\xbf"):
        raise EvalError(
            "%s 带 UTF-8 BOM（EF BB BF）；本项目踩过这个坑：必须保存为 UTF-8 无 BOM 再跑 json.load"
            % label)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvalError("%s 不是合法 UTF-8：%s" % (label, exc)) from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise EvalError("%s 不是合法 JSON：第 %d 行第 %d 列：%s"
                        % (label, exc.lineno, exc.colno, exc.msg)) from exc


def load_manifest_axes(path=MANIFEST_PATH):
    """Extract {axis: [values...]} from manifest.yaml without a YAML dependency.

    The manifest is written in a fixed shape (``axes:`` at indent 2, ``values:`` at indent 4,
    ``key: fragment`` at indent 6), so a tiny indentation-aware reader is enough and keeps the
    runner standard-library only.
    """
    raw = read_bytes(path)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise EvalError("manifest.yaml 不是合法 UTF-8：%s" % exc) from exc
    axes = {}
    current = None
    in_values = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 2 and stripped.endswith(":") and not stripped.startswith("-"):
            current = stripped[:-1].strip()
            axes[current] = []
            in_values = False
        elif indent == 4 and stripped == "values:":
            in_values = True
        elif in_values and indent == 6 and ":" in stripped:
            key = stripped.split(":", 1)[0].strip()
            if key:
                axes[current].append(key)
        elif indent <= 4:
            in_values = False
    axes = {k: v for k, v in axes.items() if v}
    for required in ("deliverable", "rigor"):
        if required not in axes:
            raise EvalError("manifest.yaml 里读不到 axes.%s 的 values（声明缺失或格式变了）" % required)
    return axes


def load_workflow_headings(path=WORKFLOW_PATH):
    """Return {step_number: heading_title} parsed from workflow.md; empty dict if unreadable."""
    try:
        text = read_bytes(path).decode("utf-8-sig")
    except (EvalError, UnicodeDecodeError):
        return {}
    headings = {}
    for line in text.splitlines():
        m = re.match(r"^##\s*Step\s*(\d+)\s*[\u2014\u2013-]\s*(.+?)\s*$", line)
        if m:
            headings[int(m.group(1))] = m.group(2).strip()
    return headings


def load_and_validate(evals_path):
    """Load evals.json + manifest, validate, return (data, axes, warnings)."""
    data = load_json_file(evals_path)
    axes = load_manifest_axes()
    errors, warnings = validate(data, axes)
    if errors:
        raise ValidationFailed(errors)
    return data, axes, warnings


class ValidationFailed(EvalError):
    def __init__(self, errors):
        super().__init__("evals.json 不合法")
        self.errors = errors


def _is_nonempty_str(value):
    return isinstance(value, str) and bool(value.strip())


def _dedupe_report(items):
    seen = set()
    dupes = []
    for item in items:
        if item in seen and item not in dupes:
            dupes.append(item)
        seen.add(item)
    return dupes


def validate(data, axes):
    """Check the v2 schema.  Returns (errors, warnings); errors are human-readable Chinese."""
    errors = []
    warnings = []

    if not isinstance(data, dict):
        return ["顶层必须是 JSON 对象"], warnings

    if not _is_nonempty_str(data.get("skill_name")):
        errors.append("skill_name 必须是非空字符串")
    if data.get("schema_version") != 2:
        errors.append("schema_version 必须是整数 2（当前 %r）" % (data.get("schema_version"),))
    if not _is_nonempty_str(data.get("eval_mode")):
        errors.append("eval_mode 必须是非空字符串（如 static+manual-judge）")

    cases = data.get("evals")
    if not isinstance(cases, list) or not cases:
        errors.append("evals 必须是非空数组")
        return errors, warnings

    seen_ids = set()
    for index, case in enumerate(cases):
        where = "evals[%d]" % index
        if not isinstance(case, dict):
            errors.append("%s 必须是对象" % where)
            continue

        cid = case.get("id")
        if not _is_nonempty_str(cid):
            errors.append("%s.id 必须是非空字符串" % where)
            label = where
        else:
            label = cid
            if cid in seen_ids:
                errors.append("case '%s': id 重复（id 必须唯一）" % cid)
            seen_ids.add(cid)

        def err(message):
            errors.append("case '%s': %s" % (label, message))

        expected = case.get("expected_output")
        if not _is_nonempty_str(case.get("prompt")):
            err("缺 prompt 或不是非空字符串")
        if not _is_nonempty_str(expected):
            err("缺 expected_output 或不是非空字符串")

        assertions = case.get("assertions")
        if not isinstance(assertions, dict):
            err("缺 assertions 或不是对象")
            continue

        include = assertions.get("must_include")
        include_valid = isinstance(include, list)
        if not include_valid:
            err("assertions.must_include 必须是数组")
            include = []
        elif len(include) < MIN_INCLUDE:
            err("assertions.must_include 至少 %d 条（当前 %d）" % (MIN_INCLUDE, len(include)))
        seen_include = []
        for pos, item in enumerate(include, 1):
            if not _is_nonempty_str(item):
                err("must_include 第 %d 条必须是非空字符串" % pos)
                continue
            seen_include.append(item)
            if item.strip() in TRUE_STRINGS:
                err("must_include 含恒真串 '%s'（黑名单：%s），换有鉴别力的短串"
                    % (item, "/".join(sorted(TRUE_STRINGS))))
            elif _is_nonempty_str(expected) and item not in expected:
                err("must_include '%s' 在 expected_output 里找不到（断言必须从判据原文提取，"
                    "不许凭空造）" % item)
        for dupe in _dedupe_report(seen_include):
            err("must_include 重复：'%s'" % dupe)

        exclude = assertions.get("must_exclude")
        exclude_valid = isinstance(exclude, list)
        if not exclude_valid:
            err("assertions.must_exclude 必须是数组")
            exclude = []
        elif len(exclude) < MIN_EXCLUDE:
            err("assertions.must_exclude 至少 %d 条（当前 %d）" % (MIN_EXCLUDE, len(exclude)))
        seen_exclude = []
        for pos, item in enumerate(exclude, 1):
            if not _is_nonempty_str(item):
                err("must_exclude 第 %d 条必须是非空字符串" % pos)
                continue
            seen_exclude.append(item)
            if item.strip() in TRUE_STRINGS:
                err("must_exclude 含恒真串 '%s'" % item)
            if _is_nonempty_str(expected) and item in expected:
                err("must_exclude '%s' 出现在 expected_output 里：正确回答会判自己 FAIL" % item)
            for inc_item in seen_include:
                if item in inc_item:
                    err("must_exclude '%s' 是 must_include '%s' 的子串：判分会自相矛盾"
                        % (item, inc_item))
            if item != item.strip():
                warnings.append("case '%s': must_exclude '%s' 首尾有空白，逐字匹配会漏判"
                                % (label, item))
        for dupe in _dedupe_report(seen_exclude):
            err("must_exclude 重复：'%s'" % dupe)

        ax = assertions.get("axes")
        if not isinstance(ax, dict):
            err("assertions.axes 必须是对象 {deliverable, rigor}")
        else:
            for key in ("deliverable", "rigor"):
                if key not in ax:
                    err("assertions.axes 缺 %s" % key)
                    continue
                value = ax[key]
                allowed = axes.get(key, [])
                if not _is_nonempty_str(value):
                    err("assertions.axes.%s 必须是非空字符串" % key)
                elif allowed and value not in allowed:
                    err("assertions.axes.%s='%s' 不是 manifest.yaml 的真实轴值 %s"
                        % (key, value, sorted(allowed)))
            for extra in sorted(set(ax) - {"deliverable", "rigor"}):
                err("assertions.axes 有未知轴 '%s'（只允许 deliverable/rigor）" % extra)

        steps = assertions.get("steps")
        if not isinstance(steps, list):
            err("assertions.steps 必须是数组")
        else:
            if not steps:
                warnings.append("case '%s': steps 为空（仅当该 case 明确不进入流程时允许）" % label)
            for step in steps:
                if not _is_nonempty_str(step):
                    err("steps 里每条都必须是非空字符串")
                elif step not in STEP_VOCAB:
                    err("steps 里的 '%s' 不是六步编号（可选：%s）"
                        % (step, " / ".join(sorted(STEP_VOCAB))))
            for dupe in _dedupe_report([s for s in steps if _is_nonempty_str(s)]):
                err("steps 重复：'%s'" % dupe)

        rubric = case.get("rubric")
        if rubric is not None:
            if not isinstance(rubric, list):
                err("rubric 必须是数组（%d 条语义要点）" % RUBRIC_SIZE)
            elif len(rubric) != RUBRIC_SIZE:
                err("rubric 必须恰好 %d 条（当前 %d）" % (RUBRIC_SIZE, len(rubric)))
            else:
                expected_text = case.get("expected_output") or ""
                for pos, item in enumerate(rubric, 1):
                    if not _is_nonempty_str(item):
                        err("rubric 第 %d 条必须是非空字符串" % pos)
                        continue
                    value = item.strip()
                    if len(value) < 8:
                        err("rubric 第 %d 条太短（<8 字），当不了判分要点" % pos)
                    elif value and value in expected_text:
                        err("rubric 第 %d 条是从 expected_output 里逐字抄的（%r）—— "
                            "rubric 要写「怎样算做到」，不能变成参考答案" % (pos, value[:24]))

        budget = case.get("budget_hint")
        if not isinstance(budget, dict):
            err("缺 budget_hint 或不是对象 {max_tokens, max_minutes}")
        else:
            for key in ("max_tokens", "max_minutes"):
                value = budget.get(key)
                if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    err("budget_hint.%s 必须是正整数" % key)

    return errors, warnings


# --------------------------------------------------------------------------- #
# static mode
# --------------------------------------------------------------------------- #
def judge_brief(case, axes):
    """Build the ready-to-paste grading brief for one case."""
    assertions = case["assertions"]
    budget = case["budget_hint"]
    cid = case["id"]
    answer_dir = os.path.join(RUNS_HINT_DIR, cid)
    answer_path = os.path.join(answer_dir, "answer.md")

    lines = []
    lines.append("=" * 78)
    lines.append("CASE: %s    [deliverable=%s, rigor=%s]"
                 % (cid, assertions["axes"]["deliverable"], assertions["axes"]["rigor"]))
    lines.append("=" * 78)
    lines.append("")
    lines.append(u"\u3010case prompt\u3011")
    lines.append(case["prompt"])
    lines.append("")
    lines.append(u"\u3010expected_output\uff08\u5224\u636e\u539f\u6587\uff0c\u51bb\u7ed3\uff0c\u4e0d\u5f97\u6539\u5199\uff09\u3011")
    lines.append(case["expected_output"])
    lines.append("")
    lines.append(u"\u3010must_include\uff08\u9010\u5b57\u547d\u4e2d\uff0c\u5c11\u4e00\u6761\u5373 FAIL\uff09\u3011")
    for pos, item in enumerate(assertions["must_include"], 1):
        lines.append("  %d. %s" % (pos, item))
    lines.append("")
    lines.append(u"\u3010must_exclude\uff08\u4efb\u4e00\u547d\u4e2d\u5373 FAIL\uff09\u3011")
    for item in assertions["must_exclude"]:
        lines.append("  - %s" % item)
    lines.append("")
    lines.append(u"\u3010\u6d41\u7a0b\u6b65\u9aa4\u3011" +
                 (u" \u2192 ".join(assertions["steps"]) if assertions["steps"]
                  else u"\uff08\u8be5 case \u660e\u786e\u4e0d\u8fdb\u5165\u6d41\u7a0b\uff09"))
    lines.append(u"\u3010token \u9884\u7b97\u63d0\u793a\u3011max_tokens=%d, max_minutes=%d"
                 % (budget["max_tokens"], budget["max_minutes"]))
    lines.append(u"\u3010\u8f93\u51fa\u53bb\u5411\u5efa\u8bae\u3011\u628a judge \u5b50\u667a\u80fd\u4f53\u7684\u56de\u7b54\u5b58\u6210 "
                 "%s\uff0c\u7136\u540e\u8fd0\u884c\uff1a" % answer_path.replace(os.sep, "/"))
    lines.append("  python scripts/run_evals.py --mode grade --case %s --answer %s"
                 % (cid, answer_path.replace(os.sep, "/")))
    lines.append("")
    lines.append(u"\u3010\u7ed9 judge \u7684\u8bc4\u5206\u8981\u6c42\uff08\u4e0a\u9762\u6574\u6bb5\u76f4\u63a5\u7c98\u7ed9\u5b50\u667a\u80fd\u4f53\uff09\u3011")
    lines.append(u"\u4f60\u662f\u72ec\u7acb\u8bc4\u5206\u5458\u3002\u53ea\u4f9d\u636e\u4e0a\u9762\u7684\u65ad\u8a00\u5224\u5206\uff0c"
                 u"\u4e0d\u5f97\u6539\u5199\u5224\u636e\u3001\u4e0d\u5f97\u81ea\u884c\u53d1\u6325\uff1a")
    lines.append(u"  1. must_include \u6bcf\u4e00\u6761\u90fd\u5fc5\u987b\u5728\u56de\u7b54\u91cc\u9010\u5b57\u51fa\u73b0\uff0c"
                 u"\u5c11\u4e00\u6761\u5373\u5224 FAIL\uff1b")
    lines.append(u"  2. must_exclude \u4efb\u4e00\u6761\u51fa\u73b0\u5373\u5224 FAIL\uff1b")
    lines.append(u"  3. \u9010\u6761\u8f93\u51fa [ok]/[x]\uff0c\u6700\u540e\u4e00\u884c\u53ea\u5199\uff1a"
                 u"CASE %s PASS \u6216 CASE %s FAIL\u3002" % (cid, cid))
    lines.append("")
    return "\n".join(lines)


def cmd_static(args):
    evals_path = args.evals or DEFAULT_EVALS
    try:
        data, axes, warnings = load_and_validate(evals_path)
    except ValidationFailed as exc:
        for message in exc.errors:
            print("[x] %s" % message)
        print("[x] \u5171 %d \u6761\u9519\u8bef\uff1aevals \u4e0d\u5408\u6cd5\uff08exit 2\uff09" % len(exc.errors))
        return EXIT_CANNOT
    except EvalError as exc:
        print("[x] %s" % exc)
        print("[x] static \u6821\u9a8c\u65e0\u6cd5\u6267\u884c\uff08exit 2\uff09")
        return EXIT_CANNOT

    for message in warnings:
        print("[warn] %s" % message)

    headings = load_workflow_headings()
    used_steps = set()
    for case in data["evals"]:
        used_steps.update(case["assertions"]["steps"])
    for slug in sorted(used_steps, key=lambda s: (int(s.split("-")[0]), s)):
        number = int(slug.split("-")[0])
        expected_title = STEP_VOCAB[slug].split(u"\u2014", 1)[-1].strip()
        if headings and number not in headings:
            print("[warn] %s: workflow.md \u91cc\u627e\u4e0d\u5230 Step %d\uff08\u6b65\u9aa4\u7f16\u53f7\u5df2\u53d8\uff1f\uff09"
                  % (slug, number))
        elif headings and expected_title not in headings[number]:
            print("[warn] %s: workflow.md \u6807\u9898\u4e0e\u9884\u671f\u4e0d\u4e00\u81f4\uff08%s vs %s\uff09"
                  % (slug, expected_title, headings[number]))

    cases = data["evals"]
    print("project-dept evals \u00b7 static \u6821\u9a8c\u901a\u8fc7")
    print("  skill_name  : %s" % data["skill_name"])
    print("  schema      : v%s" % data["schema_version"])
    print("  eval_mode   : %s" % data["eval_mode"])
    print("  cases       : %d" % len(cases))
    print("  axes        : deliverable=%s rigor=%s"
          % ("/".join(axes["deliverable"]), "/".join(axes["rigor"])))
    print("  steps vocab : %s" % " / ".join(sorted(STEP_VOCAB)))
    print("")

    for index, case in enumerate(cases, 1):
        print(judge_brief(case, axes))
        if index != len(cases):
            print("")

    total_tokens = sum(c["budget_hint"]["max_tokens"] for c in cases)
    print("-" * 78)
    print("\u5168\u90e8 %d \u4e2a case \u7684\u8bc4\u5206\u63d0\u793a\u5df2\u6253\u5370\uff1b"
          "\u9884\u7b97\u5408\u8ba1 \u2264%d tokens\u3002" % (len(cases), total_tokens))
    print("\u63d0\u793a\uff1akeyword \u5224\u5206\u53ea\u80fd\u505a\u786e\u5b9a\u6027\u56de\u5f52\uff0c"
          "\u5f62\u5f0f\u5bf9\u4e0d\u4ee3\u8868\u610f\u601d\u5bf9\uff1b\u4e24\u4e2a\u76ee\u5f55\u7684\u5bf9\u7167"
          "\u4e5f\u4e0d\u662f\u7b49\u4ef7\u6027\u8bc1\u660e\u3002")
    return EXIT_PASS


# --------------------------------------------------------------------------- #
# grading
# --------------------------------------------------------------------------- #
def find_case(data, case_id):
    for case in data["evals"]:
        if case["id"] == case_id:
            return case
    return None


def grade_text(case, text):
    """Deterministically grade one answer string against one case."""
    assertions = case["assertions"]
    include_rows = [(item, item in text) for item in assertions["must_include"]]
    exclude_rows = [(item, item in text) for item in assertions["must_exclude"]]
    include_ok = sum(1 for _, ok in include_rows if ok)
    exclude_hit = sum(1 for _, hit in exclude_rows if hit)
    passed = include_ok == len(include_rows) and exclude_hit == 0
    return {
        "passed": passed,
        "include_rows": include_rows,
        "exclude_rows": exclude_rows,
        "include_ok": include_ok,
        "include_total": len(include_rows),
        "exclude_hit": exclude_hit,
        "exclude_total": len(exclude_rows),
    }


def read_answer(path):
    if not os.path.exists(path):
        raise EvalError("\u7b54\u6848\u6587\u4ef6\u4e0d\u5b58\u5728\uff1a%s" % path)
    if not os.path.isfile(path):
        raise EvalError("\u7b54\u6848\u8def\u5f84\u4e0d\u662f\u6587\u4ef6\uff1a%s" % path)
    raw = read_bytes(path)
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise EvalError("\u7b54\u6848\u6587\u4ef6\u65e0\u6cd5\u6309 UTF-8 / GB18030 \u89e3\u7801\uff1a%s" % path)


def print_grade_report(case_id, result):
    for item, ok in result["include_rows"]:
        if ok:
            print("[ok] must_include  %s" % item)
        else:
            print("[x]  must_include  %s  \uff08\u672a\u51fa\u73b0\uff09" % item)
    for item, hit in result["exclude_rows"]:
        if hit:
            print("[x]  must_exclude  %s  \uff08\u51fa\u73b0\uff0c\u76f4\u63a5 FAIL\uff09" % item)
        else:
            print("[ok] must_exclude  %s  \uff08\u672a\u51fa\u73b0\uff0c\u6b63\u786e\uff09" % item)
    print("include %d/%d\uff0cexclude \u547d\u4e2d %d \u6761 \u2192 %s"
          % (result["include_ok"], result["include_total"], result["exclude_hit"],
             "PASS" if result["passed"] else "FAIL"))
    print("CASE %s %s" % (case_id, "PASS" if result["passed"] else "FAIL"))


def cmd_grade(args):
    print(DEPRECATED_GRADE)
    if not args.case:
        print("[x] --mode grade \u9700\u8981 --case <id>")
        return EXIT_CANNOT
    if not args.answer:
        print("[x] --mode grade \u9700\u8981 --answer <path>")
        return EXIT_CANNOT
    evals_path = args.evals or DEFAULT_EVALS
    try:
        data, _axes, _warnings = load_and_validate(evals_path)
        case = find_case(data, args.case)
        if case is None:
            raise EvalError("case '%s' \u4e0d\u5b58\u5728\uff1b\u53ef\u7528\uff1a%s"
                            % (args.case, ", ".join(c["id"] for c in data["evals"])))
        text = read_answer(args.answer)
    except ValidationFailed as exc:
        for message in exc.errors:
            print("[x] %s" % message)
        print("[x] evals \u4e0d\u5408\u6cd5\uff0c\u65e0\u6cd5\u5224\u5206\uff08exit 2\uff09")
        return EXIT_CANNOT
    except EvalError as exc:
        print("[x] %s" % exc)
        return EXIT_CANNOT

    print("case: %s   answer: %s   chars: %d" % (case["id"], args.answer, len(text)))
    if not text.strip():
        print("[warn] \u7b54\u6848\u6587\u4ef6\u4e3a\u7a7a\uff0c\u6240\u6709 must_include \u90fd\u4f1a\u7b97\u672a\u547d\u4e2d")
    result = grade_text(case, text)
    print_grade_report(case["id"], result)
    return EXIT_PASS if result["passed"] else EXIT_FAIL


# --------------------------------------------------------------------------- #
# judge / tally modes: blind judging + paired statistics (backlog P-15-8)
# --------------------------------------------------------------------------- #
ARMS = ("with", "without")
RUBRIC_SIZE = 4
SMALL_N = 10
Z_95 = 1.96
JUDGE_SALT = "project-dept-judge-v1"

# Printed by grade mode on every run.  Exact wording matters: P-15-8 says keyword grading
# must not be used as an acceptance criterion.
DEPRECATED_GRADE = (
    "[!] DEPRECATED: 关键词逐字判分不可作为验收判据（见 P-15-8）——请用 judge + tally"
)

ANSWER_NAME_RE = re.compile(
    r"^(?P<case>.+)-(?P<arm>with|without)-r(?P<rep>[1-9][0-9]*)\.txt$")
MAP_VALUE_RE = re.compile(r"^(?P<arm>with|without)-r(?P<rep>[1-9][0-9]*)$")
SCORES_NAME_RE = re.compile(r"^scores_(?P<template>template_)?(?P<case>.+)\.json$")
MAP_NAME_RE = re.compile(r"^map_(?P<case>.+)\.json$")


def label_for(index):
    """0 -> A ... 25 -> Z, 26 -> A1, 27 -> B1 ...  Stable and collision-free."""
    if index < 26:
        return chr(ord("A") + index)
    return "%s%d" % (chr(ord("A") + index % 26), index // 26)


def write_text_file(path, text):
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except OSError as exc:
        raise EvalError("写不进 %s：%s" % (path, exc)) from exc


def write_json_file(path, payload):
    write_text_file(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def resolve_case_selector(cases, token):
    """Resolve a case selector to a full case id: exact id first, then a unique prefix.

    Answer files may use short labels (e.g. ``base`` for ``baseline-is-wrong``); an
    ambiguous prefix must fail loudly instead of silently picking one case.
    """
    ids = [case["id"] for case in cases]
    for case_id in ids:
        if case_id == token:
            return case_id
    matches = [case_id for case_id in ids if case_id.startswith(token)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise EvalError("case '%s' 不存在；可用：%s" % (token, ", ".join(ids)))
    raise EvalError("case '%s' 是多个 case 的前缀（%s），请写完整 id"
                    % (token, ", ".join(matches)))


def build_rubric(case):
    """Return exactly RUBRIC_SIZE rubric strings for one case.

    Prefer the case's optional ``rubric`` field (must be 4 non-empty strings).  Otherwise
    split ``assertions.must_include`` evenly into 4 groups; every group is phrased as
    "要点：a、b、c" plus an explicit hit threshold.  expected_output is never used: copying
    the model answer into the rubric would turn the rubric into a reference answer.
    """
    explicit = case.get("rubric")
    if explicit is not None:
        if (not isinstance(explicit, (list, tuple)) or len(explicit) != RUBRIC_SIZE
                or not all(_is_nonempty_str(item) for item in explicit)):
            raise EvalError("case '%s' 的 rubric 必须是 %d 条非空字符串"
                            % (case.get("id", "?"), RUBRIC_SIZE))
        return [item.strip() for item in explicit]
    assertions = case.get("assertions") or {}
    must_include = assertions.get("must_include") or []
    if (not isinstance(must_include, (list, tuple))
            or not must_include
            or not all(_is_nonempty_str(item) for item in must_include)):
        raise EvalError("case '%s' 缺少可用的 assertions.must_include，无法派生 rubric"
                        % case.get("id", "?"))
    total = len(must_include)
    if total < RUBRIC_SIZE:
        raise EvalError("case '%s' 只有 %d 条 must_include，无法均分成 %d 条 rubric"
                        % (case.get("id", "?"), total, RUBRIC_SIZE))
    base, remainder = divmod(total, RUBRIC_SIZE)
    groups = []
    start = 0
    for index in range(RUBRIC_SIZE):
        size = base + (1 if index < remainder else 0)
        groups.append(must_include[start:start + size])
        start += size
    rubric = []
    for group in groups:
        need = len(group) // 2 + 1
        rubric.append("要点：%s（命中该组多数，至少 %d/%d 个要点给 1）"
                      % ("、".join(group), need, len(group)))
    return rubric


def scan_answer_files(answers_dir):
    """Scan ``<case>-<arm>-r<rep>.txt`` files; any other entry is a hard error."""
    if not os.path.isdir(answers_dir):
        raise EvalError("答案目录不存在或不是目录：%s" % answers_dir)
    try:
        names = sorted(os.listdir(answers_dir))
    except OSError as exc:
        raise EvalError("读不到答案目录 %s：%s" % (answers_dir, exc)) from exc
    records = []
    for name in names:
        path = os.path.join(answers_dir, name)
        match = ANSWER_NAME_RE.match(name)
        if match is None or not os.path.isfile(path):
            raise EvalError(
                "答案目录里有不符合 <case>-<with|without>-r<正整数>.txt 命名的条目：%s"
                % path)
        records.append({
            "name": name,
            "path": path,
            "case": match.group("case"),
            "arm": match.group("arm"),
            "rep": int(match.group("rep")),
        })
    if not records:
        raise EvalError("答案目录里没有任何答案文件：%s" % answers_dir)
    return records


def group_answers(records, cases):
    """Map real case id -> answer records, rejecting duplicate (case, arm, rep)."""
    grouped = {}
    seen = {}
    for record in records:
        case_id = resolve_case_selector(cases, record["case"])
        key = (case_id, record["arm"], record["rep"])
        if key in seen:
            raise EvalError("同一 case/臂/rep 出现两次：%s 与 %s"
                            % (seen[key], record["name"]))
        seen[key] = record["name"]
        record["case_id"] = case_id
        grouped.setdefault(case_id, []).append(record)
    return grouped


def check_arm_balance(case_id, records):
    """Both arms must exist and cover exactly the same rep numbers."""
    by_arm = {arm: [] for arm in ARMS}
    for record in records:
        by_arm[record["arm"]].append(record)
    for arm in ARMS:
        if not by_arm[arm]:
            raise EvalError("case '%s' 缺少 %s 臂的答案" % (case_id, arm))
    reps = {arm: sorted(record["rep"] for record in by_arm[arm]) for arm in ARMS}
    if reps["with"] != reps["without"]:
        raise EvalError("case '%s' 两臂答案数/rep 不一致：with=%s without=%s"
                        % (case_id, ", ".join(str(n) for n in reps["with"]) or "-",
                           ", ".join(str(n) for n in reps["without"]) or "-"))
    return by_arm, reps["with"]


def plan_judge_case(case_id, records, seed):
    """Shuffle one case's answers reproducibly and return (entries, label -> key, reps)."""
    _by_arm, reps = check_arm_balance(case_id, records)
    ordered = sorted(records, key=lambda record: (record["arm"], record["rep"]))
    digest = hashlib.sha256(
        ("%s|%d|%s" % (JUDGE_SALT, seed, case_id)).encode("utf-8")).hexdigest()
    random.Random(int(digest[:16], 16)).shuffle(ordered)
    entries = []
    mapping = {}
    for index, record in enumerate(ordered):
        label = label_for(index)
        mapping[label] = "%s-r%d" % (record["arm"], record["rep"])
        entries.append((label, record))
    return entries, mapping, len(reps)


def render_judge_prompt(case_id, rubric, entries):
    """Render the blind-judge prompt.  Never mention an arm name or any arm-revealing hint."""
    lines = [
        "# 盲判任务单：%s" % case_id,
        "",
        "## 判分说明",
        "",
        "你是独立判官。只依据下面的 %d 条评分要点，对每一份答复独立打分。" % RUBRIC_SIZE,
        "- 每条要点满分 1 分：命中给 1，未命中给 0；不接受 0.5 或其它分数。",
        "- 各份答复彼此独立，不要相互比较，也不要推测答复的来源或版本。",
        "- 不要逐字比对：意思到了就算命中，措辞不同不影响判定。",
        "- 把结果填进同目录的 `scores_template_%s.json`：`scores` 下每个字母对应"
        "一行 %d 个 0/1。" % (case_id, RUBRIC_SIZE),
        "",
        "## 评分要点（%d 条）" % RUBRIC_SIZE,
        "",
    ]
    for index, text in enumerate(rubric):
        lines.append("R%d. %s" % (index + 1, text))
    lines.extend(["", "## 待判答复（匿名为 A、B、C…，顺序已打乱）", ""])
    for label, record in entries:
        lines.append("===== 答复 %s 开始 =====" % label)
        lines.append(read_answer(record["path"]).rstrip("\n"))
        lines.append("===== 答复 %s 结束 =====" % label)
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def render_scores_template(case_id, items, labels):
    return {
        "case": case_id,
        "items": [{"id": "R%d" % (index + 1), "text": text}
                  for index, text in enumerate(items)],
        "scores": {label: [None] * len(items) for label in labels},
    }


def cmd_judge(args):
    if not args.answers:
        print("[x] --mode judge 需要 --answers <答案目录>")
        return EXIT_CANNOT
    if not args.out:
        print("[x] --mode judge 需要 --out <输出目录>")
        return EXIT_CANNOT
    evals_path = args.evals or DEFAULT_EVALS
    try:
        data = load_json_file(evals_path)
        cases = data.get("evals") if isinstance(data, dict) else None
        if not isinstance(cases, list) or not cases:
            raise EvalError("%s 里没有非空的 evals 列表" % evals_path)
        records = scan_answer_files(args.answers)
        grouped = group_answers(records, cases)
        selected = cases
        if args.case:
            wanted = resolve_case_selector(cases, args.case)
            if wanted not in grouped:
                raise EvalError("答案目录里没有 case '%s' 的答案" % wanted)
            selected = [case for case in cases if case["id"] == wanted]
        else:
            selected = [case for case in cases if case["id"] in grouped]
        if not selected:
            raise EvalError("答案目录里没有可判的 case（目录里只有：%s）"
                            % ", ".join(sorted(grouped)))
        os.makedirs(args.out, exist_ok=True)
        answers_per_case = {}
        # Plan every case first: a bad case must not leave a half-written output directory.
        plans = []
        for case in selected:
            case_id = case["id"]
            entries, mapping, reps = plan_judge_case(case_id, grouped[case_id], args.seed)
            plans.append((case_id, entries, mapping, reps, build_rubric(case)))
        for case_id, entries, mapping, reps, items in plans:
            write_text_file(os.path.join(args.out, "judge_prompt_%s.md" % case_id),
                            render_judge_prompt(case_id, items, entries))
            write_json_file(
                os.path.join(args.out, "scores_template_%s.json" % case_id),
                render_scores_template(case_id, items, [label for label, _ in entries]))
            write_json_file(os.path.join(args.out, "map_%s.json" % case_id), mapping)
            answers_per_case[case_id] = reps
    except EvalError as exc:
        print("[x] %s" % exc)
        return EXIT_CANNOT
    print("judge: 写出 %d 个 case / 每 case %s 份答案 / seed=%d → %s"
          % (len(answers_per_case),
             "/".join(str(answers_per_case[cid]) for cid in sorted(answers_per_case)),
             args.seed, args.out))
    return EXIT_PASS


def wilson_interval(successes, trials, z=Z_95):
    """Wilson score interval for a binomial proportion (clamped to [0, 1])."""
    if trials <= 0:
        return {"p": None, "n": 0, "lower": None, "upper": None, "z": z}
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = p + z * z / (2.0 * trials)
    margin = z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials))
    return {
        "p": p,
        "n": trials,
        "lower": max(0.0, (centre - margin) / denominator),
        "upper": min(1.0, (centre + margin) / denominator),
        "z": z,
    }


def scan_tally_files(out_dir):
    """Return ({case: 'scores_*.json' meta}, {case: 'map_*.json' path}) with pairing checks."""
    if not os.path.isdir(out_dir):
        raise EvalError("judge 输出目录不存在或不是目录：%s" % out_dir)
    try:
        names = sorted(os.listdir(out_dir))
    except OSError as exc:
        raise EvalError("读不到 judge 输出目录 %s：%s" % (out_dir, exc)) from exc
    scores = {}
    maps = {}
    for name in names:
        path = os.path.join(out_dir, name)
        if not os.path.isfile(path):
            continue
        match = SCORES_NAME_RE.match(name)
        if match:
            case_key = match.group("case")
            candidate = {"path": path, "template": bool(match.group("template"))}
            previous = scores.get(case_key)
            # A filled scores_<case>.json wins over the untouched scores_template_<case>.json.
            if previous is None or (previous["template"] and not candidate["template"]):
                scores[case_key] = candidate
            continue
        match = MAP_NAME_RE.match(name)
        if match:
            case_key = match.group("case")
            if case_key in maps:
                raise EvalError("同一个 case 有两份 map：%s 与 %s"
                                % (maps[case_key], name))
            maps[case_key] = path
    if not scores and not maps:
        raise EvalError("目录里没有 scores_*.json 或 map_*.json：%s" % out_dir)
    for case_key in sorted(set(scores) | set(maps)):
        if case_key not in maps:
            raise EvalError("case '%s' 有 scores 但没有对应 map_%s.json（配对缺失）"
                            % (case_key, case_key))
        if case_key not in scores:
            raise EvalError("case '%s' 有 map 但没有对应 scores_*.json（配对缺失）"
                            % case_key)
    return scores, maps


def load_tally_pair(case_key, scores_meta, map_path):
    """Validate one scores/map pair; return (case summary, per-item rows, pair rows)."""
    scores_payload = load_json_file(scores_meta["path"],
                                    label=os.path.basename(scores_meta["path"]))
    mapping = load_json_file(map_path, label=os.path.basename(map_path))
    if not isinstance(scores_payload, dict):
        raise EvalError("%s 顶层必须是 JSON 对象" % scores_meta["path"])
    case_id = scores_payload.get("case")
    if not _is_nonempty_str(case_id):
        raise EvalError("%s 缺少 case 字段" % scores_meta["path"])
    if case_id != case_key:
        raise EvalError("%s 里 case='%s' 与文件名里的 '%s' 不一致"
                        % (scores_meta["path"], case_id, case_key))
    items = scores_payload.get("items")
    if not isinstance(items, list) or not items:
        raise EvalError("case '%s' 的 items 必须是非空数组" % case_id)
    item_ids = []
    for index, item in enumerate(items):
        if isinstance(item, dict):
            item_id, item_text = item.get("id"), item.get("text")
        elif isinstance(item, str):
            item_id, item_text = "R%d" % (index + 1), item
        else:
            raise EvalError("case '%s' 的 items[%d] 既不是对象也不是字符串"
                            % (case_id, index))
        if not _is_nonempty_str(item_id) or not _is_nonempty_str(item_text):
            raise EvalError("case '%s' 的 items[%d] 缺少 id/text" % (case_id, index))
        if item_id in item_ids:
            raise EvalError("case '%s' 的 item id 重复：%s" % (case_id, item_id))
        item_ids.append(item_id)
    rows = scores_payload.get("scores")
    if not isinstance(rows, dict) or not rows:
        raise EvalError("case '%s' 的 scores 必须是非空对象" % case_id)
    if not isinstance(mapping, dict) or not mapping:
        raise EvalError("case '%s' 的 map 必须是非空对象" % case_id)
    if set(rows) != set(mapping):
        only_scores = sorted(set(rows) - set(mapping))
        only_map = sorted(set(mapping) - set(rows))
        raise EvalError("case '%s' 的 scores 标签与 map 不一致：scores 多 %s，map 多 %s"
                        % (case_id, only_scores or "-", only_map or "-"))
    parsed = {}
    seen_keys = {}
    for label in sorted(mapping):
        value = mapping[label]
        if not isinstance(value, str):
            raise EvalError("case '%s' 的 map['%s'] 不是字符串：%r" % (case_id, label, value))
        match = MAP_VALUE_RE.match(value)
        if match is None:
            raise EvalError("case '%s' 的 map['%s']='%s' 不符合 with|without-r<正整数>"
                            % (case_id, label, value))
        key = (match.group("arm"), int(match.group("rep")))
        if key in seen_keys:
            raise EvalError("case '%s' 的 map 里 %s 出现两次（%s 与 %s）"
                            % (case_id, value, seen_keys[key], label))
        seen_keys[key] = label
        parsed[label] = key
    missing = []
    matrix = {}
    for label in sorted(rows):
        row = rows[label]
        if not isinstance(row, list):
            raise EvalError("case '%s' 标签 %s 的分数必须是数组" % (case_id, label))
        if len(row) != len(item_ids):
            raise EvalError("case '%s' 标签 %s 有 %d 格分数，但 rubric 是 %d 条"
                            % (case_id, label, len(row), len(item_ids)))
        for index, score in enumerate(row):
            if score is None:
                missing.append((case_id, item_ids[index], label, mapping[label]))
                continue
            if isinstance(score, bool) or not isinstance(score, int) or score not in (0, 1):
                raise EvalError("case '%s' 标签 %s / %s 的分数非法：%r（只接受 0/1 整数）"
                                % (case_id, label, item_ids[index], score))
        matrix[label] = list(row)
    if missing:
        detail = "；".join("%s 的 %s / 标签 %s（原答案 %s）" % cell for cell in missing)
        raise EvalError("有 %d 个格子还没打分（null），判官未填完：%s"
                        % (len(missing), detail))
    by_arm = {arm: {} for arm in ARMS}
    for label, (arm, rep) in parsed.items():
        by_arm[arm][rep] = label
    for arm in ARMS:
        if not by_arm[arm]:
            raise EvalError("case '%s' 缺少 %s 臂的分数（某臂缺答案）" % (case_id, arm))
    if sorted(by_arm["with"]) != sorted(by_arm["without"]):
        raise EvalError("case '%s' 两臂 rep 不一致：with=%s without=%s"
                        % (case_id, sorted(by_arm["with"]), sorted(by_arm["without"])))
    reps = sorted(by_arm["with"])
    pairs = []
    for rep in reps:
        with_total = sum(matrix[by_arm["with"][rep]])
        without_total = sum(matrix[by_arm["without"][rep]])
        if with_total > without_total:
            winner = "with"
        elif with_total < without_total:
            winner = "without"
        else:
            winner = "tie"
        pairs.append({"case": case_id, "rep": rep, "with": with_total,
                      "without": without_total, "winner": winner})
    item_rows = []
    for index, item_id in enumerate(item_ids):
        item_rows.append({
            "case": case_id,
            "item": item_id,
            "with": sum(matrix[by_arm["with"][rep]][index] for rep in reps),
            "without": sum(matrix[by_arm["without"][rep]][index] for rep in reps),
            "max": len(reps),
        })
    case_row = {
        "case": case_id,
        "items": len(item_ids),
        "reps": len(reps),
        "max": len(item_ids) * len(reps),
        "with": sum(pair["with"] for pair in pairs),
        "without": sum(pair["without"] for pair in pairs),
    }
    return case_row, item_rows, pairs


def tally_statistics(case_rows, item_rows, pair_rows):
    trial_count = len(pair_rows)
    with_better = sum(1 for pair in pair_rows if pair["winner"] == "with")
    without_better = sum(1 for pair in pair_rows if pair["winner"] == "without")
    ties = trial_count - with_better - without_better
    win_rate = (with_better / trial_count) if trial_count else None
    warnings = []
    warnings.append("平局计入配对胜率分母（胜率 = with 更好的对数 / 全部配对数）")
    if ties:
        warnings.append("有 %d 对两臂同分，计入分母但不算 with 更好" % ties)
    if trial_count < SMALL_N:
        warnings.append("配对数 n=%d < %d：Wilson 95%% 区间只能当方向性参考，不能当显著性"
                        "或通过判据" % (trial_count, SMALL_N))
    return {
        "cases": case_rows,
        "items": item_rows,
        "pairs": pair_rows,
        "per_arm": {
            "with": sum(row["with"] for row in case_rows),
            "without": sum(row["without"] for row in case_rows),
            "max": sum(row["max"] for row in case_rows),
            "pairs": {
                "n": trial_count,
                "with_better": with_better,
                "without_better": without_better,
                "tie": ties,
                "win_rate": win_rate,
            },
        },
        "wilson": wilson_interval(with_better, trial_count),
        "warnings": warnings,
    }


def print_tally_report(stats):
    print("=== 每 case 两臂总分 ===")
    print("%-30s %8s %8s %8s" % ("case", "with", "without", "满分"))
    for row in stats["cases"]:
        print("%-30s %8d %8d %8d" % (row["case"], row["with"], row["without"], row["max"]))
    print("")
    print("=== 每条 rubric 两臂命中数 ===")
    print("%-30s %6s %8s %8s %6s" % ("case", "item", "with", "without", "满分"))
    for row in stats["items"]:
        print("%-30s %6s %8d %8d %6d"
              % (row["case"], row["item"], row["with"], row["without"], row["max"]))
    print("")
    pairs = stats["per_arm"]["pairs"]
    print("=== 配对比较（单位 = case × rep）===")
    print("配对数 n=%d：with 更好 %d / 更差 %d / 平 %d"
          % (pairs["n"], pairs["with_better"], pairs["without_better"], pairs["tie"]))
    print("配对胜率 = %s"
          % ("-" if pairs["win_rate"] is None else "%.4f" % pairs["win_rate"]))
    wilson = stats["wilson"]
    if wilson["n"]:
        print("Wilson 95%% CI = [%.4f, %.4f]（z=%.2f）"
              % (wilson["lower"], wilson["upper"], wilson["z"]))
    else:
        print("Wilson 95%% CI = 无配对，无法计算")
    print("")
    print("=== 总分 ===")
    print("with %d / %d   without %d / %d"
          % (stats["per_arm"]["with"], stats["per_arm"]["max"],
             stats["per_arm"]["without"], stats["per_arm"]["max"]))
    for warning in stats["warnings"]:
        print("[warn] %s" % warning)


def precheck_blank_scores(scores_meta):
    """一次性收集所有 case 的空格，避免只报排序第一个 case。"""
    report = []
    for case_key in sorted(scores_meta):
        path = scores_meta[case_key]["path"]
        payload = load_json_file(path, label=os.path.basename(path))
        if not isinstance(payload, dict):
            continue
        rows = payload.get("scores")
        if not isinstance(rows, dict):
            continue
        item_ids = []
        for index, item in enumerate(payload.get("items") or []):
            if isinstance(item, dict):
                item_ids.append(str(item.get("id") or ("R%d" % (index + 1))))
            else:
                item_ids.append("R%d" % (index + 1))
        cells = []
        for label in sorted(rows):
            row = rows[label]
            if not isinstance(row, list):
                continue
            for index, score in enumerate(row):
                if score is None:
                    item_id = item_ids[index] if index < len(item_ids) else "第%d条" % (index + 1)
                    cells.append((label, item_id))
        if cells:
            report.append((case_key, cells))
    return report


def cmd_tally(args):
    if not args.out:
        sys.stderr.write("[x] --mode tally 需要 --out <judge 输出目录>\n")
        return EXIT_CANNOT
    try:
        scores_meta, map_paths = scan_tally_files(args.out)
        blanks = precheck_blank_scores(scores_meta)
        if blanks:
            parts = []
            total = 0
            for case_key, cells in blanks:
                total += len(cells)
                sample = "、".join(
                    "%s / 标签 %s（null）" % (item_id, label)
                    for label, item_id in cells[:6]
                )
                more = " 等" if len(cells) > 6 else ""
                parts.append("case '%s' 空 %d 格（%s%s）"
                             % (case_key, len(cells), sample, more))
            raise EvalError("判官没填完（null），共 %d 个 case 有空格、合计 %d 格：%s"
                            % (len(blanks), total, "；".join(parts)))
        case_rows, item_rows, pair_rows = [], [], []
        for case_key in sorted(scores_meta):
            case_row, item_row, pair_row = load_tally_pair(
                case_key, scores_meta[case_key], map_paths[case_key])
            case_rows.append(case_row)
            item_rows.extend(item_row)
            pair_rows.extend(pair_row)
        stats = tally_statistics(case_rows, item_rows, pair_rows)
    except EvalError as exc:
        sys.stderr.write("[x] %s\n" % exc)
        return EXIT_CANNOT
    if args.json_out:
        print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    else:
        print_tally_report(stats)
    return EXIT_PASS


# --------------------------------------------------------------------------- #
# compare mode
# --------------------------------------------------------------------------- #
def resolve_answer_path(root, case_id, case_count):
    """Find the answer file for one case inside one run directory."""
    candidates = [
        os.path.join(root, case_id, "answer.md"),
        os.path.join(root, case_id + ".md"),
        os.path.join(root, case_id, "answer.txt"),
        os.path.join(root, "answer_" + case_id + ".md"),
        os.path.join(root, case_id + "_answer.md"),
    ]
    if case_count == 1:
        candidates.append(os.path.join(root, "answer.md"))
    for path in candidates:
        if os.path.isfile(path):
            return path
    # "or any .md": a single top-level markdown file is unambiguous only for a one-case eval set.
    if case_count == 1 and os.path.isdir(root):
        mds = sorted(name for name in os.listdir(root)
                     if name.lower().endswith(".md") and os.path.isfile(os.path.join(root, name)))
        if len(mds) == 1:
            return os.path.join(root, mds[0])
    return None


def side_verdict(data, root):
    """Return {case_id: (status, detail)} for one directory."""
    cases = data["evals"]
    verdicts = {}
    for case in cases:
        cid = case["id"]
        path = resolve_answer_path(root, cid, len(cases))
        if path is None:
            verdicts[cid] = ("MISSING", u"\u627e\u4e0d\u5230\u7b54\u6848\u6587\u4ef6")
            continue
        try:
            text = read_answer(path)
        except EvalError as exc:
            verdicts[cid] = ("ERROR", str(exc))
            continue
        result = grade_text(case, text)
        verdicts[cid] = ("PASS" if result["passed"] else "FAIL", result)
    return verdicts


def cmd_compare(args):
    if not args.with_dir or not args.without_dir:
        print("[x] --mode compare \u9700\u8981 --with <dir> --without <dir>")
        return EXIT_CANNOT
    for label, path in (("--with", args.with_dir), ("--without", args.without_dir)):
        if not os.path.isdir(path):
            print("[x] %s \u76ee\u5f55\u4e0d\u53ef\u8bfb\uff1a%s" % (label, path))
            return EXIT_CANNOT
    evals_path = args.evals or DEFAULT_EVALS
    try:
        data, _axes, _warnings = load_and_validate(evals_path)
    except ValidationFailed as exc:
        for message in exc.errors:
            print("[x] %s" % message)
        print("[x] evals \u4e0d\u5408\u6cd5\uff0c\u65e0\u6cd5\u5bf9\u6bd4\uff08exit 2\uff09")
        return EXIT_CANNOT
    except EvalError as exc:
        print("[x] %s" % exc)
        return EXIT_CANNOT

    with_side = side_verdict(data, args.with_dir)
    without_side = side_verdict(data, args.without_dir)

    print("A/B compare   with: %s   without: %s" % (args.with_dir, args.without_dir))
    print("%-28s %-10s %-10s" % ("CASE", "WITH", "WITHOUT"))
    print("-" * 50)
    with_pass = without_pass = 0
    with_fail = False
    for case in data["evals"]:
        cid = case["id"]
        w_status = with_side[cid][0]
        wo_status = without_side[cid][0]
        if w_status == "PASS":
            with_pass += 1
        else:
            with_fail = True
        if wo_status == "PASS":
            without_pass += 1
        print("%-28s %-10s %-10s" % (cid, w_status, wo_status))

    total = len(data["evals"])
    print("-" * 50)
    print("%-28s %-10s %-10s" % ("TOTAL PASS", "%d/%d" % (with_pass, total),
                                 "%d/%d" % (without_pass, total)))
    print("%-28s %+d" % ("\u5dee\u503c\uff08with - without\uff09", with_pass - without_pass))
    for case in data["evals"]:
        cid = case["id"]
        for label, side in (("with", with_side), ("without", without_side)):
            status, detail = side[cid]
            if status in ("MISSING", "ERROR"):
                print("[warn] %s \u4fa7 case '%s'\uff1a%s%s"
                      % (label, cid, status,
                         ("\uff1a" + detail) if isinstance(detail, str) else ""))
    print("")
    print("[warn] \u6837\u672c\u91cf\u5c0f\uff08%d \u4e2a case\uff0c\u6bcf\u4e2a case \u5355\u6b21\u5224\u5206\uff09\uff1a"
          "\u8fd9\u662f\u65b9\u5411\u6027\u5bf9\u7167\uff0c\u4ec5\u4f9b\u53c2\u8003\uff0c"
          "\u4e0d\u80fd\u5f53\u7b49\u4ef7\u6027\u8bc1\u660e\u3002" % total)
    return EXIT_FAIL if with_fail else EXIT_PASS


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def build_parser():
    parser = argparse.ArgumentParser(
        prog="run_evals.py",
        description=(
            "project-dept evals runner.  Modes: static (default) = validate evals/evals.json "
            "schema; grade = DEPRECATED verbatim keyword grading (rejects answers that make "
            "the right point in different words; 12/12 false FAILs on 12 real answers, "
            "backlog P-15-8); compare = grade two answer directories A/B; judge = anonymise "
            "<case>-<arm>-r<rep>.txt answers into blind-judge prompts + score templates + arm "
            "map; tally = paired per-rubric statistics with a Wilson 95% CI."),
        epilog=(
            "Keyword grading is not an acceptance criterion: it rejects correct answers that "
            "use different wording (measured 12/12 false FAILs on real answers, P-15-8).  "
            "Use --mode judge to produce anonymous grading material, then --mode tally to "
            "compute paired per-rubric statistics."))
    parser.add_argument("--mode", choices=("static", "grade", "compare", "judge", "tally"),
                        default="static",
                        help="static (default) | grade (deprecated) | compare | judge | tally")
    parser.add_argument("--evals", default=None,
                        help="path to evals.json (default: <skill>/evals/evals.json)")
    parser.add_argument("--case", default=None,
                        help="case id (grade mode) or case selector (judge mode, id or unique prefix)")
    parser.add_argument("--answer", default=None, help="answer/transcript text file (grade mode)")
    parser.add_argument("--with", dest="with_dir", default=None, help="run directory of the with-skill answers")
    parser.add_argument("--without", dest="without_dir", default=None, help="run directory of the without-skill answers")
    parser.add_argument("--answers", default=None,
                        help="answer directory of <case>-<with|without>-r<rep>.txt files (judge mode)")
    parser.add_argument("--out", default=None,
                        help="output directory (judge mode) / judge output directory (tally mode)")
    parser.add_argument("--seed", type=int, default=7,
                        help="shuffle seed for reproducible anonymisation (judge mode, default 7)")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="print the tally result as a single JSON document on stdout")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.mode == "static":
        return cmd_static(args)
    if args.mode == "grade":
        return cmd_grade(args)
    if args.mode == "compare":
        return cmd_compare(args)
    if args.mode == "judge":
        return cmd_judge(args)
    if args.mode == "tally":
        return cmd_tally(args)
    print("[x] 未知 mode：%s" % args.mode)
    return EXIT_CANNOT


if __name__ == "__main__":
    sys.exit(main())
