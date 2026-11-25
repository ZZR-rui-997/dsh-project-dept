# -*- coding: utf-8 -*-
"""tests/test_dept_gate_json.py — dept_gate.py 的 --json 输出契约。

回归点：v1.1.0 的 --json 把 `[anchor]` 行、分隔线、人类可读结论一起打到 stdout，
只有最后一行能解析；复核脚本只能靠「取末行」，很脆。v1.1.1 起 `--json` 的 stdout
必须是**纯 JSON**（整段可直接 json.loads）。

运行:
    python -m unittest tests.test_dept_gate_json -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
GATE = PKG_ROOT / "scripts" / "dept_gate.py"

CONFIG = """{
  "project_name": "gate-json-fixture",
  "ledger_dir": "_team",
  "board_file": "看板.md",
  "flow_file": "工作流.md",
  "register_file": "交付登记簿.md",
  "baseline_file": "基准清单.md",
  "role_dir": "岗位",
  "required_roles": ["lead", "audit", "reviewer"],
  "artefact_dir": "out",
  "scratch_patterns": ["probe_*"]
}
"""

BOARD = """# 看板

## 当前板块

板块 9「gate json 夹具」。

## 未完成事项（债务账本）

- [x] **D1** 夹具里的已完成债
"""


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def make_project(base: Path) -> Path:
    root = base / "gate-json-fixture"
    root.mkdir(parents=True)
    write(root / "dept.config.json", CONFIG)
    team = root / "_team"
    write(team / "看板.md", BOARD)
    write(team / "工作流.md", "# 工作流\n\n夹具。\n")
    write(team / "交付登记簿.md", "# 交付登记簿\n\n| 日期 | 结论 |\n|---|---|\n")
    write(team / "基准清单.md", "# 基准清单\n\n| # | 说法 | 出处 | 等级 |\n|---|---|---|---|\n")
    for role in ("lead", "audit", "reviewer"):
        write(team / "岗位" / f"{role}.md", f"# {role}\n\n夹具岗位卡。\n")
    (team / "out").mkdir(parents=True, exist_ok=True)
    return root


def run_gate(*args):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(GATE), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )


class TestDeptGateJson(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = make_project(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_json_stdout_is_pure_json(self):
        proc = run_gate("--root", self.root, "--json")
        # 整段 stdout 必须能解析（旧版会因为前面有 [anchor]/分隔线而失败）
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - 失败即回归
            self.fail("--json 的 stdout 不是纯 JSON：%s\n前 200 字符：%r" % (exc, proc.stdout[:200]))
        self.assertIn("anchor", data)
        self.assertIn("code", data)
        self.assertIn("warnings_list", data)
        self.assertIn("violations_list", data)
        self.assertEqual(data["code"], proc.returncode)

    def test_anchor_has_five_fields(self):
        proc = run_gate("--root", self.root, "--json")
        data = json.loads(proc.stdout)
        parts = data["anchor"].split()
        self.assertEqual(len(parts), 5, parts)
        self.assertTrue(parts[0].startswith("config="), parts)

    def test_human_mode_still_prints_anchor(self):
        proc = run_gate("--root", self.root)
        self.assertIn("[anchor]", proc.stdout)
        self.assertIn("结论：", proc.stdout)


if __name__ == "__main__":
    unittest.main()
