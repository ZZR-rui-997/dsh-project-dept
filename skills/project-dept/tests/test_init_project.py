#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for scripts/init_project.py.

These run the real CLI in a subprocess against a temporary project and then run
the real gate on the result — the point is to prove the scaffold is *accepted by
the gate*, not that a blob of text was written.

Regression discipline for this package: every fix must ship with a test that
fails if the fix is reverted. The cases below were each written after an
observed failure mode:

* baseline legend containing the untraced marker made every fresh project show
  a false "1 untraced baseline" warning (the gate scans lines, including the
  legend) — guards ``test_fresh_scaffold_has_no_warnings``;
* writing a fake current package just to make the gate exit 0 would be lying to
  the gate — guards ``test_no_package_asks_for_a_decision``;
* an idempotent re-run must not silently rewrite hand-edited ledgers — guards
  ``test_rerun_does_not_overwrite``.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
INIT = os.path.join(SCRIPTS, "init_project.py")
GATE = os.path.join(SCRIPTS, "dept_gate.py")
FORM = os.path.join(SCRIPTS, "check_review_form.py")
PY = sys.executable


def run(args):
    return subprocess.run([PY] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def gate(root):
    """Return (exit_code, payload_or_None, stdout)."""
    proc = run([GATE, "--root", root, "--json"])
    payload = None
    for line in reversed(proc.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                payload = json.loads(line)
            except ValueError:
                pass
            break
    return proc.returncode, payload, proc.stdout


class InitProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="initproj_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def make(self, name="demo"):
        root = os.path.join(self.tmp, name)
        os.makedirs(root)
        return root

    def init(self, root, *extra):
        proc = run([INIT, "--root", root] + list(extra))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    # ---- the gate is the contract -------------------------------------
    def test_fresh_scaffold_is_accepted_by_the_gate(self):
        root = self.make()
        self.init(root, "--desc", "smoke", "--open-package", "package 1")
        code, payload, out = gate(root)
        self.assertEqual(code, 0, out)
        self.assertIsNotNone(payload, out)

    def test_fresh_scaffold_has_no_warnings(self):
        # Regression: the baseline legend used to contain the untraced marker,
        # so every fresh project immediately showed "1 untraced baseline".
        root = self.make()
        self.init(root, "--open-package", "package 1")
        code, payload, out = gate(root)
        self.assertEqual(code, 0, out)
        self.assertEqual(payload.get("warnings_list", []), [], out)

    def test_no_package_asks_for_a_decision(self):
        root = self.make()
        self.init(root)
        code, payload, out = gate(root)
        self.assertEqual(code, 2, out)
        self.assertIn("D0", out)

    def test_open_debt_after_init_blocks(self):
        root = self.make()
        self.init(root, "--open-package", "package 1")
        board = os.path.join(root, "_team", "看板.md")
        with io.open(board, encoding="utf-8") as fh:
            text = fh.read()
        text = text.replace("- [x] **D0**",
                            "- [ ] **D1** deliberately open debt\n- [x] **D0**", 1)
        with io.open(board, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        code, payload, out = gate(root)
        self.assertEqual(code, 2, out)
        self.assertIn("D1", out)

    # ---- idempotence / safety ----------------------------------------
    def test_rerun_does_not_overwrite(self):
        root = self.make()
        self.init(root, "--open-package", "package 1")
        board = os.path.join(root, "_team", "看板.md")
        with io.open(board, "a", encoding="utf-8") as fh:
            fh.write("\nHAND-EDIT-MARKER\n")
        proc = run([INIT, "--root", root, "--json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["created"], [])
        self.assertTrue(result["skipped"])
        with io.open(board, encoding="utf-8") as fh:
            self.assertIn("HAND-EDIT-MARKER", fh.read())

    def test_force_overwrites(self):
        root = self.make()
        self.init(root, "--open-package", "package 1")
        board = os.path.join(root, "_team", "看板.md")
        with io.open(board, "a", encoding="utf-8") as fh:
            fh.write("\nHAND-EDIT-MARKER\n")
        proc = run([INIT, "--root", root, "--force", "--json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["overwritten"])
        with io.open(board, encoding="utf-8") as fh:
            self.assertNotIn("HAND-EDIT-MARKER", fh.read())

    def test_dry_run_writes_nothing(self):
        root = self.make()
        proc = run([INIT, "--root", root, "--dry-run", "--json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["dry_run"])
        self.assertEqual(sorted(os.listdir(root)), [])

    # ---- generated content --------------------------------------------
    def test_config_is_valid_json_and_named_after_dir(self):
        root = self.make("myproject")
        self.init(root)
        with io.open(os.path.join(root, "dept.config.json"), encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertEqual(cfg["project_name"], "myproject")
        self.assertEqual(cfg["ledger_dir"], "_team")
        self.assertIn("baseline_changelog", cfg)

    def test_config_env_notes_do_not_hardcode_a_machine_path(self):
        """v1.3.10: 默认环境提示必须是通用的。

        观察到的失效（v1.3.9 盲审）：生成的 config 里写死了本机 venv 绝对路径，
        与文档「只给通用环境提示 / 不写死本机路径」直接矛盾。
        """
        root = self.make()
        self.init(root)
        with io.open(os.path.join(root, "dept.config.json"), encoding="utf-8") as fh:
            notes = json.load(fh)["environment"]["notes"]
        joined = "\n".join(notes)
        for bad in ("pySimFrac", "Scripts\\python.exe", "E:\\"):
            self.assertNotIn(bad, joined, "默认环境提示里写死了本机路径：%r" % bad)
        self.assertGreaterEqual(len(notes), 3, notes)

    def test_env_note_option_appends_to_config(self):
        root = self.make()
        self.init(root, "--env-note", "本项目专用：解释器在 .venv 里")
        with io.open(os.path.join(root, "dept.config.json"), encoding="utf-8") as fh:
            notes = json.load(fh)["environment"]["notes"]
        self.assertIn("本项目专用：解释器在 .venv 里", notes)
        self.assertGreaterEqual(len(notes), 4, notes)

    def test_chinese_ledger_filenames_exist(self):
        root = self.make()
        self.init(root)
        ledger = os.path.join(root, "_team")
        for name in ("README.md", "工作流.md", "看板.md", "交付登记簿.md",
                     "基准清单.md", "基准变更记录.md"):
            self.assertTrue(os.path.isfile(os.path.join(ledger, name)), name)
        for name in ("lead.md", "audit.md", "reviewer.md"):
            self.assertTrue(os.path.isfile(os.path.join(ledger, "岗位", name)), name)

    def test_generated_review_template_is_not_vacuously_valid(self):
        # The review-form checker must still complain about a blank skeleton;
        # otherwise the template would be "passing" for the wrong reason.
        root = self.make()
        self.init(root)
        proc = run([FORM, os.path.join(root, "_team", "templates", "复核单.md")])
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    def test_roles_flag_controls_role_cards(self):
        root = self.make()
        self.init(root, "--roles", "lead,reviewer")
        roles = sorted(os.listdir(os.path.join(root, "_team", "岗位")))
        self.assertEqual(roles, ["lead.md", "reviewer.md"])
        with io.open(os.path.join(root, "dept.config.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["required_roles"], ["lead", "reviewer"])


if __name__ == "__main__":
    unittest.main()
