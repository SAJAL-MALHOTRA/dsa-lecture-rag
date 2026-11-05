import json
import os
import random
import shutil
import tempfile
import unittest
from pathlib import Path

import eval_harness as eh
import leakage_check as lc
import llm_compare as lcmp
from video_holdout import assign_folds, describe, filter_records, main, split_queries


def vocab_text(rng, n=18):
    return " ".join(f"w{rng.randrange(10 ** 6)}" for _ in range(n))


def make_corpus(seed=0, videos=("v1", "v2", "v3", "v4"), segs=40):
    rng = random.Random(seed)
    return {v: [(float(t), float(t + 10), vocab_text(rng)) for t in range(0, segs * 10, 10)] for v in videos}


def rec(user, bullets=None):
    asst = json.dumps({"bullets": [{"text": "x", "sources": [1]}] if bullets is None else bullets})
    return {"messages": [{"role": "system", "content": "TA"}, {"role": "user", "content": user},
                         {"role": "assistant", "content": asst}]}


def excerpt(tr, vid, start, n=4):
    return " ".join(t for a, b, t in tr[vid] if start <= a < start + 10 * n)


def golden_items(tr):
    items, i = [], 0
    for v in sorted(tr):
        for st in (50, 150, 250):
            i += 1
            items.append({"id": f"q{i:02d}", "query": f"question number {i} about material in {v} please",
                          "type": ["lexical", "paraphrase", "conceptual", "symptom"][i % 4],
                          "split": "test" if i % 2 else "dev",
                          "relevant": [{"video_id": v, "start_sec": st, "end_sec": st + 60}]})
    return items


class Folds(unittest.TestCase):
    def test_balanced_deterministic_and_group_stratified(self):
        vids = [f"v{i}" for i in range(8)]
        groups = {v: "ABCD"[i // 2] for i, v in enumerate(vids)}
        a = assign_folds(vids, 2, seed=0, groups=groups)
        self.assertEqual(a, assign_folds(vids, 2, seed=0, groups=groups))
        self.assertEqual(sorted(a), vids)
        self.assertEqual(sum(1 for f in a.values() if f == 0), 4)
        for g in "ABCD":
            self.assertEqual({a[v] for v in vids if groups[v] == g}, {0, 1})   # each topic in both folds
        self.assertTrue(any(assign_folds(vids, 2, seed=s, groups=groups) != a for s in range(1, 10)))

    def test_three_folds_and_errors(self):
        a = assign_folds([f"v{i}" for i in range(7)], 3, seed=1)
        sizes = sorted(sum(1 for f in a.values() if f == k) for k in range(3))
        self.assertEqual(sizes, [2, 2, 3])
        with self.assertRaises(ValueError):
            assign_folds(["v1"], 2, 0)
        with self.assertRaises(ValueError):
            assign_folds(["v1", "v2"], 1, 0)

    def test_each_query_is_held_out_in_exactly_one_fold_and_straddlers_never(self):
        tr = make_corpus()
        items = golden_items(tr)
        items.append({"id": "mix", "query": "spans two videos here ok", "type": "lexical", "split": "dev",
                      "relevant": [{"video_id": "v1", "start_sec": 10, "end_sec": 50},
                                   {"video_id": "v2", "start_sec": 10, "end_sec": 50}]})
        a = assign_folds(list(tr), 2, 0)
        a["v1"], a["v2"] = 0, 1                                  # force a straddle
        held0, st0 = split_queries(items, a, 0)
        held1, st1 = split_queries(items, a, 1)
        self.assertEqual(st0, ["mix"])
        ids0, ids1 = {i["id"] for i in held0}, {i["id"] for i in held1}
        self.assertFalse(ids0 & ids1)
        self.assertNotIn("mix", ids0 | ids1)
        self.assertEqual(len(ids0 | ids1), len(items) - 1)


class Filtering(unittest.TestCase):
    def setUp(self):
        self.tr = make_corpus()
        self.items = golden_items(self.tr)

    def test_records_touching_heldout_videos_are_dropped(self):
        records = [rec("Excerpts: " + excerpt(self.tr, "v1", 0)),            # held-out video
                   rec("Excerpts: " + excerpt(self.tr, "v3", 0)),            # train video
                   rec("Excerpts: " + excerpt(self.tr, "v3", 0) + " " + excerpt(self.tr, "v2", 100)),  # mixed
                   rec("Question: how to deploy a web app\nExcerpts: nothing", [])]  # refusal, no lecture text
        held_items = [i for i in self.items if i["relevant"][0]["video_id"] in ("v1", "v2")]
        kept, st = filter_records(records, ["v1", "v2"], self.tr, held_items, 8, 3)
        self.assertEqual([r["messages"][1]["content"][:20] for r in kept],
                         [records[1]["messages"][1]["content"][:20], records[3]["messages"][1]["content"][:20]])
        self.assertEqual((st["in"], st["kept"], st["dropped_video"], st["dropped_query"]), (4, 2, 2, 0))
        self.assertEqual(st["per_video"], {"v1": 1, "v2": 1})

    def test_record_containing_a_heldout_question_is_dropped_even_without_lecture_text(self):
        q = self.items[0]                                                      # on v1
        records = [rec("Question: " + q["query"] + "\nExcerpts: unrelated filler words only here"),
                   rec("Question: something else entirely different to ask\nExcerpts: filler")]
        kept, st = filter_records(records, ["v1"], self.tr, [q], 8, 3)
        self.assertEqual(len(kept), 1)
        self.assertEqual((st["dropped_video"], st["dropped_query"]), (0, 1))

    def test_describe_reports_refusal_share(self):
        d = describe([rec("a"), rec("b", []), rec("c", [])])
        self.assertEqual((d["n"], d["refusals"]), (3, 2))
        self.assertAlmostEqual(d["refusal_share"], 2 / 3)
        self.assertEqual(describe([])["refusal_share"], 0.0)


class Cli(unittest.TestCase):
    def build(self, per_video=20):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        tr = make_corpus()
        os.makedirs(f"{d}/tr")
        for v, segs in tr.items():
            with open(f"{d}/tr/{v}.json", "w") as f:
                json.dump([{"start": a, "end": b, "text": t} for a, b, t in segs], f)
        items = golden_items(tr)
        with open(f"{d}/golden.json", "w") as f:
            json.dump({"queries": items}, f)
        with open(f"{d}/groups.json", "w") as f:
            json.dump({"v1": "A", "v2": "A", "v3": "B", "v4": "B"}, f)
        rng = random.Random(9)
        train = [rec("Q: explain part\nExcerpts: " + excerpt(tr, v, 10 * rng.randrange(0, 30)))
                 for v in tr for _ in range(per_video)]
        train += [rec("Q: deploy next.js\nExcerpts: none", []) for _ in range(4)]
        val = [rec("Q: v\nExcerpts: " + excerpt(tr, v, 10 * rng.randrange(0, 30))) for v in tr for _ in range(2)]
        for name, rows in (("train", train), ("val", val)):
            with open(f"{d}/{name}.jsonl", "w") as f:
                f.write("".join(json.dumps(r) + "\n" for r in rows))
        return d, tr, items

    def split(self, d, *extra):
        return main(["split", "--golden", f"{d}/golden.json", "--transcripts", f"{d}/tr", "--train", f"{d}/train.jsonl",
                     "--val", f"{d}/val.jsonl", "--out-dir", f"{d}/out", "--groups", f"{d}/groups.json", *extra])

    def test_end_to_end_two_folds_leave_no_trace_of_heldout_videos(self):
        d, tr, items = self.build()
        self.assertEqual(self.split(d), 0)
        seen_queries = []
        for k in (0, 1):
            fd = Path(f"{d}/out/fold{k}")
            man = json.loads((fd / "manifest.json").read_text())
            held = set(man["heldout_videos"])
            self.assertEqual(len(held), 2)
            self.assertEqual(held & set(man["train_videos"]), set())
            gold = json.loads((fd / "golden.holdout.json").read_text())
            self.assertEqual({q["relevant"][0]["video_id"] for q in gold["queries"]}, held)
            seen_queries += [q["id"] for q in gold["queries"]]
            # the independent leakage tool agrees: held-out videos have zero training records
            queries, _ = eh.load_golden(str(fd / "golden.holdout.json"))
            files = {"train": lc.prepare(lc.load_jsonl(str(fd / "train.jsonl")), 5),
                     "val": lc.prepare(lc.load_jsonl(str(fd / "val.jsonl")), 5)}
            cov = lc.video_coverage(queries, files, eh.load_transcripts(f"{d}/tr"), 8, 3)
            self.assertTrue(all(r["train"] == 0 and r["val"] == 0 for r in cov), cov)
            code = lc.main(["--golden", str(fd / "golden.holdout.json"), "--train", str(fd / "train.jsonl"),
                            "--val", str(fd / "val.jsonl"), "--transcripts", f"{d}/tr"])
            self.assertEqual(code, 0)
            self.assertTrue(man["sufficient"])
            self.assertGreater(man["train_after"]["n"], 10)
        self.assertEqual(sorted(seen_queries), sorted(i["id"] for i in items))       # every question once

    def test_too_few_surviving_records_exit_3(self):
        d, _, _ = self.build(per_video=2)
        self.assertEqual(self.split(d, "--min-train-records", "50"), 3)

    def test_bad_inputs_exit_2(self):
        d, _, _ = self.build()
        os.remove(f"{d}/tr/v4.json")
        self.assertEqual(self.split(d), 2)


class Pool(unittest.TestCase):
    def fold_json(self, d, name, ids, tuned_fails):
        items = [{"id": i, "question": "q", "type": "conceptual", "split": "dev", "answerable": True, "gold_index": 0,
                  "excerpts": [{"video_id": "v1", "start_sec": 0.0, "end_sec": 10.0, "text": "the fast pointer moves twice"}]}
                 for i in ids]
        good = json.dumps({"bullets": [{"text": "the fast pointer moves twice", "sources": [1]}]})
        build = lambda q, ex: [{"role": "user", "content": q}]
        base = lcmp.run_condition(items, lambda m, a: "nope", build, 0, 0.5, 1)
        tuned = lcmp.run_condition(items, lambda m, a: "nope" if (a == 0 and tuned_fails) else good, build, 0, 0.5, 1)
        meta = {"golden_sha": "a" * 64, "split": "all", "context": "oracle", "n_ctx": 4, "seed": 0, "ground_thr": 0.5,
                "retries": 0, "index_base": 1, "default_prompt": False}
        p = Path(d) / name
        p.write_text(json.dumps({"meta": meta, "items": items, "results": {"base": base, "tuned": tuned}}))
        return str(p)

    def test_pool_concatenates_folds_and_rejects_overlap(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        a = self.fold_json(d, "f0.json", ["q1", "q2", "q3"], False)
        b = self.fold_json(d, "f1.json", ["q4", "q5", "q6"], False)
        c = self.fold_json(d, "f2.json", ["q3", "q9"], False)
        out = f"{d}/pooled.md"
        self.assertEqual(main(["pool", "--results", a, b, "--out", out]), 0)
        text = Path(out).read_text()
        self.assertIn("6 questions (6 answerable, 0 unanswerable)", text)
        self.assertIn("pooled over 2 video-holdout folds", text)
        self.assertIn("6/6 (100%)", text)                       # tuned answer_ok in every question
        self.assertEqual(main(["pool", "--results", a, c]), 2)  # q3 appears twice
        self.assertEqual(main(["pool", "--results", a]), 2)


if __name__ == "__main__":
    unittest.main()
