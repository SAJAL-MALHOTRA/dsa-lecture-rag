#!/usr/bin/env python3
"""Leakage check: did the fine-tuning data see the golden evaluation set?

Reads the chat-style JSONL files used for fine-tuning (train, and optionally val)
and compares them with the golden set and the transcripts. Standard library only.

Checks
  A. Query leakage      golden query text appearing (near-verbatim) in a training record.
  B. Span leakage       golden answer-span text (from the transcripts) appearing in training
                        records. If a test-split span is in the training data, the model has
                        seen the answer it will be graded on.
  C. Video coverage     how many training records draw on each golden video. If every golden
                        video is in training, "held out" can only mean held-out questions,
                        not held-out lectures.
  D. Train/val overlap  duplicates and near-duplicates between train and validation, and how
                        many validation records share transcript text with training records.
                        High overlap means validation scores measure memorisation of the
                        template and the lecture text, not generalisation.
  E. Label balance      share of training records whose target is an empty-bullets refusal.

Record formats understood: {"messages":[{"role","content"},...]}, {"prompt","completion"},
or any JSON object (all string values are read as user text).

  python leakage_check.py --golden eval/golden.json --train training/data/train.jsonl \
      --val training/data/val.jsonl --transcripts transcripts/ --out leakage_report.md

Exit code: 1 if any TEST-split query or span leaks (a hard failure), else 0.
Dev-split leaks and train/val overlap are warnings.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from statistics import median
from pathlib import Path

import eval_harness as eh

WORD = re.compile(r"[a-z0-9]+")
WEAK_QUERY_WORDS = 4   # queries shorter than this match common phrases by accident


# --------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------
def words(text: str) -> list:
    return WORD.findall(text.lower())


def shingles(ws: list, n: int) -> set:
    if n <= 0 or len(ws) < n:
        return set()
    return {tuple(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_jsonl(path) -> list:
    out = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{i}: invalid JSON ({e.msg})") from None
    return out


def _strings(obj) -> list:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in _strings(v)]
    return []


def record_texts(rec):
    """-> (user_text, assistant_text). The system prompt is deliberately ignored: it is the
    same in every record and would otherwise make everything look alike."""
    if isinstance(rec, dict) and isinstance(rec.get("messages"), list):
        user, asst = [], []
        for m in rec["messages"]:
            if not isinstance(m, dict):
                continue
            role, content = m.get("role", "user"), str(m.get("content", ""))
            if role == "assistant":
                asst.append(content)
            elif role != "system":
                user.append(content)
        return "\n".join(user), "\n".join(asst)
    if isinstance(rec, dict) and "prompt" in rec:
        return str(rec.get("prompt", "")), str(rec.get("completion", ""))
    return "\n".join(_strings(rec)), ""


def parse_assistant(text: str):
    """The target object, or None if it is not the expected {"bullets": [...]} JSON."""
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(obj, dict) and isinstance(obj.get("bullets"), list):
        return obj
    return None


def prepare(records: list, sim_ngram: int) -> list:
    out = []
    for r in records:
        user, asst = record_texts(r)
        uw, aw = words(user), words(asst)
        parsed = parse_assistant(asst)
        out.append({"uw": uw, "aw": aw, "raw_asst": asst, "cache": {},
                    "u_sim": shingles(uw, sim_ngram), "a_sim": shingles(aw, sim_ngram),
                    "empty_answer": bool(parsed is not None and not parsed["bullets"]),
                    "parsed": parsed is not None})
    return out


def grams(p: dict, n: int) -> set:
    if n not in p["cache"]:
        p["cache"][n] = shingles(p["uw"], n) | shingles(p["aw"], n)
    return p["cache"][n]


def span_text(transcripts: dict, span: eh.Span) -> str:
    segs = transcripts.get(span.video_id) or []
    return " ".join(t.strip() for a, b, t in segs if b > span.start and a < span.end)


# --------------------------------------------------------------------------
# A. query leakage
# --------------------------------------------------------------------------
def query_leaks(queries, files: dict, thresh: float) -> list:
    rows = []
    for q in queries:
        qw = words(q.query)
        if not qw:
            continue
        n = min(3, len(qw))
        qsh = shingles(qw, n)
        for fname, prepared in files.items():
            best, best_i = 0.0, None
            for i, p in enumerate(prepared):
                s = len(qsh & grams(p, n)) / len(qsh)
                if s > best:
                    best, best_i = s, i
            if best_i is not None and best >= thresh:
                allw = prepared[best_i]["uw"] + prepared[best_i]["aw"]
                pos = next((j for j in range(len(allw) - n + 1) if tuple(allw[j:j + n]) in qsh), 0)
                rows.append({"query_id": q.id, "split": q.split, "file": fname, "record": best_i + 1,
                             "score": best, "n_words": len(qw), "weak": len(qw) < WEAK_QUERY_WORDS,
                             "snippet": " ".join(allw[max(0, pos - 8):pos + n + 12])})
    return rows


# --------------------------------------------------------------------------
# B. span leakage
# --------------------------------------------------------------------------
def span_leaks(queries, files: dict, transcripts: dict, ngram: int, min_shared: int):
    rows, skipped = [], []
    for q in queries:
        pieces = [span_text(transcripts, g) for g in q.relevant if g.video_id in transcripts]
        if not pieces:
            skipped.append((q.id, "video has no transcript"))
            continue
        sh = shingles(words(" ".join(pieces)), ngram)
        if not sh:
            skipped.append((q.id, f"span has fewer than {ngram} words"))
            continue
        for fname, prepared in files.items():
            shared = [(i, len(sh & grams(p, ngram))) for i, p in enumerate(prepared)]
            shared = [(i, c) for i, c in shared if c >= min_shared]
            top = max((c for _, c in shared), default=0)
            rows.append({"query_id": q.id, "split": q.split, "file": fname, "records": len(shared),
                         "max_shared": top, "coverage": top / len(sh),
                         "record_ids": [i + 1 for i, _ in sorted(shared, key=lambda x: -x[1])[:5]]})
    return rows, skipped


# --------------------------------------------------------------------------
# C. video coverage
# --------------------------------------------------------------------------
def video_coverage(queries, files: dict, transcripts: dict, ngram: int, min_shared: int) -> list:
    vids = sorted({g.video_id for q in queries for g in q.relevant})
    rows = []
    for vid in vids:
        segs = transcripts.get(vid)
        if not segs:
            continue
        vsh = shingles(words(" ".join(t for _, _, t in segs)), ngram)
        row = {"video_id": vid, "queries": sum(1 for q in queries if any(g.video_id == vid for g in q.relevant))}
        for fname, prepared in files.items():
            row[fname] = sum(1 for p in prepared if len(vsh & grams(p, ngram)) >= min_shared)
        rows.append(row)
    return rows


# --------------------------------------------------------------------------
# D. train / val overlap
# --------------------------------------------------------------------------
def split_overlap(train: list, val: list, ngram: int, min_shared: int) -> dict:
    ukeys = {tuple(p["uw"]) for p in train}
    akeys = {tuple(p["aw"]) for p in train if not p["empty_answer"]}
    dup_user = sum(1 for p in val if tuple(p["uw"]) in ukeys)
    val_ans = [p for p in val if not p["empty_answer"]]
    dup_asst = sum(1 for p in val_ans if tuple(p["aw"]) in akeys)
    u_sims, a_sims = [], []
    for p in val:
        u_sims.append(max((jaccard(p["u_sim"], t["u_sim"]) for t in train), default=0.0))
    for p in val_ans:
        a_sims.append(max((jaccard(p["a_sim"], t["a_sim"]) for t in train if not t["empty_answer"]), default=0.0))
    shares = sum(1 for p in val
                 if any(len(grams(p, ngram) & grams(t, ngram)) >= min_shared for t in train))
    return {"n_val": len(val), "n_val_answers": len(val_ans), "dup_user": dup_user, "dup_asst": dup_asst,
            "u_sims": u_sims, "a_sims": a_sims, "share_text": shares}


# --------------------------------------------------------------------------
# E. label balance
# --------------------------------------------------------------------------
def label_balance(prepared: list) -> dict:
    return {"n": len(prepared), "empty": sum(1 for p in prepared if p["empty_answer"]),
            "unparseable": sum(1 for p in prepared if not p["parsed"])}


# --------------------------------------------------------------------------
# verdict and report
# --------------------------------------------------------------------------
def verdict(q_rows, s_rows, overlap) -> tuple:
    fails, warns = [], []
    for r in q_rows:
        if r["weak"]:
            continue
        msg = f"query {r['query_id']} ({r['split']}) appears in {r['file']} record {r['record']} (score {r['score']:.2f})"
        (fails if r["split"] == "test" else warns).append(msg)
    for r in s_rows:
        if r["records"]:
            msg = (f"answer span of {r['query_id']} ({r['split']}) appears in {r['records']} {r['file']} record(s) "
                   f"(max {r['max_shared']} shared n-grams, {100 * r['coverage']:.0f}% of the span)")
            (fails if r["split"] == "test" else warns).append(msg)
    if overlap and overlap["n_val"] and overlap["share_text"] / overlap["n_val"] >= 0.5:
        warns.append(f"{overlap['share_text']}/{overlap['n_val']} validation records share transcript text with training records")
    status = "FAIL" if fails else ("WARN" if warns else "PASS")
    return status, fails, warns


def _stats(vals: list) -> str:
    if not vals:
        return "n/a"
    return f"median {median(vals):.2f}, max {max(vals):.2f}, share >= 0.5: {sum(1 for v in vals if v >= 0.5)}/{len(vals)}"


def build_report(meta, q_rows, s_rows, skipped, vcov, overlap, balance, status, fails, warns) -> str:
    md = ["# Fine-tuning leakage report", "", f"**Verdict: {status}**", ""]
    md += [f"- golden `sha256:{meta['golden_sha'][:12]}`, {meta['n_queries']} queries "
           f"(dev {meta['n_dev']}, test {meta['n_test']})",
           "- training files: " + ", ".join(f"`{k}`" for k, v in meta["files"].items()),
           f"- span/transcript matching: {meta['ngram']}-word n-grams, >= {meta['min_shared']} shared "
           f"counts as overlap; query matching threshold {meta['query_thresh']:.2f}", ""]
    if fails:
        md += ["## Hard failures (test split)", ""] + [f"- {m}" for m in fails] + [""]
    if warns:
        md += ["## Warnings", ""] + [f"- {m}" for m in warns[:40]]
        if len(warns) > 40:
            md.append(f"- ... and {len(warns) - 40} more")
        md.append("")

    md += ["## A. Golden queries found in training records", ""]
    strong = [r for r in q_rows if not r["weak"]]
    if strong:
        md += ["| query | split | file | record | score | context |", "|---|---|---|---:|---:|---|"]
        md += [f"| {r['query_id']} | {r['split']} | {r['file']} | {r['record']} | {r['score']:.2f} | …{r['snippet']}… |"
               for r in strong[:25]]
        md += ["", "Check the context: a match inside lecture text (not in the question) means the lecturer "
                   "said the same words, which is a different issue from the question itself being in training."]
    else:
        md.append("None at or above the threshold.")
    weak = [r for r in q_rows if r["weak"]]
    if weak:
        md += ["", f"{len(weak)} short queries (under {WEAK_QUERY_WORDS} words) matched but are ignored: "
                   "short phrases match by accident."]
    md.append("")

    md += ["## B. Golden answer spans found in training records", ""]
    if s_rows is None:
        md += ["Skipped: pass --transcripts.", ""]
    else:
        per_split = {}
        for r in s_rows:
            d = per_split.setdefault((r["file"], r["split"]), [0, 0])
            d[0] += 1
            d[1] += 1 if r["records"] else 0
        md += ["| file | split | golden queries | spans seen in training |", "|---|---|---:|---:|"]
        md += [f"| {f} | {s} | {n} | {k} ({100 * k / n:.0f}%) |" for (f, s), (n, k) in sorted(per_split.items())]
        hit = [r for r in s_rows if r["records"]]
        if hit:
            md += ["", "| query | split | file | records | max shared | span coverage | record ids |", "|---|---|---|---:|---:|---:|---|"]
            md += [f"| {r['query_id']} | {r['split']} | {r['file']} | {r['records']} | {r['max_shared']} | "
                   f"{100 * r['coverage']:.0f}% | {', '.join(map(str, r['record_ids']))} |" for r in hit[:25]]
        if skipped:
            md += ["", f"Skipped {len(skipped)} queries: " + "; ".join(f"{a} ({b})" for a, b in skipped[:10])]
        md.append("")

    md += ["## C. Golden videos used in training", ""]
    if vcov is None:
        md += ["Skipped: pass --transcripts.", ""]
    else:
        files = list(meta["files"])
        md += ["| video | golden queries | " + " | ".join(f"records in {f}" for f in files) + " |",
               "|---|---:|" + "---:|" * len(files)]
        md += [f"| {r['video_id']} | {r['queries']} | " + " | ".join(str(r[f]) for f in files) + " |" for r in vcov]
        if vcov and all(r.get(files[0], 0) > 0 for r in vcov):
            md += ["", "Every golden video appears in training. Questions can be held out, lectures cannot: "
                       "the model has seen the lecture text. For a held-out claim, train on some videos and "
                       "evaluate on others."]
        md.append("")

    md += ["## D. Train / validation overlap", ""]
    if overlap is None:
        md += ["Skipped: no --val file.", ""]
    else:
        n = overlap["n_val"]
        md += [f"- validation records: {n} ({overlap['n_val_answers']} with answers)",
               f"- identical user prompts also in train: {overlap['dup_user']}/{n}",
               f"- identical answer outputs also in train: {overlap['dup_asst']}/{overlap['n_val_answers']}",
               f"- nearest-train similarity of user prompts (word 5-gram Jaccard): {_stats(overlap['u_sims'])}",
               f"- nearest-train similarity of answer outputs: {_stats(overlap['a_sims'])}",
               f"- validation records sharing transcript text with some training record: {overlap['share_text']}/{n}", "",
               "Read: high similarity or high shared-text means validation loss and format scores say "
               "little about performance on new questions or new lecture material.", ""]

    md += ["## E. Label balance", ""]
    md += ["| file | records | empty-bullets (refusal) | target not parseable |", "|---|---:|---:|---:|"]
    md += [f"| {f} | {b['n']} | {b['empty']} ({100 * b['empty'] / b['n']:.0f}%) | {b['unparseable']} |"
           for f, b in balance.items() if b["n"]]
    return "\n".join(md)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--golden", required=True)
    ap.add_argument("--train", required=True)
    ap.add_argument("--val")
    ap.add_argument("--transcripts")
    ap.add_argument("--ngram", type=int, default=8)
    ap.add_argument("--min-shared", type=int, default=3)
    ap.add_argument("--query-thresh", type=float, default=0.8)
    ap.add_argument("--sim-ngram", type=int, default=5)
    ap.add_argument("--out")
    ap.add_argument("--json-out")
    args = ap.parse_args(argv)

    try:
        queries, sha = eh.load_golden(args.golden)
        train = prepare(load_jsonl(args.train), args.sim_ngram)
        val = prepare(load_jsonl(args.val), args.sim_ngram) if args.val else None
    except eh.GoldenError as e:
        print("Golden file is invalid:", *e.errors, sep="\n  - ", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not train:
        print("training file is empty", file=sys.stderr)
        return 2
    transcripts = eh.load_transcripts(args.transcripts) if args.transcripts else None

    files = {"train": train}
    if val is not None:
        files["val"] = val
    q_rows = query_leaks(queries, files, args.query_thresh)
    s_rows = skipped = vcov = None
    if transcripts is not None:
        s_rows, skipped = span_leaks(queries, files, transcripts, args.ngram, args.min_shared)
        vcov = video_coverage(queries, files, transcripts, args.ngram, args.min_shared)
    overlap = split_overlap(train, val, args.ngram, args.min_shared) if val is not None else None
    balance = {k: label_balance(v) for k, v in files.items()}
    status, fails, warns = verdict(q_rows, s_rows or [], overlap)
    meta = {"golden_sha": sha, "n_queries": len(queries), "n_dev": sum(q.split == "dev" for q in queries),
            "n_test": sum(q.split == "test" for q in queries), "files": {k: len(v) for k, v in files.items()},
            "ngram": args.ngram, "min_shared": args.min_shared, "query_thresh": args.query_thresh}
    report = build_report(meta, q_rows, s_rows, skipped, vcov, overlap, balance, status, fails, warns)
    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(
            {"status": status, "fails": fails, "warns": warns, "queries": q_rows, "spans": s_rows,
             "video_coverage": vcov, "balance": balance}, indent=2, default=str), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
