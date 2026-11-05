# Viva Defense & Technical Architecture Guide
**Project:** DSA Lecture RAG — Timestamped Multimodal Retrieval & Mentorship Platform  
**Author:** Sajal Malhotra  

This document provides rigorous, academically sound answers and engineering justifications for the critical architecture and defense questions likely to be asked during your academic evaluation or viva.

---

### Question 1: Why does deployed behavior differ from the benchmarked system?

**Viva Answer:**
> *"In our empirical research benchmark, our primary goal was maximizing semantic recall across diverse spoken queries, where our Hybrid RRF Retriever (BM25 + SentenceTransformers MiniLM-L12-v2 + Cross-Encoder) achieves **30.0% Hit@3** on verified lecture moments. 
> 
> However, production deployment operates under a strict physical resource constraint: Render’s Free Tier web instances enforce a hard **512 MB RAM ceiling**. Initializing PyTorch, CUDA runtime stubs, and SentenceTransformers neural weights in Python consumes between 420 MB and 650 MB of memory, triggering exit code 137 (`OOMKilled`) or unresponsiveness during cold boots.
> 
> As an engineering decision under real-world constraints, we decouple the deployed cloud tier from the high-memory benchmark:
> 1. **Zero-Torch Memory Footprint (<65 MB RSS):** On Render, the system defaults to our optimized BM25Okapi sparse lexical engine, which boots in **<0.05 seconds** and never risks OOM crashes.
> 2. **Multi-Source Structured Catalogs:** Rather than relying purely on dense retrieval, we augment sparse retrieval with deterministic metadata injection from curated catalogs (`topic_resources.json`, `curriculum_graph.json`, and `patterns_corpus.json`), providing students with verified pattern code, interactive visualizers, and practice problems with zero neural latency.
> 3. **Configurable Toggle:** For environments with $\ge 1\text{GB}$ RAM (or local workstations), setting `ENABLE_DENSE_ON_RENDER=1` re-enables full neural vector search."*

---

### Question 2: How is `/api/execute` isolated, and what happens if it's bypassed?

**Viva Answer:**
> *"We follow the principle of defense-in-depth, combining client-side compute offloading with server-side sandboxing:
> 
> 1. **Client-Side WebAssembly Execution (Primary):** For Python, code executes directly inside the user's browser using **Pyodide WebAssembly**. This completely moves compute off the server, provides zero-millisecond network round-trips, and runs with browser-level sandbox isolation. The server executes zero Python code.
> 2. **Cloud Production Protection:** When running on cloud infrastructure (`os.getenv('RENDER')`), the `/api/execute` server endpoint returns an immediate 403 response directing execution to the client-side WebAssembly runner, preventing any untrusted arbitrary code execution on cloud multi-tenant infrastructure.
> 3. **Subprocess & Environment Sanitization:** For local testing, subprocesses spawned for compilation or execution never inherit `os.environ`. We inject a strictly sanitized environment (`clean_env`) containing only `PATH` and temporary working directories, preventing environment secrets or API keys from ever being accessed.
> 4. **AST & Lexical Security Validator:** Before any code is saved or executed, an AST parser walks the syntax tree, strictly rejecting:
>    - Dangerous imports (`os`, `subprocess`, `shutil`, `socket`, `ctypes`, `requests`).
>    - Dangerous functions (`eval()`, `exec()`, `open()`, `compile()`, `__import__`).
>    - Attribute jailbreaks (`__subclasses__`, `__globals__`).
>    - C++ header attacks (`<windows.h>`, `<unistd.h>`, `<fstream>`, `system()`, `popen()`, `fork()`)."*

---

### Question 3: With $n = 30$ (or $n = 104$) and transcript-derived labels, what can you actually claim?

**Viva Answer:**
> *"We hold ourselves to a strict standard of evaluation honesty:
> 
> 1. **Non-Transcript Labeling Protocol:** In our pre-registered methodology ([`LABELING_PROTOCOL.md`](LABELING_PROTOCOL.md)), query labels were created strictly without looking at the transcript text. A student was shown the video whiteboard visual and asked to describe the concept in their own words. This avoids transcript lexical bias where keywords artificially inflate BM25 scores.
> 2. **Benchmark Scale:** We expanded from the initial $n=30$ pilot study to a pre-registered **$104$-query benchmark** ($39$ dev, $65$ test) spanning $18$ lecture videos across $8$ distinct algorithmic topics.
> 3. **Statistical Confidence Intervals & TOST:** We report **Wilson 95% confidence intervals** and exact **McNemar test p-values** ($p = 0.5078$) for all pairwise retriever comparisons. Because a failure to reject the null hypothesis ($p > 0.05$) does not prove equivalence, we implemented Two One-Sided Tests (TOST) with an equivalence bound $\Delta = 0.05$ and Bayesian credible intervals.
> 4. **Honest Scope of Claims:** We do not claim that dense search dramatically outperforms lexical search on raw keyword matching; rather, we claim that **Hybrid RRF rank fusion** provides maximum robustness when students describe algorithmic symptoms or slang (e.g., *'Kadane resets to 0'* or *'fast and slow pointer meets'*), bridging informal queries to technical whiteboard moments."*

---

### Question 4: Where did the solutions, visualizers, and transcripts come from, and are you allowed to ship them?

**Viva Answer:**
> *"Our project is built upon open educational resources and adheres to fair use and open-source licensing principles:
> 
> 1. **Lecture Transcripts:** The transcripts were extracted from publicly available YouTube lectures published by Raj Vikramaditya (take U forward / Striver). They are utilized strictly for non-commercial educational research, semantic indexing, and academic retrieval (Fair Use doctrine for educational information retrieval systems). We do not host or republish video media; all search results redirect to the official YouTube platform with exact timestamps, driving engagement and views directly to the original creator.
> 2. **Algorithmic Solutions:** Base code templates originate from open-source educational repositories (`Codensity30/Strivers-A2Z-DSA-Sheet`, licensed under permissive open-source terms), with extensive multi-language refactoring and syntax fixes applied in our codebase.
> 3. **External Catalogs & Visualizers:**
>    - `ashishps1/awesome-leetcode-resources` (MIT License): Extracted pattern code templates and conceptual study guides.
>    - `avinash201199/DSA-KIT` (MIT License): Extracted external links to tools and interactive visualizers (VisuAlgo, CS Academy, USFCA).
>    - `helloworldbyprince/Complete-DSA-Preparation` (MIT License): Curriculum prerequisite DAG and curated problem references.
> 4. **Attribution:** Full upstream attribution, copyright notices, and repository links are explicitly documented in Section 8 of our [`README.md`](README.md) and exposed within the platform UI."*
