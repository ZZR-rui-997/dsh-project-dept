# -*- coding: utf-8 -*-
"""v1.3.5 P-15-9：基准作废必须有变更记录（dept_gate 7b）。

判据要挂在强制产出物上，否则 agent 拿到全文也不执行（v1.3.0 A/B 实测）。
这组用例把「作废行 + 缺记录 ⇒ 阻断」钉死；同时保证「没作废行时不误伤」。
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

import dept_gate  # noqa: E402


def build_project(root, baseline_lines, changelog_text=None, config_extra=None):
    """搭一个能被闸门跑通的最小项目；返回 None。"""
    ledger = os.path.join(root, "_team")
    os.makedirs(os.path.join(ledger, "岗位"), exist_ok=True)
    os.makedirs(os.path.join(ledger, "out"), exist_ok=True)

    board = [
        "# 看板",
        "",
        "## 当前板块",
        "板块 1（进行中）",
        "",
        "## 未完成事项（债务账本）",
        "- [x] D1 已处置",
        "",
        "## 方向复盘（pre-mortem）",
        "1. 若结论错，最可能错在方法层：已填",
        "",
    ]
    io.open(os.path.join(ledger, "看板.md"), "w", encoding="utf-8",
            newline="\n").write("\n".join(board))
    io.open(os.path.join(ledger, "工作流.md"), "w", encoding="utf-8",
            newline="\n").write("# 工作流\n\nStep 0 gate, then Steps 1-6\n")
    io.open(os.path.join(ledger, "交付登记簿.md"), "w", encoding="utf-8",
            newline="\n").write("# 交付登记簿\n\n| 日期 | 板块 | 结论 |\n|---|---|---|\n"
                                "| 2026-11-25 | 板块 1 | 通过 |\n")
    io.open(os.path.join(ledger, "基准清单.md"), "w", encoding="utf-8",
            newline="\n").write("# 基准清单\n\n" + "\n".join(baseline_lines) + "\n")
    for role in ("lead", "geom", "sim", "write", "audit", "reviewer"):
        io.open(os.path.join(ledger, "岗位", role + ".md"), "w", encoding="utf-8",
                newline="\n").write("# %s\n" % role)
    if changelog_text is not None:
        io.open(os.path.join(ledger, "基准变更记录.md"), "w", encoding="utf-8",
                newline="\n").write(changelog_text)

    config = {
        "project_name": os.path.basename(root),
        "ledger_dir": "_team",
        "board_file": "看板.md",
        "flow_file": "工作流.md",
        "register_file": "交付登记簿.md",
        "baseline_file": "基准清单.md",
        "role_dir": "岗位",
        "artefact_dir": "out",
        "required_roles": ["lead", "geom", "sim", "write", "audit", "reviewer"],
    }
    if config_extra:
        config.update(config_extra)
    io.open(os.path.join(root, "dept.config.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(config, ensure_ascii=False, indent=2) + "\n")


def run_gate(root):
    """跑闸门，返回 (exit_code, stdout)。"""
    buf = io.StringIO()
    old = sys.stdout
    try:
        sys.stdout = buf
        code = dept_gate.main(["--root", root])
    finally:
        sys.stdout = old
    return code, buf.getvalue()


class TestBaselineChangelogGate(unittest.TestCase):
    """作废行必须有变更记录，否则结构性阻断。"""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="gate7b_")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_retired_row_without_changelog_blocks(self):
        build_project(
            self.root,
            baseline_lines=["| B1 | 相关长度 | [已作废] 旧值 0.896 |", "| B2 | CFL | 0.25 |"],
            changelog_text=None,
            config_extra={"baseline_changelog": "基准变更记录.md"},
        )
        code, out = run_gate(self.root)
        self.assertEqual(code, dept_gate.EXIT_BLOCKED, out)
        self.assertIn("基准变更记录.md", out)
        self.assertIn("已作废", out)

    def test_retired_row_with_empty_changelog_blocks(self):
        build_project(
            self.root,
            baseline_lines=["| B1 | 相关长度 | [superseded] 旧值 0.896 |"],
            changelog_text="# 基准变更记录\n\n## B-01\n",
            config_extra={"baseline_changelog": "基准变更记录.md"},
        )
        code, out = run_gate(self.root)
        self.assertEqual(code, dept_gate.EXIT_BLOCKED, out)

    def test_retired_row_with_changelog_passes(self):
        build_project(
            self.root,
            baseline_lines=["| B1 | 相关长度 | [已作废] 旧值 0.896 |"],
            changelog_text=(
                "# 基准变更记录\n\n## B-01 相关长度\n\n- 旧值：0.896\n"
                "- 新值：按 acf_integral 口径复现 0.8958643\n- superseded_by：基准清单:112-128\n"
                "- 下游影响：第 3 章补口径\n- 重跑状态：不重跑\n"),
            config_extra={"baseline_changelog": "基准变更记录.md"},
        )
        code, out = run_gate(self.root)
        self.assertEqual(code, dept_gate.EXIT_PASS, out)
        self.assertIn("基准变更记录", out)

    def test_short_but_complete_record_passes(self):
        """v1.3.6：不许再用未声明的长度阈值 —— 38 字的完整记录也算有记录。"""
        build_project(
            self.root,
            baseline_lines=["| B1 | 相关长度 | [已作废] 0.896 |"],
            # 全文含标题只有 ~32 字符：只为证明「非空即算有记录」，撞不出任何长度阈值
            changelog_text="# 基准变更记录\n- 旧值 0.896 → 0.8958643\n",
            config_extra={"baseline_changelog": "基准变更记录.md"},
        )
        code, out = run_gate(self.root)
        self.assertEqual(code, dept_gate.EXIT_PASS, out)
        self.assertIn("基准变更记录", out)

    def test_uppercase_superseded_marker_is_detected(self):
        """v1.3.6：行首 [Superseded] 的大小写变体也要拦（表格路径本来就大小写不敏感）。"""
        build_project(
            self.root,
            baseline_lines=["[Superseded] 旧口径 CFL 0.32", "| B2 | CFL | 0.25 |"],
            changelog_text=None,
            config_extra={"baseline_changelog": "基准变更记录.md"},
        )
        code, out = run_gate(self.root)
        self.assertEqual(code, dept_gate.EXIT_BLOCKED, out)
        self.assertIn("已作废", out)

    def test_retired_row_without_config_key_blocks(self):
        """v1.3.6：有作废行但没配 baseline_changelog 不能只告警 —— 否则这条规矩可绕过。"""
        build_project(
            self.root,
            baseline_lines=["| B1 | 相关长度 | [已作废] 0.896 |"],
            changelog_text="# 基准变更记录\n\n- 旧值 0.896 → 新值 0.8958643\n",
            config_extra={},
        )
        code, out = run_gate(self.root)
        self.assertEqual(code, dept_gate.EXIT_BLOCKED, out)
        self.assertIn("baseline_changelog", out)

    def test_no_retired_rows_does_not_require_changelog(self):
        build_project(
            self.root,
            baseline_lines=["| B1 | 相关长度 | 0.8958643 |"],
            changelog_text=None,
            config_extra={"baseline_changelog": "基准变更记录.md"},
        )
        code, out = run_gate(self.root)
        self.assertEqual(code, dept_gate.EXIT_PASS, out)
        self.assertNotIn("基准变更记录", out)

    def test_marker_in_table_cell_without_leading_pipe_is_detected(self):
        """v1.3.7：合法表格行没有首竖线（B2 | ... | [已作废] |）也必须被拦。"""
        build_project(
            self.root,
            baseline_lines=["| ID | 名称 | 状态 |",
                            "B2 | 相关长度 | [已作废] |"],
            # 配了键但文件不存在：只有「真的认出了这行标记」才会阻断；认不出就会 exit 0
            changelog_text=None,
            config_extra={"baseline_changelog": "基准变更记录.md"},
        )
        code, out = run_gate(self.root)
        self.assertEqual(code, dept_gate.EXIT_BLOCKED, out)

    def test_marker_in_bullet_is_detected(self):
        """v1.3.7：`- [superseded]` 这种列表形态也要拦。"""
        build_project(
            self.root,
            baseline_lines=["- [superseded] CFL 0.32", "| B2 | CFL | 0.25 |"],
            changelog_text=None,
            config_extra={"baseline_changelog": "基准变更记录.md"},
        )
        code, out = run_gate(self.root)
        self.assertEqual(code, dept_gate.EXIT_BLOCKED, out)

    def test_marker_in_ordered_list_is_detected(self):
        """v1.3.7：`1. [已作废]` 这种有序列表形态也要拦。"""
        build_project(
            self.root,
            baseline_lines=["1. [已作废] 长宽比 14.2", "| B2 | CFL | 0.25 |"],
            changelog_text=None,
            config_extra={"baseline_changelog": "基准变更记录.md"},
        )
        code, out = run_gate(self.root)
        self.assertEqual(code, dept_gate.EXIT_BLOCKED, out)

    def test_marker_with_inner_spaces_is_detected(self):
        """v1.3.8：方括号内含空白（含全角空格）也是合法写法，必须拦。"""
        for raw in ("[ 已作废 ] 旧值 0.896", "[superseded ] CFL 0.32", "[\u3000superseded\u3000] 长宽比 14.2"):
            with self.subTest(marker=raw):
                root = tempfile.mkdtemp(prefix="gate8_")
                self.addCleanup(shutil.rmtree, root, True)
                build_project(
                    root,
                    baseline_lines=["| B2 | CFL | 0.25 |", raw],
                    changelog_text=None,
                    config_extra={"baseline_changelog": "基准变更记录.md"},
                )
                code, out = run_gate(root)
                self.assertEqual(code, dept_gate.EXIT_BLOCKED, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)