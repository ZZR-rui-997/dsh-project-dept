# -*- coding: utf-8 -*-
"""Tests for ``scripts/run_evals.py`` (the project-dept evals runner).

Deliberately stdlib-only ``unittest``: the runner is driven as a real subprocess so the
tests check exit codes and stdout exactly the way a user / CI would.  The real
``evals/evals.json`` is only read, never modified: every bad-schema case is a temp copy.

Run:
    python -m unittest tests.test_run_evals -v
    python -m unittest discover -s tests -v
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
RUNNER = os.path.join(SKILL_ROOT, "scripts", "run_evals.py")
REAL_EVALS = os.path.join(SKILL_ROOT, "evals", "evals.json")

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def load_json(path=REAL_EVALS):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def gold_answer(case):
    """A synthetic answer that contains every must_include and no must_exclude."""
    return "\n".join(case["assertions"]["must_include"])


def run_runner(*args):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, RUNNER, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=SKILL_ROOT,
    )


def import_runner():
    spec = importlib.util.spec_from_file_location("run_evals_under_test", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TempEvalsMixin:
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="pd_evals_")
        self.tmp = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def write_variant(self, mutate, name="evals.json"):
        data = load_json()
        mutate(data)
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        return path

    def static(self, *extra):
        return run_runner("--mode", "static", *extra)


class TestStaticRealPackage(unittest.TestCase):
    def test_real_evals_static_passes_and_prints_seven_briefs(self):
        proc = run_runner("--mode", "static")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("static 校验通过", proc.stdout)
        cases = load_json()["evals"]
        self.assertEqual(len(cases), 7)
        for case in cases:
            self.assertIn("CASE: " + case["id"], proc.stdout)
        self.assertEqual(proc.stdout.count("【给 judge 的评分要求"), 7)
        self.assertEqual(proc.stdout.count("token 预算提示"), 7)

    def test_default_mode_is_static(self):
        proc = run_runner()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("static 校验通过", proc.stdout)

    def test_gold_expected_output_passes_its_own_assertions(self):
        # Derivation invariant: every include is in expected_output, no exclude is.  If this
        # breaks, the assertions were not extracted from the frozen criterion.
        for case in load_json()["evals"]:
            gold = case["expected_output"]
            for item in case["assertions"]["must_include"]:
                self.assertIn(item, gold, "%s: include '%s'" % (case["id"], item))
            for item in case["assertions"]["must_exclude"]:
                self.assertNotIn(item, gold, "%s: exclude '%s'" % (case["id"], item))


class TestStaticBadSchema(TempEvalsMixin, unittest.TestCase):
    def assert_invalid(self, path, needle):
        proc = self.static("--evals", path)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn(needle, proc.stdout)
        self.assertIn("exit 2", proc.stdout)

    def test_missing_assertions_named(self):
        def mutate(data):
            del data["evals"][0]["assertions"]
        self.assert_invalid(self.write_variant(mutate), "assertions")

    def test_duplicate_id_named(self):
        def mutate(data):
            data["evals"][1]["id"] = data["evals"][0]["id"]
        self.assert_invalid(self.write_variant(mutate), "id 重复")

    def test_tautological_include_rejected(self):
        def mutate(data):
            data["evals"][0]["assertions"]["must_include"].append("的")
        self.assert_invalid(self.write_variant(mutate), "恒真串")

    def test_include_not_extractable_from_expected_output(self):
        def mutate(data):
            data["evals"][0]["assertions"]["must_include"].append("这句判据里根本没有")
        self.assert_invalid(self.write_variant(mutate), "expected_output 里找不到")

    def test_exclude_present_in_expected_output_rejected(self):
        def mutate(data):
            data["evals"][0]["assertions"]["must_exclude"].append("验收标准")
        self.assert_invalid(self.write_variant(mutate), "出现在 expected_output 里")

    def test_too_few_assertions_rejected(self):
        def mutate(data):
            data["evals"][2]["assertions"]["must_include"] = ["三段式"]
            data["evals"][2]["assertions"]["must_exclude"] = ["跳过 L2"]
        self.assert_invalid(self.write_variant(mutate), "至少")

    def test_bad_axis_value_named(self):
        def mutate(data):
            data["evals"][0]["assertions"]["axes"]["rigor"] = "super-critical"
        self.assert_invalid(self.write_variant(mutate), "不是 manifest.yaml 的真实轴值")

    def test_bad_step_named(self):
        def mutate(data):
            data["evals"][0]["assertions"]["steps"] = ["0-gate", "9-invented"]
        self.assert_invalid(self.write_variant(mutate), "不是六步编号")

    def test_missing_budget_named(self):
        def mutate(data):
            del data["evals"][0]["budget_hint"]
        self.assert_invalid(self.write_variant(mutate), "budget_hint")

    def test_utf8_bom_rejected(self):
        path = self.write_variant(lambda data: None, name="bom.json")
        with open(path, "rb") as fh:
            raw = fh.read()
        with open(path, "wb") as fh:
            fh.write(b"\xef\xbb\xbf" + raw)
        self.assert_invalid(path, "BOM")

    def test_broken_json_named(self):
        path = os.path.join(self.tmp, "broken.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json,")
        self.assert_invalid(path, "不是合法 JSON")


class TestGradeMode(TempEvalsMixin, unittest.TestCase):
    def grade(self, case_id, text):
        answer = os.path.join(self.tmp, "answer.md")
        with open(answer, "w", encoding="utf-8") as fh:
            fh.write(text)
        return run_runner("--mode", "grade", "--case", case_id, "--answer", answer)

    def test_gold_answer_passes_for_every_case(self):
        for case in load_json()["evals"]:
            proc = self.grade(case["id"], gold_answer(case))
            self.assertEqual(proc.returncode, 0, case["id"] + "\n" + proc.stdout)
            self.assertEqual(proc.stdout.strip().splitlines()[-1],
                             "CASE %s PASS" % case["id"])
            self.assertEqual(proc.stdout.count("[x]"), 0,
                             "%s: no assertion should fail\n%s" % (case["id"], proc.stdout))

    def test_missing_one_include_fails_with_marker(self):
        case = load_json()["evals"][0]
        answer = "\n".join(case["assertions"]["must_include"][1:])
        proc = self.grade(case["id"], answer)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("[x]", proc.stdout)
        self.assertIn(case["assertions"]["must_include"][0], proc.stdout)
        self.assertEqual(proc.stdout.strip().splitlines()[-1], "CASE %s FAIL" % case["id"])

    def test_present_exclude_fails_even_with_all_includes(self):
        case = load_json()["evals"][1]
        answer = gold_answer(case) + "\n" + case["assertions"]["must_exclude"][0]
        proc = self.grade(case["id"], answer)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("直接 FAIL", proc.stdout)
        self.assertEqual(proc.stdout.strip().splitlines()[-1], "CASE %s FAIL" % case["id"])

    def test_unknown_case_exits_2(self):
        proc = self.grade("no-such-case", "whatever")
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("不存在", proc.stdout)

    def test_missing_answer_file_exits_2(self):
        proc = run_runner("--mode", "grade", "--case", "full-package",
                          "--answer", os.path.join(self.tmp, "nope.md"))
        self.assertEqual(proc.returncode, 2, proc.stdout)

    def test_empty_answer_fails_not_crashes(self):
        proc = self.grade("mechanism-choice", "")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stdout.strip().splitlines()[-1],
                         "CASE mechanism-choice FAIL")

    def test_without_required_args_exits_2(self):
        self.assertEqual(run_runner("--mode", "grade").returncode, 2)
        self.assertEqual(run_runner("--mode", "grade", "--case", "full-package").returncode, 2)


class TestCompareMode(TempEvalsMixin, unittest.TestCase):
    def make_side(self, name, break_case=None):
        root = os.path.join(self.tmp, name)
        for case in load_json()["evals"]:
            case_dir = os.path.join(root, case["id"])
            os.makedirs(case_dir, exist_ok=True)
            answer = gold_answer(case)
            if case["id"] == break_case:
                answer = "\n".join(case["assertions"]["must_include"][1:])
            with open(os.path.join(case_dir, "answer.md"), "w", encoding="utf-8") as fh:
                fh.write(answer)
        return root

    def test_both_sides_graded_and_counts_printed(self):
        with_dir = self.make_side("with")
        without_dir = self.make_side("without", break_case="full-package")
        proc = run_runner("--mode", "compare", "--with", with_dir, "--without", without_dir)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("WITH", proc.stdout)
        self.assertIn("WITHOUT", proc.stdout)
        self.assertIn("TOTAL PASS", proc.stdout)
        self.assertIn("7/7", proc.stdout)
        self.assertIn("6/7", proc.stdout)
        self.assertIn("不能当等价性证明", proc.stdout)

    def test_failure_on_with_side_exits_1(self):
        with_dir = self.make_side("with_bad", break_case="checker-must-fail")
        without_dir = self.make_side("without_ok")
        proc = run_runner("--mode", "compare", "--with", with_dir, "--without", without_dir)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAIL", proc.stdout)

    def test_unreadable_directory_exits_2(self):
        proc = run_runner("--mode", "compare",
                          "--with", os.path.join(self.tmp, "missing-a"),
                          "--without", os.path.join(self.tmp, "missing-b"))
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("目录不可读", proc.stdout)

    def test_missing_answer_file_is_reported_not_crashed(self):
        empty_dir = os.path.join(self.tmp, "empty")
        os.makedirs(empty_dir)
        with_dir = self.make_side("with")
        proc = run_runner("--mode", "compare", "--with", with_dir, "--without", empty_dir)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("MISSING", proc.stdout)


class TestResolveAnswerPath(unittest.TestCase):
    def test_single_case_falls_back_to_answer_md(self):
        runner = import_runner()
        with tempfile.TemporaryDirectory(prefix="pd_evals_") as root:
            path = os.path.join(root, "answer.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("x")
            self.assertEqual(runner.resolve_answer_path(root, "solo", 1), path)
            self.assertIsNone(runner.resolve_answer_path(root, "solo", 7))


JUDGE_CASES = ("baseline-is-wrong", "executor-self-complete", "mechanism-choice")


def real_case(case_id):
    for case in load_json()["evals"]:
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def answer_body(case_id, arm, rep):
    """Unique body text with no arm name in it (so leaking an arm is detectable)."""
    index = (0 if arm == "with" else 2) + rep
    return "正文标记 %s-%d" % (case_id, index)


def make_answers(root, cases=JUDGE_CASES, reps=(1, 2)):
    for case_id in cases:
        for arm in ("with", "without"):
            for rep in reps:
                path = os.path.join(root, "%s-%s-r%d.txt" % (case_id, arm, rep))
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(answer_body(case_id, arm, rep) + "\n")


def read_text(path):
    with open(path, encoding="utf-8-sig") as fh:
        return fh.read()


def write_pair(root, case_key, mapping, scores, items=None):
    if items is None:
        items = [{"id": "R%d" % (index + 1), "text": "要点 %d" % (index + 1)}
                 for index in range(4)]
    payload = {"case": case_key, "items": items, "scores": scores}
    for name, data in (("scores_%s.json" % case_key, payload),
                       ("map_%s.json" % case_key, mapping)):
        with open(os.path.join(root, name), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)


def parse_stdout_json(proc):
    return json.loads(proc.stdout)


class TestJudgeMode(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="pd_judge_")
        self.tmp = self._tmpdir.name
        self.answers = os.path.join(self.tmp, "answers")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(self.answers)

    def tearDown(self):
        self._tmpdir.cleanup()

    def judge(self, *extra):
        return run_runner("--mode", "judge", "--answers", self.answers,
                          "--out", self.out, *extra)

    def test_end_to_end_writes_prompt_template_and_map(self):
        make_answers(self.answers)
        proc = self.judge("--seed", "7")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for case_id in JUDGE_CASES:
            prompt_path = os.path.join(self.out, "judge_prompt_%s.md" % case_id)
            template_path = os.path.join(self.out, "scores_template_%s.json" % case_id)
            map_path = os.path.join(self.out, "map_%s.json" % case_id)
            self.assertTrue(os.path.isfile(prompt_path), prompt_path)
            self.assertTrue(os.path.isfile(template_path), template_path)
            self.assertTrue(os.path.isfile(map_path), map_path)
            prompt = read_text(prompt_path).lower()
            self.assertNotIn("with", prompt, "%s: prompt leaks an arm name" % case_id)
            self.assertNotIn("without", prompt, "%s: prompt leaks an arm name" % case_id)
            self.assertEqual(prompt.count("===== 答复 ".lower()), 8)  # 4 blocks, start + end
            self.assertEqual(prompt.count("开始 =====".lower()), 4)
            for arm in ("with", "without"):
                for rep in (1, 2):
                    self.assertIn(answer_body(case_id, arm, rep).lower(), prompt)
            template = load_json(template_path)
            mapping = load_json(map_path)
            self.assertEqual(template["case"], case_id)
            self.assertEqual(len(template["items"]), 4)
            self.assertEqual(sorted(template["scores"]), ["A", "B", "C", "D"])
            self.assertEqual(sorted(mapping), ["A", "B", "C", "D"])
            self.assertEqual(set(mapping.values()),
                             {"with-r1", "with-r2", "without-r1", "without-r2"})
            self.assertEqual(set(template["scores"]), set(mapping))
            for row in template["scores"].values():
                self.assertEqual(row, [None, None, None, None])

    def test_anonymised_order_is_not_the_file_order(self):
        make_answers(self.answers)
        proc = self.judge("--seed", "7")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        canonical = ["with-r1", "with-r2", "without-r1", "without-r2"]
        orders = []
        for case_id in JUDGE_CASES:
            mapping = load_json(os.path.join(self.out, "map_%s.json" % case_id))
            orders.append([mapping[label] for label in sorted(mapping)])
        self.assertTrue(any(order != canonical for order in orders),
                        "every case kept the original arm/rep order: %s" % orders)

    def test_same_seed_gives_identical_anonymisation(self):
        make_answers(self.answers)
        self.assertEqual(self.judge("--seed", "7").returncode, 0)
        first = {cid: read_text(os.path.join(self.out, "map_%s.json" % cid))
                 for cid in JUDGE_CASES}
        second_out = os.path.join(self.tmp, "out2")
        proc = run_runner("--mode", "judge", "--answers", self.answers,
                          "--out", second_out, "--seed", "7")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for case_id in JUDGE_CASES:
            self.assertEqual(first[case_id],
                             read_text(os.path.join(second_out, "map_%s.json" % case_id)))

    def test_bad_answer_filename_exits_2_and_names_it(self):
        make_answers(self.answers, cases=("baseline-is-wrong",))
        bad = os.path.join(self.answers, "notes.txt")
        with open(bad, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("not an answer\n")
        proc = self.judge()
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("notes.txt", proc.stdout + proc.stderr)
        self.assertIn("不符合", proc.stdout + proc.stderr)

    def test_unequal_arm_counts_exit_2(self):
        for rep in (1, 2):
            path = os.path.join(self.answers, "baseline-is-wrong-with-r%d.txt" % rep)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(answer_body("baseline-is-wrong", "with", rep) + "\n")
        path = os.path.join(self.answers, "baseline-is-wrong-without-r1.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(answer_body("baseline-is-wrong", "without", 1) + "\n")
        proc = self.judge()
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("不一致", proc.stdout + proc.stderr)

    def test_case_selector_filters_output(self):
        make_answers(self.answers)
        proc = self.judge("--case", "mech")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        written = sorted(os.listdir(self.out))
        self.assertEqual(written, [
            "judge_prompt_mechanism-choice.md",
            "map_mechanism-choice.json",
            "scores_template_mechanism-choice.json",
        ])

    def test_rubric_derived_from_must_include_has_four_items(self):
        runner = import_runner()
        case = real_case("baseline-is-wrong")
        case.pop("rubric", None)  # v1.3.5 起真 case 自带 rubric；这里专测「没有 rubric 时怎么派生」
        rubric = runner.build_rubric(case)
        self.assertEqual(len(rubric), 4)
        joined = "\n".join(rubric)
        for item in case["assertions"]["must_include"]:
            self.assertIn(item, joined)
        self.assertNotIn(case["expected_output"], joined)
        for item in rubric:
            self.assertTrue(item.startswith("要点："), item)

    def test_explicit_rubric_overrides_derivation(self):
        data = load_json()
        target = data["evals"][0]
        custom = ["自定义要点一", "自定义要点二", "自定义要点三", "自定义要点四"]
        target["rubric"] = custom
        evals_path = os.path.join(self.tmp, "evals_rubric.json")
        with open(evals_path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False)
        make_answers(self.answers, cases=(target["id"],))
        proc = self.judge("--evals", evals_path, "--case", target["id"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        template = load_json(os.path.join(self.out, "scores_template_%s.json" % target["id"]))
        self.assertEqual([item["text"] for item in template["items"]], custom)


class TestRubricField(unittest.TestCase):
    """v1.3.5：evals.json 自带 rubric 必须被优先采用；抄参考答案/条数不对要被静态校验抓住。"""

    def test_real_cases_use_explicit_rubric(self):
        runner = import_runner()
        for cid in ("full-package", "baseline-is-wrong", "mechanism-choice"):
            case = real_case(cid)
            self.assertIn("rubric", case, cid)
            self.assertEqual(len(case["rubric"]), 4, cid)
            self.assertEqual(runner.build_rubric(case), case["rubric"], cid)

    def test_rubric_copied_from_expected_output_is_rejected(self):
        runner = import_runner()
        data = load_json()
        case = data["evals"][0]
        case["rubric"] = [case["expected_output"][:20]] + case["rubric"][1:]
        errors, _warnings = runner.validate(data, runner.load_manifest_axes())
        joined = "\n".join(errors)
        self.assertIn("rubric", joined)
        self.assertTrue(("逐字抄" in joined) or ("参考答案" in joined), joined)

    def test_rubric_wrong_length_is_rejected(self):
        runner = import_runner()
        data = load_json()
        case = data["evals"][0]
        case["rubric"] = case["rubric"][:3]
        errors, _warnings = runner.validate(data, runner.load_manifest_axes())
        self.assertTrue(any("rubric" in e for e in errors), errors)


class TestTallyMode(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="pd_tally_")
        self.tmp = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def tally(self, *extra):
        return run_runner("--mode", "tally", "--out", self.tmp, *extra)

    def test_hand_computed_paired_statistics(self):
        # with totals 4+4=8, without totals 2+3=5 (4 rubric items x 2 reps each).
        write_pair(
            self.tmp, "c1",
            {"A": "with-r1", "B": "without-r1", "C": "with-r2", "D": "without-r2"},
            {"A": [1, 1, 1, 1], "B": [0, 1, 0, 1],
             "C": [1, 1, 1, 1], "D": [1, 1, 0, 1]})
        proc = self.tally("--json")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        stats = parse_stdout_json(proc)
        self.assertEqual(stats["per_arm"]["with"], 8)
        self.assertEqual(stats["per_arm"]["without"], 5)
        self.assertEqual(stats["per_arm"]["max"], 8)
        self.assertEqual(stats["cases"][0]["with"], 8)
        self.assertEqual(stats["cases"][0]["without"], 5)
        pairs = stats["per_arm"]["pairs"]
        self.assertEqual(pairs["n"], 2)
        self.assertEqual(pairs["with_better"], 2)
        self.assertEqual(pairs["without_better"], 0)
        self.assertEqual(pairs["tie"], 0)
        self.assertEqual(pairs["win_rate"], 1.0)
        self.assertAlmostEqual(stats["wilson"]["lower"], 1.0 / (1.0 + 1.96 ** 2 / 2.0), places=6)
        self.assertAlmostEqual(stats["wilson"]["lower"], 0.342, places=3)
        self.assertAlmostEqual(stats["wilson"]["upper"], 1.0, places=6)
        self.assertEqual(stats["wilson"]["n"], 2)
        self.assertTrue(any("方向性" in warning for warning in stats["warnings"]))
        item_hits = {row["item"]: (row["with"], row["without"]) for row in stats["items"]}
        self.assertEqual(item_hits["R3"], (2, 0))

    def test_null_score_exits_2_and_names_the_cell(self):
        write_pair(self.tmp, "c1",
                   {"A": "with-r1", "B": "without-r1"},
                   {"A": [1, None, 1, 1], "B": [1, 1, 1, 1]})
        proc = self.tally()
        self.assertEqual(proc.returncode, 2, proc.stdout)
        combined = proc.stdout + proc.stderr
        self.assertIn("null", combined)
        self.assertIn("R2", combined)
        self.assertIn("标签 A", combined)
        self.assertIn("c1", combined)

    def test_blanks_in_every_case_are_named_together(self):
        """v1.3.1（c1 轻微项）：多个 case 半填时，要一次点名所有受影响的 case。

        旧行为是遇到第一个 case 就抛错，后面的 case 空格永远不会被报出来。
        """
        write_pair(self.tmp, "c1",
                   {"A": "with-r1", "B": "without-r1"},
                   {"A": [1, None, 1, 1], "B": [1, 1, 1, 1]})
        write_pair(self.tmp, "c2",
                   {"A": "with-r1", "B": "without-r1"},
                   {"A": [1, 1, 1, 1], "B": [1, 1, None, 1]})
        proc = self.tally()
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        combined = proc.stdout + proc.stderr
        self.assertIn("null", combined)
        self.assertIn("c1", combined)
        self.assertIn("c2", combined)
        self.assertIn("2 个 case", combined)

    def test_unequal_arm_counts_exit_2(self):
        write_pair(self.tmp, "c1",
                   {"A": "with-r1", "B": "without-r1", "C": "with-r2"},
                   {"A": [1, 1, 1, 1], "B": [1, 1, 1, 1], "C": [1, 1, 1, 1]})
        proc = self.tally()
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("两臂 rep 不一致", proc.stdout + proc.stderr)

    def test_json_stdout_is_a_single_document(self):
        write_pair(self.tmp, "c1",
                   {"A": "with-r1", "B": "without-r1"},
                   {"A": [1, 1, 1, 1], "B": [0, 0, 0, 0]})
        proc = self.tally("--json")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        stats = json.loads(proc.stdout)  # must parse whole stdout, no banner mixed in
        for key in ("cases", "items", "pairs", "per_arm", "wilson", "warnings"):
            self.assertIn(key, stats)
        self.assertTrue(proc.stdout.lstrip().startswith("{"), proc.stdout[:80])
        self.assertNotIn("===", proc.stdout)

    def test_unpaired_files_exit_2(self):
        write_pair(self.tmp, "c1",
                   {"A": "with-r1", "B": "without-r1"},
                   {"A": [1, 1, 1, 1], "B": [0, 0, 0, 0]})
        os.remove(os.path.join(self.tmp, "map_c1.json"))
        proc = self.tally()
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("配对缺失", proc.stdout + proc.stderr)

    def test_score_outside_0_or_1_exits_2(self):
        write_pair(self.tmp, "c1",
                   {"A": "with-r1", "B": "without-r1"},
                   {"A": [1, 2, 1, 1], "B": [0, 0, 0, 0]})
        proc = self.tally()
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("分数非法", proc.stdout + proc.stderr)


class TestGradeDeprecation(unittest.TestCase):
    def test_pass_still_works_and_prints_deprecated(self):
        case = load_json()["evals"][0]
        with tempfile.TemporaryDirectory(prefix="pd_grade_") as tmp:
            answer = os.path.join(tmp, "answer.md")
            with open(answer, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(gold_answer(case))
            proc = run_runner("--mode", "grade", "--case", case["id"], "--answer", answer)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("DEPRECATED", proc.stdout)
        self.assertIn("P-15-8", proc.stdout)
        self.assertIn("CASE %s PASS" % case["id"], proc.stdout)

    def test_fail_still_exits_1_and_prints_deprecated(self):
        case = load_json()["evals"][0]
        with tempfile.TemporaryDirectory(prefix="pd_grade_") as tmp:
            answer = os.path.join(tmp, "answer.md")
            with open(answer, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("完全无关的答案")
            proc = run_runner("--mode", "grade", "--case", case["id"], "--answer", answer)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("DEPRECATED", proc.stdout)
        self.assertIn("CASE %s FAIL" % case["id"], proc.stdout)


class TestHelpDocumentsFourModes(unittest.TestCase):
    def test_help_lists_judge_tally_and_deprecation_reason(self):
        proc = run_runner("--help")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for token in ("static", "grade", "compare", "judge", "tally",
                      "DEPRECATED", "P-15-8", "Wilson"):
            self.assertIn(token, proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
