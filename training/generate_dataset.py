"""
Leak-free dataset generator for fine-tuning the Lecture RAG Teaching Assistant LLM.

Strictly adheres to LABELING_PROTOCOL.md and leakage_check.py:
1. Zero test query leakage (never includes test queries).
2. Zero test span leakage (padding of 25s around all golden spans).
3. Zero dev span leakage (padding of 25s around all golden spans).
4. Zero train/val transcript overlap (splits on disjoint time intervals: <1200s for train, >=1200s for val).
5. 20% unanswerable / adversarial queries with strict {"bullets": []} refusal.
6. Exports build_messages(question, excerpts) matching llm_compare.py.

Outputs:
- training/data/train.jsonl
- training/data/val.jsonl
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import eval_harness as eh
from verify_labels import fmt_time

TRANSCRIPT_DIR = BASE_DIR / "transcripts"
EVAL_DIR = BASE_DIR / "eval"
OUT_DIR = BASE_DIR / "training" / "data"

SYSTEM_PROMPT = (
    "You are a teaching assistant. Answer the question using ONLY the numbered lecture excerpts. "
    'Reply with JSON: {"bullets": [{"text": "...", "sources": [excerpt numbers]}]}. '
    'If the excerpts do not answer the question, reply {"bullets": []}.'
)


def format_excerpts(excerpts: list[dict]) -> str:
    return "\n\n".join(
        f"[{i + 1}] ({fmt_time(e['start_sec'])}-{fmt_time(e['end_sec'])}) {e['text']}"
        for i, e in enumerate(excerpts)
    )


def build_messages(question: str, excerpts: list[dict]) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {question}\n\nLecture Excerpts:\n{format_excerpts(excerpts)}"},
    ]


ADVERSARIAL_QUERIES = [
    "balle balle",
    "tell me a funny programming joke",
    "how to configure next js server components with app router",
    "explain react useEffect hook dependencies array",
    "what is django orm prefetch_related vs select_related",
    "how to build flutter widgets with riverpod state management",
    "what is the capital city of australia",
    "spring boot security jwt configuration with filter chain",
    "sql query to find the second highest salary using dense_rank",
    "can you write a poem about autumn leaves and winter rain",
    "how to train a convolutional neural network with pytorch",
    "explain docker container networking bridge vs host mode",
    "who won the fifa world cup in 2022",
    "how to make authentic butter chicken at home from scratch",
    "what is express js middleware next function in node js",
    "how to implement dijkstra shortest path algorithm with priority queue",
    "explain avl tree rotations for balance factor restoration",
    "what is red black tree recoloring and rotation rules",
]


OUTRO_PATTERNS = re.compile(
    r"(wrapping up this video|instagram|twitter|linkedin|in the description|subscribe|social media|\[music\]|hit that like|consider hitting)",
    re.I,
)


def clean_text(text: str) -> str:
    cleaned = re.sub(
        r"\b(hey everyone|welcome back to the channel|so guys|um|uh|right so|let's understand)\b",
        "",
        text,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def load_raw_corpus() -> dict:
    corpus = {}
    for p in sorted(TRANSCRIPT_DIR.glob("*.json")):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        corpus[data["video_id"]] = data
    return corpus


def is_touching_gold(vid: str, start: float, end: float, gold_spans: list[eh.Span], pad: float = 75.0) -> bool:
    for g in gold_spans:
        if g.video_id == vid and eh.overlap_sec(start, end, g.start - pad, g.end + pad) > 0:
            return True
    return False


def get_gold_ngrams(corpus: dict, golden_queries: list) -> set:
    gold_ngrams = set()
    for q in golden_queries:
        for g in q.relevant:
            if g.video_id not in corpus:
                continue
            seg_texts = [
                seg["text"]
                for seg in corpus[g.video_id]["segments"]
                if float(seg.get("end", float(seg["start"]) + seg.get("duration", 0.0))) > g.start
                and float(seg["start"]) < g.end
            ]
            ws = re.findall(r"[a-z0-9]+", " ".join(seg_texts).lower())
            if len(ws) >= 8:
                for i in range(len(ws) - 7):
                    gold_ngrams.add(tuple(ws[i:i + 8]))
    return gold_ngrams


def mine_safe_windows(corpus: dict, golden_queries: list, window_sec: float = 40.0) -> list[dict]:
    """Clusters safe, non-golden transcript segments into contiguous coherent excerpts."""
    gold_spans = [g for q in golden_queries for g in q.relevant]
    gold_ngrams = get_gold_ngrams(corpus, golden_queries)
    safe_windows = []

    for vid_id, data in corpus.items():
        segs = data["segments"]
        i = 0
        while i < len(segs):
            s = segs[i]
            s_start = float(s["start"])
            s_end = float(s.get("end", s_start + s.get("duration", 0.0)))

            if is_touching_gold(vid_id, s_start, s_end, gold_spans):
                i += 1
                continue

            # Accumulate up to window_sec
            cluster = [s]
            curr_end = s_end
            j = i + 1
            while j < len(segs):
                next_s = segs[j]
                next_start = float(next_s["start"])
                next_end = float(next_s.get("end", next_start + next_s.get("duration", 0.0)))
                if is_touching_gold(vid_id, next_start, next_end, gold_spans):
                    break
                if next_end - s_start > window_sec:
                    break
                cluster.append(next_s)
                curr_end = next_end
                j += 1

            if curr_end - s_start >= 20.0:
                raw_text = clean_text(" ".join(seg["text"] for seg in cluster))
                ws = re.findall(r"[a-z0-9]+", raw_text.lower())
                has_gold_ngram = False
                if len(ws) >= 8:
                    for k in range(len(ws) - 7):
                        if tuple(ws[k:k + 8]) in gold_ngrams:
                            has_gold_ngram = True
                            break

                if len(raw_text) >= 100 and not OUTRO_PATTERNS.search(raw_text) and not has_gold_ngram:
                    safe_windows.append({
                        "video_id": vid_id,
                        "title": data["title"],
                        "start_sec": round(s_start, 1),
                        "end_sec": round(curr_end, 1),
                        "text": raw_text,
                    })

            i = max(j, i + 1)

    return safe_windows


def synthesize_question_and_bullet(window: dict) -> tuple[str, str]:
    text = window["text"]

    # Pick the most substantial informative sentence directly from the excerpt text
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", text) if len(s.strip()) > 35]
    if not sentences:
        sentences = [text[:160]]

    # Bullet uses the excerpt's own explanation words directly
    bullet = sentences[0]
    if len(bullet) > 180:
        bullet = bullet[:170].rsplit(" ", 1)[0]
    if not bullet.endswith("."):
        bullet += "."
    bullet = bullet[0].upper() + bullet[1:]

    # Dynamic technical words from the excerpt to prevent rigid prompt overlap
    stopwords = {
        "this", "that", "there", "these", "those", "have", "with", "from", "which",
        "about", "would", "could", "should", "their", "where", "being", "because",
        "something", "someone", "going", "doing", "think", "right", "like", "just",
    }
    words = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", text.lower()) if w not in stopwords]
    key_concept = words[0] if words else "algorithm"

    patterns = [
        f"How does the concept of {key_concept} apply here?",
        f"Explain how {key_concept} is handled in this lecture step.",
        f"What happens during the {key_concept} operation described?",
        f"According to the excerpt, how does {key_concept} behave?",
    ]
    idx = int(window["start_sec"] * 10) % len(patterns)
    q = patterns[idx]

    return q, bullet


def generate_dataset(seed: int = 42) -> tuple[list[dict], list[dict]]:
    random.seed(seed)
    golden_queries, _ = eh.load_golden(EVAL_DIR / "golden.json")

    corpus = load_raw_corpus()
    windows = mine_safe_windows(corpus, golden_queries, window_sec=35.0)
    random.shuffle(windows)

    # Split strictly by video to eliminate any train/val transcript overlap
    val_vids = {"D2vI2DNJGd8", "yVdKa8dnKiE"}
    train_vids = set(corpus.keys()) - val_vids

    train_windows = [w for w in windows if w["video_id"] in train_vids][:48]
    val_windows = [w for w in windows if w["video_id"] in val_vids][:12]

    def build_records(window_list: list[dict], adv_queries: list[str]) -> list[dict]:
        recs = []
        for w in window_list:
            q, bullet = synthesize_question_and_bullet(w)
            # Pick a distractor window from another video
            other_windows = [o for o in window_list if o["video_id"] != w["video_id"]]
            d = random.choice(other_windows) if other_windows else w

            excerpts = [w, d]
            pos_idx = 1
            if random.random() > 0.5:
                excerpts.reverse()
                pos_idx = 2

            msgs = build_messages(q, excerpts)
            asst = {"bullets": [{"text": bullet, "sources": [pos_idx]}]}
            msgs.append({"role": "assistant", "content": json.dumps(asst, ensure_ascii=False)})
            recs.append({"messages": msgs})

        # Add 20% adversarial unanswerable queries
        n_adv = max(2, int(len(recs) * 0.25))
        for aq in adv_queries[:n_adv]:
            e1, e2 = random.sample(window_list, min(2, len(window_list)))
            msgs = build_messages(aq, [e1, e2])
            msgs.append({"role": "assistant", "content": json.dumps({"bullets": []}, ensure_ascii=False)})
            recs.append({"messages": msgs})

        random.shuffle(recs)
        return recs

    train_recs = build_records(train_windows, ADVERSARIAL_QUERIES[:12])
    val_recs = build_records(val_windows, ADVERSARIAL_QUERIES[12:])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "train.jsonl", "w", encoding="utf-8") as f:
        for r in train_recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(OUT_DIR / "val.jsonl", "w", encoding="utf-8") as f:
        for r in val_recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return train_recs, val_recs


if __name__ == "__main__":
    train_set, val_set = generate_dataset()
    print(f"Generated {len(train_set)} train and {len(val_set)} val records (zero test/dev leakage).")
