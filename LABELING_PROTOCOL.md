# Labeling Protocol for the Lecture-Retrieval Golden Set

Goal: a golden set of 50+ queries whose labels do not favor any retriever, so that differences between BM25, dense, hybrid and reranked systems reflect the systems and not the way the test was built.

## 1. What this protocol prevents

| Bias | How it happens | Control in this protocol |
|---|---|---|
| **Label leakage** | Ground-truth timestamps found by keyword-searching transcripts, so the labels favor lexical matching | Spans are labeled by watching the video; no text search of transcripts while labeling (section 4) |
| **Query leakage** | Queries written after reading the transcript reuse the lecturer's exact words | Queries are written from non-transcript sources (section 3), then audited with `--transcripts` |
| **Tuning on the test set** | You tweak chunk size or models until the numbers go up | dev/test split, frozen hash, test evaluated once per pre-declared system (section 8) |
| **Vague "hit"** | Partial overlaps counted generously; overlapping chunks fill top-k | Formal hit definition and temporal dedup (sections 6 and 7) |
| **Tiny n** | 10 queries; one query = 10 points | 50+ queries, confidence intervals, paired tests (section 9) |

## 2. Corpus requirements

- At least **5 videos**, at least **3 distinct topics**, ideally **2 or more lecturers or styles** (one lecturer's verbal habits can favor one retriever).
- No single video holds more than **20%** of the queries.
- Freeze the corpus: record video ids and the transcription settings (model, language, `initial_prompt`). Changing the transcripts later invalidates comparisons, because labels are in video time but retrieval depends on transcript text.

## 3. Writing queries (before anything else)

**Sources allowed:** video title and description, chapter list, slide titles, a syllabus or topic list, your own course notes, or real questions you or classmates asked.

**Sources forbidden:** the transcript, anything produced by a retriever, search results from your own pipeline.

If you use an LLM to draft queries, give it only the allowed sources, never the transcript.

**Query types and target mix**

| type | what it is | example (DSA lecture) | target share |
|---|---|---|---|
| `lexical` | uses a term the lecture defines | "tortoise and hare" | 20-30% |
| `paraphrase` | same idea, different words | "technique with two pointers moving at different speeds" | 25-30% |
| `conceptual` | a why/how question | "why does Floyd's algorithm find the cycle start" | 25-30% |
| `symptom` | a student's confusion or bug | "my recursive function never stops" | 15-20% |

Rules:
1. One information need per query. No compound questions.
2. A query must be answerable by a specific moment in at least one video. If you cannot point to the moment, drop the query.
3. Do not include numbers like "part 3" or video titles in the query.
4. Write queries as a student would type them, not as the lecturer would say them.

## 4. Labeling spans (watching, not searching)

**Blind rule:** no retriever has been run on these queries, and you do not Ctrl-F the transcript. Find the moment by watching or scrubbing the video, using chapters and slides to navigate.

**Span definition:** from the moment the lecturer begins addressing the concept to the moment the explanation of it is complete. Record `start_sec` and `end_sec` to the second.

- Minimum length 5s (enforced), typically 30-180s. Over 240s triggers a warning: split it or tighten it.
- If the lecturer returns to the topic later with a real re-explanation, add a **second span** to `relevant`. A passing mention or recap is not a span.
- If a tangent interrupts the explanation, end the span before the tangent and start a new one after it.
- Include the setup sentence ("so how do we detect a loop?") if the explanation depends on it.
- Do not pad boundaries "to be safe". The hit definition already tolerates lead-in (section 6).

**Two-person variant (recommended for at least 15 queries):** a second labeler marks spans independently without seeing the first labeler's spans. Agreement = the first labeler's `start_sec` falls inside the second labeler's span window, as defined for `seek` hits. Target 85% or higher. Below that, the span rules are too loose: tighten them and relabel the disagreements.

**Solo variant:** write all queries first, then wait at least a day before labeling, and label in a different order than you wrote them.

## 5. Splits

Assign each query `dev` or `test` when you write it, before any retriever runs. Use roughly 40% dev and 60% test, stratified so each type and video appears in both. Tune chunk size, models and fusion weights on **dev only**.

## 6. Formal hit definition

A retrieved result `r = (video, start, end)` is a **hit** for a ground-truth span `g` iff it is in the same video and satisfies one of:

- **`seek` (primary):** `g.start - 20s <= r.start <= g.start + 0.5 * len(g)`
  This matches what the UI does (`player.seekTo(r.start)`): the user lands at most 20s before the answer begins and early enough that most of it is still ahead. A chunk that starts 60s before the answer is a miss, which is correct, because the user would sit through a minute of lead-in.
- **`overlap` (secondary):** `intersection(r, g) >= min(0.5 * len(g), 30s)`
  The result contains a meaningful part of the answer, regardless of where it starts. The 30s cap stops long spans from requiring excessive coverage.

A query is hit at k if any of the top-k deduped results hits any of its spans. Report both definitions; a large gap between them means your chunks are too long or start too early, not that retrieval is wrong. Defaults are changeable (`--lead-tol`, `--seek-max-frac`, `--overlap-frac`, `--overlap-cap`), but **fix them before the first run** and do not change them afterwards.

## 7. Temporal deduplication

Overlapping windows fill the top-k with near-copies of one moment. Before scoring, walk each ranked list best-first and drop any result that overlaps an already-kept result in the same video by 50% or more of the shorter span. Then truncate to k. Dump **at least 30 raw results** per query so dedup has material to work with.

## 8. Freezing and discipline

1. Finish labeling. Run `--validate-only`; fix errors.
2. Record the golden file's SHA-256 (the report prints it). Commit the file.
3. Write down, before running test, the exact list of systems you will compare.
4. Evaluate `dev` as often as you like. Evaluate `test` once per final system list.
5. If you find a labeling error afterwards, fix it, record the change in an errata note, and re-hash. Never edit labels to help a retriever.

## 9. Metrics and how to read them

- **Hit@k** with Wilson 95% interval. **MRR@k** with bootstrap 95% interval. **Span recall@k** for multi-span queries. Precision@k is omitted on purpose: with one correct moment its ceiling is 1/k, which punishes large k.
- **Paired comparison:** for two systems, count queries only A found vs only B found, with an exact McNemar test, plus a bootstrap interval on the MRR difference.
- **Sample size reality check:** with 60 queries and about 12 disagreements between two systems, a 10-2 split gives p of about 0.04, which is a gap of roughly 13 points. Smaller gaps will not be resolvable. Report intervals, not rankings.
- **Lexical audit:** `--transcripts` reports how many query words appear in the answer span. If fewer than 30% of queries have under 50% overlap, the set favors BM25 by construction.
- **Seek precision:** median `|r.start - g.start|` for the first hit, in seconds.

## 10. File formats

`golden.json`: see `golden.template.json`. `type` is one of `lexical | paraphrase | conceptual | symptom`; `split` is `dev | test`.

Run files, one per retriever, ranked best-first:

```python
import json

def dump_run(retrieve, golden_path, out_path, n=30):
    """retrieve(query_text, n) -> iterable of objects with video_id/start_sec/end_sec."""
    queries = json.load(open(golden_path))["queries"]
    run = {q["id"]: [{"video_id": r.video_id, "start_sec": r.start_sec, "end_sec": r.end_sec}
                     for r in retrieve(q["query"], n)] for q in queries}
    json.dump(run, open(out_path, "w"))
```

Transcripts for the audit: `transcripts/<video_id>.json`, a list of `{"start","end","text"}`.

## 11. Commands

```bash
python eval_harness.py --golden golden.json --validate-only --transcripts transcripts/
python eval_harness.py --golden golden.json --split dev \
    --runs bm25=runs_bm25.json dense=runs_dense.json hybrid=runs_hybrid.json \
    --compare bm25 hybrid --transcripts transcripts/ --out report_dev.md --json-out report_dev.json
python eval_harness.py --golden golden.json --split test --runs ... --out report_test.md
```

## 12. Time budget and checklist

About 4-6 minutes per query (write, locate, label). Roughly 5 hours for 60 queries, plus agreement checks.

- [ ] 5+ videos, 3+ topics, frozen transcription settings
- [ ] Queries written from non-transcript sources; type mix near target
- [ ] dev/test assigned before any retriever runs
- [ ] Spans labeled by watching; multi-span queries handled
- [ ] Second labeler on 15+ queries; agreement 85% or higher
- [ ] `--validate-only` clean; leakage audit reviewed
- [ ] Hit definition parameters fixed; SHA-256 recorded; system list written down

## 13. What you may and may not claim

- You may claim a number you measured on the test split with its interval and the set size ("Hit@3 of 71% (95% CI 58-81%) on 60 held-out queries across 6 videos").
- You may not claim a ranking between systems whose intervals overlap and whose paired test is not significant. "No detectable difference" is a legitimate finding.
- Never report dev numbers as final results.
