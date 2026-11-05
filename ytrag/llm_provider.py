"""
Unified LLM Provider Interface for YT Lecture RAG.
Supports Groq, xAI Grok, OpenAI, and Local GPU Models (RTX 5050 / Qwen2.5-Coder-7B).
Integrates multi-source lecture transcripts, verified pattern code templates,
and deterministic curriculum & visualizer enrichment metadata.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

# Standard provider configurations
PROVIDER_CONFIGS = {
    "grok": {
        "name": "Grok (xAI)",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-2-latest",
        "fallback_model": "grok-beta",
    },
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "fallback_model": "llama-3.1-8b-instant",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "fallback_model": "gpt-4o",
    },
}

ALLOWED_LLM_HOSTS = {
    "api.groq.com",
    "api.x.ai",
    "api.openai.com",
}


def sanitize_base_url(url_str: str) -> str:
    """SSRF guard: validates scheme and restricts hosts to approved LLM domains."""
    if not url_str or not url_str.strip():
        return ""
    clean = url_str.strip()
    parsed = urllib.parse.urlparse(clean)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: '{parsed.scheme}'. Only http/https are allowed.")

    host = (parsed.hostname or "").lower()
    if os.getenv("RENDER"):
        if host not in ALLOWED_LLM_HOSTS:
            raise ValueError(f"Untrusted LLM host '{host}'. Approved providers: {', '.join(sorted(ALLOWED_LLM_HOSTS))}")
    else:
        # In local development, also allow localhost / 127.0.0.1 for local Ollama / vLLM, but forbid cloud metadata
        forbidden = {"169.254.169.254", "metadata.google.internal"}
        if host in forbidden or host.startswith("169.254."):
            raise ValueError(f"Access to private cloud metadata host '{host}' is prohibited.")

    return clean.rstrip("/")


def get_provider_details(provider: str, custom_base_url: str = "", custom_model: str = "") -> tuple[str, str]:
    """Resolves the base URL and target model for the requested provider."""
    provider_key = (provider or "groq").lower().strip()
    cfg = PROVIDER_CONFIGS.get(provider_key, {})

    if custom_base_url and custom_base_url.strip():
        base_url = sanitize_base_url(custom_base_url)
    else:
        base_url = cfg.get("base_url", "https://api.groq.com/openai/v1")

    model = custom_model.strip() if custom_model else cfg.get("default_model", "llama-3.3-70b-versatile")
    return base_url.rstrip("/"), model


def validate_api_key(
    provider: str,
    api_key: str,
    base_url: str = "",
    model: str = "",
    timeout: float = 8.0,
) -> dict:
    """
    Validates an API key against the provider's authenticated /models endpoint.
    """
    p_clean = (provider or "").lower().strip()
    if p_clean in ("local", "striver-rtx5050", "striver"):
        from ytrag.local_llm import LocalTeachingAssistant
        assistant = LocalTeachingAssistant.get_instance()
        return {
            "valid": True,
            "provider": "local",
            "model": "Qwen2.5-Coder-7B-Striver (RTX 5050)",
            "message": "Connected to Local NVIDIA RTX 5050 Striver Model (No Cloud Keys Needed)!",
            "available_models": ["striver_dsa_lora_final"],
        }

    api_key = api_key.strip()
    if not api_key:
        return {
            "valid": False,
            "provider": provider,
            "error": "API key cannot be empty.",
            "message": "Please enter an API key.",
        }

    try:
        resolved_base_url, resolved_model = get_provider_details(provider, base_url, model)
    except Exception as exc:
        return {
            "valid": False,
            "provider": provider,
            "error": str(exc),
            "message": f"Invalid provider URL: {exc}",
        }

    url = f"{resolved_base_url}/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "YTLectureRAG/1.0",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models_list = [m.get("id", "") for m in data.get("data", []) if isinstance(m, dict)]
            return {
                "valid": True,
                "provider": provider,
                "model": resolved_model,
                "available_models": models_list[:15],
                "message": f"Successfully connected to {provider.upper()}!",
            }
    except urllib.error.HTTPError as exc:
        err_msg = f"HTTP {exc.code} Authentication Failed: {exc.reason}. Invalid API Key."
        return {
            "valid": False,
            "provider": provider,
            "error": err_msg,
            "message": f"{provider.upper()} rejected the key ({exc.code}).",
        }
    except Exception as exc:
        return {
            "valid": False,
            "provider": provider,
            "error": f"Connection failed to provider endpoint: {exc}.",
            "message": "Network or timeout issue while validating key.",
        }


def generate_llm_answer(
    query: str,
    lecture_excerpts: list[dict],
    dsa_context: Optional[dict] = None,
    pattern_excerpts: Optional[list[dict]] = None,
    enrichment_metadata: Optional[dict] = None,
    provider: str = "groq",
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    timeout: float = 30.0,
) -> dict:
    """
    Generates a structured, evidence-grounded answer using the configured provider.
    Combines lecture moments, verified pattern code, and deterministic curriculum metadata.
    """
    p_clean = (provider or "").lower().strip()
    if p_clean in ("local", "striver-rtx5050", "striver"):
        from ytrag.local_llm import LocalTeachingAssistant
        assistant = LocalTeachingAssistant.get_instance()
        if not assistant.is_available:
            raise RuntimeError("Local model weights not found on this machine.")
        return assistant.generate_answer(
            query=query,
            lecture_excerpts=lecture_excerpts,
            dsa_context=dsa_context,
        )

    resolved_base_url, resolved_model = get_provider_details(provider, base_url, model)

    context_str = json.dumps({
        "question": query,
        "lecture_moments": [
            {
                "source_id": i + 1,
                "video_title": item.get("video_title", ""),
                "timestamp": item.get("timestamp_display", ""),
                "transcript": item.get("snippet", "")[:1200],
            }
            for i, item in enumerate(lecture_excerpts)
        ],
        "verified_pattern_code": [
            {
                "title": p.get("title", ""),
                "pattern_name": p.get("pattern_name", ""),
                "language": p.get("language", ""),
                "content_type": p.get("content_type", ""),
                "code_snippet": p.get("text", "")[:1500],
            }
            for p in (pattern_excerpts or [])
        ],
        "canonical_dsa_knowledge": {
            "title": dsa_context.get("title", "") if dsa_context else "",
            "approach": dsa_context.get("approach", "") if dsa_context else "",
            "time_complexity": dsa_context.get("time_complexity", "") if dsa_context else "",
            "space_complexity": dsa_context.get("space_complexity", "") if dsa_context else "",
        } if dsa_context else None,
        "enrichment_resources": enrichment_metadata or None,
    }, ensure_ascii=False)

    system_prompt = (
        "You are Striver (Raj Vikramaditya) from 'take U forward', creator of the A2Z DSA Sheet and mentor to software engineers worldwide.\n"
        "Your mission is to clear the student's doubt with pure intuition and conceptual clarity, exactly in your signature teaching style.\n\n"
        "Teaching Methodology:\n"
        "1. Intuition-First (Brute -> Better -> Optimal): Always lead with the raw intuition ('What is the first naive thing that comes to your mind?'), point out why it's slow (e.g. O(N^2) time), and then explain how we optimize it (e.g. two-pointer, hashing, or Kadane) to achieve optimal time/space.\n"
        "2. Voice & Tone: Warm, energetic, encouraging, and razor-sharp on whiteboard dry-runs (pointer movements, indices, base cases). Talk directly to the student as their mentor ('Take a deep breath', 'Let's write this down on paper and dry run it', 'Remember this pattern for your interviews').\n"
        "3. Strict Grounding: Base technical explanations strictly on the provided lecture moments, verified pattern templates, and canonical DSA sheet knowledge. Cite valid source_id numbers (1 to N) so the student can jump directly to that timestamp in your video.\n"
        "4. Never invent source IDs or citations.\n"
        "5. Output Format: Return strictly a valid JSON object with this exact schema:\n"
        '{\n'
        '  "approach_summary": "1-2 sentence core intuition breaking down Brute -> Optimal in Striver\'s voice",\n'
        '  "bullets": [\n'
        '    {"text": "Pedagogical explanation with dry-run/pointer details in Striver\'s voice", "sources": [1]}\n'
        '  ]\n'
        '}'
    )

    payload = {
        "model": resolved_model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context_str},
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    url = f"{resolved_base_url}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    raw_content = body["choices"][0]["message"]["content"]
    parsed = json.loads(raw_content)
    return parsed


def generate_striver_chat_reply(
    messages: list[dict],
    lecture_excerpts: list[dict],
    dsa_context: Optional[dict] = None,
    pattern_excerpts: Optional[list[dict]] = None,
    enrichment_metadata: Optional[dict] = None,
    provider: str = "groq",
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    timeout: float = 30.0,
) -> str:
    """
    Generates a conversational, multi-turn Striver mentor reply.
    Incorporates lecture timestamps, pattern code templates, and appends
    a deterministic 'Practice, Visualizers & Next Steps' section.
    """
    p_clean = (provider or "").lower().strip()
    if p_clean in ("local", "striver-rtx5050", "striver"):
        from ytrag.local_llm import LocalTeachingAssistant
        assistant = LocalTeachingAssistant.get_instance()
        if not assistant.is_available:
            raise RuntimeError("Local model weights not found on this machine.")
        last_user_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        res = assistant.generate_answer(
            query=last_user_msg,
            lecture_excerpts=lecture_excerpts,
            dsa_context=dsa_context,
        )
        bullets_text = "\n".join(f"- {b.get('text', '')}" for b in res.get("bullets", []))
        summary = res.get("approach_summary", "")
        reply = f"{summary}\n\n{bullets_text}".strip()
        if enrichment_metadata:
            from ytrag.context_enricher import get_context_enricher
            reply += "\n\n" + get_context_enricher().format_markdown_section(enrichment_metadata)
        return reply

    resolved_base_url, resolved_model = get_provider_details(provider, base_url, model)

    context_lines = []
    for i, item in enumerate(lecture_excerpts):
        context_lines.append(
            f"Source [{i + 1}]: {item.get('video_title', '')} ({item.get('timestamp_display', '')})\n"
            f"Transcript snippet: {item.get('snippet', '')[:800]}"
        )
    lecture_block = "\n\n".join(context_lines)

    pattern_block = ""
    if pattern_excerpts:
        p_lines = []
        for p in pattern_excerpts[:2]:
            p_lines.append(
                f"Pattern Template: {p.get('title', '')} ({p.get('language', 'general')})\n"
                f"{p.get('text', '')[:1000]}"
            )
        pattern_block = "\n\nVerified Pattern Code Templates:\n" + "\n\n".join(p_lines)

    dsa_block = ""
    if dsa_context:
        dsa_block = (
            f"\nCanonical Striver A2Z Problem: {dsa_context.get('title', '')}\n"
            f"Approach: {dsa_context.get('approach', '')[:500]}\n"
            f"Time Complexity: {dsa_context.get('time_complexity', '')}\n"
            f"Space Complexity: {dsa_context.get('space_complexity', '')}\n"
        )

    system_prompt = (
        "You are Striver (Raj Vikramaditya) from 'take U forward', creator of the A2Z DSA Sheet and mentor to software engineers worldwide.\n"
        "Talk directly to the student as their mentor ('Hey everyone!', 'Let's understand the intuition', 'Take a deep breath and write it down on paper').\n\n"
        "Teaching Methodology:\n"
        "1. Beginner / Roadmap Queries: If the student says they don't know DSA, are a beginner, or ask where to start, do NOT hallucinate random algorithm problems. Reassure them warmly ('Everybody starts from zero'), and give Striver's 4-step beginner roadmap (Pick C++/Java/Python, learn Big-O, follow the A2Z sheet step-by-step starting with Basics and Arrays, dry run on paper).\n"
        "2. Intuition-First (Brute -> Better -> Optimal): When answering algorithmic questions, always lead with the raw intuition ('What is the first naive thing that strikes your mind?'), point out why it's slow (e.g. O(N^2)), and then show how we optimize it (e.g. two-pointer, hashing, Kadane).\n"
        "3. Step-by-Step Dry Runs: Use small sample inputs (like [2, 7, 11, 15]) and explain pointer movements, loop invariants, and base cases.\n"
        "4. Strict Grounding & Citations: Ground your technical explanations strictly in the provided lecture moments and pattern templates. Reference valid sources like [1], [2] whenever explaining a concept from the lecture so the student can jump to the video.\n"
        "5. Tone: Energetic, encouraging, warm, and crystal-clear on algorithmic thinking.\n\n"
        f"Verified Lecture Moments:\n{lecture_block}\n{dsa_block}\n{pattern_block}"
    )

    llm_messages = [{"role": "system", "content": system_prompt}]
    for m in messages[-8:]:
        role = "assistant" if m.get("role") in ("assistant", "striver", "bot") else "user"
        llm_messages.append({"role": role, "content": m.get("content", "")})

    payload = {
        "model": resolved_model,
        "temperature": 0.3,
        "messages": llm_messages,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    url = f"{resolved_base_url}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    reply_content = body["choices"][0]["message"]["content"]

    # Append structured "Practice, Visualizers & Next Steps" section
    if enrichment_metadata:
        from ytrag.context_enricher import get_context_enricher
        enrichment_section = get_context_enricher().format_markdown_section(enrichment_metadata)
        if enrichment_section and enrichment_section not in reply_content:
            reply_content += "\n\n" + enrichment_section

    return reply_content
