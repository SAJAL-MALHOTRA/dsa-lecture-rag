import unittest

from verify_labels import (
    SheetError, apply_sheet, assign_modes, build_report, build_worksheet, fmt_time,
    parse_spans, parse_time,
)


def item(qid, qtype="conceptual", start=100.0, end=200.0, vid="v1", extra=None):
    rel = [{"video_id": vid, "start_sec": start, "end_sec": end}] + (extra or [])
    return {"id": qid, "query": f"question {qid}", "type": qtype, "split": "dev", "relevant": rel}


def sheet_for(items, blind=()):
    rows = build_worksheet(items, set(blind))
    return {r["query_id"]: r for r in rows}


class Times(unittest.TestCase):
    def test_parse_variants(self):
        cases = {"750": 750, "12m30s": 750, "12m": 720, "45s": 45, "12:30": 750,
                 "1:02:30": 3750, " 12M30S ": 750, "0m05s": 5, "": None, None: None}
        for text, want in cases.items():
            self.assertEqual(parse_time(text), want, text)

    def test_parse_rejects_garbage(self):
        for bad in ("abc", "12:75", "1:75:00", "12:3:4:5", "-5"):
            with self.assertRaises(ValueError, msg=bad):
                parse_time(bad)

    def test_format_roundtrip(self):
        self.assertEqual(fmt_time(750), "12m30s")
        self.assertEqual(fmt_time(65), "1m05s")
        for sec in (0, 5, 65, 750, 4510):
            self.assertEqual(parse_time(fmt_time(sec)), sec)

    def test_parse_spans_validation(self):
        self.assertEqual(parse_spans({"s1_start": "10", "s1_end": "50", "s2_start": "1m", "s2_end": "2m"}),
                         [(10.0, 50.0), (60.0, 120.0)])
        for row in ({"s1_start": "10"}, {"s1_start": "50", "s1_end": "10"}, {"s1_start": "10", "s1_end": "12"}):
            with self.assertRaises(ValueError):
                parse_spans(row)


class Worksheet(unittest.TestCase):
    def test_assignment_is_deterministic_and_stratified(self):
        items = [item(f"q{i}", ["lexical", "paraphrase", "conceptual", "symptom"][i % 4]) for i in range(16)]
        a, b = assign_modes(items, 0.25, seed=7), assign_modes(items, 0.25, seed=7)
        self.assertEqual(a, b)
        self.assertNotEqual(a, assign_modes(items, 0.25, seed=8))
        types = {it["type"] for it in items if it["id"] in a}
        self.assertEqual(types, {"lexical", "paraphrase", "conceptual", "symptom"})
        self.assertEqual(len(a), 4)
        self.assertEqual(assign_modes(items, 0, seed=7), set())

    def test_confirm_shows_span_blind_hides_it(self):
        rows = sheet_for([item("a", start=140, end=245), item("b", start=1490, end=1600)], blind=["b"])
        self.assertEqual(rows["a"]["mode"], "confirm")
        self.assertIn("2m20s - 4m05s", rows["a"]["proposed_spans"])
        self.assertIn("t=110s", rows["a"]["watch_link"])        # 30s before the proposed start
        self.assertEqual(rows["b"]["mode"], "blind")
        self.assertNotIn("1490", rows["b"]["proposed_spans"] + rows["b"]["hint_region"])
        self.assertNotIn("24m50s", rows["b"]["proposed_spans"] + rows["b"]["hint_region"])
        self.assertIn("t=1200s", rows["b"]["watch_link"])       # 10-minute bucket start
        self.assertIn("20m00s", rows["b"]["hint_region"])
        self.assertIn("30m00s", rows["b"]["hint_region"])

    def test_multi_video_and_too_many_spans_are_rejected(self):
        multi = item("m", extra=[{"video_id": "v2", "start_sec": 10, "end_sec": 60}])
        many = item("n", extra=[{"video_id": "v1", "start_sec": 300 + 100 * i, "end_sec": 350 + 100 * i} for i in range(3)])
        with self.assertRaises(SheetError) as cm:
            build_worksheet([multi, many], set())
        text = "\n".join(cm.exception.errors)
        self.assertIn("several videos", text)
        self.assertIn("at most 3", text)


class Apply(unittest.TestCase):
    def setUp(self):
        self.items = [item("c_ok", start=100, end=200), item("c_adj", start=300, end=400),
                      item("c_drop", start=500, end=600), item("b_found", start=700, end=800),
                      item("b_far", start=900, end=1000), item("b_drop", start=1100, end=1200)]
        self.rows = sheet_for(self.items, blind=["b_found", "b_far", "b_drop"])

    def fill(self, qid, verdict, *spans, notes=""):
        r = self.rows[qid]
        r["verdict"] = verdict
        r["notes"] = notes
        for i, (s, e) in enumerate(spans, start=1):
            r[f"s{i}_start"], r[f"s{i}_end"] = str(s), str(e)

    def fill_all(self):
        self.fill("c_ok", "ok")
        self.fill("c_adj", "adjust", (330, 420), notes="starts later")
        self.fill("c_drop", "drop")
        self.fill("b_found", "found", (705, 790))      # agent start 700: inside [685, 747.5]
        self.fill("b_far", "found", (1000, 1100))      # agent start 900: 100s early -> disagrees
        self.fill("b_drop", "drop")

    def run_apply(self, **kw):
        return apply_sheet(self.items, list(self.rows.values()), **kw)

    def test_full_flow(self):
        self.fill_all()
        res = self.run_apply()
        ids = [i["id"] for i in res["items"]]
        self.assertEqual(ids, ["c_ok", "c_adj", "b_found", "b_far"])      # drops removed, order kept
        by = {i["id"]: i for i in res["items"]}
        self.assertEqual(by["c_ok"]["label_source"], "agent_confirmed")
        self.assertEqual(by["c_adj"]["relevant"], [{"video_id": "v1", "start_sec": 330.0, "end_sec": 420.0}])
        self.assertEqual(by["c_adj"]["agent_relevant"][0]["start_sec"], 300)   # provenance kept
        self.assertTrue(all(i["verified"] for i in res["items"]))
        c = res["stats"]["counts"]
        self.assertEqual((c["confirm_ok"], c["confirm_adjust"], c["confirm_drop"], c["blind_found"], c["blind_drop"]),
                         (1, 1, 1, 2, 1))

    def test_blind_agreement_and_shifts(self):
        self.fill_all()
        st = self.run_apply()["stats"]
        self.assertEqual((st["blind"]["human_spans"], st["blind"]["matched"]), (2, 1))
        self.assertEqual(st["blind"]["start_diffs"], [-5.0])               # agent 700 vs human 705
        self.assertEqual(sorted(set(st["blind"]["unmatched"])), ["b_drop", "b_far"])
        self.assertEqual(st["confirm_shifts"], [-30.0])                   # agent 300 vs human 330: early

    def test_errata_lists_only_real_changes(self):
        self.fill_all()
        self.fill("b_found", "found", (700, 800))                         # identical to agent: no errata row
        res = self.run_apply()
        got = {(e["query_id"], e["field"]) for e in res["errata"]}
        self.assertEqual(got, {("c_adj", "relevant"), ("c_drop", "query"), ("b_far", "relevant"), ("b_drop", "query")})
        adj = next(e for e in res["errata"] if e["query_id"] == "c_adj")
        self.assertEqual((adj["before"], adj["after"]), ("5m00s - 6m40s", "5m30s - 7m00s"))
        self.assertEqual(adj["note"], "starts later")

    def test_problems_are_all_reported_and_nothing_is_returned(self):
        self.fill("c_ok", "ok", (10, 60))              # ok but spans filled
        self.fill("c_adj", "adjust")                    # adjust without spans
        self.fill("b_found", "ok")                      # wrong verdict for blind mode
        self.fill("c_drop", "maybe")
        self.fill("b_far", "found", (50, 10))           # end before start
        with self.assertRaises(SheetError) as cm:       # b_drop left blank
            self.run_apply()
        text = "\n".join(cm.exception.errors)
        for needle in ("span cells are filled", "needs at least one span", "not allowed in blind mode",
                       "verdict 'maybe'", "ends before it starts", "b_drop: verdict is blank"):
            self.assertIn(needle, text)

    def test_allow_partial_keeps_agent_labels(self):
        self.fill("c_ok", "ok")
        res = self.run_apply(allow_partial=True)
        self.assertEqual(res["stats"]["counts"]["unverified"], 5)
        by = {i["id"]: i for i in res["items"]}
        self.assertFalse(by["c_adj"]["verified"])
        self.assertEqual(by["c_adj"]["relevant"][0]["start_sec"], 300)

    def test_transcript_length_typo_check(self):
        self.fill_all()
        self.fill("c_adj", "adjust", (330, 99999))
        transcripts = {"v1": [(0.0, 10.0, "x"), (1190.0, 1300.0, "y")]}
        with self.assertRaises(SheetError) as cm:
            self.run_apply(transcripts=transcripts)
        self.assertIn("past the end of the transcript", "\n".join(cm.exception.errors))

    def test_unknown_ids_and_bad_mode(self):
        self.fill_all()
        rows = list(self.rows.values()) + [{"query_id": "ghost", "mode": "confirm", "verdict": "ok"}]
        with self.assertRaises(SheetError) as cm:
            apply_sheet(self.items, rows)
        self.assertIn("unknown query id 'ghost'", "\n".join(cm.exception.errors))
        self.rows["c_ok"]["mode"] = "sneaky"
        with self.assertRaises(SheetError):
            self.run_apply()

    def test_report_flags_low_agreement(self):
        self.fill_all()
        res = self.run_apply()
        text = build_report("a" * 64, "b" * 64, res, len(self.items))
        self.assertIn("1/2 = 50%", text)
        self.assertIn("below the protocol's 85% target", text)
        self.assertIn("b_far", text)


if __name__ == "__main__":
    unittest.main()
