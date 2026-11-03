"""
Generates detailed per-query diagnostic and failure analysis data
for the viva demonstration dashboard.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent

def build_diagnostics_payload(force: bool = False) -> dict:
    cache_file = BASE_DIR / "data" / "diagnostics_104.json"
    if cache_file.exists() and not force:
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    golden_file = BASE_DIR / "eval" / "golden.json"
    if not golden_file.exists():
        return {"error": "golden.json not found"}

    with open(golden_file, "r", encoding="utf-8") as f:
        golden_data = json.load(f)
    queries = golden_data.get("queries", [])

    # Load runs if available
    run_bm25_p = BASE_DIR / "runs" / "run_104_bm25.json"
    run_en_p = BASE_DIR / "runs" / "run_104_hybrid_en.json"
    run_multi_p = BASE_DIR / "runs" / "run_104_hybrid_multi.json"
    run_rerank_p = BASE_DIR / "runs" / "run_104_reranked.json"

    runs = {}
    for name, p in [
        ("bm25", run_bm25_p),
        ("hybrid_en", run_en_p),
        ("hybrid_multi", run_multi_p),
        ("reranked", run_rerank_p),
    ]:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                runs[name] = json.load(f)

    # Load benchmark reports
    report_test_p = BASE_DIR / "report_104_test.json"
    report_dev_p = BASE_DIR / "report_104_dev.json"

    report_test = json.load(open(report_test_p, "r", encoding="utf-8")) if report_test_p.exists() else {}
    report_dev = json.load(open(report_dev_p, "r", encoding="utf-8")) if report_dev_p.exists() else {}

    lead_tol = 20.0
    seek_max_frac = 0.5
    overlap_frac = 0.5
    overlap_cap = 30.0

    query_details = []
    for q in queries:
        qid = q["id"]
        rel = q.get("relevant", [{}])[0]
        gt_vid = rel.get("video_id", "")
        gt_start = float(rel.get("start_sec", 0))
        gt_end = float(rel.get("end_sec", 0))
        gt_len = max(1.0, gt_end - gt_start)

        q_info = {
            "id": qid,
            "query": q["query"],
            "type": q.get("type", "unknown"),
            "split": q.get("split", "dev"),
            "notes": q.get("notes", ""),
            "gt_video": gt_vid,
            "gt_start": int(gt_start),
            "gt_end": int(gt_end),
            "gt_duration": int(gt_len),
            "systems": {},
        }

        for sname, srun in runs.items():
            res_list = srun.get(qid, [])
            top1 = res_list[0] if res_list else None

            # Calculate hit status
            hit_k1 = False
            hit_k3 = False
            hit_k5 = False
            first_hit_rank = None
            first_hit_error = None

            for rank, r in enumerate(res_list[:5], start=1):
                rvid = r.get("video_id", "")
                rstart = float(r.get("start_sec", 0))
                rend = float(r.get("end_sec", rstart + 75))

                if rvid == gt_vid:
                    # Seek hit condition:
                    # gt.start - 20s <= result.start <= gt.start + 0.5 * len(gt)
                    is_seek_hit = (gt_start - lead_tol <= rstart <= gt_start + seek_max_frac * gt_len)
                    if is_seek_hit:
                        if rank == 1:
                            hit_k1 = True
                        if rank <= 3:
                            hit_k3 = True
                        if rank <= 5:
                            hit_k5 = True
                        if first_hit_rank is None:
                            first_hit_rank = rank
                            first_hit_error = round(abs(rstart - gt_start), 1)

            top1_seek = int(top1.get("start_sec", 0)) if top1 else None
            top1_vid = top1.get("video_id", "") if top1 else ""
            top1_error = round(abs(top1_seek - gt_start), 1) if (top1 and top1_vid == gt_vid) else None

            q_info["systems"][sname] = {
                "top1_video": top1_vid,
                "top1_seek": top1_seek,
                "top1_error": top1_error,
                "same_video": (top1_vid == gt_vid) if top1 else False,
                "hit_k1": hit_k1,
                "hit_k3": hit_k3,
                "hit_k5": hit_k5,
                "first_hit_rank": first_hit_rank,
                "first_hit_error": first_hit_error,
            }

        query_details.append(q_info)

    return {
        "total_queries": len(query_details),
        "split_counts": {
            "dev": sum(1 for q in query_details if q["split"] == "dev"),
            "test": sum(1 for q in query_details if q["split"] == "test"),
        },
        "type_counts": {
            "lexical": sum(1 for q in query_details if q["type"] == "lexical"),
            "paraphrase": sum(1 for q in query_details if q["type"] == "paraphrase"),
            "conceptual": sum(1 for q in query_details if q["type"] == "conceptual"),
            "symptom": sum(1 for q in query_details if q["type"] == "symptom"),
        },
        "queries": query_details,
        "report_test": report_test,
        "report_dev": report_dev,
    }

if __name__ == "__main__":
    payload = build_diagnostics_payload(force=True)
    cache_file = BASE_DIR / "data" / "diagnostics_104.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("Diagnostics payload built and cached successfully!")
    print(f"Total queries: {payload.get('total_queries')}")
    print(f"Sample query 0: {payload['queries'][0]['id']} -> {payload['queries'][0]['query']}")
    print(f"Sample systems: {list(payload['queries'][0]['systems'].keys())}")
