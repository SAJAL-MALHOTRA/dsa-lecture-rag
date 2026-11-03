# Retrieval evaluation report

- golden: `sha256:6acc2e6d4d2b`, 39 queries, split = **dev**
- temporal dedup: overlap >= 50% of the shorter span
- primary k = 3; CIs: Wilson (hit rate), bootstrap (MRR), 2000 resamples

## Lexical-leakage audit

Mean query-to-answer word overlap: **0.52** over 39 queries (0 skipped: no transcript).

| type | n | mean overlap | share >= 0.8 |
|---|---:|---:|---:|
| lexical | 14 | 0.70 | 50% |
| paraphrase | 5 | 0.40 | 0% |
| conceptual | 15 | 0.47 | 0% |
| symptom | 5 | 0.27 | 0% |


Highly leaky queries (>= 0.8):
- q001 (1.00): tortoise and hare algorithm
- q030 (1.00): base condition in recursion
- q035 (1.00): hashing collisions
- q059 (0.80): breadth first search traversal in graph
- q068 (1.00): square root using binary search
- q084 (1.00): best time to buy and sell stock
- q101 (0.83): minimise maximum distance between gas stations

## Results: hit definition `seek`

Hit iff same video and gt.start - 20s <= result.start <= gt.start + 0.5 x len(gt).

| retriever | k | Hit@k | 95% CI | MRR@k | 95% CI | span recall@k |
|---|---:|---:|---|---:|---|---:|
| bm25 | 1 | 10.3% | 4.1% to 23.6% | 0.103 | 0.026 to 0.205 | 10.3% |
| bm25 | 3 | 30.8% | 18.6% to 46.4% | 0.197 | 0.103 to 0.308 | 29.5% |
| bm25 | 5 | 33.3% | 20.6% to 49.0% | 0.203 | 0.109 to 0.312 | 32.1% |
| bm25 | 10 | 38.5% | 24.9% to 54.1% | 0.210 | 0.116 to 0.318 | 37.2% |
| hybrid_en | 1 | 12.8% | 5.6% to 26.7% | 0.128 | 0.026 to 0.231 | 11.5% |
| hybrid_en | 3 | 30.8% | 18.6% to 46.4% | 0.205 | 0.111 to 0.321 | 29.5% |
| hybrid_en | 5 | 35.9% | 22.7% to 51.6% | 0.217 | 0.120 to 0.333 | 34.6% |
| hybrid_en | 10 | 41.0% | 27.1% to 56.6% | 0.224 | 0.128 to 0.339 | 39.7% |
| hybrid_multi | 1 | 15.4% | 7.2% to 29.7% | 0.154 | 0.051 to 0.282 | 15.4% |
| hybrid_multi | 3 | 25.6% | 14.6% to 41.1% | 0.197 | 0.094 to 0.321 | 25.6% |
| hybrid_multi | 5 | 35.9% | 22.7% to 51.6% | 0.218 | 0.117 to 0.339 | 34.6% |
| hybrid_multi | 10 | 43.6% | 29.3% to 59.0% | 0.229 | 0.128 to 0.348 | 42.3% |

Seek precision:
- bm25: median |start error| of first hit = 20.0s (n=15)
- hybrid_en: median |start error| of first hit = 16.5s (n=16)
- hybrid_multi: median |start error| of first hit = 20.0s (n=17)

### Hit@3 by query type

| type | n | bm25 | hybrid_en | hybrid_multi |
|---|---:|---:|---:|---:|
| lexical | 14 | 50.0% | 57.1% | 42.9% |
| paraphrase | 5 | 0.0% | 20.0% | 0.0% |
| conceptual | 15 | 33.3% | 20.0% | 20.0% |
| symptom | 5 | 0.0% | 0.0% | 20.0% |

### Missed by every retriever at k=3 (check labels first)

- q001 [lexical]: tortoise and hare algorithm
- q006 [conceptual]: how to reverse a linked list using three pointers iteratively
- q008 [symptom]: lost reference to the rest of the list when reversing next pointer
- q012 [conceptual]: why two pointers fails if we need to return original indices in two sum
- q015 [paraphrase]: find contiguous subarray with given sum using prefix sums
- q022 [conceptual]: why is merge sort space complexity O(N)
- q025 [lexical]: partitioning algorithm in quick sort
- q027 [conceptual]: why does quicksort take O(N squared) time in worst case
- q032 [conceptual]: why does infinite recursion cause segmentation fault
- q042 [paraphrase]: how to find middle of linked list without counting total length first
- q044 [paraphrase]: recursive call tree depth and maximum memory consumed
- q046 [paraphrase]: in place partitioning without creating extra arrays
- q048 [lexical]: tail recursion
- q050 [conceptual]: two sum brute force nested loops time complexity
- q056 [symptom]: recursive fibonacci takes forever to execute for n greater than 40
- q063 [conceptual]: time complexity of bfs traversal with v vertices and e edges
- q066 [conceptual]: difference in call stack depth between dfs and bfs
- q075 [symptom]: empty stack exception when popping closing bracket on string starting with right parenthesis
- q080 [lexical]: implement queue using array
- q084 [lexical]: best time to buy and sell stock
- q088 [conceptual]: space complexity comparison of matrix versus list representation of graph
- q091 [conceptual]: definition of balanced binary tree in terms of left and right subtree heights
- q104 [symptom]: precision issues with float comparison in binary search termination condition

### Paired comparison at k=3: hybrid_en vs hybrid_multi

- hybrid_en only: 4 | hybrid_multi only: 2 | both: 8 | neither: 25
- exact McNemar p = 0.6875
- TOST Equivalence (margin delta = +/-10.0%): p_TOST = 0.2170 -> **Inconclusive / Not Equivalent**
- Bayesian Posterior P(|diff| < 10.0%): **79.2%** (95% Credible Interval [-7.9%, +17.6%])
- MRR difference (hybrid_en - hybrid_multi) = +0.009 (95% CI -0.103 to +0.124)

Only hybrid_en found:
- q030: base condition in recursion
- q040: how to count frequencies of characters in a string without a map
- q059: breadth first search traversal in graph
- q101: minimise maximum distance between gas stations

Only hybrid_multi found:
- q018: prefix sum hash map gives wrong length when array has zeros
- q020: divide and conquer merge sort

## Results: hit definition `overlap`

Hit iff same video and overlap >= min(0.5 x len(gt), 30s).

| retriever | k | Hit@k | 95% CI | MRR@k | 95% CI | span recall@k |
|---|---:|---:|---|---:|---|---:|
| bm25 | 1 | 15.4% | 7.2% to 29.7% | 0.154 | 0.051 to 0.282 | 15.4% |
| bm25 | 3 | 35.9% | 22.7% to 51.6% | 0.248 | 0.141 to 0.372 | 35.9% |
| bm25 | 5 | 43.6% | 29.3% to 59.0% | 0.267 | 0.165 to 0.395 | 43.6% |
| bm25 | 10 | 51.3% | 36.2% to 66.1% | 0.277 | 0.174 to 0.404 | 51.3% |
| hybrid_en | 1 | 17.9% | 9.0% to 32.7% | 0.179 | 0.077 to 0.308 | 16.7% |
| hybrid_en | 3 | 38.5% | 24.9% to 54.1% | 0.269 | 0.154 to 0.397 | 38.5% |
| hybrid_en | 5 | 43.6% | 29.3% to 59.0% | 0.281 | 0.172 to 0.408 | 43.6% |
| hybrid_en | 10 | 53.8% | 38.6% to 68.4% | 0.295 | 0.187 to 0.415 | 53.8% |
| hybrid_multi | 1 | 15.4% | 7.2% to 29.7% | 0.154 | 0.051 to 0.282 | 15.4% |
| hybrid_multi | 3 | 25.6% | 14.6% to 41.1% | 0.197 | 0.094 to 0.321 | 25.6% |
| hybrid_multi | 5 | 43.6% | 29.3% to 59.0% | 0.235 | 0.136 to 0.350 | 42.3% |
| hybrid_multi | 10 | 53.8% | 38.6% to 68.4% | 0.250 | 0.151 to 0.363 | 52.6% |

Seek precision:
- bm25: median |start error| of first hit = 32.5s (n=20)
- hybrid_en: median |start error| of first hit = 25.0s (n=21)
- hybrid_multi: median |start error| of first hit = 32.0s (n=21)

### Hit@3 by query type

| type | n | bm25 | hybrid_en | hybrid_multi |
|---|---:|---:|---:|---:|
| lexical | 14 | 57.1% | 71.4% | 42.9% |
| paraphrase | 5 | 0.0% | 20.0% | 0.0% |
| conceptual | 15 | 40.0% | 26.7% | 20.0% |
| symptom | 5 | 0.0% | 0.0% | 20.0% |

### Missed by every retriever at k=3 (check labels first)

- q001 [lexical]: tortoise and hare algorithm
- q006 [conceptual]: how to reverse a linked list using three pointers iteratively
- q008 [symptom]: lost reference to the rest of the list when reversing next pointer
- q012 [conceptual]: why two pointers fails if we need to return original indices in two sum
- q015 [paraphrase]: find contiguous subarray with given sum using prefix sums
- q022 [conceptual]: why is merge sort space complexity O(N)
- q025 [lexical]: partitioning algorithm in quick sort
- q027 [conceptual]: why does quicksort take O(N squared) time in worst case
- q042 [paraphrase]: how to find middle of linked list without counting total length first
- q044 [paraphrase]: recursive call tree depth and maximum memory consumed
- q046 [paraphrase]: in place partitioning without creating extra arrays
- q048 [lexical]: tail recursion
- q050 [conceptual]: two sum brute force nested loops time complexity
- q056 [symptom]: recursive fibonacci takes forever to execute for n greater than 40
- q063 [conceptual]: time complexity of bfs traversal with v vertices and e edges
- q066 [conceptual]: difference in call stack depth between dfs and bfs
- q075 [symptom]: empty stack exception when popping closing bracket on string starting with right parenthesis
- q088 [conceptual]: space complexity comparison of matrix versus list representation of graph
- q091 [conceptual]: definition of balanced binary tree in terms of left and right subtree heights
- q104 [symptom]: precision issues with float comparison in binary search termination condition

### Paired comparison at k=3: hybrid_en vs hybrid_multi

- hybrid_en only: 7 | hybrid_multi only: 2 | both: 8 | neither: 22
- exact McNemar p = 0.1797
- TOST Equivalence (margin delta = +/-10.0%): p_TOST = 0.6482 -> **Inconclusive / Not Equivalent**
- Bayesian Posterior P(|diff| < 10.0%): **38.6%** (95% Credible Interval [-2.1%, +26.7%])
- MRR difference (hybrid_en - hybrid_multi) = +0.073 (95% CI -0.056 to +0.209)

Only hybrid_en found:
- q030: base condition in recursion
- q032: why does infinite recursion cause segmentation fault
- q040: how to count frequencies of characters in a string without a map
- q059: breadth first search traversal in graph
- q080: implement queue using array
- q084: best time to buy and sell stock
- q101: minimise maximum distance between gas stations

Only hybrid_multi found:
- q018: prefix sum hash map gives wrong length when array has zeros
- q020: divide and conquer merge sort
