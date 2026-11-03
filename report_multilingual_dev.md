# Retrieval evaluation report

- golden: `sha256:ff6d9eeecbf5`, 22 queries, split = **dev**
- temporal dedup: overlap >= 50% of the shorter span
- primary k = 3; CIs: Wilson (hit rate), bootstrap (MRR), 2000 resamples

## Lexical-leakage audit

Mean query-to-answer word overlap: **0.48** over 22 queries (0 skipped: no transcript).

| type | n | mean overlap | share >= 0.8 |
|---|---:|---:|---:|
| lexical | 7 | 0.66 | 43% |
| paraphrase | 5 | 0.40 | 0% |
| conceptual | 8 | 0.38 | 0% |
| symptom | 2 | 0.39 | 0% |


Highly leaky queries (>= 0.8):
- q001 (1.00): tortoise and hare algorithm
- q030 (1.00): base condition in recursion
- q035 (1.00): hashing collisions

## Results: hit definition `seek`

Hit iff same video and gt.start - 20s <= result.start <= gt.start + 0.5 x len(gt).

| retriever | k | Hit@k | 95% CI | MRR@k | 95% CI | span recall@k |
|---|---:|---:|---|---:|---|---:|
| english | 1 | 9.1% | 2.5% to 27.8% | 0.091 | 0.000 to 0.227 | 9.1% |
| english | 3 | 27.3% | 13.2% to 48.2% | 0.159 | 0.045 to 0.303 | 25.0% |
| english | 5 | 27.3% | 13.2% to 48.2% | 0.159 | 0.045 to 0.303 | 25.0% |
| english | 10 | 50.0% | 30.7% to 69.3% | 0.189 | 0.080 to 0.323 | 47.7% |
| multilingual | 1 | 13.6% | 4.7% to 33.3% | 0.136 | 0.000 to 0.273 | 13.6% |
| multilingual | 3 | 22.7% | 10.1% to 43.4% | 0.174 | 0.045 to 0.341 | 22.7% |
| multilingual | 5 | 27.3% | 13.2% to 48.2% | 0.183 | 0.055 to 0.345 | 27.3% |
| multilingual | 10 | 27.3% | 13.2% to 48.2% | 0.183 | 0.055 to 0.345 | 27.3% |

Seek precision:
- english: median |start error| of first hit = 30.0s (n=11)
- multilingual: median |start error| of first hit = 44.5s (n=6)

### Hit@3 by query type

| type | n | english | multilingual |
|---|---:|---:|---:|
| lexical | 7 | 42.9% | 42.9% |
| paraphrase | 5 | 20.0% | 0.0% |
| conceptual | 8 | 12.5% | 12.5% |
| symptom | 2 | 50.0% | 50.0% |

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
- q037 [conceptual]: separate chaining collision resolution using linked list
- q042 [paraphrase]: how to find middle of linked list without counting total length first
- q044 [paraphrase]: recursive call tree depth and maximum memory consumed
- q046 [paraphrase]: in place partitioning without creating extra arrays
- q048 [lexical]: tail recursion
- q050 [conceptual]: two sum brute force nested loops time complexity

### Paired comparison at k=3: english vs multilingual

- english only: 2 · multilingual only: 1 · both: 4 · neither: 15
- exact McNemar p = 1.0000
- MRR difference (english - multilingual) = -0.015 (95% CI -0.159 to +0.114)

Only english found:
- q030: base condition in recursion
- q040: how to count frequencies of characters in a string without a map

Only multilingual found:
- q020: divide and conquer merge sort

## Results: hit definition `overlap`

Hit iff same video and overlap >= min(0.5 x len(gt), 30s).

| retriever | k | Hit@k | 95% CI | MRR@k | 95% CI | span recall@k |
|---|---:|---:|---|---:|---|---:|
| english | 1 | 4.5% | 0.8% to 21.8% | 0.045 | 0.000 to 0.136 | 4.5% |
| english | 3 | 18.2% | 7.3% to 38.5% | 0.091 | 0.015 to 0.197 | 18.2% |
| english | 5 | 18.2% | 7.3% to 38.5% | 0.091 | 0.015 to 0.197 | 18.2% |
| english | 10 | 36.4% | 19.7% to 57.0% | 0.116 | 0.036 to 0.222 | 36.4% |
| multilingual | 1 | 13.6% | 4.7% to 33.3% | 0.136 | 0.000 to 0.273 | 13.6% |
| multilingual | 3 | 22.7% | 10.1% to 43.4% | 0.174 | 0.045 to 0.341 | 22.7% |
| multilingual | 5 | 31.8% | 16.4% to 52.7% | 0.192 | 0.061 to 0.352 | 31.8% |
| multilingual | 10 | 31.8% | 16.4% to 52.7% | 0.192 | 0.061 to 0.352 | 31.8% |

Seek precision:
- english: median |start error| of first hit = 43.5s (n=8)
- multilingual: median |start error| of first hit = 59.0s (n=7)

### Hit@3 by query type

| type | n | english | multilingual |
|---|---:|---:|---:|
| lexical | 7 | 28.6% | 42.9% |
| paraphrase | 5 | 20.0% | 0.0% |
| conceptual | 8 | 0.0% | 12.5% |
| symptom | 2 | 50.0% | 50.0% |

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
- q037 [conceptual]: separate chaining collision resolution using linked list
- q042 [paraphrase]: how to find middle of linked list without counting total length first
- q044 [paraphrase]: recursive call tree depth and maximum memory consumed
- q046 [paraphrase]: in place partitioning without creating extra arrays
- q048 [lexical]: tail recursion
- q050 [conceptual]: two sum brute force nested loops time complexity

### Paired comparison at k=3: english vs multilingual

- english only: 1 · multilingual only: 2 · both: 3 · neither: 16
- exact McNemar p = 1.0000
- MRR difference (english - multilingual) = -0.083 (95% CI -0.242 to +0.061)

Only english found:
- q040: how to count frequencies of characters in a string without a map

Only multilingual found:
- q003: why does the fast pointer never jump over the slow pointer in a cycle
- q020: divide and conquer merge sort
