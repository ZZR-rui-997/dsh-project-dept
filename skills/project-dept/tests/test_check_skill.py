# -*- coding: utf-8 -*-
"""tests/test_check_skill.py — scripts/check_skill.py 的单元测试（标准库 only）。

覆盖 8 项检查的关键判据与 CLI 契约（exit 0/1/2）。除最后一条 smoke 外，全部用
tempfile.mkdtemp() 造夹具，不依赖真实包路径。

运行:
    python -m unittest tests.test_check_skill -v
    python -m unittest discover -s tests
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
CHECK_SKILL = PKG_ROOT / "scripts" / "check_skill.py"


# ---------------------------------------------------------------- CLI 辅助


def run_cli(*args):
    """以子进程方式跑 check_skill.py，强制 UTF-8 输出。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(CHECK_SKILL), *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(PKG_ROOT),
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- 夹具


SKILL_MD = """---
name: {name}
description: 测试夹具：一个最小合法 skill 包，用来验证静态自检器的通过路径。
metadata:
  version: {version}
  tags: [test]
---

# {name}

最小夹具正文。

## 加载

- 先读 `static/core/principles.md`
- 需要时读 `references/ref.md`
"""

MANIFEST = """name: {name}
version: {version}
description: >
  test fixture

always_load:
  - static/core/principles.md

references:
  on_demand:
    - condition: test only
      path: references/ref.md

quality_tools:
  gate_script: scripts/dept_gate.py
  audit_script: scripts/check_doc.py
"""

README = "# {name}\n\n当前版本 {version}。\n"
README_EN = "# {name}\n\nCurrent version: {version}\n"


def make_pkg(base: Path, dirname: str = "project-dept", version: str = "1.0.0",
             skill_name=None) -> Path:
    """在 base 下造一个最小合法包，返回包目录。"""
    name = skill_name or dirname
    root = base / dirname
    write_text(root / "SKILL.md", SKILL_MD.format(name=name, version=version))
    write_text(root / "manifest.yaml", MANIFEST.format(name=name, version=version))
    write_text(root / "README.md", README.format(name=name, version=version))
    write_text(root / "README_EN.md", README_EN.format(name=name, version=version))
    write_text(root / "static" / "core" / "principles.md", "# principles\n\n夹具内容。\n")
    write_text(root / "references" / "ref.md", "# ref\n\n夹具内容。\n")
    write_text(root / "scripts" / "dept_gate.py", "# placeholder\n")
    write_text(root / "scripts" / "check_doc.py", "# placeholder\n")
    (root / "tests").mkdir(parents=True, exist_ok=True)
    write_text(
        root / "evals" / "evals.json",
        json.dumps(
            {
                "skill_name": name,
                "evals": [
                    {"id": "case-1", "prompt": "问题一", "expected_output": "答案一"},
                    {"id": "case-2", "prompt": "问题二", "expected_output": "答案二"},
                ],
            },
            ensure_ascii=False,
        ),
    )
    return root


# ---------------------------------------------------------------- 测试类


class CheckSkillCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="check_skill_"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)

    # -- 通用断言

    def assertExit(self, proc, expected):
        self.assertEqual(
            proc.returncode,
            expected,
            msg="stdout:\n%s\nstderr:\n%s" % (proc.stdout, proc.stderr),
        )

    @staticmethod
    def nonempty_lines(proc):
        return [line for line in proc.stdout.splitlines() if line.strip()]

    # -- 1. 最小合法包

    def test_minimal_valid_package_passes(self):
        pkg = make_pkg(self.tmp)
        proc = run_cli("--root", pkg)
        self.assertExit(proc, 0)
        lines = self.nonempty_lines(proc)
        self.assertTrue(lines[0].startswith("SKILL CHECK · "), lines[0])
        self.assertEqual(lines[-1], "结论：通过（exit 0）")
        self.assertNotIn("[x]", proc.stdout)
        self.assertEqual(proc.stderr.strip(), "")

    # -- 2. name 与目录名不符

    def test_name_mismatch_detected(self):
        pkg = make_pkg(self.tmp, skill_name="other-dept")
        proc = run_cli("--root", pkg)
        self.assertExit(proc, 1)
        self.assertIn("name", proc.stdout)
        self.assertIn("不符", proc.stdout)
        self.assertEqual(self.nonempty_lines(proc)[-1], "结论：有缺陷（exit 1）")

    # -- 2b. name 与目录名不符，但显式放开（盲审副本场景）

    def test_name_mismatch_downgraded_with_flag(self):
        pkg = make_pkg(self.tmp, skill_name="other-dept")
        proc = run_cli("--root", pkg, "--allow-dirname-mismatch")
        self.assertExit(proc, 0)
        self.assertIn("不符", proc.stdout)
        self.assertIn("[!]", proc.stdout)
        self.assertEqual(self.nonempty_lines(proc)[-1], "结论：通过（exit 0）")

    # -- 3. 版本漂移

    def test_version_drift_detected(self):
        pkg = make_pkg(self.tmp, version="1.0.14")
        write_text(pkg / "README.md", "# project-dept\n\n当前版本 1.0.13。\n")
        proc = run_cli("--root", pkg)
        self.assertExit(proc, 1)
        self.assertIn("1.0.13", proc.stdout)
        self.assertIn("1.0.14", proc.stdout)
        self.assertIn("版本不一致", proc.stdout)

    # -- 4. SKILL.md 引用不存在的资产

    def test_missing_referenced_asset_detected(self):
        pkg = make_pkg(self.tmp)
        skill = pkg / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8") + "\n\n详见 `references/nope.md`。\n",
            encoding="utf-8",
        )
        proc = run_cli("--root", pkg)
        self.assertExit(proc, 1)
        self.assertIn("references/nope.md", proc.stdout)
        self.assertIn("SKILL.md:", proc.stdout)

    # -- 4b. manifest 声明的资产缺失（抓死引用）

    def test_missing_manifest_asset_detected(self):
        pkg = make_pkg(self.tmp)
        (pkg / "references" / "ref.md").unlink()
        proc = run_cli("--root", pkg)
        self.assertExit(proc, 1)
        self.assertIn("manifest.yaml:", proc.stdout)
        self.assertIn("references/ref.md", proc.stdout)

    # -- 5. 禁出现文件名

    def test_forbidden_filename_detected(self):
        pkg = make_pkg(self.tmp)
        skill = pkg / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8") + "\n\n回归见 VERIFICATION.md。\n",
            encoding="utf-8",
        )
        proc = run_cli("--root", pkg)
        self.assertExit(proc, 1)
        self.assertIn("VERIFICATION.md", proc.stdout)
        self.assertIn("[x]", proc.stdout)

    # -- 6. evals.json 坏 JSON

    def test_broken_evals_json_detected(self):
        pkg = make_pkg(self.tmp)
        write_text(pkg / "evals" / "evals.json", "{ this is not json")
        proc = run_cli("--root", pkg)
        self.assertExit(proc, 1)
        self.assertIn("evals", proc.stdout)
        self.assertIn("JSON", proc.stdout)

    # -- 6b. evals 字段缺失 / id 重复

    def test_evals_missing_field_and_duplicate_id_detected(self):
        pkg = make_pkg(self.tmp)
        write_text(
            pkg / "evals" / "evals.json",
            json.dumps(
                {
                    "evals": [
                        {"id": "dup", "prompt": "p1", "expected_output": "o1"},
                        {"id": "dup", "prompt": "p2", "expected_output": "o2"},
                        {"id": "case-3", "prompt": "p3"},
                    ]
                },
                ensure_ascii=False,
            ),
        )
        proc = run_cli("--root", pkg)
        self.assertExit(proc, 1)
        self.assertIn("id 重复", proc.stdout)
        self.assertIn("expected_output", proc.stdout)

    # -- 7. 目录不存在 → exit 2

    def test_missing_root_exits_two(self):
        proc = run_cli("--root", self.tmp / "does-not-exist")
        self.assertExit(proc, 2)
        self.assertIn("无法执行", proc.stdout)
        self.assertEqual(self.nonempty_lines(proc)[-1], "结论：未执行（exit 2）")

    # -- 7b. SKILL.md 缺失 → exit 2

    def test_missing_skill_md_exits_two(self):
        pkg = make_pkg(self.tmp)
        (pkg / "SKILL.md").unlink()
        proc = run_cli("--root", pkg)
        self.assertExit(proc, 2)
        self.assertIn("SKILL.md", proc.stdout)
        self.assertEqual(self.nonempty_lines(proc)[-1], "结论：未执行（exit 2）")

    # -- 8. 入口正文超硬上限：exit 1（v1.2.0 起不是警告）

    def test_skill_body_over_hard_limit_is_defect(self):
        pkg = make_pkg(self.tmp)
        skill = pkg / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8") + "\n" + ("超预算填充" * 1200) + "\n",
            encoding="utf-8",
        )
        proc = run_cli("--root", pkg)
        self.assertExit(proc, 1)
        self.assertIn("硬上限 3000", proc.stdout)
        self.assertEqual(self.nonempty_lines(proc)[-1], "结论：有缺陷（exit 1）")

        proc_json = run_cli("--root", pkg, "--json")
        self.assertExit(proc_json, 1)
        data = json.loads(proc_json.stdout)
        self.assertFalse(data["ok"])
        self.assertEqual(data["budget"]["skill_md_limit"], 3000)
        self.assertGreater(data["budget"]["skill_md_tokens"], 3000)

    # -- 9. --json 契约

    def test_json_output_is_machine_readable(self):
        pkg = make_pkg(self.tmp)
        proc = run_cli("--root", pkg, "--json")
        self.assertExit(proc, 0)
        data = json.loads(proc.stdout)  # stdout 上必须只有 JSON
        for key in ("ok", "defects", "warnings", "budget"):
            self.assertIn(key, data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["defects"], [])
        self.assertIsInstance(data["warnings"], list)
        self.assertIsInstance(data["budget"], dict)
        self.assertGreater(data["budget"]["skill_md_tokens"], 0)
        self.assertEqual(data["budget"]["skill_md_limit"], 3000)
        self.assertEqual(data["budget"]["total_limit"], 9000)

        broken = make_pkg(self.tmp, dirname="broken-pkg", skill_name="other")
        proc_broken = run_cli("--root", broken, "--json")
        self.assertExit(proc_broken, 1)
        data_broken = json.loads(proc_broken.stdout)
        self.assertFalse(data_broken["ok"])
        self.assertTrue(data_broken["defects"])

    # -- 10. 真实包 smoke（唯一依赖真实包的用例）

    def test_real_package_smoke(self):
        """真实包：CLI 必须能跑通，输出结构与退出码自洽。

        任务单原本要求「真实包 exit 0」。本检查器对真实包当前给出 1 条 [x]
        （README.md 的变更记录里出现不随包分发的文件名 VERIFICATION.md，属既有缺陷，
        按任务单要求不修改现有文件、记入汇报由 Lead 决定）。因此这里断言「能跑通且
        自洽」；一旦该缺陷被 Lead 处置、真实包变干净，下面的分支自动升级为断言 exit 0。
        """
        proc = run_cli()
        self.assertNotEqual(proc.returncode, 2, msg=proc.stdout + proc.stderr)
        self.assertIn(proc.returncode, (0, 1), msg=proc.stdout + proc.stderr)

        lines = self.nonempty_lines(proc)
        self.assertTrue(lines[0].startswith("SKILL CHECK · "), lines[0])
        expected_word = "通过" if proc.returncode == 0 else "有缺陷"
        self.assertEqual(
            lines[-1], "结论：%s（exit %d）" % (expected_word, proc.returncode)
        )
        if proc.returncode == 0:
            self.assertNotIn("[x]", proc.stdout)
        else:
            self.assertIn("[x]", proc.stdout)

        proc_json = run_cli("--json")
        self.assertEqual(proc_json.returncode, proc.returncode)
        data = json.loads(proc_json.stdout)
        self.assertEqual(data["ok"], proc.returncode == 0)
        self.assertIn("budget", data)
        self.assertEqual(data["exit_code"], proc.returncode)


# ---------------------------------------------------------------- v1.2.1 回归
#
# 这四条对应 v1.2.1 修掉的四个"判据可被绕过 / 会腐化"的问题。
# 冻结纪律：把对应修复回退掉，这些用例必须失败（不是恒真）。


class TestV121Regression(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ck121_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _add_tool(self, pkg: Path, rel: str, line: str) -> None:
        mf = pkg / "manifest.yaml"
        mf.write_text(mf.read_text(encoding="utf-8").rstrip("\n") + "\n" + line + "\n",
                      encoding="utf-8")
        write_text(pkg / rel, "# placeholder\n")

    def test_kana_padding_hits_hard_limit(self):
        """假名曾按 3.5 字符/token 估算：4000 个假名 ≈1142 tokens，exit 0 放行。"""
        pkg = make_pkg(self.tmp)
        skill = pkg / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\n" + ("あ" * 4000) + "\n",
                         encoding="utf-8")
        proc = run_cli("--root", pkg)
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        self.assertIn("硬上限 3000", proc.stdout)

    def test_hangul_and_emoji_arms_of_the_same_check(self):
        """谚文与 emoji 走同一段码位判定；各造一份恰好越线的填充。"""
        for filler, label in ((("한" * 3200), "hangul"), (("🌸" * 3200), "emoji")):
            pkg = make_pkg(self.tmp, dirname="p-" + label)
            skill = pkg / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\n" + filler + "\n",
                             encoding="utf-8")
            proc = run_cli("--root", pkg)
            self.assertEqual(proc.returncode, 1, msg="%s: %s" % (label, proc.stdout))
            self.assertIn("硬上限 3000", proc.stdout)

    def test_fragment_bloat_is_a_defect(self):
        """轴片段以前完全不计入预算：往片段里灌 20,000 字仍然 exit 0。"""
        pkg = make_pkg(self.tmp)
        mf = pkg / "manifest.yaml"
        mf.write_text(
            mf.read_text(encoding="utf-8").rstrip("\n")
            + "\n\naxes:\n  deliverable:\n    values:\n"
              "      document: static/fragments/deliverable/document.md\n",
            encoding="utf-8",
        )
        write_text(pkg / "static" / "fragments" / "deliverable" / "document.md",
                   "# 文档交付\n\n" + ("填" * 20000) + "\n")
        proc = run_cli("--root", pkg)
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        self.assertIn("单次开工实际加载", proc.stdout)
        self.assertIn("硬上限 14000", proc.stdout)

    def test_extensionless_tool_declaration_missing_is_a_defect(self):
        """`scripts/no_such_gate` 这种不带扩展名的声明以前整条逃检。"""
        pkg = make_pkg(self.tmp)
        mf = pkg / "manifest.yaml"
        mf.write_text(
            mf.read_text(encoding="utf-8").replace(
                "gate_script: scripts/dept_gate.py",
                "gate_script: scripts/no_such_gate",
            ),
            encoding="utf-8",
        )
        proc = run_cli("--root", pkg)
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        self.assertIn("quality_tools", proc.stdout)
        self.assertIn("找不到实体", proc.stdout)

    def test_stale_tool_count_phrase_is_a_defect(self):
        """实体 3 个脚本、文档里还写"只有俩" ⇒ 缺陷（计数已腐化）。"""
        pkg = make_pkg(self.tmp)
        self._add_tool(pkg, "scripts/run_evals.py", "  eval_runner: scripts/run_evals.py")
        readme = pkg / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8") + "\n历史说明：两个脚本足以覆盖。\n",
            encoding="utf-8",
        )
        proc = run_cli("--root", pkg)
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        self.assertIn("计数已腐化", proc.stdout)
        self.assertIn("README.md", proc.stdout)

    def test_stale_phrase_in_non_entry_doc_is_a_defect(self):
        """规则不能只在三份入口文档生效：references/ 里的旧措辞一样算缺陷（v1.2.2）。"""
        pkg = make_pkg(self.tmp)
        self._add_tool(pkg, "scripts/run_evals.py", "  eval_runner: scripts/run_evals.py")
        write_text(pkg / "references" / "scaffold.md",
                   "# scaffold\n\n## 6. Wire the two scripts\n")
        proc = run_cli("--root", pkg)
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        self.assertIn("references/scaffold.md", proc.stdout)
        self.assertIn("计数已腐化", proc.stdout)

    def test_two_tools_package_stays_clean(self):
        """反面：实体就是 2 个时，旧措辞不该被误伤。"""
        pkg = make_pkg(self.tmp)
        readme = pkg / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8") + "\n历史说明：两个脚本足以覆盖。\n",
            encoding="utf-8",
        )
        proc = run_cli("--root", pkg)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout)


class TestV130ManifestSyntax(unittest.TestCase):
    """v1.3.0：第 8 项「manifest 语法」。

    动机：manifest.yaml 曾两次被写成断行（plain scalar 的续行里带 "key: "），
    而 build_payload / 正则扫描都发现不了，一路带着坏 YAML 发版。这一族错误
    只能靠真的解析一遍才能抓住。
    """

    def setUp(self):
        import tempfile as _tf
        self.tmp = Path(_tf.mkdtemp(prefix="check_skill_v130yaml_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def assertExit(self, proc, expected):
        self.assertEqual(
            proc.returncode,
            expected,
            msg="exit=%d expected=%d\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, expected, proc.stdout, proc.stderr),
        )

    def _append_broken_continuation(self, pkg: Path) -> None:
        mpath = pkg / "manifest.yaml"
        text = mpath.read_text(encoding="utf-8")
        text += "\n  demo_note: this is a plain scalar\n    Nested: continuation with a colon\n"
        mpath.write_text(text, encoding="utf-8")

    def test_broken_yaml_is_a_defect(self):
        pkg = make_pkg(self.tmp)
        self._append_broken_continuation(pkg)
        proc = run_cli("--root", str(pkg))
        self.assertExit(proc, 1)
        out = proc.stdout + proc.stderr
        self.assertIn("不是合法 YAML", out)
        self.assertIn("manifest 语法", out)

    def test_clean_package_passes_and_lists_eight_checks(self):
        pkg = make_pkg(self.tmp)
        proc = run_cli("--root", str(pkg))
        self.assertExit(proc, 0)
        out = proc.stdout + proc.stderr
        self.assertIn("[8/8]", out)
        self.assertIn("manifest 语法", out)

    def test_heuristic_flags_plain_scalar_continuation(self):
        import importlib.util as _ilu
        script = Path(__file__).resolve().parent.parent / "scripts" / "check_skill.py"
        spec = _ilu.spec_from_file_location("_check_skill_under_test", str(script))
        mod = _ilu.module_from_spec(spec)
        import sys as _sys
        _sys.modules[spec.name] = mod  # dataclasses 需要它先登记，否则 __module__ 查不到
        spec.loader.exec_module(mod)

        broken = "a:\n  key: value one\n    Nested: looks like a mapping\n"
        self.assertTrue(mod._yaml_suspicion(broken))

        legit = (
            "list:\n"
            "  - condition: something\n"
            "    path: references/ref.md\n"
            "struct:\n"
            "  child: value\n"
            "folded: >-\n"
            "  first line\n"
            "  Key: this colon inside a block scalar is fine\n"
        )
        self.assertFalse(mod._yaml_suspicion(legit))


class TestV131DuplicateTopLevelKeys(unittest.TestCase):
    """v1.3.1（c1 轻微项）：重复顶层键必须报缺陷。

    PyYAML 对重复键不报错、后者静默覆盖前者 —— 只看「解析成功」等于没查。
    """

    def setUp(self):
        import tempfile as _tf
        self.tmp = Path(_tf.mkdtemp(prefix="check_skill_v131dup_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_duplicate_top_level_key_is_a_defect(self):
        pkg = make_pkg(self.tmp)
        mpath = pkg / "manifest.yaml"
        text = mpath.read_text(encoding="utf-8")
        mpath.write_text(text + "\nversion: 9.9.9\n", encoding="utf-8")
        proc = run_cli("--root", str(pkg))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        out = proc.stdout + proc.stderr
        self.assertIn("出现多次", out)
        self.assertIn("静默覆盖", out)
        self.assertIn("version", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestV130Regression(unittest.TestCase):
    """v1.3.0（P-15-5）：读不出来的 .md 不许静默跳过。

    以前 read_text() 返回 None 时两处循环都 continue —— 一个 GBK 编码的
    .md 就能让「陈旧措辞 / 禁名」这两条规则对它永不生效（复核人实测逃检）。
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="check_skill_v130_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def assertExit(self, proc, expected):
        self.assertEqual(
            proc.returncode,
            expected,
            msg="exit=%d expected=%d\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, expected, proc.stdout, proc.stderr),
        )

    def _add_third_tool(self, pkg: Path) -> None:
        mpath = pkg / "manifest.yaml"
        text = mpath.read_text(encoding="utf-8")
        assert "quality_tools:" in text
        text = text.replace(
            "quality_tools:", "quality_tools:\n  skill_lint_script: scripts/check_skill.py"
        )
        mpath.write_text(text, encoding="utf-8")
        write_text(pkg / "scripts" / "check_skill.py", "# placeholder\n")

    def test_gbk_md_escaping_stale_scan_is_a_defect(self):
        pkg = make_pkg(self.tmp)
        self._add_third_tool(pkg)  # 3 个脚本才会触发陈旧计数扫描
        (pkg / "references" / "gbk.md").write_bytes("# 中文标题\n\n内容\n".encode("gbk"))
        proc = run_cli("--root", str(pkg))
        self.assertExit(proc, 1)
        out = proc.stdout + proc.stderr
        self.assertIn("不是 UTF-8", out)
        self.assertIn("references/gbk.md", out)

    def test_gbk_readme_is_a_defect(self):
        pkg = make_pkg(self.tmp)
        (pkg / "README.md").write_bytes("# 中文说明\n".encode("gbk"))
        proc = run_cli("--root", str(pkg))
        self.assertExit(proc, 1)
        out = proc.stdout + proc.stderr
        self.assertIn("不是 UTF-8", out)
        self.assertIn("README.md", out)

    def test_all_utf8_package_stays_clean(self):
        pkg = make_pkg(self.tmp)
        self._add_third_tool(pkg)
        proc = run_cli("--root", str(pkg))
        self.assertExit(proc, 0)
        self.assertNotIn("不是 UTF-8", proc.stdout + proc.stderr)

