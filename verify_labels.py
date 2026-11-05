#!/usr/bin/env python3
"""Blind verification of golden-set labels (spans set by an agent from transcripts).

Why: spans found by scanning transcript text can echo the transcript's own wording and
segmentation, which rewards lexical retrieval and keyword-snapping. A human who WATCHES
the video is the independent check the labeling protocol asks for.

Two row modes, assigned by a seeded, type-stratified draw:
  confirm  the sheet shows the proposed span; you confirm it or correct it (fast, fixes errors).
  blind    the sheet hides the span and shows only a coarse time region; you find the answer
           yourself. This subset gives an UNBIASED agreement rate for the agent's labels.

The worksheet never reads run files or retrieval output, so it cannot leak them.

  python verify_labels.py worksheet --golden eval/golden.json --out verification_sheet.csv
  # ... fill the sheet by watching the videos (see the generated README) ...
  python verify_labels.py apply --golden eval/golden.json --sheet verification_sheet.csv \
        --out eval/golden.verified.json --errata errata.csv --report verification_report.md \
        [--transcripts transcripts/]

`apply` never overwrites the original golden file. Evaluate with BOTH files and report both.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import eval_harness as eh
from eval_harness import HitConfig, Span, is_hit

MAX_SPANS = 3
DEFAULT_URL = "https://www.youtube.com/watch?v={video_id}&t={t}s"
SHEET_COLUMNS = ["query_id", "mode", "query", "video_id", "watch_link", "proposed_spans",
                 "hint_region", "verdict", "s1_start", "s1_end", "s2_start", "s2_end",
                 "s3_start", "s3_end", "notes"]
CONFIRM_VERDICTS = {"ok", "adjust", "drop"}
BLIND_VERDICTS = {"found", "drop"}
START_TOL_SEC = 5.0   # report whether the agent's start sat early/late by more than this

README = """VERIFICATION SHEET: how to fill it
==================================
Do this WITHOUT looking at any retrieval results, run files or reports.

Times: type plain seconds (750) or 12m30s. Avoid 12:30 in Excel, which turns it into a clock
time. Google Sheets is safer; if you use Excel, format the s*_start / s*_end columns as Text.

confirm rows (proposed_spans is shown)
  1. Open watch_link (it starts 30s before the proposed start).
  2. Find where the lecturer BEGINS addressing the concept and where the explanation is COMPLETE.
  3. verdict = ok      if you would move neither edge by more than about 10 seconds.
     verdict = adjust  otherwise; fill s1_start/s1_end (and s2_*, s3_* for genuine re-explanations).
     verdict = drop    if the video does not clearly answer the query.

blind rows (proposed_spans is hidden)
  1. Open watch_link; the answer is somewhere in hint_region (it may recur elsewhere in the video).
  2. Fill s1_start/s1_end (and s2_*, s3_*) with the span(s) you find.
     verdict = found, or drop if you cannot find a clear answer.

Span rules (LABELING_PROTOCOL.md section 4): start when the explanation begins, end when it is
complete, at least 5 seconds, no padding, a second span only for a real re-explanation.
Do not edit columns other than verdict, s*_start, s*_end, notes.
"""


class SheetError(Exception):
    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = list(errors)


# --------------------------------------------------------------------------
# time helpers
# --------------------------------------------------------------------------
_NUM = re.compile(r"^\d+(?:\.\d+)?$")
_MS = re.compile(r"^(\d+)m(?:(\d+(?:\.\d+)?)s?)?$")
_S = re.compile(r"^(\d+(?:\.\d+)?)s$")
_CLOCK2 = re.compile(r"^(\d+):(\d{1,2})$")
_CLOCK3 = re.compile(r"^(\d+):(\d{1,2}):(\d{1,2})$")


def parse_time(text):
    """'750' | '12m30s' | '12m' | '45s' | '12:30' (mm:ss) | '1:02:30' (h:mm:ss) -> seconds, or None if blank."""
    t = (text or "").strip().lower().replace(" ", "")
    if not t:
        return None
    if _NUM.match(t):
        return float(t)
    m = _MS.match(t)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2) or 0)
    m = _S.match(t)
    if m:
        return float(m.group(1))
    m = _CLOCK2.match(t)
    if m:
        mm, ss = int(m.group(1)), int(m.group(2))
        if ss >= 60:
            raise ValueError(f"bad time {text!r}: seconds must be < 60")
        return mm * 60 + ss
    m = _CLOCK3.match(t)
    if m:
        h, mm, ss = (int(g) for g in m.groups())
        if mm >= 60 or ss >= 60:
            raise ValueError(f"bad time {text!r}")
        return h * 3600 + mm * 60 + ss
    raise ValueError(f"cannot parse time {text!r}")


def fmt_time(sec: float) -> str:
    total = int(round(sec))
    m, s = divmod(total, 60)
    return f"{m}m{s:02d}s"


# --------------------------------------------------------------------------
# worksheet
# --------------------------------------------------------------------------
def assign_modes(items, blind_frac: float, seed: int) -> set:
    """Seeded draw, stratified by query type: ceil(blind_frac * n_type) blind queries per type."""
    rng = random.Random(seed)
    by_type: dict = {}
    for it in items:
        by_type.setdefault(it["type"], []).append(it["id"])
    blind: set = set()
    for t in sorted(by_type):
        ids = sorted(by_type[t])
        rng.shuffle(ids)
        n = math.ceil(blind_frac * len(ids)) if blind_frac > 0 else 0
        blind.update(ids[:n])
    return blind


def build_worksheet(items, blind_ids, url_template: str = DEFAULT_URL, hint_bucket: float = 600.0) -> list:
    rows, errors = [], []
    for it in items:
        spans = it["relevant"]
        vids = {str(s["video_id"]) for s in spans}
        if len(vids) != 1:
            errors.append(f"{it['id']}: spans in several videos {sorted(vids)}; split into one query per video")
            continue
        if len(spans) > MAX_SPANS:
            errors.append(f"{it['id']}: {len(spans)} spans; the sheet holds at most {MAX_SPANS}")
            continue
        vid = vids.pop()
        spans = sorted(spans, key=lambda s: float(s["start_sec"]))
        first = float(spans[0]["start_sec"])
        row = {c: "" for c in SHEET_COLUMNS}
        row.update(query_id=it["id"], query=it["query"], video_id=vid)
        if it["id"] in blind_ids:
            lo = math.floor(first / hint_bucket) * hint_bucket
            row.update(mode="blind", watch_link=url_template.format(video_id=vid, t=int(lo)),
                       proposed_spans="(hidden: find it yourself)",
                       hint_region=f"somewhere between {fmt_time(lo)} and {fmt_time(lo + hint_bucket)}"
                                   " (the topic may recur elsewhere)")
        else:
            row.update(mode="confirm",
                       watch_link=url_template.format(video_id=vid, t=max(0, int(first - 30))),
                       proposed_spans="; ".join(f"{fmt_time(float(s['start_sec']))} - {fmt_time(float(s['end_sec']))}"
                                                for s in spans))
        rows.append(row)
    if errors:
        raise SheetError(errors)
    rows.sort(key=lambda r: (r["video_id"], r["query_id"]))
    return rows


def write_sheet(rows, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def read_sheet(path) -> list:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------
def parse_spans(row) -> list:
    out = []
    for i in range(1, MAX_SPANS + 1):
        s, e = parse_time(row.get(f"s{i}_start")), parse_time(row.get(f"s{i}_end"))
        if s is None and e is None:
            continue
        if s is None or e is None:
            raise ValueError(f"span {i} is incomplete (needs both start and end)")
        if e <= s:
            raise ValueError(f"span {i} ends before it starts ({s:g} to {e:g})")
        if e - s < eh.MIN_SPAN_SEC:
            raise ValueError(f"span {i} is shorter than {eh.MIN_SPAN_SEC:g}s")
        out.append((s, e))
    return out


def _fmt_spans(spans) -> str:
    return "; ".join(f"{fmt_time(s)} - {fmt_time(e)}" for s, e in spans)


def apply_sheet(items, sheet_rows, transcripts=None, allow_partial: bool = False,
                seek_cfg: HitConfig | None = None) -> dict:
    """Pure function: returns {'items', 'errata', 'stats'}; raises SheetError listing every problem."""
    cfg = seek_cfg or HitConfig("seek")
    by_id = {(r.get("query_id") or "").strip(): r for r in sheet_rows}
    known = {it["id"] for it in items}
    errors = [f"sheet has unknown query id {q!r}" for q in by_id if q not in known]
    out_items, errata = [], []
    counts = {"confirm_ok": 0, "confirm_adjust": 0, "confirm_drop": 0,
              "blind_found": 0, "blind_drop": 0, "unverified": 0}
    blind = {"queries": 0, "human_spans": 0, "matched": 0, "agent_extra": 0,
             "start_diffs": [], "unmatched": []}
    confirm_shifts: list = []

    for it in items:
        row = by_id.get(it["id"])
        qid = it["id"]
        if row is None or not (row.get("verdict") or "").strip():
            if allow_partial:
                counts["unverified"] += 1
                out_items.append(dict(it, verified=False, label_source="agent"))
            else:
                errors.append(f"{qid}: " + ("missing from sheet" if row is None else "verdict is blank"))
            continue
        mode = (row.get("mode") or "").strip().lower()
        verdict = row["verdict"].strip().lower()
        if mode not in ("confirm", "blind"):
            errors.append(f"{qid}: mode {mode!r} must be confirm or blind")
            continue
        if verdict not in (CONFIRM_VERDICTS if mode == "confirm" else BLIND_VERDICTS):
            allowed = sorted(CONFIRM_VERDICTS if mode == "confirm" else BLIND_VERDICTS)
            errors.append(f"{qid}: verdict {verdict!r} not allowed in {mode} mode (use {allowed})")
            continue
        try:
            human = parse_spans(row)
        except ValueError as e:
            errors.append(f"{qid}: {e}")
            continue
        needs_spans = verdict in ("adjust", "found")
        if needs_spans and not human:
            errors.append(f"{qid}: verdict {verdict!r} needs at least one span")
            continue
        if not needs_spans and human:
            errors.append(f"{qid}: verdict {verdict!r} but span cells are filled")
            continue
        vid = str(it["relevant"][0]["video_id"])
        segs = (transcripts or {}).get(vid)
        if segs and human:
            last_end = max(s[1] for s in segs)
            bad = [e for _, e in human if e > last_end + 5]
            if bad:
                errors.append(f"{qid}: span end {max(bad):g}s is past the end of the transcript ({last_end:g}s); typo?")
                continue

        agent = [Span(str(s["video_id"]), float(s["start_sec"]), float(s["end_sec"])) for s in it["relevant"]]
        key = "blind" if mode == "blind" else "confirm"
        if verdict == "drop":
            counts[f"{key}_drop"] += 1
            errata.append({"query_id": qid, "mode": mode, "verdict": verdict, "field": "query",
                           "before": _fmt_spans([(a.start, a.end) for a in agent]), "after": "(dropped)",
                           "note": row.get("notes", "")})
            continue
        if verdict == "ok":
            counts["confirm_ok"] += 1
            out_items.append(dict(it, verified=True, verification_mode=mode, label_source="agent_confirmed"))
            continue

        counts["confirm_adjust" if mode == "confirm" else "blind_found"] += 1
        human_spans = [Span(vid, s, e) for s, e in human]
        new_rel = [{"video_id": vid, "start_sec": s, "end_sec": e} for s, e in human]
        out_items.append(dict(it, relevant=new_rel, verified=True, verification_mode=mode,
                              label_source="human", agent_relevant=it["relevant"]))
        before = [(a.start, a.end) for a in agent]
        if sorted(before) != sorted(human):
            errata.append({"query_id": qid, "mode": mode, "verdict": verdict, "field": "relevant",
                           "before": _fmt_spans(before), "after": _fmt_spans(human), "note": row.get("notes", "")})

        pair_diffs = []
        for h in human_spans:
            near = min(agent, key=lambda a: abs(a.start - h.start))
            pair_diffs.append(near.start - h.start)
        if mode == "confirm":
            confirm_shifts.extend(pair_diffs)
        else:
            blind["queries"] += 1
            matched = [any(is_hit(a, h, cfg) for a in agent) for h in human_spans]
            extra = [a for a in agent if not any(is_hit(a, h, cfg) for h in human_spans)]
            blind["human_spans"] += len(human_spans)
            blind["matched"] += sum(matched)
            blind["agent_extra"] += len(extra)
            blind["start_diffs"].extend(d for d, m in zip(pair_diffs, matched) if m)
            if not all(matched) or extra:
                blind["unmatched"].append(qid)
    # blind queries where the human found nothing count as total disagreement with the agent label
    for it in items:
        row = by_id.get(it["id"])
        if row and (row.get("mode") or "").strip().lower() == "blind" \
                and (row.get("verdict") or "").strip().lower() == "drop":
            blind["unmatched"].append(it["id"])
    if errors:
        raise SheetError(errors)
    return {"items": out_items, "errata": errata,
            "stats": {"counts": counts, "blind": blind, "confirm_shifts": confirm_shifts}}


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def _shift_summary(diffs) -> str:
    if not diffs:
        return "no paired spans"
    early = sum(1 for d in diffs if d < -START_TOL_SEC)
    late = sum(1 for d in diffs if d > START_TOL_SEC)
    return (f"n={len(diffs)}, median agent-minus-human start = {median(diffs):+.1f}s; "
            f"agent started >{START_TOL_SEC:g}s early on {early}, >{START_TOL_SEC:g}s late on {late}")


def build_report(src_sha, new_sha, result, n_total) -> str:
    st, c, b = result["stats"], result["stats"]["counts"], result["stats"]["blind"]
    md = ["# Label verification report", "",
          f"- original golden `sha256:{src_sha[:12]}` ({n_total} queries) -> verified `sha256:{new_sha[:12]}` "
          f"({len(result['items'])} queries)", "",
          "## Counts", "",
          f"- confirm rows: {c['confirm_ok']} ok, {c['confirm_adjust']} adjusted, {c['confirm_drop']} dropped",
          f"- blind rows: {c['blind_found']} found, {c['blind_drop']} dropped (answer not found)",
          f"- unverified (left as agent labels): {c['unverified']}", ""]
    md += ["## Blind subset: agreement of agent labels with an independent human", ""]
    total_blind_q = b["queries"] + c["blind_drop"]
    if b["human_spans"]:
        lo, hi = eh.wilson(b["matched"], b["human_spans"])
        rate = b["matched"] / b["human_spans"]
        md += [f"- {total_blind_q} blind queries; {b['human_spans']} human spans; "
               f"agent label agreed on **{b['matched']}/{b['human_spans']} = {100 * rate:.0f}%** "
               f"(95% Wilson CI {100 * lo:.0f}% to {100 * hi:.0f}%)",
               f"- agent spans with no matching human span: {b['agent_extra']}",
               f"- start difference where they agree: {_shift_summary(b['start_diffs'])}",
               "- agreement rule: the agent's start lies within [human.start - 20s, human.start + 0.5 x len(human)]"]
        if rate < 0.85:
            md.append("- WARNING: below the protocol's 85% target. The agent labels are not reliable enough "
                      "to report unqualified; use the verified file as primary.")
        if b["unmatched"]:
            md.append("- queries to inspect: " + ", ".join(sorted(set(b["unmatched"]))))
    else:
        md.append("- no blind queries were filled, so there is no unbiased agreement estimate.")
    md += ["", "## Confirm subset: how the agent's starts compare", "",
           f"- adjusted spans: {_shift_summary(st['confirm_shifts'])}", "",
           "## Errata", "",
           f"{len(result['errata'])} changes; every one is listed in the errata file with before/after.", "",
           "## What to do next", "",
           "1. Re-run the evaluation on BOTH golden files (same run files; query ids are unchanged) and report both.",
           "2. If conclusions differ between them, trust the verified file and say so.",
           "3. Do not edit labels again after seeing test results."]
    return "\n".join(md)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_raw(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["queries"] if isinstance(data, dict) else data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("worksheet")
    w.add_argument("--golden", required=True)
    w.add_argument("--out", default="verification_sheet.csv")
    w.add_argument("--blind-frac", type=float, default=0.25)
    w.add_argument("--seed", type=int, default=7)
    w.add_argument("--hint-bucket", type=float, default=600.0)
    w.add_argument("--url-template", default=DEFAULT_URL)
    w.add_argument("--force", action="store_true")
    a = sub.add_parser("apply")
    a.add_argument("--golden", required=True)
    a.add_argument("--sheet", required=True)
    a.add_argument("--out", default="golden.verified.json")
    a.add_argument("--errata", default="errata.csv")
    a.add_argument("--report", default="verification_report.md")
    a.add_argument("--transcripts")
    a.add_argument("--allow-partial", action="store_true")
    a.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    try:
        queries, sha = eh.load_golden(args.golden)
    except eh.GoldenError as e:
        print("Golden file is invalid:", *e.errors, sep="\n  - ", file=sys.stderr)
        return 2
    items = _load_raw(args.golden)

    if args.cmd == "worksheet":
        if not ("{video_id}" in args.url_template and "{t}" in args.url_template):
            print("--url-template must contain {video_id} and {t}", file=sys.stderr)
            return 2
        out = Path(args.out)
        if out.exists() and not args.force:
            print(f"{out} exists; refusing to overwrite (use --force). Filled sheets are precious.", file=sys.stderr)
            return 2
        try:
            rows = build_worksheet(items, assign_modes(items, args.blind_frac, args.seed),
                                   args.url_template, args.hint_bucket)
        except SheetError as e:
            print("Cannot build the worksheet:", *e.errors, sep="\n  - ", file=sys.stderr)
            return 2
        write_sheet(rows, out)
        readme = out.with_suffix(".README.txt")
        readme.write_text(README, encoding="utf-8")
        nb = sum(1 for r in rows if r["mode"] == "blind")
        print(f"wrote {out} ({len(rows)} rows: {nb} blind, {len(rows) - nb} confirm) and {readme}")
        print(f"golden sha256:{sha[:12]}  seed={args.seed}  blind_frac={args.blind_frac}")
        return 0

    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"{out} exists; refusing to overwrite (use --force).", file=sys.stderr)
        return 2
    transcripts = eh.load_transcripts(args.transcripts) if args.transcripts else None
    try:
        result = apply_sheet(items, read_sheet(args.sheet), transcripts, args.allow_partial)
    except SheetError as e:
        print("Sheet problems (nothing was written):", *e.errors, sep="\n  - ", file=sys.stderr)
        return 2
    payload = {"_provenance": {"source_golden_sha256": sha, "sheet": Path(args.sheet).name,
                               "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "note": "labels verified by a human watching the videos; see errata"},
               "queries": result["items"]}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        _, new_sha = eh.load_golden(out)
    except eh.GoldenError as e:
        out.unlink()
        print("Verified file failed validation (removed):", *e.errors, sep="\n  - ", file=sys.stderr)
        return 2
    with open(args.errata, "w", newline="", encoding="utf-8-sig") as f:
        cw = csv.DictWriter(f, fieldnames=["query_id", "mode", "verdict", "field", "before", "after", "note"])
        cw.writeheader()
        cw.writerows(result["errata"])
    report = build_report(sha, new_sha, result, len(items))
    Path(args.report).write_text(report, encoding="utf-8")
    print(report)
    print(f"\nwrote {out} (sha256:{new_sha[:12]}), {args.errata}, {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
