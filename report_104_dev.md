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
| bm25 | 1 | 7.7% | 2.7% to 20.3% | 0.077 | 0.000 to 0.179 | 7.7% |
| bm25 | 3 | 28.2% | 16.5% to 43.8% | 0.167 | 0.081 to 0.269 | 26.9% |
| bm25 | 5 | 35.9% | 22.7% to 51.6% | 0.185 | 0.097 to 0.285 | 34.6% |
| bm25 | 10 | 43.6% | 29.3% to 59.0% | 0.195 | 0.111 to 0.293 | 42.3% |
| hybrid_en | 1 | 12.8% | 5.6% to 26.7% | 0.128 | 0.051 to 0.256 | 12.8% |
| hybrid_en | 3 | 33.3% | 20.6% to 49.0% | 0.214 | 0.115 to 0.333 | 32.1% |
| hybrid_en | 5 | 35.9% | 22.7% to 51.6% | 0.219 | 0.120 to 0.335 | 34.6% |
| hybrid_en | 10 | 48.7% | 33.9% to 63.8% | 0.236 | 0.138 to 0.346 | 47.4% |
| hybrid_multi | 1 | 15.4% | 7.2% to 29.7% | 0.154 | 0.051 to 0.282 | 15.4% |
| hybrid_multi | 3 | 25.6% | 14.6% to 41.1% | 0.197 | 0.094 to 0.321 | 25.6% |
| hybrid_multi | 5 | 33.3% | 20.6% to 49.0% | 0.213 | 0.112 to 0.334 | 33.3% |
| hybrid_multi | 10 | 35.9% | 22.7% to 51.6% | 0.216 | 0.115 to 0.336 | 35.9% |

Seek precision:
- bm25: median |start error| of first hit = 17.0s (n=17)
- hybrid_en: median |start error| of first hit = 25.0s (n=19)
- hybrid_multi: median |start error| of first hit = 26.0s (n=14)

### Hit@3 by query type

| type | n | bm25 | hybrid_en | hybrid_multi |
|---|---:|---:|---:|---:|
| lexical | 14 | 50.0% | 57.1% | 42.9% |
| paraphrase | 5 | 0.0% | 20.0% | 0.0% |
| conceptual | 15 | 26.7% | 20.0% | 20.0% |
| symptom | 5 | 0.0% | 20.0% | 20.0% |

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
- q098 [conceptual]: partitioning two arrays such that all elements on the left are smaller than on the right
- q104 [symptom]: precision issues with float comparison in binary search termination condition

### Paired comparison at k=3: hybrid_en vs hybrid_multi

- hybrid_en only: 4 | hybrid_multi only: 1 | both: 9 | neither: 25
- exact McNemar p = 0.3750
- TOST Equivalence (margin delta = +/-10.0%): p_TOST = 0.3401 -> **Inconclusive / Not Equivalent**
- Bayesian Posterior P(|diff| < 10.0%): **69.6%** (95% Credible Interval [-3.9%, +19.5%])
- MRR difference (hybrid_en - hybrid_multi) = +0.017 (95% CI -0.081 to +0.115)

Only hybrid_en found:
- q030: base condition in recursion
- q040: how to count frequencies of characters in a string without a map
- q059: breadth first search traversal in graph
- q101: minimise maximum distance between gas stations

Only hybrid_multi found:
- q020: divide and conquer merge sort

## Results: hit definition `overlap`

Hit iff same video and overlap >= min(0.5 x len(gt), 30s).

| retriever | k | Hit@k | 95% CI | MRR@k | 95% CI | span recall@k |
|---|---:|---:|---|---:|---|---:|
| bm25 | 1 | 7.7% | 2.7% to 20.3% | 0.077 | 0.000 to 0.179 | 7.7% |
| bm25 | 3 | 23.1% | 12.6% to 38.3% | 0.145 | 0.060 to 0.248 | 23.1% |
| bm25 | 5 | 30.8% | 18.6% to 46.4% | 0.163 | 0.079 to 0.266 | 30.8% |
| bm25 | 10 | 38.5% | 24.9% to 54.1% | 0.174 | 0.091 to 0.274 | 38.5% |
| hybrid_en | 1 | 7.7% | 2.7% to 20.3% | 0.077 | 0.000 to 0.179 | 7.7% |
| hybrid_en | 3 | 25.6% | 14.6% to 41.1% | 0.150 | 0.064 to 0.252 | 25.6% |
| hybrid_en | 5 | 28.2% | 16.5% to 43.8% | 0.155 | 0.069 to 0.258 | 28.2% |
| hybrid_en | 10 | 38.5% | 24.9% to 54.1% | 0.169 | 0.086 to 0.271 | 38.5% |
| hybrid_multi | 1 | 15.4% | 7.2% to 29.7% | 0.154 | 0.051 to 0.282 | 15.4% |
| hybrid_multi | 3 | 23.1% | 12.6% to 38.3% | 0.188 | 0.085 to 0.312 | 23.1% |
| hybrid_multi | 5 | 33.3% | 20.6% to 49.0% | 0.210 | 0.107 to 0.329 | 33.3% |
| hybrid_multi | 10 | 35.9% | 22.7% to 51.6% | 0.213 | 0.110 to 0.334 | 35.9% |

Seek precision:
- bm25: median |start error| of first hit = 17.0s (n=15)
- hybrid_en: median |start error| of first hit = 25.0s (n=15)
- hybrid_multi: median |start error| of first hit = 27.0s (n=14)

### Hit@3 by query type

| type | n | bm25 | hybrid_en | hybrid_multi |
|---|---:|---:|---:|---:|
| lexical | 14 | 35.7% | 42.9% | 35.7% |
| paraphrase | 5 | 0.0% | 20.0% | 0.0% |
| conceptual | 15 | 26.7% | 13.3% | 20.0% |
| symptom | 5 | 0.0% | 20.0% | 20.0% |

### Missed by every retriever at k=3 (check labels first)

- q001 [lexical]: tortoise and hare algorithm
- q006 [conceptual]: how to reverse a linked list using three pointers iteratively
- q008 [symptom]: lost reference to the rest of the list when reversing next pointer
- q012 [conceptual]: why two pointers fails if we need to return original indices in two sum
- q015 [paraphrase]: find contiguous subarray with given sum using prefix sums
- q022 [conceptual]: why is merge sort space complexity O(N)
- q025 [lexical]: partitioning algorithm in quick sort
- q027 [conceptual]: why does quicksort take O(N squared) time in worst case
- q030 [lexical]: base condition in recursion
- q032 [conceptual]: why does infinite recursion cause segmentation fault
- q042 [paraphrase]: how to find middle of linked list without counting total length first
- q044 [paraphrase]: recursive call tree depth and maximum memory consumed
- q046 [paraphrase]: in place partitioning without creating extra arrays
- q048 [lexical]: tail recursion
- q050 [conceptual]: two sum brute force nested loops time complexity
- q056 [symptom]: recursive fibonacci takes forever to execute for n greater than 40
- q063 [conceptual]: time complexity of bfs traversal with v vertices and e edges
- q066 [conceptual]: difference in call stack depth between dfs and bfs
- q072 [lexical]: check for balanced parentheses
- q075 [symptom]: empty stack exception when popping closing bracket on string starting with right parenthesis
- q080 [lexical]: implement queue using array
- q084 [lexical]: best time to buy and sell stock
- q088 [conceptual]: space complexity comparison of matrix versus list representation of graph
- q091 [conceptual]: definition of balanced binary tree in terms of left and right subtree heights
- q098 [conceptual]: partitioning two arrays such that all elements on the left are smaller than on the right
- q104 [symptom]: precision issues with float comparison in binary search termination condition

### Paired comparison at k=3: hybrid_en vs hybrid_multi

- hybrid_en only: 3 | hybrid_multi only: 2 | both: 7 | neither: 27
- exact McNemar p = 1.0000
- TOST Equivalence (margin delta = +/-10.0%): p_TOST = 0.0968 -> **Inconclusive / Not Equivalent**
- Bayesian Posterior P(|diff| < 10.0%): **88.7%** (95% Credible Interval [-9.5%, +14.5%])
- MRR difference (hybrid_en - hybrid_multi) = -0.038 (95% CI -0.145 to +0.060)

Only hybrid_en found:
- q040: how to count frequencies of characters in a string without a map
- q059: breadth first search traversal in graph
- q101: minimise maximum distance between gas stations

Only hybrid_multi found:
- q003: why does the fast pointer never jump over the slow pointer in a cycle
- q020: divide and conquer merge sort
