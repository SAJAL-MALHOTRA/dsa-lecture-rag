import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import diagnostics
import eval_harness as eh
import preregister as pr


def capture(fn, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(argv)
    return code, out.getvalue(), err.getvalue()


def span(v, s, e):
    return {"video_id": v, "start_sec": s, "end_sec": e}


def golden_doc():
    qs = []
    flags = {"d1": True, "d2": True, "d3": False, "t1": True, "t2": True, "t3": True}
    for i, (qid, ok) in enumerate(flags.items()):
        qs.append({"id": qid, "query": f"question {qid} about topic", "type": ["lexical", "paraphrase", "conceptual", "symptom"][i % 4],
                   "split": "dev" if qid.startswith("d") else "test", "verified": ok,
                   "relevant": [span("v1", 100 * (i + 1), 100 * (i + 1) + 80)]})
    return {"queries": qs}


class Env(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.p = lambda name: os.path.join(self.d, name)
        with open(self.p("golden.json"), "w") as f:
            json.dump(golden_doc(), f)
        with open(self.p("code.py"), "w") as f:
            f.write("print('retriever v1')\n")
        for name, off in (("a", 0), ("b", 200)):
            run = {}
            for q in golden_doc()["queries"]:
                start = q["relevant"][0]["start_sec"] - 5 + (off if q["id"] == "t3" else 0)
                run[q["id"]] = [{"video_id": "v1", "start_sec": start, "end_sec": start + 75}]
            with open(self.p(f"run_{name}.json"), "w") as f:
                json.dump(run, f)
        self.config = {"systems": {"a": "system A", "b": "system B"}, "code": [self.p("code.py")],
                       "eval": {"split": "test", "verified_only": True, "hit_def": "both", "k": [1, 3, 5, 10],
                                "primary_k": 3, "dedup_overlap": 0.5, "lead_tol": 20.0, "seek_max_frac": 0.5,
                                "overlap_frac": 0.5, "overlap_cap": 30.0}}

    def lock(self, **over):
        cfg = json.loads(json.dumps(self.config))
        cfg.update(over)
        return pr.make_lock(cfg, self.p("golden.json"))

    def write_lock(self):
        with open(self.p("lock.json"), "w") as f:
            json.dump(self.lock(), f)
        return self.p("lock.json")

    def harness(self, *extra, split="test", verified=True):
        args = ["--golden", self.p("golden.json"), "--split", split,
                "--runs", f"a={self.p('run_a.json')}", f"b={self.p('run_b.json')}", "--boot", "50", *extra]
        if verified:
            args.append("--verified-only")
        return capture(eh.main, args)


class LockUnit(Env):
    def test_make_lock_records_hashes_and_config(self):
        lock = self.lock()
        self.assertEqual(lock["golden"]["sha256"], pr.sha_file(self.p("golden.json")))
        self.assertEqual(lock["code"][self.p("code.py")], pr.sha_file(self.p("code.py")))
        self.assertEqual(lock["eval"]["k"], [1, 3, 5, 10])
        self.assertEqual(set(lock["systems"]), {"a", "b"})
        self.assertEqual(len(lock["config_sha256"]), 64)

    def test_make_lock_collects_every_problem(self):
        bad = {"systems": {"a": ""}, "code": [self.p("nope.py")], "eval": {"split": "dev"}}
        with self.assertRaises(pr.PreregError) as cm:
            pr.make_lock(bad, self.p("golden.json"))
        text = "\n".join(cm.exception.problems)
        for needle in ("'systems' must map", "missing:", "split must be 'test'", "code file not found"):
            self.assertIn(needle, text)

    def test_tampered_lock_is_rejected(self):
        path = self.write_lock()
        data = json.loads(Path(path).read_text())
        data["eval"]["primary_k"] = 5
        Path(path).write_text(json.dumps(data))
        with self.assertRaises(pr.PreregError) as cm:
            pr.load_lock(path)
        self.assertIn("edited after it was written", str(cm.exception))

    def test_check_lock_flags_each_kind_of_drift(self):
        lock = self.lock()
        cfg = dict(lock["eval"])
        self.assertEqual(pr.check_lock(lock, self.p("golden.json"), cfg, ["a", "b"]), [])
        p = lambda **o: pr.check_lock(lock, self.p("golden.json"), {**cfg, **o}, ["a", "b"])
        self.assertIn("setting k", " ".join(p(k=[1, 3])))
        self.assertIn("setting hit_def", " ".join(p(hit_def="seek")))
        self.assertIn("setting verified_only", " ".join(p(verified_only=False)))
        self.assertIn("missing from --runs", " ".join(pr.check_lock(lock, self.p("golden.json"), cfg, ["a"])))
        self.assertIn("not in the lock", " ".join(pr.check_lock(lock, self.p("golden.json"), cfg, ["a", "b", "c"])))
        Path(self.p("code.py")).write_text("print('changed')\n")
        self.assertIn("code changed since lock", " ".join(p()))
        os.remove(self.p("code.py"))
        self.assertIn("locked code file is missing", " ".join(p()))
        data = golden_doc()
        data["queries"][3]["relevant"][0]["start_sec"] += 1
        Path(self.p("golden.json")).write_text(json.dumps(data))
        self.assertIn("golden file differs", " ".join(p()))

    def test_ledger_and_banner(self):
        path = self.write_lock()
        self.assertEqual(pr.prior_runs(path), [])
        e = pr.record_run(path, "test_run", "report text", {"a": self.p("run_a.json")},
                          now=datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc))
        self.assertEqual(e["runs"]["a"], pr.sha_file(self.p("run_a.json")))
        self.assertEqual(e["report_sha256"], pr.sha_text("report text"))
        prior = pr.prior_runs(path)
        self.assertEqual([x["event"] for x in prior], ["test_run"])
        lock = pr.load_lock(path)
        self.assertIn("first recorded test run", pr.banner(lock, [], "test_run")[0])
        self.assertIn("TEST RE-RUN", pr.banner(lock, prior, "test_rerun")[0])
        self.assertIn("2026-10-12", pr.banner(lock, prior, "test_rerun")[0])


class SelectAndLoad(Env):
    def test_verified_flag_parsing_and_validation(self):
        qs, _ = eh.load_golden(self.p("golden.json"))
        self.assertEqual([q.verified for q in qs], [True, True, False, True, True, True])
        data = golden_doc()
        data["queries"][0]["verified"] = "yes"
        Path(self.p("bad.json")).write_text(json.dumps(data))
        with self.assertRaises(eh.GoldenError) as cm:
            eh.load_golden(self.p("bad.json"))
        self.assertIn("'verified' must be true or false", str(cm.exception))

    def test_select_queries(self):
        qs, _ = eh.load_golden(self.p("golden.json"))
        sel, note, err = eh.select_queries(qs, "dev", True)
        self.assertEqual([q.id for q in sel], ["d1", "d2"])
        self.assertIn("2 of 3 dev queries; 1 unverified excluded", note)
        self.assertEqual([q.id for q in eh.select_queries(qs, "dev", False)[0]], ["d1", "d2", "d3"])
        self.assertEqual(len(eh.select_queries(qs, "all", True)[0]), 5)
        unflagged = [eh.Query(q.id, q.query, q.type, q.split, q.relevant) for q in qs]    # verified=None everywhere
        sel, note, err = eh.select_queries(unflagged, "dev", True)
        self.assertEqual(sel, [])
        self.assertIn("verification flags", err)

    def test_warning_about_unverified_queries(self):
        qs, _ = eh.load_golden(self.p("golden.json"))
        self.assertTrue(any("1 of 6 queries are marked unverified" in w for w in eh.golden_warnings(qs)))


class DevRuns(Env):
    def test_dev_needs_no_lock_and_verified_only_filters(self):
        code, out, err = self.harness(split="dev")
        self.assertEqual(code, 0, err)
        self.assertIn("verified-only (2 of 3 dev queries; 1 unverified excluded)", out)
        self.assertIn("2 queries, split = **dev**", out)
        code, out, _ = self.harness(split="dev", verified=False)
        self.assertIn("3 queries, split = **dev**", out)

    def test_diagnostics_refuses_test_without_flag_and_honours_filter(self):
        base = ["--golden", self.p("golden.json"), "--runs", f"a={self.p('run_a.json')}"]
        code, _, err = capture(diagnostics.main, base + ["--split", "test"])
        self.assertEqual(code, 2)
        self.assertIn("peek at held-out data", err)
        code, out, err = capture(diagnostics.main, base + ["--split", "dev", "--verified-only"])
        self.assertEqual(code, 0, err)
        self.assertIn("2 queries", out)
        self.assertIn("verified-only", out)
        code, out, _ = capture(diagnostics.main, base + ["--split", "test", "--allow-test"])
        self.assertEqual(code, 0)


class TestRunOnce(Env):
    def test_test_split_requires_a_lock(self):
        code, out, err = self.harness()
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("needs a pre-registration lock", err)

    def test_unregistered_run_is_stamped(self):
        code, out, _ = self.harness("--unregistered")
        self.assertEqual(code, 0)
        self.assertIn("UNREGISTERED TEST RUN", out)

    def test_registered_run_is_logged_then_second_run_refused_then_rerun_is_stamped(self):
        lock = self.write_lock()
        code, out, err = self.harness("--prereg", lock)
        self.assertEqual(code, 0, err)
        self.assertIn("first recorded test run", out)
        self.assertIn("3 queries, split = **test**", out)
        ledger = pr.prior_runs(lock)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["event"], "test_run")
        self.assertEqual(ledger[0]["report_sha256"], pr.sha_text(out[:-1]))      # print() added one newline
        self.assertEqual(set(ledger[0]["runs"]), {"a", "b"})

        code, out2, err2 = self.harness("--prereg", lock)
        self.assertEqual(code, 2)
        self.assertEqual(out2, "")
        self.assertIn("already recorded", err2)
        self.assertEqual(len(pr.prior_runs(lock)), 1)

        code, out3, _ = self.harness("--prereg", lock, "--allow-rerun")
        self.assertEqual(code, 0)
        self.assertIn("TEST RE-RUN, not pre-registered", out3)
        self.assertEqual([e["event"] for e in pr.prior_runs(lock)], ["test_run", "test_rerun"])

    def test_nothing_is_scored_or_logged_when_the_run_drifts_from_the_lock(self):
        lock = self.write_lock()
        for extra, needle in ((["--primary-k", "5"], "setting primary_k"),
                              (["--hit-def", "seek"], "setting hit_def")):
            code, out, err = self.harness("--prereg", lock, *extra)
            self.assertEqual((code, out), (2, ""), needle)
            self.assertIn(needle, err)
        code, out, err = capture(eh.main, ["--golden", self.p("golden.json"), "--split", "test", "--verified-only",
                                           "--runs", f"a={self.p('run_a.json')}", "--prereg", lock])
        self.assertEqual(code, 2)
        self.assertIn("locked systems missing", err)
        code, out, err = self.harness("--prereg", lock, verified=False)
        self.assertEqual(code, 2)
        self.assertIn("setting verified_only", err)
        Path(self.p("code.py")).write_text("print('retriever v2')\n")
        code, out, err = self.harness("--prereg", lock)
        self.assertEqual(code, 2)
        self.assertIn("code changed since lock", err)
        self.assertEqual(pr.prior_runs(lock), [])

    def test_split_all_is_not_a_way_around_the_lock(self):
        code, out, err = self.harness(split="all")
        self.assertEqual(code, 2)
        self.assertIn("needs a pre-registration lock", err)
        lock = self.write_lock()
        code, out, err = self.harness("--prereg", lock, split="all")
        self.assertEqual(code, 2)
        self.assertIn("setting split", err)

    def test_lock_cli(self):
        cfg = self.p("cfg.json")
        Path(cfg).write_text(json.dumps(self.config))
        args = ["lock", "--config", cfg, "--golden", self.p("golden.json"), "--out", self.p("l2.json")]
        code, out, _ = capture(pr.main, args)
        self.assertEqual(code, 0)
        self.assertIn("2 systems, 1 code files hashed", out)
        self.assertEqual(capture(pr.main, args)[0], 2)                        # refuses to overwrite
        self.assertEqual(capture(pr.main, ["verify", "--lock", self.p("l2.json")])[0], 0)
        Path(self.p("code.py")).write_text("changed\n")
        code, _, err = capture(pr.main, ["verify", "--lock", self.p("l2.json")])
        self.assertEqual(code, 1)
        self.assertIn("code changed since lock", err)
        code, out, _ = capture(pr.main, ["status", "--lock", self.p("l2.json")])
        self.assertIn("test runs recorded: 0", out)
        code, out, _ = capture(pr.main, ["template"])
        self.assertEqual(sorted(json.loads(out)), ["code", "eval", "notes", "systems"])


if __name__ == "__main__":
    unittest.main()
