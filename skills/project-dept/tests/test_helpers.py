# -*- coding: utf-8 -*-
"""Tests for the pure helpers in the two department scripts.

Deliberately written with **unittest** (standard library) rather than pytest:
a test file that cannot run on the target machine is worse than no test file.
No project fixture and no python-docx needed.

Run:
    python -m unittest discover -s tests -v
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def load(name, relpath):
    path = os.path.join(SKILL_ROOT, relpath)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = load("dept_gate", os.path.join("scripts", "dept_gate.py"))
doc = load("check_doc", os.path.join("scripts", "check_doc.py"))


class TestClassifyGate(unittest.TestCase):
    def test_pass_when_clean(self):
        self.assertEqual(gate.classify_gate(True, []), gate.EXIT_PASS)

    def test_decision_when_only_debts(self):
        self.assertEqual(gate.classify_gate(True, [(1, "x")]), gate.EXIT_DECISION)

    def test_blocked_when_structural(self):
        self.assertEqual(gate.classify_gate(False, []), gate.EXIT_BLOCKED)

    def test_structural_wins_over_debts(self):
        self.assertEqual(gate.classify_gate(False, [(1, "x")]), gate.EXIT_BLOCKED)


class TestGlobMatch(unittest.TestCase):
    def test_cases(self):
        cases = [
            ("probe_x.py", "probe_*", True),
            ("_scan1.py", "_scan*", True),
            ("_summ.txt", "_summ*", True),
            ("probe_x.py", "*.py", True),
            ("probe_x.py", "_scan*", False),
            ("PROBE_X.PY", "probe_*", True),
            ("a.py", "?.py", True),
            ("ab.py", "?.py", False),
        ]
        for name, pat, expected in cases:
            with self.subTest(name=name, pattern=pat):
                self.assertIs(gate._glob_match(name, pat), expected)


class TestSectionLines(unittest.TestCase):
    def test_stops_at_next_heading(self):
        text = "## A\nline1\n## B\nline2\n"
        sec = gate.section_lines(text, r"^##\s*A")
        self.assertEqual([l for _, l in sec], ["## A", "line1"])

    def test_empty_when_absent(self):
        self.assertEqual(gate.section_lines("## B\nx\n", r"^##\s*A"), [])


class TestContiguity(unittest.TestCase):
    def test_cases(self):
        cases = [
            ([1, 2, 3], []),
            ([1, 3], [2]),
            ([2, 3, 4], []),   # 从最小值起算：单章文档不该报缺 1
            ([5, 7], [6]),
            ([], []),
            ([3, 3, 4], []),
        ]
        for nums, expected in cases:
            with self.subTest(nums=nums):
                self.assertEqual(doc.contiguity(nums), expected)


class TestHeadNumber(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(doc.head_number("2.3.1 方法"), "2.3.1")
        self.assertEqual(doc.head_number("2.3 方法"), "2.3")
        self.assertIsNone(doc.head_number("无编号的标题"))
        self.assertIsNone(doc.head_number(""))


class TestHeadingTexts(unittest.TestCase):
    def test_ignores_body_and_table_text(self):
        body = [
            ("2.1 第一节", "Heading 2", "p"),
            ("1.6 mm 不是小节号", "", "table"),
            ("普通正文", "", "p"),
        ]
        self.assertEqual(doc.heading_texts(body), ["2.1 第一节"])

    def test_recognises_chinese_style_name(self):
        body = [("2.1 第一节", "标题 2", "p")]
        self.assertEqual(doc.heading_texts(body), ["2.1 第一节"])


class TestLoadBannedTerms(unittest.TestCase):
    def test_missing_config_raises(self):
        # v1.0.3 起：配置拿不到不再静默返回 []（会让 A8 静默失效却仍 PASS）
        with self.assertRaises(ValueError):
            doc.load_banned_terms(None)
        with self.assertRaises(ValueError):
            doc.load_banned_terms(os.path.join(SKILL_ROOT, "no-such.json"))

    def test_bad_json_raises(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "bad.json")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write("{not json")
            with self.assertRaises(ValueError):
                doc.load_banned_terms(cfg)

    def test_reads_patterns_and_default_flags(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "dept.config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"banned_terms": [
                    {"pattern": "FooBar", "reason": "foobar", "flags": ""},
                    {"pattern": "WPS", "reason": "avoid"},
                ]}, f)
            terms = doc.load_banned_terms(cfg)
            self.assertEqual([t["pattern"] for t in terms], ["FooBar", "WPS"])
            self.assertEqual(terms[1]["flags"], "")

    def test_accepts_plain_strings(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "dept.config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"banned_terms": ["Foo"]}, f)
            terms = doc.load_banned_terms(cfg)
            self.assertEqual(terms[0]["pattern"], "Foo")


class TestCheckTerms(unittest.TestCase):
    BANNED = [{"pattern": "FooBar", "reason": "foobar", "flags": ""}]

    def test_flags_a_hit(self):
        ok, msg = doc.check_terms([("用了 FooBar 生成", "", "p")], "", self.BANNED)
        self.assertIs(ok, False)
        self.assertIn("FooBar", msg)

    def test_passes_when_clean(self):
        ok, msg = doc.check_terms([("用了 foobar 生成", "", "p")], "", self.BANNED)
        self.assertIs(ok, True)

    def test_none_when_not_executed(self):
        ok, msg = doc.check_terms([("x", "", "p")], "", [])
        self.assertIsNone(ok)          # None = 未执行，不是 PASS
        self.assertIn("未执行", msg)


class TestCheckCaptions(unittest.TestCase):
    CAP = r"^\s*图\s*(?:(?P<ch>\d+)\s*[-–.]\s*)?(?P<n>\d+)\s"
    REF = r"图\s*(?:(?P<ch>\d+)\s*[-–.]\s*)?(?P<n>\d+)"

    def test_bidirectional_ok(self):
        body = [
            ("图 2-1 示意图", "", "p"),
            ("如图 2-1 所示", "", "p"),
        ]
        ok, _ = doc.check_captions(body, "图", self.CAP, self.REF)
        self.assertIs(ok, True)

    def test_uncited_caption_is_failure(self):
        body = [
            ("图 2-1 示意图", "", "p"),
            ("图 2-2 另一张", "", "p"),
            ("如图 2-1 所示", "", "p"),
        ]
        ok, msg = doc.check_captions(body, "图", self.CAP, self.REF)
        self.assertIs(ok, False)
        self.assertIn("2", msg)

    def test_orphan_reference_is_failure(self):
        body = [("如图 2-5 所示", "", "p")]
        ok, msg = doc.check_captions(body, "图", self.CAP, self.REF)
        self.assertIs(ok, False)


class TestCheckSections(unittest.TestCase):
    def test_contiguous(self):
        body = [
            ("2.1 甲", "Heading 2", "p"),
            ("2.2 乙", "Heading 2", "p"),
        ]
        ok, _ = doc.check_sections(body)
        self.assertIs(ok, True)

    def test_gap_detected(self):
        body = [
            ("2.1 甲", "Heading 2", "p"),
            ("2.3 丙", "Heading 2", "p"),
        ]
        ok, msg = doc.check_sections(body)
        self.assertIs(ok, False)
        self.assertIn("2", msg)

    def test_no_heading_styles_is_not_a_pass(self):
        body = [("2.1 甲", "", "p")]
        ok, msg = doc.check_sections(body)
        self.assertIsNone(ok)      # 没有标题样式 -> 未执行，不硬猜


class TestNumberingRegimes(unittest.TestCase):
    """v1.0.3：两种编号制式都要支持，且不许跨章并集抵消（V1/V2 验证轮实证）。"""

    FIG_CH = r"图\s*(?P<ch>\d+)\s*[-–.]\s*(?P<n>\d+)"
    FIG_GLOBAL = r"图\s*(?P<n>\d+)(?!\s*[-–.]\s*\d)"

    def _body(self, *texts):
        return [(t, "", "p") for t in texts]

    def test_global_numbering_gap_detected(self):
        ok, msg = doc.check_series(self._body("图 1 甲", "图 3 乙"), "", "图",
                                   self.FIG_CH, self.FIG_GLOBAL)
        self.assertIs(ok, False)
        self.assertIn("2", msg)

    def test_global_numbering_contiguous(self):
        ok, _ = doc.check_series(self._body("图 1 甲", "图 2 乙"), "", "图",
                                 self.FIG_CH, self.FIG_GLOBAL)
        self.assertIs(ok, True)

    def test_cross_chapter_union_does_not_hide_gap(self):
        # 第 2 章缺 2-2，第 3 章有 3-1/3-2：并集 1,2,3 看似连续，逐章核对必须报缺
        body = self._body("图 2-1 甲", "图 2-3 乙", "图 3-1 丙", "图 3-2 丁")
        ok, msg = doc.check_series(body, "", "图", self.FIG_CH, self.FIG_GLOBAL)
        self.assertIs(ok, False)
        self.assertIn("2", msg)

    def test_chapter_filter_only_checks_that_chapter(self):
        body = self._body("图 2-1 甲", "图 2-2 乙", "图 3-1 丙")
        ok, _ = doc.check_series(body, "", "图", self.FIG_CH, self.FIG_GLOBAL, chapter=2)
        self.assertIs(ok, True)

    def test_mixed_regimes_is_failure(self):
        ok, msg = doc.check_series(self._body("图 1 甲", "图 2-1 乙"), "", "图",
                                   self.FIG_CH, self.FIG_GLOBAL)
        self.assertIs(ok, False)
        self.assertIn("混用", msg)


class TestRefsWithoutCaptions(unittest.TestCase):
    def test_refs_but_no_captions_is_failure(self):
        body = [("如图 2-5 所示", "", "p")]
        cap = r"^\s*图\s*(?:(?P<ch>\d+)\s*[-–.]\s*)?(?P<n>\d+)\s"
        ref = r"图\s*(?:(?P<ch>\d+)\s*[-–.]\s*)?(?P<n>\d+)"
        ok, _ = doc.check_captions(body, "图", cap, ref)
        self.assertIs(ok, False)


class TestCaptionHeuristic(unittest.TestCase):
    """v1.0.6：图注识别（Y1/Y2 第五轮实证）。

    两头都要防：
    - 正文段落「图 2-1 所示的…」曾被当成图注 ⇒ A4 假 PASS；
    - 只认空格/冒号、且分隔符写成字面转义 ⇒ 制表符/全角空格分隔的真实长图注假 FAIL。
    """

    CAP = r"^\s*图\s*(?:(?P<ch>\d+)\s*[-–.]\s*)?(?P<n>\d+)"

    def match(self, text):
        return doc._caption_match(text, self.CAP) is not None

    def test_separator_variants_are_captions(self):
        long_tail = ("裂隙开度分布图，(a) 整体分布（单位 mm）；(b) 局部放大（x=100~200 mm 段）；"
                     "(c) 沿程剖面（虚线为平均位置）；(d) 概率密度（对数纵轴，五组结果叠加）")
        for sep in (" ", "\t", "\u3000", "：", ":"):
            text = "图 2-1" + sep + long_tail
            self.assertGreater(len(text), 80)      # 必须超过"无分隔符"的 80 字上限
            self.assertTrue(self.match(text), "separator %r not recognised" % sep)

    def test_no_separator_short_caption(self):
        self.assertTrue(self.match("图2-1示意图"))

    def test_no_separator_long_is_not_caption(self):
        self.assertFalse(self.match("图2-1" + "开" * 100))

    def test_separator_but_over_upper_bound_is_not_caption(self):
        self.assertFalse(self.match("图 2-1 " + "开" * 400))

    def test_prose_starting_with_figure_number_is_not_caption(self):
        prose = ("图 2-1 所示的裂隙开度场是在 250 mm × 50 mm 域上生成的，采用 spectral 方法，"
                 "相关长度与粗糙度按第 2 章的口径取值，整体呈现明显的非均质性特征。")
        self.assertFalse(self.match(prose))

    def test_caption_containing_prose_words_is_still_caption(self):
        # 「对应」「说明」出现在图注中段很常见，不能因此判成正文
        self.assertTrue(self.match("图 2-10 开度场的自关联性（R1 与 R5 对应的正态曲线）"))


class TestDanglingCitation(unittest.TestCase):
    """v1.0.6：给了 --chapter 时，本章引用了图却一条图注都没有 ⇒ FAIL（悬空引用），不是未执行。"""

    CAP = r"^\s*图\s*(?:(?P<ch>\d+)\s*[-–.]\s*)?(?P<n>\d+)"
    REF = r"图\s*(?:(?P<ch>\d+)\s*[-–.]\s*)?(?P<n>\d+)"

    def test_chapter_ref_without_any_caption_is_failure(self):
        body = [("图 2-1 所示的裂隙开度场是在 250 mm 域上生成的，整体呈现明显的非均质性。", "", "p"),
                ("正文另处再次引用图 2-1。", "", "p")]
        ok, msg = doc.check_captions(body, "图", self.CAP, self.REF, chapter=2)
        self.assertIs(ok, False, msg)

    def test_chapter_without_captions_or_refs_is_not_executed(self):
        body = [("本章没有任何图。", "", "p")]
        ok, _ = doc.check_captions(body, "图", self.CAP, self.REF, chapter=2)
        self.assertIsNone(ok)


class TestCaptionRegressionsV108(unittest.TestCase):
    """第七轮（P1/P2）抓到的两类回归：动词表穷举漏词、名词短语式图注被误杀。"""

    CAP = r"^[ \t\u3000]*图[ \t\u3000]*(?:(?P<ch>\d+)[ \t\u3000]*[-–.][ \t\u3000]*)?(?P<n>\d+)"

    def _cap(self, text):
        return doc._caption_match(text, self.CAP)

    def test_verb_plus_le_is_prose(self):
        for text in ("图 2-1 显示了裂隙的开度场分布并给出趋势",
                     "图 2-1 展示了裂隙的开度场分布",
                     "图 2-1 中给出了五组算例的参数",
                     "图 2-1 描绘了五组裂隙的形态"):
            self.assertIsNone(self._cap(text), text)

    def test_noun_phrase_captions_not_killed(self):
        for text in ("图 2-1 中给出的开度分布", "图 2-1 所示的开度场",
                     "图 2-1 对应的开度分布", "图 2-1 显示的分布"):
            self.assertIsNotNone(self._cap(text), text)

    def test_sentence_end_punctuation_is_prose(self):
        self.assertIsNone(self._cap("图 2-1 记录了五组试验的开度场。"))


class TestCrossChapterDanglingV109(unittest.TestCase):
    """v1.0.9：跨章悬空必须按 (章号, 编号) 比，不能只比数字。

    第八轮 Q1/Q2 实测：`--chapter 3` 正文引 图 9-9、全篇有 图 2-9 ⇒ 旧实现把「9」当同一编号，
    记成未执行/通过（exit 0 假 PASS）。
    """

    CAP = r"^[ \t\u3000]*图[ \t\u3000]*(?:(?P<ch>\d+)[ \t\u3000]*[-–.][ \t\u3000]*)?(?P<n>\d+)"
    REF = r"图[ \t\u3000]*(?:(?P<ch>\d+)[ \t\u3000]*[-–.][ \t\u3000]*)?(?P<n>\d+)"

    def test_same_number_in_other_chapter_does_not_excuse(self):
        body = [("图 2-9 五组裂隙的开度场分布", "", "p"),
                ("本章引用了图 9-9 的结果。", "", "p")]
        ok, msg = doc.check_captions(body, "图", self.CAP, self.REF, chapter=3)
        self.assertIs(ok, False, msg)

    def test_chapter_citing_only_other_chapter_captions_is_honest_not_executed(self):
        # 第 3 章自己没有图注、只引用第 2 章的图：这不是悬空引用（别章有注），
        # 但也不许谎报成"既没有图注也没有引用" —— 必须是未执行 + 说明。
        body = [("图 2-1 五组裂隙的开度场分布", "", "p"),
                ("第 3 章正文再次引用图 2-1。", "", "p")]
        ok, msg = doc.check_captions(body, "图", self.CAP, self.REF, chapter=3)
        self.assertIsNone(ok, msg)
        self.assertIn("其他章节", msg)

    def test_bare_number_ref_satisfied_by_any_chapter(self):
        # 省略章号的「图 9」：只要某章有 9 号图注就算满足，第 3 章无图注时应记未执行（不是 FAIL）
        body = [("图 2-9 五组裂隙的开度场分布", "", "p"),
                ("第 3 章正文引用图 9。", "", "p")]
        ok, msg = doc.check_captions(body, "图", self.CAP, self.REF, chapter=3)
        self.assertIsNone(ok, msg)
        self.assertIn("其他章节", msg)

    def test_bare_number_ref_unsatisfied_reports_without_fake_chapter(self):
        # 省略章号的「图 7」且全篇无 7 号图注 ⇒ FAIL，且不许报成「图 3-7」
        body = [("图 2-9 五组裂隙的开度场分布", "", "p"),
                ("第 3 章正文引用图 7。", "", "p")]
        ok, msg = doc.check_captions(body, "图", self.CAP, self.REF, chapter=3)
        self.assertIs(ok, False, msg)
        self.assertNotIn("3-7", msg)

    def test_verb_regex_covers_longer_verbs(self):
        for text in ("图 2-1 详细描述了五组裂隙的几何形态",
                     "图 2-1 进一步给出了开度场的统计结果"):
            self.assertIsNone(doc._caption_match(text, self.CAP), text)

    def test_bare_ref_to_other_chapter_not_reported_as_this_chapter(self):
        # 图 7 是第 3 章的图（图 3-7），在第 2 章的核对里不许被报成「第 2 章 图 7」
        body = [("图 2-9 第二章的图", "", "p"),
                ("图 3-7 第三章的图", "", "p"),
                ("第 2 章正文引用图 7。", "", "p")]
        ok, msg = doc.check_captions(body, "图", self.CAP, self.REF, chapter=2)
        self.assertIs(ok, False, msg)      # 第 2 章的 图 2-9 没被引用 -> FAIL
        # 旧缺陷的文案是「正文引用了 第 2 章 [7]」（方括号编号），所以必须断言 [7] 不出现；
        # 只断言不含「图 7」是不够的（第十二轮 B1 实测：回退代码后该用例仍全绿）。
        self.assertNotIn("[7]", msg)        # 裸编号属于别章，不得出现在本章的引用报告里
        self.assertNotIn("图 7", msg)


class TestMixedRefKeysV1011(unittest.TestCase):
    """v1.0.11：`--chapter` 下「带章号引用」与「裸编号引用」混在一起、且本章无图注时，
    旧实现 `sorted({(k, n) ...})` 会把 None 与 str 混排 -> `TypeError: '<' not supported
    between 'NoneType' and 'str'`（第十轮 T1 实测：exit 1 来自 traceback，没有结论行）。
    """

    CAP = r"^[ \t\u3000]*图[ \t\u3000]*(?:(?P<ch>\d+)[ \t\u3000]*[-–.][ \t\u3000]*)?(?P<n>\d+)"
    REF = r"图[ \t\u3000]*(?:(?P<ch>\d+)[ \t\u3000]*[-–.][ \t\u3000]*)?(?P<n>\d+)"

    def test_mixed_keys_do_not_crash(self):
        body = [("图 2-9 五组裂隙的开度场分布", "", "p"),
                ("第 3 章正文引用图 2-9，也引用图 9。", "", "p")]
        ok, msg = doc.check_captions(body, "图", self.CAP, self.REF, chapter=3)
        self.assertIsNone(ok, msg)          # 别章有注 + 裸编号被他章满足 => 未执行，不是崩溃也不是 FAIL
        self.assertIn("其他章节", msg)

    def test_mixed_keys_missing_set_does_not_crash(self):
        # v1.0.14 补：上面那条用例的 mixed keys 恰好都"被满足"，missing 为空集 ⇒
        # 旧实现的 sorted() 从未比较过 None 与 str，因此把修复回退后测试仍全绿（自己变异测出来的漏洞）。
        # 这里造一个 missing **非空且同时含裸编号与带章号** 的用例，才能真正触发 None/str 混排比较。
        body = [("图 2-9 五组裂隙的开度场分布", "", "p"),
                ("正文引用图 2-9 与图 3-5，另外还引用了图 7。", "", "p")]
        ok, msg = doc.check_captions(body, "图", self.CAP, self.REF, chapter=3)
        self.assertIs(ok, False, msg)        # 两个都无人满足 ⇒ FAIL（不是崩溃、不是未执行）
        self.assertIn("图 3-5", msg)          # 带章号的缺号要报出来
        self.assertIn("图 7", msg)            # 裸编号缺号也要报出来

    def test_caption_without_chapter_number_not_given_fake_chapter(self):
        # 图注本身没章号（全局编号制）时，文案不许把它说成当前章。
        # 第十一轮 A1 的变异测试指出：只断言 "3-7" 不在 msg 里太弱——若 msg 完全不含图号也会通过。
        # 因此同时断言 msg 里**必须**出现「图 7」，且不出现当前章号 3。
        body = [("图 7 五组裂隙的开度场分布", "", "p"),
                ("正文引用图 7。", "", "p")]
        ok, msg = doc.check_captions(body, "图", self.CAP, self.REF, chapter=3)
        self.assertIn("图 7", msg)          # 图号要被报出来
        self.assertNotIn("3-7", msg)         # 不许拼成章-号
        self.assertNotIn("第 3 章 图 7", msg)  # 也不许说成「第 3 章 图 7」


if __name__ == "__main__":
    unittest.main(verbosity=2)
