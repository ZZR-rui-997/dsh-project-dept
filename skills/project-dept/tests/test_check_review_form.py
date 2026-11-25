# -*- coding: utf-8 -*-
"""tests/test_check_review_form.py — scripts/check_review_form.py 的单元测试。

标准库 only（unittest + subprocess + tempfile），不依赖项目夹具。
每个用例都用 tempfile 现造一份复核单文本，再跑真实 CLI，断言退出码与文案；
这样「把任何一条规则回退」都会让对应用例失败。

Run:
    python -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
CHECKER = os.path.join(SKILL_ROOT, "scripts", "check_review_form.py")
PYTHON = sys.executable

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

DEF_START = "HASH aaaaaaaaaaaa FILES 30 ROOT /tmp/demo"
DEF_END = "HASH aaaaaaaaaaaa FILES 30 ROOT /tmp/demo"


def build_form(
    snap_start=DEF_START,
    snap_end=DEF_END,
    conclusion="- 两次是否一致：一致（整个复核期包未被改动）",
    verdict="通过但要修",
    verdict_block=None,
    section1_title="## 1. 我的独立结论（在打开作者自检之前完成）",
    with_section2=True,
    evidence_rows=True,
    problem_rows=True,
    extra_problem_row="",
    section2_extra="",
    independence_sentence=True,
    evidence_row_count=2,
):
    """造一份结构完整的复核单；各参数用来定点破坏某一条规则。"""
    lines = ["# 复核单 `demo`（盲审）", "", "## 0. 我看了什么", ""]
    lines.append("- 盲审包：`_team/review/blind/demo/`")
    if snap_start:
        lines.append(snap_start)
    if snap_end:
        lines.append(snap_end)
    if conclusion:
        lines.append(conclusion)

    lines += ["", section1_title, ""]
    if verdict_block is not None:
        lines += list(verdict_block)
    else:
        lines.append("- **判定**：%s" % verdict)

    lines += ["", "- 我独立做了什么（带命令）：", ""]
    lines += ["| # | 我重算/重跑/重查了什么 | 方法或命令 | 结果 |", "|---|---|---|---|"]
    if evidence_rows:
        rows = [
            "| 1 | 重跑检查器 | `python scripts/check_skill.py --root .` | exit 1 |",
            "| 2 | 核产物 sha256 | `sha256sum 产物.py` | 与快照一致 |",
        ]
        lines += rows[:max(1, evidence_row_count)]

    lines += ["", "- **发现的问题**：", ""]
    if problem_rows:
        lines += [
            "| # | 位置（文件:行/节） | 问题 | 为什么是问题（证据） | 严重度 |",
            "|---|---|---|---|---|",
            "| 1 | 结果表第 2 行 | 条件写反 | 复跑后输出与预期不符 | 重要 |",
        ]
        if extra_problem_row:
            lines.append(extra_problem_row)

    if with_section2:
        lines += ["", "## 2. 对照作者自检（判完之后才写）", ""]
        if independence_sentence:
            lines.append(
                "- 独立性：§1 的独立结论写完之后，我才打开作者自检文件对照。"
            )
        lines.append("- 作者声称做过的，我验证的结果：一致")

    if section2_extra:
        lines += ["", section2_extra]
    return "\n".join(lines) + "\n"


class ReviewFormCheckerTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="review_form_")

    def tearDown(self):
        for name in os.listdir(self._tmpdir):
            try:
                os.unlink(os.path.join(self._tmpdir, name))
            except OSError:  # pragma: no cover - 极端清理失败不掩盖测试结果
                pass
        try:
            os.rmdir(self._tmpdir)
        except OSError:  # pragma: no cover
            pass

    # ---------------------------------------------------------------- 辅助

    def make_file(self, text, name="复核单.md"):
        path = os.path.join(self._tmpdir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return path

    def run_cli(self, path, json_mode=False):
        cmd = [PYTHON, CHECKER, path]
        if json_mode:
            cmd.append("--json")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=120,
        )

    # ---------------------------------------------------------------- 1 合格

    def test_valid_form_exits_zero(self):
        r = self.run_cli(self.make_file(build_form()))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("结论：合规（exit 0）", r.stdout)
        self.assertEqual(r.stdout.count("[ok]"), 7)

    # ------------------------------------------------------- 2 缺快照

    def test_missing_snapshot_is_defect(self):
        text = build_form(snap_start="", snap_end="")
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("§0 缺被验快照", r.stdout)
        self.assertIn("无法证明期间文件没被改过", r.stdout)

    # ----------------------------------------------- 3 两次取值不同

    def test_differing_hash_without_inconsistency_is_defect(self):
        text = build_form(
            snap_end="HASH bbbbbbbbbbbb FILES 30 ROOT /tmp/demo",
            conclusion="- 两次取值：一致",
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("不一致", r.stdout)

    def test_differing_hash_with_inconsistency_and_limit_is_ok(self):
        text = build_form(
            snap_end="HASH bbbbbbbbbbbb FILES 30 ROOT /tmp/demo",
            conclusion="- 两次不一致，本轮结论只对 start 版有效",
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_differing_hash_without_limit_is_defect(self):
        text = build_form(
            snap_end="HASH bbbbbbbbbbbb FILES 30 ROOT /tmp/demo",
            conclusion="- 两次不一致",
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("限定", r.stdout)

    def test_differing_files_count_without_limit_is_defect(self):
        text = build_form(
            snap_end="HASH aaaaaaaaaaaa FILES 29 ROOT /tmp/demo",
            conclusion="- 两次不一致",
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("限定", r.stdout)

    # ------------------------------------------------------ 4 判定

    def test_verdict_fail_is_legal(self):
        r = self.run_cli(self.make_file(build_form(verdict="不通过")))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_verdict_basically_pass_is_illegal(self):
        r = self.run_cli(self.make_file(build_form(verdict="基本通过")))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("未给出合法判定", r.stdout)

    def test_verdict_far_from_keyword_is_defect(self):
        text = build_form(verdict_block=["- **判定**：", "", "", "", "", "- 通过"])
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("附近 3 行", r.stdout)

    def test_verdict_on_next_line_is_accepted(self):
        text = build_form(verdict_block=["- **判定**：", "- 通过"])
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_verdict_explicit_bold_is_accepted(self):
        text = build_form(verdict_block=["- **判定**：**通过但要修**"])
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 0, r.stdout)

    # ------------------------------------------- 5 判通过却有必改项

    def test_pass_with_unfixed_mustfix_is_defect(self):
        text = build_form(
            verdict="通过",
            extra_problem_row="| 2 | `C.py:20` | 条件写反 | 复跑 exit 1 | 必改 |",
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("矛盾", r.stdout)

    def test_pass_with_fixed_mustfix_is_ok(self):
        text = build_form(
            verdict="通过",
            extra_problem_row="| 2 | `C.py:20` | 条件写反 | 已修：复跑 exit 0 | 必改 |",
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 0, r.stdout)

    # ------------------------------------------------- 6 禁用证据词

    def test_banned_phrase_reports_line_number(self):
        bad = "- 这个改动看起来合理，我就没重算。"
        text = build_form(section2_extra=bad)
        expected_line = text.splitlines().index(bad) + 1
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("看起来合理", r.stdout)
        self.assertIn("第 %d 行" % expected_line, r.stdout)

    # -------------------------------------------------- 7 机械证据

    def test_no_evidence_rows_is_defect(self):
        text = build_form(evidence_rows=False)
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("§1 缺机械证据", r.stdout)

    # ---------------------------------------------------- 8 真问题

    def test_no_problem_table_and_no_exemption_is_defect(self):
        text = build_form(problem_rows=False)
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("无法证明复核人真找了问题", r.stdout)

    # ------------------------------------------------- 9 独立性

    def test_missing_self_check_section_is_defect(self):
        text = build_form(section1_title="## 1. 我的独立结论", with_section2=False)
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("无法确认独立性", r.stdout)

    def test_self_check_without_qualifier_is_defect(self):
        text = build_form(section1_title="## 1. 我的独立结论（对照自检）", with_section2=False)
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("附近没有", r.stdout)

    # --------------------------------- 9b v1.3.1 收紧：标题行不算证据
    def test_template_heading_alone_is_not_independence(self):
        text = build_form(independence_sentence=False)
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("标题行与模板提示行不算证据", r.stdout)

    # ------------------------- 9c v1.3.2 修：句中含提示词不该被当成模板行
    def test_sentence_with_hint_word_in_middle_is_still_evidence(self):
        """正文声明句里顺带出现「要求 / 说明」等词，不能被整句跳过（A1 必改①）。"""
        sentence = (
            "- 独立性：我按要求先写 §1 的独立结论，之后才打开作者自检文件对照。"
        )
        text = build_form(section2_extra=sentence)
        # 关掉默认那句，只留这一句含「要求」的声明
        text = text.replace(
            "- 独立性：§1 的独立结论写完之后，我才打开作者自检文件对照。\n", ""
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_template_label_line_is_not_independence(self):
        """以「必填」开头的模板标签行，即使写着「自检之前」也不算证据。"""
        text = build_form(
            independence_sentence=False,
            section2_extra="- 必填：先在打开作者自检之前写完结论",
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_blockquote_hint_line_is_not_independence(self):
        """> 引用块的提示语同样不算证据。"""
        text = build_form(
            independence_sentence=False,
            section2_extra="> 提示：在打开自检之前写完独立结论",
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)

    # ------------------------- 9d v1.3.3：引用/括号开头的合法声明不能被整行丢掉
    def test_parenthesised_declaration_is_accepted(self):
        text = build_form(
            independence_sentence=False,
            section2_extra="- (1) 我按要求先写 §1 的独立结论，之后才打开作者自检文件对照。",
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_blockquote_declaration_is_accepted(self):
        text = build_form(
            independence_sentence=False,
            section2_extra="> 我按要求先写 §1 的独立结论，之后才打开作者自检文件对照。",
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_bullet_hint_label_line_is_not_independence(self):
        """`- 提示：…自检之前…` 这种模板骨架行不能白送通过（v1.3.3 遗留建议）。"""
        text = build_form(
            independence_sentence=False,
            section2_extra="- 提示：先在打开作者自检之前写完结论",
        )
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)

    # ------------------- 9e v1.3.4：标记叠加时也要认得出模板痕迹 / 不误伤合法句
    HINT_FORMS = [
        "- 提示：先在打开作者自检之前写完结论",
        "> 提示：先在打开作者自检之前写完结论",
        "> **提示**：先在打开作者自检之前写完结论",
        ">**提示**",
        "（**提示**）",
        "> - **提示**",
        "> - 提示：先看自检再写",
        "- **必填**：先看自检再写结论",
        "（示例）先看自检再写结论",
        "> **说明**：先看自检再写结论",
    ]
    LEGIT_FORMS = [
        "- 独立性：我按要求先写 §1 的独立结论，之后才打开作者自检文件对照。",
        "> 我按要求先写 §1 的独立结论，之后才打开作者自检文件对照。",
        "- (1) 我按要求先写 §1 的独立结论，之后才打开作者自检文件对照。",
        "> **我按要求先写 §1 的独立结论，之后才打开作者自检文件对照。**",
        "- **独立性**：先写独立结论，之后才看作者自检。",
    ]

    def test_hint_forms_are_not_independence(self):
        """十种模板痕迹写法都必须判缺陷（含引用块/列表/强调符叠加）。"""
        for form in self.HINT_FORMS:
            with self.subTest(form=form):
                text = build_form(independence_sentence=False, section2_extra=form)
                r = self.run_cli(self.make_file(text))
                self.assertEqual(r.returncode, 1, "%r ->\n%s" % (form, r.stdout))

    def test_legit_forms_are_independence(self):
        """五种合法写法都必须通过（不能被标记剥离逻辑误伤）。"""
        for form in self.LEGIT_FORMS:
            with self.subTest(form=form):
                text = build_form(independence_sentence=False, section2_extra=form)
                r = self.run_cli(self.make_file(text))
                self.assertEqual(r.returncode, 0, "%r ->\n%s" % (form, r.stdout))

    def test_violation_reports_body_line_not_heading(self):
        """违规时要指出真正的正文行，而不是被跳过的标题行（A1 必改②）。"""
        body = "- 我看了作者自检后写出上面的结论。"
        text = build_form(
            section1_title="## 1. 我的独立结论（对照作者自检）",
            with_section2=False,
            section2_extra=body,
        )
        expected_line = text.splitlines().index(body) + 1
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("第 %d 行" % expected_line, r.stdout)

    def test_single_evidence_row_is_not_enough(self):
        text = build_form(evidence_row_count=1)
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("至少 2 行真实数据", r.stdout)

    # ------------------------------------------------- 10 --json

    def test_json_mode_clean_and_exit_code_matches(self):
        r = self.run_cli(self.make_file(build_form()), json_mode=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("REVIEW FORM CHECK", r.stdout)
        self.assertTrue(r.stdout.strip().startswith("{"))
        payload = json.loads(r.stdout)
        self.assertEqual(payload["exit_code"], r.returncode)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["defects"], [])
        self.assertEqual(payload["warnings"], [])

    def test_json_mode_defect_payload(self):
        text = build_form(section2_extra="- 这个改动看起来合理。")
        r = self.run_cli(self.make_file(text), json_mode=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["exit_code"], 1)
        self.assertFalse(payload["ok"])
        self.assertTrue(any(d["rule"] == "banned" for d in payload["defects"]))
        for defect in payload["defects"]:
            self.assertIn("rule", defect)
            self.assertIn("line", defect)
            self.assertIn("message", defect)
        self.assertEqual(payload["warnings"], [])

    # --------------------------------------------- 11 文件不存在

    def test_missing_file_exits_two(self):
        missing = os.path.join(self._tmpdir, "no_such_review.md")
        r = self.run_cli(missing)
        self.assertEqual(r.returncode, 2)
        self.assertIn("文件不存在", r.stdout)

    def test_missing_file_json_exits_two(self):
        missing = os.path.join(self._tmpdir, "no_such_review.md")
        r = self.run_cli(missing, json_mode=True)
        self.assertEqual(r.returncode, 2)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["exit_code"], 2)
        self.assertFalse(payload["ok"])

    # ------------------------------------------- 12 中文 UTF-8

    def test_chinese_text_not_mojibake(self):
        bad = "- 作者说跑通了，不用复算。"
        text = build_form(section2_extra=bad)
        r = self.run_cli(self.make_file(text))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertNotIn("\ufffd", r.stdout)
        self.assertIn("作者说", r.stdout)
        self.assertIn("跑通了", r.stdout)


if __name__ == "__main__":
    unittest.main()