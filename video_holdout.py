#!/usr/bin/env python3
"""Video-level holdout (k-fold) for the fine-tuning experiment.

Why: random held-out QUESTIONS from lectures the model trained on only show that it learned
the lecture text and the output format. To test whether fine-tuning generalises to material
it never saw, hold out whole VIDEOS: train without them, evaluate only on questions about them.

What this does (it does not need your dataset generator)
  split     assigns every golden video to one of K folds (seeded; stratified by topic group if
            you pass --groups). For each fold k it writes, into <out-dir>/foldk/:
              train.jsonl, val.jsonl    your existing records minus every record that draws on a
                                        held-out video (8-gram transcript overlap) or contains a
                                        held-out golden question
              golden.holdout.json       the golden queries whose videos are ALL held out in fold k
              train_videos.txt, heldout_videos.txt, manifest.json
            Each golden query is held out in exactly one fold, so over K folds every question is
            answered by a model that never saw its video. Queries spanning several videos that land
            in different folds cannot be held out cleanly and are listed as excluded.
  pool      merges the JSON outputs of llm_compare.py from the K folds into one report.

Records are dropped on ANY overlap with a held-out video, including distractor excerpts. If too
few records survive (exit code 3), regenerate the dataset restricted to train_videos.txt instead.

  python video_holdout.py split --golden eval/golden.json --transcripts transcripts/ \
      --train training/data/train.jsonl --val training/data/val.jsonl --folds 2 --out-dir holdout/
  # train one model per fold on holdout/foldK/train.jsonl, then per fold:
  python llm_compare.py --golden holdout/foldK/golden.holdout.json --split all ... --json-out foldK.json
  python video_holdout.py pool --results fold0.json fold1.json --out pooled.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

import eval_harness as eh
import leakage_check as lc
import llm_compare as lcmp

MAX_REFUSAL_SHARE = 0.40


# --------------------------------------------------------------------------
# fold assignment
# --------------------------------------------------------------------------
def assign_folds(videos, folds: int, seed: int, groups: dict | None = None) -> dict:
    """video -> fold index. Round-robin within seeded-shuffled groups, with one running counter,
    so every group is spread across folds and fold sizes differ by at most one."""
    videos = sorted(set(videos))
    if folds < 2:
        raise ValueError("--folds must be at least 2")
    if len(videos) < folds:
        raise ValueError(f"{len(videos)} golden videos cannot fill {folds} folds")
    rng = random.Random(seed)
    by_group: dict = {}
    for v in videos:
        by_group.setdefault((groups or {}).get(v, "_"), []).append(v)
    assign, counter = {}, 0
    for g in sorted(by_group):
        vs = by_group[g]
        rng.shuffle(vs)
        for v in vs:
            assign[v] = counter % folds
            counter += 1
    return assign


def split_queries(raw_items: list, assign: dict, fold: int):
    """-> (items held out in this fold, ids of queries that straddle folds)."""
    held, straddle = [], []
    for it in raw_items:
        folds_of = {assign.get(str(s["video_id"])) for s in it["relevant"]}
        if len(folds_of) > 1:
            straddle.append(it["id"])
        elif folds_of == {fold}:
            held.append(it)
    return held, straddle


# --------------------------------------------------------------------------
# record filtering
# --------------------------------------------------------------------------
def filter_records(records: list, heldout: list, transcripts: dict, held_queries: list,
                   ngram: int, min_shared: int, query_thresh: float = 0.8):
    """Drop records that draw on any held-out video or contain a held-out golden question.
    -> (kept, stats)"""
    prepared = lc.prepare(records, 5)
    vsh = {v: lc.shingles(lc.words(" ".join(t for _, _, t in transcripts[v])), ngram)
           for v in heldout if v in transcripts}
    qsh = []
    for q in held_queries:
        qw = lc.words(q["query"])
        if len(qw) >= lc.WEAK_QUERY_WORDS:
            n = min(3, len(qw))
            qsh.append((n, lc.shingles(qw, n)))
    kept, by_video, by_query = [], {v: 0 for v in vsh}, 0
    for rec, p in zip(records, prepared):
        g = lc.grams(p, ngram)
        hit = [v for v, sh in vsh.items() if len(sh & g) >= min_shared]
        for v in hit:
            by_video[v] += 1
        if hit:
            continue
        if any(len(sh & lc.grams(p, n)) / len(sh) >= query_thresh for n, sh in qsh):
            by_query += 1
            continue
        kept.append(rec)
    return kept, {"in": len(records), "kept": len(kept), "dropped_video": len(records) - len(kept) - by_query,
                  "dropped_query": by_query, "per_video": by_video}


def describe(records: list) -> dict:
    prepared = lc.prepare(records, 5)
    n = len(prepared)
    empty = sum(1 for p in prepared if p["empty_answer"])
    return {"n": n, "refusals": empty, "refusal_share": (empty / n) if n else 0.0}


def verify_clean(kept_train: list, kept_val: list, held_vids: list, held_queries_raw: list,
                 transcripts: dict, ngram: int, min_shared: int) -> list:
    """Independent re-check with leakage_check's own functions. Returns a list of problems."""
    queries = [eh.Query(q["id"], q["query"], q["type"], q["split"],
                        tuple(eh.Span(str(s["video_id"]), float(s["start_sec"]), float(s["end_sec"]))
                              for s in q["relevant"])) for q in held_queries_raw]
    files = {"train": lc.prepare(kept_train, 5)}
    if kept_val:
        files["val"] = lc.prepare(kept_val, 5)
    problems = []
    rows, _ = lc.span_leaks(queries, files, transcripts, ngram, min_shared)
    problems += [f"span of {r['query_id']} still in {r['file']} ({r['records']} records)" for r in rows if r["records"]]
    problems += [f"query {r['query_id']} still in {r['file']} record {r['record']}"
                 for r in lc.query_leaks(queries, files, 0.8) if not r["weak"]]
    hv = [v for v in held_vids if v in transcripts]
    cover = lc.video_coverage([eh.Query("x", "a b c d", "lexical", "dev", (eh.Span(v, 0.0, 10.0),)) for v in hv],
                              files, transcripts, ngram, min_shared)
    problems += [f"video {r['video_id']} still appears in {f}" for r in cover for f in files if r.get(f)]
    return problems


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def sha_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_jsonl(path, records):
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")


def run_split(args) -> int:
    try:
        queries, gsha = eh.load_golden(args.golden)
    except eh.GoldenError as e:
        print("Golden file is invalid:", *e.errors, sep="\n  - ", file=sys.stderr)
        return 2
    raw = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    raw_items = raw["queries"] if isinstance(raw, dict) else raw
    transcripts = eh.load_transcripts(args.transcripts)
    groups = json.loads(Path(args.groups).read_text(encoding="utf-8")) if args.groups else None
    try:
        train_recs = lc.load_jsonl(args.train)
        val_recs = lc.load_jsonl(args.val) if args.val else []
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    gold_videos = sorted({str(s["video_id"]) for it in raw_items for s in it["relevant"]})
    missing = [v for v in gold_videos if v not in transcripts]
    if missing:
        print(f"error: no transcript for golden video(s): {missing}", file=sys.stderr)
        return 2
    try:
        assign = assign_folds(gold_videos, args.folds, args.seed, groups)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    out_root = Path(args.out_dir)
    insufficient, summary = False, []
    for k in range(args.folds):
        held_vids = sorted(v for v, f in assign.items() if f == k)
        train_vids = sorted(v for v in transcripts if v not in held_vids)
        held_items, straddle = split_queries(raw_items, assign, k)
        k_train, st_train = filter_records(train_recs, held_vids, transcripts, held_items, args.ngram, args.min_shared)
        k_val, st_val = filter_records(val_recs, held_vids, transcripts, held_items, args.ngram, args.min_shared)
        problems = verify_clean(k_train, k_val, held_vids, held_items, transcripts, args.ngram, args.min_shared)
        if problems:
            print(f"fold {k}: filtered data still leaks (bug or threshold issue):", *problems, sep="\n  - ", file=sys.stderr)
            return 1
        d = out_root / f"fold{k}"
        d.mkdir(parents=True, exist_ok=True)
        write_jsonl(d / "train.jsonl", k_train)
        write_jsonl(d / "val.jsonl", k_val)
        (d / "train_videos.txt").write_text("\n".join(train_vids) + "\n", encoding="utf-8")
        (d / "heldout_videos.txt").write_text("\n".join(held_vids) + "\n", encoding="utf-8")
        (d / "golden.holdout.json").write_text(json.dumps(
            {"_provenance": {"source_golden_sha256": gsha, "fold": k, "folds": args.folds, "seed": args.seed,
                             "heldout_videos": held_vids},
             "queries": held_items}, indent=2), encoding="utf-8")
        desc = describe(k_train)
        enough = len(k_train) >= args.min_train_records
        insufficient |= not enough
        manifest = {"fold": k, "folds": args.folds, "seed": args.seed, "ngram": args.ngram, "min_shared": args.min_shared,
                    "golden_sha256": gsha, "inputs": {"train": sha_file(args.train),
                                                      "val": sha_file(args.val) if args.val else None},
                    "assignment": assign, "heldout_videos": held_vids, "train_videos": train_vids,
                    "heldout_queries": [q["id"] for q in held_items], "straddling_queries": straddle,
                    "train": st_train, "val": st_val, "train_after": desc, "sufficient": enough}
        (d / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        summary.append((k, held_vids, held_items, straddle, st_train, st_val, desc, enough))

    print(f"golden sha256:{gsha[:12]}, {len(raw_items)} queries, {len(gold_videos)} videos, {args.folds} folds, seed {args.seed}")
    for k, hv, items, straddle, st_t, st_v, desc, enough in summary:
        print(f"\nfold {k}: held-out videos {', '.join(hv)}")
        print(f"  held-out queries: {len(items)} (dev {sum(i['split'] == 'dev' for i in items)}, "
              f"test {sum(i['split'] == 'test' for i in items)})"
              + (f"; excluded as straddling folds: {', '.join(straddle)}" if straddle else ""))
        print(f"  train records: {st_t['in']} -> {st_t['kept']} kept "
              f"({st_t['dropped_video']} drew on held-out videos, {st_t['dropped_query']} contained a held-out question)")
        if args.val:
            print(f"  val records:   {st_v['in']} -> {st_v['kept']} kept")
        if desc["n"]:
            print(f"  refusal share among kept train records: {desc['refusals']}/{desc['n']} ({100 * desc['refusal_share']:.0f}%)")
            if desc["refusal_share"] > MAX_REFUSAL_SHARE:
                print(f"  WARNING: refusals dominate (> {MAX_REFUSAL_SHARE:.0%}); a model trained on this learns to refuse. "
                      "Regenerate with the train videos instead of filtering.")
        if not enough:
            print(f"  INSUFFICIENT: fewer than {args.min_train_records} records survive. "
                  f"Regenerate the dataset using only {out_root / f'fold{k}' / 'train_videos.txt'}.")
    if insufficient:
        return 3
    print("\nVerified: no kept record touches a held-out video or question, in any fold.")
    print("Next: train one model per fold on foldK/train.jsonl (check train_lora.py --help for its data and output "
          "options), evaluate each with llm_compare.py --golden foldK/golden.holdout.json --split all, then run `pool`.")
    return 0


# --------------------------------------------------------------------------
# pooling
# --------------------------------------------------------------------------
def run_pool(args) -> int:
    loaded = []
    for p in args.results:
        try:
            loaded.append(json.loads(Path(p).read_text(encoding="utf-8")))
        except (OSError, ValueError) as e:
            print(f"error reading {p}: {e}", file=sys.stderr)
            return 2
    if len(loaded) < 2:
        print("error: give at least two --results files", file=sys.stderr)
        return 2
    names = list(loaded[0]["results"])
    for d in loaded[1:]:
        if list(d["results"]) != names:
            print("error: folds were run with different condition names", file=sys.stderr)
            return 2
    keys = ("context", "n_ctx", "ground_thr", "retries", "index_base", "default_prompt")
    for d in loaded[1:]:
        diff = [k for k in keys if d["meta"].get(k) != loaded[0]["meta"].get(k)]
        if diff:
            print(f"error: folds were run with different settings: {diff}", file=sys.stderr)
            return 2
    conds = {n: [r for d in loaded for r in d["results"][n]] for n in names}
    ids = [r["id"] for r in conds[names[0]]]
    if len(set(ids)) != len(ids):
        print("error: the same question appears in more than one fold; folds must not overlap", file=sys.stderr)
        return 2
    meta = dict(loaded[0]["meta"])
    meta["golden_sha"] = hashlib.sha256("".join(d["meta"]["golden_sha"] for d in loaded).encode()).hexdigest()
    meta["split"] = f"pooled over {len(loaded)} video-holdout folds"
    report = lcmp.build_report(meta, conds, [])
    report += ("\n\n## Pooling note\n\n"
               f"{len(ids)} questions from {len(loaded)} folds. Each question was answered by a model that never saw "
               "its video during fine-tuning. Within a fold the conditions are paired, so the McNemar tables above "
               "pool paired outcomes across folds; different folds used different tuned models.")
    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split")
    s.add_argument("--golden", required=True)
    s.add_argument("--transcripts", required=True)
    s.add_argument("--train", required=True)
    s.add_argument("--val")
    s.add_argument("--folds", type=int, default=2)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--groups", help="JSON {video_id: topic_group}; spreads each topic across folds")
    s.add_argument("--out-dir", default="holdout")
    s.add_argument("--ngram", type=int, default=8)
    s.add_argument("--min-shared", type=int, default=3)
    s.add_argument("--min-train-records", type=int, default=30)
    p = sub.add_parser("pool")
    p.add_argument("--results", nargs="+", required=True, help="llm_compare.py --json-out files, one per fold")
    p.add_argument("--out")
    args = ap.parse_args(argv)
    return run_split(args) if args.cmd == "split" else run_pool(args)


if __name__ == "__main__":
    sys.exit(main())
