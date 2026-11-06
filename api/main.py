"""
FastAPI application for YouTube Lecture RAG and DSA Learning Platform.

Provides:
- GET  /api/health        : System status and indexed corpus metrics
- GET  /api/search        : Deduplicated, seek-refined lecture moments + matching DSA problem
- GET  /api/dsa-snippet   : Multi-language DSA code, approach, and complexities from Striver's sheet
- POST /api/validate-key  : Live authenticated ping to Grok / Groq / OpenAI API endpoints
- POST /api/execute       : Sandboxed Python & C++ code execution with timeout enforcement
- GET  /api/edge-cases    : Canonical edge-case stress-testing suites per problem category
- POST /api/grill-me      : Interactive FAANG interview drill (question generation + answer evaluation)
- POST /api/answer        : Evidence-grounded synthesis with timestamp citations and code
- GET  /api/corpus        : Indexed course metadata
- Static HTML UI mount    : Single-page DSA Learning Interface with pop-out algorithm drawer
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# Ensure project root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
import time
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import eval_harness as eh
from eval_harness import Span, dedup
from diagnostics import SegmentIndex
from ytrag.models import Segment, Chunk
from ytrag.chunk import chunk_segments
from ytrag.retriever import BM25Retriever, DenseRetriever, HybridRetriever
from ytrag.summarize import GroundedSummarizer
from ytrag.dsa_sheet import DSASheetIndex, DSASolution
from ytrag.llm_provider import validate_api_key, generate_llm_answer, get_provider_details
from ytrag.query_expander import expand_dsa_query
from ytrag.pattern_retriever import PatternRetriever, get_pattern_retriever
from ytrag.context_enricher import ContextEnricher, get_context_enricher
from ytrag.topic_classifier import classify_canonical_topics

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
TRANSCRIPT_DIR = BASE_DIR / "transcripts"
STATIC_DIR = BASE_DIR / "api" / "static"
DSA_SHEET_DIR = BASE_DIR / "data" / "strivers_a2z_sheet"
CORPUS_DB = BASE_DIR / "data" / "corpus_v1.sqlite"

# In-memory retrieval state
state: dict = {}


def load_corpus() -> tuple[list[Chunk], dict, list[dict]]:
    """Loads transcripts, builds full-duration chunks, and constructs segment index."""
    # Fast-path: Load from frozen SQLite database if available
    if CORPUS_DB.exists():
        try:
            from ytrag.corpus_store import load_chunks_from_db, load_raw_transcripts_from_db
            chunks = load_chunks_from_db(CORPUS_DB)
            raw_transcripts, videos_meta = load_raw_transcripts_from_db(CORPUS_DB)
            if chunks and raw_transcripts:
                return chunks, raw_transcripts, videos_meta
        except Exception:
            pass  # Fall back to directory parsing on error

    chunks: list[Chunk] = []
    videos_meta: list[dict] = []
    raw_transcripts = eh.load_transcripts(TRANSCRIPT_DIR)

    for p in sorted(TRANSCRIPT_DIR.glob("*.json")):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        vid_id = data["video_id"]
        title = data["title"]
        segs = [
            Segment(
                start=float(s["start"]),
                end=float(s.get("end", s["start"] + s.get("duration", 0.0))),
                text=s["text"],
            )
            for s in data["segments"]
        ]
        vid_chunks = chunk_segments(vid_id, title, segs, window_sec=75, overlap_sec=15)
        chunks.extend(vid_chunks)

        total_dur = int(max((s.end for s in segs), default=0))
        videos_meta.append({
            "video_id": vid_id,
            "title": title,
            "duration_sec": total_dur,
            "chunk_count": len(vid_chunks),
        })

    return chunks, raw_transcripts, videos_meta


def resolve_default_provider() -> str:
    """Returns the default provider: respects DEFAULT_PROVIDER env, falls back to local if weights exist, else groq or extractive."""
    env_p = os.getenv("DEFAULT_PROVIDER", "").strip().lower()
    if env_p:
        return env_p
    if os.getenv("RENDER"):
        if os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"):
            return "groq"
        return "extractive"
    try:
        from ytrag.local_llm import LocalTeachingAssistant
        if LocalTeachingAssistant.get_instance().is_available:
            return "local"
    except Exception:
        pass
    if os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"):
        return "groq"
    return "extractive"


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    # 1. Instantly load DSA Sheet index (< 0.05s) so core metadata is available immediately
    dsa_index = DSASheetIndex(DSA_SHEET_DIR)
    state["dsa_index"] = dsa_index
    state["pattern_retriever"] = get_pattern_retriever()
    state["context_enricher"] = get_context_enricher()
    state["chunks"] = []
    state["videos_meta"] = []
    state["is_ready"] = False
    ready_event = asyncio.Event()
    state["ready_event"] = ready_event

    # 2. Warm up heavy retrievers and SQLite corpus in background executor
    # This guarantees the server binds to $PORT in < 0.1s so cloud health-checks succeed instantly!
    async def _async_warmup():
        loop = asyncio.get_running_loop()
        def _sync_load():
            chunks, raw_transcripts, videos_meta = load_corpus()
            bm25 = BM25Retriever(chunks)
            dense_model = os.getenv("EMBEDDER_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
            dense = DenseRetriever(chunks, model_name=dense_model, lazy=True)
            dense.load()
            hybrid = HybridRetriever(bm25, dense)
            segment_index = SegmentIndex(raw_transcripts, window=1)
            summarizer = GroundedSummarizer()
            return chunks, raw_transcripts, videos_meta, hybrid, segment_index, summarizer

        try:
            chunks, raw_transcripts, videos_meta, hybrid, segment_index, summarizer = await loop.run_in_executor(None, _sync_load)
            state["chunks"] = chunks
            state["hybrid"] = hybrid
            state["segment_index"] = segment_index
            state["videos_meta"] = videos_meta
            state["summarizer"] = summarizer
            state["is_ready"] = True
            ready_event.set()
            print(f"[FastAPI Lifespan] Corpus ({len(chunks)} chunks, {len(videos_meta)} videos) and retrievers initialized successfully!", flush=True)
        except Exception as e:
            print(f"[FastAPI Lifespan] Error during background index loading: {e}", file=sys.stderr, flush=True)

    warmup_task = asyncio.create_task(_async_warmup())
    if os.getenv("PYTEST_CURRENT_TEST"):
        await warmup_task
    yield
    state.clear()


app = FastAPI(title="DSA Lecture Retrieval & Learning Platform", lifespan=lifespan)


class SearchResultItem(BaseModel):
    video_id: str
    video_title: str
    seek_sec: int
    start_sec: float
    end_sec: float
    timestamp_display: str
    snippet: str
    url: str
    score: float
    dsa_snippet: Optional[dict] = None


class SearchResponse(BaseModel):
    query: str
    total_found: int
    summary: str = ""
    results: list[SearchResultItem]
    dsa_snippet: Optional[dict] = None
    canonical_topics: list[str] = []
    pattern_chunks: list[dict] = []
    enrichment: Optional[dict] = None


class KeyValidationRequest(BaseModel):
    provider: str = "groq"
    api_key: str
    base_url: str = ""
    model: str = ""


class AnswerRequest(BaseModel):
    query: str
    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    provider: Optional[str] = ""
    api_key: Optional[str] = ""
    base_url: Optional[str] = ""
    model: Optional[str] = ""


class CodeExecuteRequest(BaseModel):
    language: str = "python"
    code: str
    stdin_input: str = ""
    timeout_sec: float = 5.0


class CodeExecuteResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    execution_time_ms: float
    exit_code: int
    message: str


class EdgeCasesResponse(BaseModel):
    topic: str
    title: str
    cases: list[dict]


class GrillMeRequest(BaseModel):
    title: str
    topic: str = ""
    code: str = ""
    question: Optional[str] = None
    trap_warning: Optional[str] = None
    gold_standard: Optional[str] = None
    user_answer: Optional[str] = None
    provider: Optional[str] = "groq"
    api_key: Optional[str] = ""
    base_url: Optional[str] = ""
    model: Optional[str] = ""


class GrillMeResponse(BaseModel):
    mode: str  # "question" or "evaluation"
    question: str
    trap_warning: str
    gold_standard: Optional[str] = None
    source: str
    evaluation: Optional[dict] = None


def _retrieve(query: str, k: int = 5) -> SearchResponse:
    """Run the normal retrieval pipeline for a query with HyDE pedagogical expansion."""
    query = query.strip()
    if not query:
        return SearchResponse(query=query, total_found=0, results=[])

    # Multi-Source Integration: Topic Classification, Patterns, and Context Enrichment
    canonical_topics = classify_canonical_topics(query)
    pattern_retriever = state.get("pattern_retriever") or get_pattern_retriever()
    pattern_chunks = []
    if pattern_retriever:
        matched_patterns = pattern_retriever.retrieve(
            query,
            k=2,
            canonical_topic=canonical_topics[0] if canonical_topics else None,
        )
        pattern_chunks = [p.model_dump() for p, _ in matched_patterns]

    enricher = state.get("context_enricher") or get_context_enricher()
    enrichment_data = enricher.enrich(canonical_topics) if enricher else None

    hybrid: Optional[HybridRetriever] = state.get("hybrid")
    segment_index: Optional[SegmentIndex] = state.get("segment_index")
    dsa_index: Optional[DSASheetIndex] = state.get("dsa_index")

    # HyDE expansion: bridges code-syntax & phonetic slang to Hinglish lecture speech
    expanded_query = expand_dsa_query(query)

    # Fast fallback if background retriever indexing is still in progress
    if not hybrid or not segment_index:
        matched_dsa = None
        if dsa_index:
            sol, match_score = dsa_index.get_best_match(query)
            if sol and match_score > 0.15:
                matched_dsa = sol.to_dict()
        return SearchResponse(
            query=query,
            total_found=0,
            summary="Retriever indexes are warming up in the background. Full lecture moments will be searchable in a few moments.",
            results=[],
            dsa_snippet=matched_dsa,
            canonical_topics=canonical_topics,
            pattern_chunks=pattern_chunks,
            enrichment=enrichment_data,
        )

    # 1. Relevance / Domain Gate
    bm25_top = hybrid.bm25.retrieve(expanded_query, k=1)
    bm25_score = bm25_top[0].score if bm25_top else 0.0

    dense_top = hybrid.dense.retrieve(expanded_query, k=1)
    dense_score = dense_top[0].score if dense_top else 0.0

    qtoks = set(eh.tokens(expanded_query))
    out_of_scope_terms = {"next", "react", "vue", "angular", "django", "spring", "flutter", "express", "sql"}

    is_out_of_domain = False
    if dense_score > 0:
        if bm25_score <= 0.0 and dense_score < 0.35:
            is_out_of_domain = True
        elif any(term in qtoks for term in out_of_scope_terms) and dense_score < 0.40:
            is_out_of_domain = True
    else:
        if bm25_score <= 0.0:
            is_out_of_domain = True
        elif any(term in qtoks for term in out_of_scope_terms) and bm25_score < 1.0:
            is_out_of_domain = True

    matched_dsa = None
    if dsa_index:
        sol, match_score = dsa_index.get_best_match(query)
        if (not sol or match_score <= 0.15) and expanded_query != query:
            sol_exp, match_score_exp = dsa_index.get_best_match(expanded_query)
            if sol_exp and match_score_exp > match_score:
                sol, match_score = sol_exp, match_score_exp
        if sol and match_score > 0.15:
            matched_dsa = sol.to_dict()

    if is_out_of_domain:
        return SearchResponse(
            query=query,
            total_found=0,
            results=[],
            dsa_snippet=matched_dsa,
            canonical_topics=canonical_topics,
            pattern_chunks=pattern_chunks,
            enrichment=enrichment_data,
        )

    # 2. Retrieve candidate pool with expanded pedagogical concepts
    raw_results = hybrid.retrieve(expanded_query, k=25)
    if not raw_results:
        return SearchResponse(
            query=query,
            total_found=0,
            results=[],
            dsa_snippet=matched_dsa,
            canonical_topics=canonical_topics,
            pattern_chunks=pattern_chunks,
            enrichment=enrichment_data,
        )

    # 3. Deduplicate
    spans = [
        Span(r.chunk.video_id, float(r.chunk.start_sec), float(r.chunk.end_sec))
        for r in raw_results
    ]
    span_score_map = {(s.video_id, s.start, s.end): r.score for s, r in zip(spans, raw_results)}
    span_chunk_map = {(s.video_id, s.start, s.end): r.chunk for s, r in zip(spans, raw_results)}

    deduped_spans = dedup(spans, overlap_frac=0.5)[:k]

    # 4. Seek Refinement
    out_items: list[SearchResultItem] = []
    for sp in deduped_spans:
        chunk = span_chunk_map[(sp.video_id, sp.start, sp.end)]
        score = span_score_map.get((sp.video_id, sp.start, sp.end), 0.0)
        refined_span = segment_index.refine(sp, qtoks, pad=3.0)
        seek_sec = int(round(refined_span.start))

        m, s = divmod(seek_sec, 60)
        h, m = divmod(m, 60)
        ts_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

        # Resolve specific DSA problem for this exact video
        video_dsa = None
        if dsa_index:
            v_sol = dsa_index.get_solution_for_video(chunk.video_id, chunk.video_title)
            if v_sol:
                video_dsa = v_sol.to_dict()

        out_items.append(
            SearchResultItem(
                video_id=chunk.video_id,
                video_title=chunk.video_title,
                seek_sec=seek_sec,
                start_sec=round(float(chunk.start_sec), 2),
                end_sec=round(float(chunk.end_sec), 2),
                timestamp_display=ts_str,
                snippet=chunk.text,
                url=f"https://www.youtube.com/watch?v={chunk.video_id}&t={seek_sec}s",
                score=round(score, 4),
                dsa_snippet=video_dsa,
            )
        )
    # 5. Multi-Source Retrieval & Context Enrichment
    canonical_topics = classify_canonical_topics(query)
    pattern_retriever = state.get("pattern_retriever") or get_pattern_retriever()
    pattern_chunks = []
    if pattern_retriever:
        matched_patterns = pattern_retriever.retrieve(
            query,
            k=2,
            canonical_topic=canonical_topics[0] if canonical_topics else None,
        )
        pattern_chunks = [p.model_dump() for p, _ in matched_patterns]

    enricher = state.get("context_enricher") or get_context_enricher()
    enrichment_data = enricher.enrich(canonical_topics) if enricher else None

    return SearchResponse(
        query=query,
        total_found=len(out_items),
        summary=f"Found {len(out_items)} direct lecture whiteboard moments for your doubt.",
        results=out_items,
        dsa_snippet=matched_dsa,
        canonical_topics=canonical_topics,
        pattern_chunks=pattern_chunks,
        enrichment=enrichment_data,
    )


@app.get("/api/health")
def get_health():
    """System health check and indexed corpus counts."""
    dsa_index: DSASheetIndex = state.get("dsa_index")
    has_groq = bool(os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY"))
    has_local = False
    try:
        from ytrag.local_llm import LocalTeachingAssistant
        has_local = LocalTeachingAssistant.get_instance().is_available
    except Exception:
        pass

    is_ready = bool(state.get("is_ready", False))
    return {
        "status": "healthy" if is_ready else "warming_up",
        "ready": is_ready,
        "videos_indexed": len(state.get("videos_meta", [])),
        "lecture_chunks": len(state.get("chunks", [])),
        "dsa_problems_indexed": len(dsa_index.solutions) if dsa_index else 0,
        "default_provider": resolve_default_provider(),
        "has_local_model": has_local,
        "has_server_groq_key": has_groq,
        "local_llm_gated": not bool(os.getenv("USE_LOCAL_LLM")),
    }


@app.get("/api/corpus")
def get_corpus():
    return {
        "videos": state.get("videos_meta", []),
        "total_chunks": len(state.get("chunks", [])),
        "ready": bool(state.get("is_ready", False)),
    }


@app.get("/api/search", response_model=SearchResponse)
def search_lectures(
    q: str = Query(..., description="Student doubt / technical query"),
    k: int = Query(5, description="Number of results to return"),
):
    ev = state.get("ready_event")
    if ev is not None and not ev.is_set():
        ev.wait(timeout=3.0)
    try:
        return _retrieve(q, k)
    except Exception as e:
        logger.exception("Search encountered an unhandled exception")
        return SearchResponse(
            query=q,
            total_found=0,
            summary="Search encountered an issue. Please retry with standard algorithm terms.",
            results=[],
            dsa_snippet=None,
            canonical_topics=[],
            pattern_chunks=[],
            enrichment=None,
        )


@app.get("/api/dsa-snippet")
def get_dsa_snippet(
    q: Optional[str] = Query(None, description="Problem name or algorithm doubt"),
    title: Optional[str] = Query(None, description="Problem title alias"),
):
    """Returns the matching problem, approach, multi-language code, and complexities."""
    query = (q or title or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Missing query or title parameter.")
    dsa_index: DSASheetIndex = state.get("dsa_index")
    if not dsa_index:
        raise HTTPException(status_code=503, detail="DSA Sheet index not initialized.")
    sol, score = dsa_index.get_best_match(query)
    if not sol or score <= 0.05:
        return {"found": False, "query": query, "message": "No matching DSA problem found.", "dsa_snippet": None, "problem": None}
    sol_dict = sol.to_dict()
    return {
        "found": True,
        "query": query,
        "match_score": round(score, 3),
        "problem": sol_dict,
        "dsa_snippet": sol_dict,
    }


@app.post("/api/validate-key")
def validate_key_endpoint(req: KeyValidationRequest):
    """
    Validates an API key against Grok (xAI), Groq, or OpenAI authenticated /models endpoint.
    Ensures the user connects with a valid, working credential before running searches.
    """
    return validate_api_key(
        provider=req.provider,
        api_key=req.api_key,
        base_url=req.base_url,
        model=req.model,
    )


@app.post("/api/execute", response_model=CodeExecuteResponse)
def execute_code_endpoint(req: CodeExecuteRequest):
    """
    Executes Python or C++ code in a sandboxed scratch environment with strict timeouts.
    """
    if os.getenv("RENDER"):
        return CodeExecuteResponse(
            success=False,
            stdout="",
            stderr="Server-side execution is disabled on cloud instances. Python execution runs directly inside your browser via WebAssembly (Pyodide) with 0ms server latency and complete client isolation.",
            execution_time_ms=0.0,
            exit_code=1,
            message="Server execution disabled in cloud production (use client Pyodide Wasm).",
        )
    from ytrag.code_runner import execute_code
    return execute_code(
        language=req.language,
        code=req.code,
        stdin_input=req.stdin_input,
        timeout_sec=min(10.0, max(0.5, req.timeout_sec)),
    )


@app.get("/api/edge-cases", response_model=EdgeCasesResponse)
def get_edge_cases(topic: str = Query("", description="Problem topic"), title: str = Query("", description="Problem title")):
    """
    Returns relevant edge-case test definitions based on problem topic and title.
    """
    from ytrag.stress_tester import get_edge_cases_for_problem
    cases = get_edge_cases_for_problem(topic=topic, title=title)
    return EdgeCasesResponse(topic=topic, title=title, cases=cases)


@app.post("/api/grill-me", response_model=GrillMeResponse)
def grill_me_endpoint(req: GrillMeRequest):
    """
    Technical interview drill endpoint:
    - If user_answer is not provided: Generates a sharp, edge-case interview question based on user's code and problem.
    - If user_answer is provided: Scores candidate (1-10) with detailed feedback and gold-standard comparison.
    """
    from ytrag.stress_tester import generate_grill_question, evaluate_grill_answer

    provider = (req.provider or resolve_default_provider()).lower().strip()
    if os.getenv("RENDER"):
        api_key = req.api_key.strip()
    else:
        api_key = (
            req.api_key.strip()
            if req.api_key
            else (os.getenv("LLM_API_KEY", "") or os.getenv("GROQ_API_KEY", "") or os.getenv("GROK_API_KEY", "") or os.getenv("OPENAI_API_KEY", ""))
        )
    base_url = req.base_url.strip() if req.base_url else os.getenv("LLM_BASE_URL", "")
    model = req.model.strip() if req.model else os.getenv("LLM_MODEL", "")

    if req.user_answer and req.user_answer.strip():
        eval_result = evaluate_grill_answer(
            question=req.question or f"Edge cases for {req.title}",
            trap_warning=req.trap_warning or "",
            user_answer=req.user_answer,
            gold_standard=req.gold_standard or "",
            code=req.code,
            title=req.title,
            topic=req.topic,
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        return GrillMeResponse(
            mode="evaluation",
            question=req.question or "",
            trap_warning=req.trap_warning or "",
            gold_standard=eval_result.get("gold_standard"),
            source=eval_result.get("source", "offline"),
            evaluation=eval_result,
        )
    else:
        q_data = generate_grill_question(
            title=req.title,
            topic=req.topic,
            code=req.code,
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        return GrillMeResponse(
            mode="question",
            question=q_data["question"],
            trap_warning=q_data["trap_warning"],
            gold_standard=q_data["gold_standard"],
            source=q_data["source"],
            evaluation=None,
        )


def classify_user_intent(query: str) -> str:
    """
    Classifies user message into:
    - 'greeting': 'hi', 'hello', 'hey', 'good morning', etc.
    - 'beginner_roadmap': 'i dont know dsa', 'i am beginner', 'how to start', 'where to begin', 'confused about dsa', etc.
    - 'thanks': 'thank you', 'thanks striver', 'awesome', 'great', etc.
    - 'out_of_domain': non-dsa queries (web dev, devops, jokes, etc.)
    - 'algorithm_query': technical/problem question
    """
    q = query.strip().lower()
    q_clean = re.sub(r"[^a-z0-9\s]", " ", q)
    words = set(q_clean.split())

    greetings = {"hi", "hello", "hey", "hola", "yo", "namaste", "sup", "hey striver", "hello striver", "good morning", "good evening"}
    if q_clean in greetings or (words & {"hi", "hello", "hey"} and len(words) <= 3):
        return "greeting"

    if words & {"thanks", "thank", "thx"} or "thank you" in q_clean or q_clean in ("nice", "cool", "awesome", "great", "got it", "understood"):
        return "thanks"

    beginner_patterns = [
        r"\b(dont|don't|do not|didnt|didn't)\s+know\s+(dsa|dsaa|anything|programming|coding|algorithms|basics)\b",
        r"\b(dont|don't|do not)\s+know\s+how\s+to\s+(start|code|solve|begin)\b",
        r"\b(beginner|noob|fresher|zero|scratch|newbie|new to dsa)\b",
        r"\b(how|where)\s+(to|should i|do i|can i)\s+(start|begin|learn|prepare)\b",
        r"\b(roadmap|guide|study plan|how to study dsa|how to crack)\b",
        r"\bi\s+(am|m)\s+(confused|lost|scared|struggling)\b",
        r"\bwhat\s+is\s+(dsa|data structures|algorithms)\b",
        r"^(dsa\s+roadmap|how\s+to\s+dsa|start\s+dsa|help\s+me\s+start)$",
    ]
    for pattern in beginner_patterns:
        if re.search(pattern, q_clean):
            return "beginner_roadmap"

    ood_terms = {"react", "angular", "vue", "docker", "kubernetes", "css", "html", "django", "spring", "flask", "weather", "crypto", "bitcoin", "joke"}
    if words & ood_terms:
        return "out_of_domain"

    return "algorithm_query"


@app.post("/api/answer")
def answer_query(request: AnswerRequest):
    """
    Generate an evidence-grounded answer with citations, accompanied by verified DSA code.
    Supports Grok, Groq, OpenAI, or local deterministic extractive fallback.
    """
    query = request.query.strip()
    intent = classify_user_intent(query)
    if intent == "beginner_roadmap":
        return {
            "query": query,
            "provider": "extractive",
            "bullets": [
                {
                    "text": "Start by picking ONE programming language (C++, Java, or Python) and learn the basic syntax (loops, functions, arrays).",
                    "citations": []
                },
                {
                    "text": "Follow the Striver A2Z Sheet step-by-step: begin with Basics & Math, then master Arrays and Two-Pointers before touching advanced topics.",
                    "citations": []
                },
                {
                    "text": "Golden Rule: Always dry run on paper with small sample arrays before writing code. Check the A2Z Roadmap tab to track your progress!",
                    "citations": []
                }
            ],
            "approach_summary": "Don't panic! Everyone starts from zero. Follow Striver's 4-step beginner roadmap: Language -> Big-O -> A2Z Sheet -> Dry Runs.",
            "dsa_snippet": None,
            "message": "Beginner guidance from Striver's Take U Forward curriculum.",
        }

    retrieved = _retrieve(query, k=5)
    dsa_index: DSASheetIndex = state.get("dsa_index")
    matched_dsa = None
    if dsa_index:
        sol, score = dsa_index.get_best_match(query)
        if sol and score > 0.1:
            matched_dsa = sol.to_dict()

    if not retrieved.results:
        return {
            "query": query,
            "bullets": [],
            "dsa_snippet": matched_dsa,
            "message": "No relevant lecture moments were found for this query.",
        }

    # Resolve API Key & Provider (Enforce BYOK on Cloud Render)
    provider = request.provider.lower().strip() or resolve_default_provider()
    if os.getenv("RENDER"):
        api_key = request.api_key.strip()
    else:
        api_key = request.api_key.strip() or os.getenv("LLM_API_KEY", "") or os.getenv("GROK_API_KEY", "") or os.getenv("GROQ_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    base_url = request.base_url.strip() or os.getenv("LLM_BASE_URL", "")
    model = request.model.strip() or os.getenv("LLM_MODEL", "")

    # Check if local model can be safely called without OOM
    can_use_local = False
    if provider in ("local", "striver-rtx5050", "striver") and not os.getenv("RENDER"):
        try:
            from ytrag.local_llm import LocalTeachingAssistant
            can_use_local = LocalTeachingAssistant.get_instance().is_available
        except Exception:
            can_use_local = False

    # Call LLM if local model or credentials are provided
    if (can_use_local and provider in ("local", "striver-rtx5050", "striver")) or (api_key and provider not in ("extractive", "none")):
        try:
            llm_res = generate_llm_answer(
                query=query,
                lecture_excerpts=[item.model_dump() for item in retrieved.results],
                dsa_context=matched_dsa,
                pattern_excerpts=retrieved.pattern_chunks,
                enrichment_metadata=retrieved.enrichment,
                provider=provider,
                api_key=api_key,
                model=model,
                base_url=base_url,
            )

            # Map source IDs to actual retrieved items
            bullets = []
            for b in llm_res.get("bullets", [])[:3]:
                if not isinstance(b, dict) or not isinstance(b.get("text"), str):
                    continue
                source_ids = b.get("sources", [])
                citations = []
                for sid in source_ids:
                    if isinstance(sid, int) and 1 <= sid <= len(retrieved.results):
                        item = retrieved.results[sid - 1]
                        cit = {
                            "video_id": item.video_id,
                            "video_title": item.video_title,
                            "seek_sec": item.seek_sec,
                            "timestamp_display": item.timestamp_display,
                        }
                        if cit not in citations:
                            citations.append(cit)
                if citations:
                    bullets.append({"text": b["text"], "citations": citations})

            return {
                "query": query,
                "provider": provider,
                "bullets": bullets,
                "approach_summary": llm_res.get("approach_summary", ""),
                "dsa_snippet": matched_dsa,
                "canonical_topics": retrieved.canonical_topics,
                "pattern_chunks": retrieved.pattern_chunks,
                "enrichment": retrieved.enrichment,
                "message": f"Generated via {provider.upper()} and grounded in verified lecture timestamps.",
            }
        except Exception as exc:
            # Fall back to extractive synthesis on LLM error
            logger.warning("LLM generation failed (%s), falling back to extractive synthesis.", exc)

    # Deterministic Extractive Citation Mode (Fast, 0% Hallucination)
    qtoks = set(eh.tokens(query))
    bullets = []
    for item in retrieved.results[:3]:
        snippet = item.snippet.strip()
        cleaned = re.sub(
            r"\b(hey everyone|welcome back to the channel|so guys|um|uh|right so|let's understand)\b",
            "",
            snippet,
            flags=re.I,
        ).strip()
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", cleaned) if len(s.strip()) > 15]
        if not sentences:
            sentences = [cleaned or snippet]

        best_cand = max(sentences, key=lambda s: (len(set(eh.tokens(s)) & qtoks), -len(s)))
        lead = best_cand
        if len(lead) > 220:
            lead = lead[:200].rsplit(" ", 1)[0].rstrip(",;:- ") + "..."
        elif not lead.endswith((".", "!", "?")):
            lead += "."
        lead = lead[0].upper() + lead[1:]

        bullets.append({
            "text": f"{lead} ",
            "citations": [{
                "video_id": item.video_id,
                "video_title": item.video_title,
                "seek_sec": item.seek_sec,
                "timestamp_display": item.timestamp_display,
            }],
        })

    return {
        "query": query,
        "provider": "extractive",
        "bullets": bullets,
        "approach_summary": matched_dsa.get("approach", "")[:250] if matched_dsa else "",
        "dsa_snippet": matched_dsa,
        "canonical_topics": retrieved.canonical_topics,
        "pattern_chunks": retrieved.pattern_chunks,
        "enrichment": retrieved.enrichment,
        "message": "Grounded directly from lecture transcripts and Striver's A2Z sheet.",
    }


@app.post("/api/chat")
def striver_chat_endpoint(request: ChatRequest):
    """
    Conversational Striver AI chat endpoint for doubt clearing and mentorship.
    Retrieves grounded lecture moments from Striver's 6,881 video moments
    and returns a warm, intuitive Brute -> Better -> Optimal explanation with clickable citations.
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty.")

    query = next((m.content for m in reversed(request.messages) if m.role == "user"), "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="No user message provided.")

    intent = classify_user_intent(query)

    if intent == "beginner_roadmap":
        reply = (
            "Hey! Don't worry at all, take a deep breath. 😊\n\n"
            "Everybody starts from complete zero—when I wrote my first line of code, I had the exact same feeling! "
            "DSA is not about memorizing code; it's about training your brain to think with pure intuition step-by-step.\n\n"
            "Here is the battle-tested roadmap to go from absolute beginner to interview-ready:\n\n"
            "**1. Step 1: Pick ONE Programming Language (Week 1–2)**\n"
            "Choose C++, Java, or Python. Master basic syntax: loops, conditionals, functions, and 1D/2D arrays. Don't switch languages midway.\n\n"
            "**2. Step 2: Understand Time & Space Complexity (Week 2)**\n"
            "Never memorize Big-O! Learn how to count operations: a single loop is O(N), nested loops are O(N²), dividing search space in half is O(log N).\n\n"
            "**3. Step 3: Follow the Striver A2Z Sheet Step-by-Step**\n"
            "Follow the syllabus in order—don't jump straight into Dynamic Programming or Graphs:\n"
            "- **Basics & Math:** Digit extraction, GCD, basic recursion trees on paper.\n"
            "- **Arrays (The Foundation):** Kadane's Algorithm, Two-Sum, Dutch National Flag (0s, 1s, 2s).\n"
            "- **Binary Search:** On sorted arrays, then on search spaces (Book Allocation, Aggressive Cows).\n"
            "- **Linked Lists, Stacks, Queues:** Pointer manipulation, Fast & Slow pointers.\n"
            "- **Trees & Graphs:** BFS, DFS, Dijkstra, Topo Sort.\n\n"
            "**4. Golden Rule of Learning:**\n"
            "Always dry-run with pen and paper on small sample inputs (like `[2, 7, 11, 15]`) before touching your keyboard!\n\n"
            "👉 **Action Item:** Click the **🗺️ A2Z Roadmap tab** in the top navigation bar to see the full 369-problem syllabus. "
            "Which programming language (C++, Java, or Python) are you starting with?"
        )
        return {
            "reply": reply,
            "citations": [],
            "dsa_snippet": None,
            "provider": "extractive",
        }

    if intent == "greeting":
        reply = (
            "Hey everyone! Welcome back! 👋\n\n"
            "I'm your Striver AI mentor, grounded directly in my 305 YouTube lectures and the complete A2Z DSA Sheet.\n\n"
            "How can I help you today? You can:\n"
            "- Ask any conceptual doubt (e.g. *\"Why do two pointers work in 2 Sum?\"*, *\"What is Kadane's negative numbers trap?\"*)\n"
            "- Ask about any algorithmic pattern (Sliding Window, Binary Search on Answers, Cycle Detection)\n"
            "- Or let me know what topic you're studying right now!"
        )
        return {
            "reply": reply,
            "citations": [],
            "dsa_snippet": None,
            "provider": "extractive",
        }

    if intent == "thanks":
        reply = (
            "You're very welcome! Keep practicing consistently. Remember: consistency beats intensity every single time. "
            "Keep dry-running your code on paper, and feel free to ask anytime you get stuck on a problem! 🔥"
        )
        return {
            "reply": reply,
            "citations": [],
            "dsa_snippet": None,
            "provider": "extractive",
        }

    if intent == "out_of_domain":
        reply = (
            "Hey! That topic is outside our DSA curriculum.\n\n"
            "I am specialized strictly in Data Structures, Algorithms, Competitive Programming, and Striver's A2Z Sheet "
            "(Arrays, Linked Lists, Trees, Graphs, DP, Sorting, Recursion).\n\n"
            "Feel free to ask any DSA problem, edge-case doubt, or time complexity question!"
        )
        return {
            "reply": reply,
            "citations": [],
            "dsa_snippet": None,
            "provider": "extractive",
        }

    retrieved = _retrieve(query, k=5)
    dsa_index: DSASheetIndex = state.get("dsa_index")
    matched_dsa = None
    if dsa_index:
        sol, score = dsa_index.get_best_match(query)
        if sol and score > 0.15:
            matched_dsa = sol.to_dict()

    citations = []
    seen_cits = set()
    if retrieved.results and retrieved.total_found > 0:
        for i, item in enumerate(retrieved.results):
            cit_key = (item.video_id, item.timestamp_display)
            if cit_key in seen_cits:
                continue
            if item.score and item.score > 0.005:
                seen_cits.add(cit_key)
                citations.append({
                    "source_id": len(citations) + 1,
                    "video_id": item.video_id,
                    "video_title": item.video_title,
                    "seek_sec": item.seek_sec,
                    "timestamp_display": item.timestamp_display,
                })

    provider = (request.provider or resolve_default_provider()).lower().strip()
    if os.getenv("RENDER"):
        api_key = request.api_key.strip()
    else:
        api_key = (
            request.api_key.strip()
            or os.getenv("LLM_API_KEY", "")
            or os.getenv("GROK_API_KEY", "")
            or os.getenv("GROQ_API_KEY", "")
            or os.getenv("OPENAI_API_KEY", "")
        )
    base_url = request.base_url.strip() if request.base_url else os.getenv("LLM_BASE_URL", "")
    model = request.model.strip() if request.model else os.getenv("LLM_MODEL", "")

    can_use_local = False
    if provider in ("local", "striver-rtx5050", "striver") and not os.getenv("RENDER"):
        try:
            from ytrag.local_llm import LocalTeachingAssistant
            can_use_local = LocalTeachingAssistant.get_instance().is_available
        except Exception:
            can_use_local = False

    if (can_use_local and provider in ("local", "striver-rtx5050", "striver")) or (api_key and provider not in ("extractive", "none")):
        try:
            from ytrag.llm_provider import generate_striver_chat_reply
            reply_text = generate_striver_chat_reply(
                messages=[m.model_dump() for m in request.messages],
                lecture_excerpts=[item.model_dump() for item in retrieved.results],
                dsa_context=matched_dsa,
                pattern_excerpts=retrieved.pattern_chunks,
                enrichment_metadata=retrieved.enrichment,
                provider=provider,
                api_key=api_key,
                model=model,
                base_url=base_url,
            )
            return {
                "reply": reply_text,
                "citations": citations,
                "dsa_snippet": matched_dsa,
                "provider": provider,
                "canonical_topics": retrieved.canonical_topics,
                "pattern_chunks": retrieved.pattern_chunks,
                "enrichment": retrieved.enrichment,
            }
        except Exception as exc:
            logger.warning("Striver chat LLM error (%s), falling back to grounded extractive reply.", exc)

    if not matched_dsa and (not citations or not retrieved.canonical_topics):
        return {
            "reply": (
                f"Hey! *\"{query}\"* doesn't appear to be part of the Striver A2Z DSA Sheet curriculum.\n\n"
                "I am grounded specifically in Striver's 305 DSA YouTube lectures and 369 A2Z problems "
                "(Arrays, Linked Lists, Binary Search, Trees, Graphs, Dynamic Programming, Recursion, etc.).\n\n"
                "If you have a doubt on an algorithmic pattern or a specific A2Z problem, "
                "feel free to ask, or browse the **🗺️ A2Z Roadmap tab** above to pick a problem to study!"
            ),
            "citations": [],
            "dsa_snippet": None,
            "provider": "extractive",
            "canonical_topics": [],
            "pattern_chunks": [],
            "enrichment": None,
        }

    # Conversational Extractive Fallback (Fast, Zero Hallucination, Striver Voice)
    dsa_title = matched_dsa.get("title", "") if matched_dsa else (citations[0]["video_title"] if citations else query)
    dsa_approach = matched_dsa.get("approach", "") if matched_dsa else ""
    tc = matched_dsa.get("time_complexity", "") if matched_dsa else "O(N)"
    sc = matched_dsa.get("space_complexity", "") if matched_dsa else "O(1)"

    reply_parts = [
        f"Hey! Let's understand **{dsa_title}** with pure intuition, step-by-step just like we do on the whiteboard.\n"
    ]
    if dsa_approach:
        reply_parts.append(f"**💡 The Core Thought Process (Brute → Optimal):**\n{dsa_approach[:300].strip()}\n")
        reply_parts.append(f"**Complexity Target:** Time `{tc}` | Space `{sc}`.\n")

    if citations:
        reply_parts.append("**Verified Lecture Insights:**")
        for i, cit in enumerate(citations[:3]):
            matching_item = next((r for r in retrieved.results if r.video_id == cit["video_id"]), None)
            if matching_item:
                snip = matching_item.snippet.strip().replace("\n", " ")[:180]
                reply_parts.append(f"- At **{cit['timestamp_display']}** in *{cit['video_title']}*, Striver explains: *\"{snip}...\"* [Source {i+1}]")

    reply_parts.append("\n*Tip: Connect your free Groq API key in the top nav to unlock continuous conversational multi-turn dialogue with Striver!*")

    final_reply = "\n".join(reply_parts)
    if retrieved.enrichment:
        from ytrag.context_enricher import get_context_enricher
        enrichment_section = get_context_enricher().format_markdown_section(retrieved.enrichment)
        if enrichment_section and enrichment_section not in final_reply:
            final_reply += "\n\n" + enrichment_section

    return {
        "reply": final_reply,
        "citations": citations,
        "dsa_snippet": matched_dsa,
        "provider": "extractive",
        "canonical_topics": retrieved.canonical_topics,
        "pattern_chunks": retrieved.pattern_chunks,
        "enrichment": retrieved.enrichment,
    }


@app.get("/api/roadmap")
def get_roadmap():
    """
    Returns the complete Striver A2Z DSA sheet problem hierarchy
    grouped by Topic and Subtopic with difficulty and complexity metadata.
    """
    dsa_index: DSASheetIndex = state.get("dsa_index")
    if not dsa_index or not dsa_index.solutions:
        return {"total_problems": 0, "topics": []}

    topic_map = {}
    for sol in dsa_index.solutions:
        t_name = sol.topic
        sub_name = sol.subtopic or "General"
        if t_name not in topic_map:
            topic_map[t_name] = {}
        if sub_name not in topic_map[t_name]:
            topic_map[t_name][sub_name] = []

        diff = "Medium"
        sub_lower = sub_name.lower()
        if (
            "easy" in sub_lower
            or "1. single" in sub_lower
            or "1. learning" in sub_lower
            or "1. theory" in sub_lower
            or "1. traversals" in sub_lower
            or "1. concept" in sub_lower
            or "1d arrays" in sub_lower
            or "1. intro" in sub_lower
            or "1. learn" in sub_lower
            or "1.get strong" in sub_lower
            or "2.doubly" in sub_lower
        ):
            diff = "Easy"
        elif (
            "hard" in sub_lower
            or "promblems" in sub_lower
            or "in search space" in sub_lower
            or "3.try out" in sub_lower
            or "3. advanced" in sub_lower
            or "4. implementation" in sub_lower
            or "5. mst" in sub_lower
            or "6. other algorithms" in sub_lower
            or "7. dp on lis" in sub_lower
            or "8. dp on partition" in sub_lower
            or "9. dp on squares" in sub_lower
        ):
            diff = "Hard"

        topic_map[t_name][sub_name].append({
            "id": sol.id,
            "title": sol.title,
            "topic": sol.topic,
            "subtopic": sol.subtopic,
            "difficulty": diff,
            "time_complexity": sol.time_complexity,
            "space_complexity": sol.space_complexity,
        })

    topic_icons = {
        "01.Arrays": "📦",
        "02.Binary Search": "🔍",
        "03.Strings": "🧵",
        "04.Linked List": "🔗",
        "05.Recursion": "🔄",
        "06.Bit Manipulation": "⚡",
        "07.Stack and Queues": "📚",
        "08. Sliding Window": "🪟",
        "09. Heaps": "⛰️",
        "10. Greedy Approach": "🎯",
        "11. Binary Trees": "🌲",
        "12. Binary Search Trees": "🎋",
        "13. Graphs": "🕸️",
        "14. Dynamic Programming": "🧩",
        "15. Tries": "📖",
        "16. Strings (Hard)": "💥",
    }

    topics_list = []
    total_count = 0
    for t_name, subs in sorted(topic_map.items()):
        sub_list = []
        t_count = 0
        for sub_name, probs in sorted(subs.items()):
            sub_list.append({
                "name": sub_name,
                "count": len(probs),
                "problems": probs,
            })
            t_count += len(probs)
        total_count += t_count
        clean_name = re.sub(r"^\d+\.\s*", "", t_name).strip()
        topics_list.append({
            "raw_name": t_name,
            "name": clean_name,
            "icon": topic_icons.get(t_name, "📌"),
            "total_count": t_count,
            "subtopics": sub_list,
        })

    return {
        "total_problems": total_count,
        "topics": topics_list,
    }


# =====================================================================
# OpenAI-Compatible Endpoints (/v1/chat/completions, /v1/models)
# Enables zero-config connection to VS Code (Continue.dev, Cline),
# LangChain, and any OpenAI API client.
# =====================================================================

class OpenAIMessage(BaseModel):
    role: str
    content: str


class OpenAIChatRequest(BaseModel):
    model: Optional[str] = "striver-dsa-coder"
    messages: list[OpenAIMessage]
    temperature: Optional[float] = 0.2
    top_p: Optional[float] = 0.9
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False


@app.get("/v1/models")
@app.get("/api/v1/models")
def list_models():
    """Returns OpenAI-compatible model listing."""
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": "striver-dsa-coder",
                "object": "model",
                "created": now,
                "owned_by": "striver-local",
                "permission": [],
                "root": "striver-dsa-coder",
            },
            {
                "id": "qwen2.5-coder-7b",
                "object": "model",
                "created": now,
                "owned_by": "striver-local",
                "permission": [],
                "root": "qwen2.5-coder-7b",
            },
        ],
    }


@app.post("/v1/chat/completions")
@app.post("/api/v1/chat/completions")
async def chat_completions(req: OpenAIChatRequest):
    """
    OpenAI-compatible chat completions endpoint.
    Serves the fine-tuned Striver DSA model running locally on the RTX 5050.
    """
    from ytrag.local_llm import LocalTeachingAssistant
    assistant = LocalTeachingAssistant.get_instance()

    msg_dicts = [{"role": m.role, "content": m.content} for m in req.messages]
    req_model = req.model or "striver-dsa-coder"
    created_ts = int(time.time())
    cmpl_id = f"chatcmpl-striver-{int(time.time() * 1000)}"

    if req.stream:
        async def event_generator():
            for chunk in assistant.stream_chat_completion(
                messages=msg_dicts,
                max_tokens=req.max_tokens or 1024,
                temperature=req.temperature or 0.2,
                top_p=req.top_p or 0.9,
            ):
                payload = {
                    "id": cmpl_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": req_model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(payload)}\n\n"

            # Final stop chunk
            stop_payload = {
                "id": cmpl_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": req_model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ],
            }
            yield f"data: {json.dumps(stop_payload)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    text, prompt_tokens, completion_tokens = assistant.generate_chat_completion(
        messages=msg_dicts,
        max_tokens=req.max_tokens or 1024,
        temperature=req.temperature or 0.2,
        top_p=req.top_p or 0.9,
    )

    return {
        "id": cmpl_id,
        "object": "chat.completion",
        "created": created_ts,
        "model": req_model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


# Mount Frontend & Diagnostics Dashboard
@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/dashboard")
def serve_dashboard():
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/api/diagnostics")
def get_diagnostics():
    """Returns comprehensive 104-query benchmark data, seek errors, and TOST stats."""
    from ytrag.diagnostics_data import build_diagnostics_payload
    return build_diagnostics_payload()


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
