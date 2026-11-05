import json
import os
import tempfile
import unittest

from eval_harness import Query, Span
from leakage_check import (
    label_balance, main, prepare, query_leaks, record_texts, shingles, span_leaks,
    split_overlap, verdict, video_coverage, words,
)

SEG_A = "welcome everyone to the lecture on linked lists today"
SEG_B = ("so the tortoise and hare technique uses two pointers one moving slowly and the other "
         "moving twice as fast through the list")
SEG_C = "if there is a cycle the fast pointer will eventually meet the slow pointer inside the loop"
SEG_D = "now let us move on to reversing a linked list using three pointers previous current and next"
TRANSCRIPTS = {"v1": [(0.0, 10.0, SEG_A), (10.0, 30.0, SEG_B), (30.0, 50.0, SEG_C), (50.0, 70.0, SEG_D)]}


def rec(user, bullets=None):
    asst = json.dumps({"bullets": bullets if bullets is not None else [{"text": "x", "sources": [1]}]})
    return {"messages": [{"role": "system", "content": "You are a TA. Always answer in JSON."},
                         {"role": "user", "content": user},
                         {"role": "assistant", "content": asst}]}


def Q(qid, text, split="test", start=10.0, end=50.0):
    return Query(qid, text, "conceptual", split, (Span("v1", start, end),))


class Basics(unittest.TestCase):
    def test_words_and_shingles(self):
        self.assertEqual(words("Hello, World-2!"), ["hello", "world", "2"])
        self.assertEqual(shingles(["a", "b", "c"], 2), {("a", "b"), ("b", "c")})
        self.assertEqual(shingles(["a"], 2), set())

    def test_record_formats_and_system_is_ignored(self):
        user, asst = record_texts(rec("the question"))
        self.assertEqual(user, "the question")
        self.assertIn("bullets", asst)
        self.assertNotIn("TA", user + asst)
        self.assertEqual(record_texts({"prompt": "p", "completion": "c"}), ("p", "c"))
        self.assertEqual(record_texts({"a": "x", "b": ["y"]})[0], "x\ny")


class QueryLeaks(unittest.TestCase):
    def setUp(self):
        self.train = prepare([
            rec("Question: how do you detect a cycle in a linked list\nExcerpts: " + SEG_C),
            rec("Question: explain tail recursion\nExcerpts: " + SEG_A),
            rec("Question: what is sorting\nExcerpts: unrelated words here"),
        ], 5)

    def test_verbatim_query_is_flagged_and_reworded_is_not(self):
        qs = [Q("q1", "how do you detect a cycle in a linked list"),
              Q("q2", "finding loops in chained nodes using fast and slow walkers")]
        rows = query_leaks(qs, {"train": self.train}, 0.8)
        self.assertEqual([r["query_id"] for r in rows], ["q1"])
        self.assertEqual(rows[0]["record"], 1)
        self.assertGreaterEqual(rows[0]["score"], 0.99)
        self.assertIn("detect a cycle", rows[0]["snippet"])
        self.assertFalse(rows[0]["weak"])

    def test_short_queries_are_marked_weak(self):
        rows = query_leaks([Q("q3", "tail recursion")], {"train": self.train}, 0.8)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["weak"])


class SpanLeaks(unittest.TestCase):
    def test_span_text_in_training_is_flagged_per_split(self):
        train = prepare([rec("Excerpt: " + SEG_B + " " + SEG_C + "\nQuestion: anything"),
                         rec("Excerpt: " + SEG_D + "\nQuestion: reverse a list")], 5)
        qs = [Q("t1", "cycle detection", "test", 10, 50), Q("d1", "reversal", "dev", 50, 70)]
        rows, skipped = span_leaks(qs, {"train": train}, TRANSCRIPTS, ngram=8, min_shared=3)
        by = {r["query_id"]: r for r in rows}
        self.assertEqual(skipped, [])
        self.assertEqual((by["t1"]["records"], by["t1"]["record_ids"]), (1, [1]))
        self.assertGreater(by["t1"]["coverage"], 0.9)
        self.assertEqual((by["d1"]["records"], by["d1"]["record_ids"]), (1, [2]))

    def test_unrelated_training_data_does_not_flag(self):
        train = prepare([rec("Excerpt: binary search halves the range every step of the loop and so on")], 5)
        rows, _ = span_leaks([Q("t1", "cycle", "test", 10, 50)], {"train": train}, TRANSCRIPTS, 8, 3)
        self.assertEqual(rows[0]["records"], 0)

    def test_missing_transcript_and_tiny_span_are_skipped(self):
        qs = [Query("m", "x y z w", "lexical", "dev", (Span("nope", 0, 30),)),
              Query("s", "x y z w", "lexical", "dev", (Span("v1", 0, 5.5),))]
        rows, skipped = span_leaks(qs, {"train": prepare([rec("hi")], 5)}, TRANSCRIPTS, 12, 3)
        self.assertEqual({a for a, _ in skipped}, {"m", "s"})
        self.assertEqual(rows, [])


class Coverage(unittest.TestCase):
    def test_video_coverage_counts_records(self):
        train = prepare([rec(SEG_B + " " + SEG_C), rec(SEG_D), rec("nothing relevant at all in this one here")], 5)
        qs = [Q("a", "q one two three", "dev"), Q("b", "q four five six", "test")]
        rows = video_coverage(qs, {"train": train}, TRANSCRIPTS, 8, 3)
        self.assertEqual(rows, [{"video_id": "v1", "queries": 2, "train": 2}])


class TrainVal(unittest.TestCase):
    def test_duplicates_similarity_and_shared_text(self):
        train = prepare([rec("Excerpt: " + SEG_B + "\nQ: how do pointers move"),
                         rec("Excerpt: " + SEG_D + "\nQ: reverse it", [{"text": "three pointers", "sources": [1]}])], 5)
        val = prepare([rec("Excerpt: " + SEG_B + "\nQ: how do pointers move"),        # identical to train 1
                       rec("Excerpt: totally different content about graphs and heaps and queues here\nQ: z",
                           [{"text": "a different target entirely", "sources": [2]}])], 5)
        ov = split_overlap(train, val, 8, 3)
        self.assertEqual(ov["dup_user"], 1)
        self.assertEqual(ov["dup_asst"], 1)           # same non-empty target text
        self.assertEqual(ov["share_text"], 1)         # only the first val record shares transcript text
        self.assertAlmostEqual(max(ov["u_sims"]), 1.0)
        self.assertLess(min(ov["u_sims"]), 0.2)

    def test_refusal_outputs_are_not_counted_as_duplicate_answers(self):
        train = prepare([rec("a b c d e f g h", [])], 5)
        val = prepare([rec("x y z w v u t s", [])], 5)
        self.assertEqual(split_overlap(train, val, 8, 3)["dup_asst"], 0)

    def test_label_balance(self):
        p = prepare([rec("u", []), rec("u2"), {"messages": [{"role": "assistant", "content": "not json"}]}], 5)
        self.assertEqual(label_balance(p), {"n": 3, "empty": 1, "unparseable": 1})


class Verdict(unittest.TestCase):
    def test_test_split_leak_fails_dev_leak_warns_clean_passes(self):
        q_test = [{"query_id": "t", "split": "test", "file": "train", "record": 1, "score": 1.0, "weak": False}]
        q_dev = [dict(q_test[0], query_id="d", split="dev")]
        q_weak = [dict(q_test[0], weak=True)]
        s_dev = [{"query_id": "d", "split": "dev", "file": "train", "records": 2, "max_shared": 9, "coverage": 0.5}]
        self.assertEqual(verdict(q_test, [], None)[0], "FAIL")
        self.assertEqual(verdict([], s_dev, None)[0], "WARN")
        self.assertEqual(verdict(q_dev, [], None)[0], "WARN")
        self.assertEqual(verdict(q_weak, [], None)[0], "PASS")
        self.assertEqual(verdict([], [], None)[0], "PASS")


class Cli(unittest.TestCase):
    def _setup(self, leak_test: bool):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        golden = {"queries": [
            {"id": "t1", "query": "how does the tortoise and hare technique find a cycle", "type": "conceptual",
             "split": "test", "relevant": [{"video_id": "v1", "start_sec": 10, "end_sec": 50}]},
            {"id": "d1", "query": "reverse a list with pointers", "type": "paraphrase",
             "split": "dev", "relevant": [{"video_id": "v1", "start_sec": 50, "end_sec": 70}]}]}
        os.makedirs(f"{d}/tr")
        json.dump([{"start": a, "end": b, "text": t} for a, b, t in TRANSCRIPTS["v1"]], open(f"{d}/tr/v1.json", "w"))
        json.dump(golden, open(f"{d}/golden.json", "w"))
        train = [rec("Excerpt: " + SEG_D + "\nQ: reverse"), rec("Excerpt: graphs and heaps and queues are other topics here")]
        if leak_test:
            train.append(rec("Excerpt: " + SEG_B + " " + SEG_C + "\nQ: cycles"))
        for name, rows in (("train", train), ("val", [rec("Excerpt: yet another unrelated passage about sorting")])):
            with open(f"{d}/{name}.jsonl", "w") as f:
                f.write("\n".join(json.dumps(r) for r in rows) + "\n")
        return d

    def run_cli(self, d):
        return main(["--golden", f"{d}/golden.json", "--train", f"{d}/train.jsonl", "--val", f"{d}/val.jsonl",
                     "--transcripts", f"{d}/tr", "--out", f"{d}/report.md", "--json-out", f"{d}/report.json"])

    def test_test_span_in_training_exits_1(self):
        d = self._setup(leak_test=True)
        self.assertEqual(self.run_cli(d), 1)
        self.assertIn("Verdict: FAIL", open(f"{d}/report.md").read())
        self.assertEqual(json.load(open(f"{d}/report.json"))["status"], "FAIL")

    def test_dev_only_leak_warns_with_exit_0(self):
        d = self._setup(leak_test=False)
        self.assertEqual(self.run_cli(d), 0)
        self.assertIn("Verdict: WARN", open(f"{d}/report.md").read())

    def test_bad_inputs_exit_2(self):
        d = self._setup(leak_test=False)
        with open(f"{d}/train.jsonl", "w") as f:
            f.write("{not json}\n")
        self.assertEqual(self.run_cli(d), 2)


if __name__ == "__main__":
    unittest.main()
