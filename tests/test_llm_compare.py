import csv
import json
import os
import shutil
import sys
import tempfile
import unittest

from eval_harness import HitConfig, Span
from eval_harness import Query
from llm_compare import (
    aggregate, build_items, check_schema, main, paired, parse_output, resolve_source,
    run_condition, score_output, write_review,
)

OVERLAP = HitConfig("overlap")


def transcripts():
    return {"v1": [(float(t), float(t + 10), f"segment {t} talks about topic{t // 100} and pointer{t}") for t in range(0, 600, 10)]}


def make_queries():
    return [Query("q1", "how do pointers move", "conceptual", "dev", (Span("v1", 100, 200),)),
            Query("q2", "what about topic four", "paraphrase", "dev", (Span("v1", 400, 480),))]


def make_run():
    return {"q1": [Span("v1", 0, 75), Span("v1", 30, 105), Span("v1", 300, 375), Span("v1", 400, 475),
                   Span("v1", 500, 575), Span("v1", 150, 225)],
            "q2": [Span("v1", 100, 175), Span("v1", 200, 275), Span("v1", 410, 485), Span("v1", 0, 75)]}


def item(answerable=True, gold_index=0):
    ex = [{"video_id": "v1", "start_sec": 100.0, "end_sec": 200.0,
           "text": "the fast pointer moves twice as fast as the slow pointer through the list"},
          {"video_id": "v1", "start_sec": 300.0, "end_sec": 400.0, "text": "binary search halves the range at every step"},
          {"video_id": "v1", "start_sec": 500.0, "end_sec": 600.0, "text": "heaps keep the smallest element at the root"}]
    return {"id": "q", "question": "how do the pointers move", "excerpts": ex,
            "gold_index": gold_index if answerable else None, "answerable": answerable}


def out(*bullets):
    return json.dumps({"bullets": [{"text": t, "sources": s} for t, s in bullets]})


class Parsing(unittest.TestCase):
    def test_strict_vs_lenient(self):
        obj, strict = parse_output('{"bullets": []}')
        self.assertEqual((obj, strict), ({"bullets": []}, True))
        obj, strict = parse_output('Sure! ```json\n{"bullets": []}\n``` hope that helps')
        self.assertEqual((obj, strict), ({"bullets": []}, False))
        self.assertEqual(parse_output("no json here"), (None, False))
        self.assertEqual(parse_output("{broken"), (None, False))

    def test_schema(self):
        self.assertTrue(check_schema({"bullets": []}))
        self.assertTrue(check_schema({"bullets": [{"text": "a", "sources": [1]}]}))
        for bad in ({"bullets": [{"text": "a"}]}, {"bullets": [{"text": "a", "sources": []}]},
                    {"bullets": [{"text": " ", "sources": [1]}]}, {"bullets": "x"}, [], {"x": 1}):
            self.assertFalse(check_schema(bad), bad)


class Sources(unittest.TestCase):
    def setUp(self):
        self.ex = item()["excerpts"]

    def test_indices_timestamps_and_dicts(self):
        r = lambda s, **kw: resolve_source(s, self.ex, **kw)
        self.assertEqual((r(1), r("[2]"), r("3")), (0, 1, 2))
        self.assertEqual(r(1, index_base=0), 1)
        self.assertIsNone(r(9))                      # out of range as index, 9s as a time: nowhere near an excerpt
        self.assertEqual(r("2m00s"), 0)              # 120s is inside excerpt 1
        self.assertEqual(r("v1@5m30s"), 1)
        self.assertIsNone(r("v2@120"))
        self.assertEqual(r({"video_id": "v1", "start_sec": 120}), 0)
        self.assertIsNone(r("gibberish"))
        self.assertIsNone(r({"video_id": "v1"}))


class Scoring(unittest.TestCase):
    GOOD = ("The fast pointer moves twice as fast as the slow pointer", [1])

    def test_good_answer(self):
        r = score_output(item(), out(self.GOOD))
        self.assertTrue(r["answer_ok"])
        self.assertTrue(r["cites_gold"])
        self.assertIsNone(r["abstain_ok"])

    def test_failure_modes_are_distinguished(self):
        cases = {
            "ungrounded": out(("use a hash table for constant lookup", [1])),
            "unresolved": out((self.GOOD[0], [9])),
            "wrong_excerpt": out(("binary search halves the range at every step", [2])),
        }
        for name, text in cases.items():
            r = score_output(item(), text)
            self.assertFalse(r["answer_ok"], name)
            self.assertTrue(r["format_ok"], name)
        self.assertFalse(score_output(item(), cases["unresolved"])["resolved_all"])
        self.assertFalse(score_output(item(), cases["ungrounded"])["grounded_all"])
        self.assertFalse(score_output(item(), cases["wrong_excerpt"])["cites_gold"])

    def test_false_abstain_and_bad_format(self):
        r = score_output(item(), out())
        self.assertEqual((r["false_abstain"], r["answer_ok"]), (True, False))
        fenced = score_output(item(), "```json\n" + out(self.GOOD) + "\n```")
        self.assertEqual((fenced["format_ok"], fenced["lenient_json"], fenced["answer_ok"]), (False, True, False))
        junk = score_output(item(), "I don't know")
        self.assertEqual((junk["format_ok"], junk["lenient_json"], junk["false_abstain"]), (False, False, False))

    def test_unanswerable_items(self):
        un = item(answerable=False)
        self.assertTrue(score_output(un, out())["abstain_ok"])
        self.assertFalse(score_output(un, out(self.GOOD))["abstain_ok"])
        self.assertFalse(score_output(un, "garbage")["abstain_ok"])
        self.assertIsNone(score_output(un, out())["answer_ok"])


class BuildItems(unittest.TestCase):
    def build(self, **kw):
        args = dict(mode="oracle", n_ctx=3, unans_frac=0.0, seed=0, dedup_overlap=0.5, max_chars=1500)
        args.update(kw)
        return build_items(make_queries(), make_run(), transcripts(), args["mode"], args["n_ctx"],
                           args["unans_frac"], args["seed"], args["dedup_overlap"], args["max_chars"], OVERLAP)

    def test_oracle_contains_gold_and_only_safe_distractors(self):
        items, skipped = self.build()
        self.assertEqual(skipped, [])
        for it in items:
            self.assertTrue(it["answerable"])
            self.assertEqual(len(it["excerpts"]), 3)
            gold = it["excerpts"][it["gold_index"]]
            golds = {"q1": (100, 200), "q2": (400, 480)}[it["id"]]
            self.assertEqual((gold["start_sec"], gold["end_sec"]), golds)
            for i, e in enumerate(it["excerpts"]):
                if i != it["gold_index"]:
                    self.assertTrue(e["end_sec"] <= golds[0] or e["start_sec"] >= golds[1])

    def test_unanswerable_fraction_has_no_gold(self):
        items, _ = self.build(unans_frac=1.0)
        self.assertTrue(all(not it["answerable"] and it["gold_index"] is None for it in items))
        for it in items:
            lo, hi = {"q1": (100, 200), "q2": (400, 480)}[it["id"]]
            self.assertTrue(all(e["end_sec"] <= lo or e["start_sec"] >= hi for e in it["excerpts"]))
        items, _ = self.build(unans_frac=0.5)
        self.assertEqual(sum(not it["answerable"] for it in items), 1)

    def test_deterministic_for_a_seed(self):
        self.assertEqual(self.build(seed=3)[0], self.build(seed=3)[0])

    def test_retrieved_mode_marks_answerability_from_context(self):
        items, _ = self.build(mode="retrieved", n_ctx=3)
        by = {it["id"]: it for it in items}
        # q1 top-3 (after dedup) = 0-75, 300-375, 400-475... none overlaps 100-200 by 30s -> unanswerable
        self.assertFalse(by["q1"]["answerable"])
        # q2 top-3 = 100-175, 200-275, 410-485 -> third overlaps 400-480
        self.assertTrue(by["q2"]["answerable"])
        self.assertEqual(by["q2"]["gold_index"], 2)

    def test_empty_transcripts_are_skipped(self):
        items, skipped = build_items(make_queries(), make_run(), {}, "oracle", 3, 0.0, 0, 0.5, 1500, OVERLAP)
        self.assertEqual(items, [])
        self.assertEqual(len(skipped), 2)


class Conditions(unittest.TestCase):
    def test_retry_recovers_format_but_first_try_is_kept(self):
        good = out(("The fast pointer moves twice as fast as the slow pointer", [1]))

        def gen(messages, attempt):
            return "not json" if attempt == 0 else good

        build = lambda q, ex: [{"role": "user", "content": q}]
        res = run_condition([item()], gen, build, retries=2, ground_thr=0.5, index_base=1)[0]
        self.assertFalse(res["format_ok"])
        self.assertTrue(res["format_ok_retry"])
        self.assertEqual(res["attempts"], 1)
        res0 = run_condition([item()], gen, build, retries=0, ground_thr=0.5, index_base=1)[0]
        self.assertFalse(res0["format_ok_retry"])

    def test_aggregate_and_paired(self):
        def mk(i, ans, **kw):
            base = {"id": i, "answerable": ans, "strict_json": True, "lenient_json": True, "format_ok": True,
                    "format_ok_retry": True, "n_bullets": 1 if ans else 0, "resolved_all": True if ans else None,
                    "grounded_all": True if ans else None, "answer_ok": True if ans else None,
                    "false_abstain": False if ans else None, "abstain_ok": None if ans else True}
            base.update(kw)
            return base

        a = [mk("1", True), mk("2", True), mk("3", False), mk("4", False)]
        b = [mk("1", True), mk("2", True, answer_ok=False), mk("3", False, abstain_ok=False), mk("4", False)]
        agg = aggregate(b)
        self.assertEqual((agg["n"], agg["n_ans"], agg["answer_ok"], agg["n_una"], agg["abstain_ok"]), (4, 2, 1, 2, 1))
        c = paired(a, b, "answer_ok", True)
        self.assertEqual((c["a_only"], c["b_only"], c["both"], c["neither"]), (1, 0, 1, 0))
        c = paired(a, b, "abstain_ok", False)
        self.assertEqual((c["a_only"], c["b_only"]), (1, 0))
        self.assertEqual(paired(a, b, "format_ok", None)["both"], 4)


class Review(unittest.TestCase):
    def test_sheet_is_blind_and_key_maps_back(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        items = [dict(item(), id=f"q{i}") for i in range(4)]
        conds = {"base": [{"id": it["id"], "output": f"BASEOUT-{it['id']}"} for it in items],
                 "tuned": [{"id": it["id"], "output": f"TUNEDOUT-{it['id']}"} for it in items]}
        n = write_review(f"{d}/s.csv", f"{d}/k.csv", items, conds, 3, seed=1)
        self.assertEqual(n, 6)                                         # 3 questions x 2 conditions
        with open(f"{d}/s.csv", encoding="utf-8-sig") as f:
            sheet = list(csv.DictReader(f))
        with open(f"{d}/k.csv", encoding="utf-8-sig") as f:
            key = {r["sample_id"]: r for r in csv.DictReader(f)}
        self.assertEqual(len(sheet), 6)
        with open(f"{d}/s.csv", encoding="utf-8-sig") as f:
            header = f.readline()
        self.assertNotIn("condition", header)
        for row in sheet:
            k = key[row["sample_id"]]
            self.assertEqual(row["model_output"], f"{k['condition'].upper()}OUT-{k['item_id']}")
        self.assertEqual({r["condition"] for r in key.values()}, {"base", "tuned"})


FACTORY = '''
import json
def make(name, spec):
    def gen(messages, attempt):
        if name == "abstain":
            return json.dumps({"bullets": []})
        user = messages[-1]["content"]
        body = user.split("Excerpts:\\n", 1)[1].split("\\n\\n[2]")[0]
        text = body.split(") ", 1)[1]
        return json.dumps({"bullets": [{"text": text, "sources": [1]}]})
    return gen
'''


class EndToEnd(unittest.TestCase):
    def test_cli_with_fake_generators(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        self.addCleanup(lambda: sys.modules.pop("fake_gen_mod", None))
        os.makedirs(f"{d}/tr")
        with open(f"{d}/tr/v1.json", "w") as f:
            json.dump([{"start": a, "end": b, "text": t} for a, b, t in transcripts()["v1"]], f)
        json.dump({"queries": [
            {"id": "q1", "query": "how do pointers move", "type": "conceptual", "split": "dev",
             "relevant": [{"video_id": "v1", "start_sec": 100, "end_sec": 200}]},
            {"id": "q2", "query": "what about topic four", "type": "paraphrase", "split": "dev",
             "relevant": [{"video_id": "v1", "start_sec": 400, "end_sec": 480}]},
            {"id": "q3", "query": "third question here", "type": "lexical", "split": "dev",
             "relevant": [{"video_id": "v1", "start_sec": 250, "end_sec": 330}]},
            {"id": "q4", "query": "fourth question here", "type": "symptom", "split": "dev",
             "relevant": [{"video_id": "v1", "start_sec": 50, "end_sec": 130}]}]}, open(f"{d}/golden.json", "w"))
        run = {q: [{"video_id": "v1", "start_sec": s, "end_sec": s + 75} for s in (0, 150, 300, 450, 520)]
               for q in ("q1", "q2", "q3", "q4")}
        json.dump(run, open(f"{d}/run.json", "w"))
        open(f"{d}/fake_gen_mod.py", "w").write(FACTORY)
        sys.path.insert(0, d)
        self.addCleanup(sys.path.remove, d)
        code = main(["--golden", f"{d}/golden.json", "--runs", f"{d}/run.json", "--transcripts", f"{d}/tr",
                     "--use-default-prompt", "--gen-factory", "fake_gen_mod:make", "--n-ctx", "3",
                     "--conditions", "echo=x", "abstain=y", "--unanswerable-frac", "0.5", "--retries", "1",
                     "--out", f"{d}/r.md", "--json-out", f"{d}/r.json", "--review-csv", f"{d}/review.csv",
                     "--review-n", "2"])
        self.assertEqual(code, 0)
        with open(f"{d}/r.md") as f:
            report = f.read()
        self.assertIn("default prompt was used", report)
        self.assertIn("2 answerable, 2 unanswerable", report)
        with open(f"{d}/r.json") as f:
            data = json.load(f)
        abst = data["results"]["abstain"]
        self.assertTrue(all(r["abstain_ok"] for r in abst if not r["answerable"]))
        self.assertTrue(all(r["false_abstain"] for r in abst if r["answerable"]))
        echo_una = [r for r in data["results"]["echo"] if not r["answerable"]]
        self.assertTrue(all(r["abstain_ok"] is False for r in echo_una))   # always answers: hallucinates
        self.assertIn("Paired comparisons", report)
        self.assertTrue(os.path.exists(f"{d}/review.key.csv"))

    def test_refuses_to_run_without_a_prompt_choice(self):
        self.assertEqual(main(["--golden", "g", "--runs", "r", "--transcripts", "t"]), 2)


if __name__ == "__main__":
    unittest.main()
