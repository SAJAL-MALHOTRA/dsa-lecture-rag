# Retrieval evaluation report

- golden: `sha256:6acc2e6d4d2b`, 65 queries, split = **test**
- temporal dedup: overlap >= 50% of the shorter span
- primary k = 3; CIs: Wilson (hit rate), bootstrap (MRR), 2000 resamples
- **UNREGISTERED TEST RUN: no pre-registration lock was used. Treat these numbers as exploratory, not as the test result.**

> TEST split: evaluate each final configuration once. Do not tune against it.

## Lexical-leakage audit

Mean query-to-answer word overlap: **0.44** over 65 queries (0 skipped: no transcript).

| type | n | mean overlap | share >= 0.8 |
|---|---:|---:|---:|
| lexical | 13 | 0.54 | 8% |
| paraphrase | 21 | 0.43 | 14% |
| conceptual | 17 | 0.44 | 12% |
| symptom | 14 | 0.35 | 0% |


Highly leaky queries (>= 0.8):
- q014 (1.00): worst case time complexity of unordered_map in c++
- q060 (0.80): why is a visited array required in graph traversal
- q069 (0.80): why the search space for integer square root is from 1 to n
- q077 (0.80): visiting left subtree then root then right subtree
- q092 (0.90): binary tree where every parent node has either zero or two children
- q095 (0.80): minimum energy required to reach last stair when jumping one or two steps

## Results: hit definition `seek`

Hit iff same video and gt.start - 20s <= result.start <= gt.start + 0.5 x len(gt).

| retriever | k | Hit@k | 95% CI | MRR@k | 95% CI | span recall@k |
|---|---:|---:|---|---:|---|---:|
| bm25 | 1 | 6.2% | 2.4% to 14.8% | 0.062 | 0.015 to 0.123 | 6.2% |
| bm25 | 3 | 15.4% | 8.6% to 26.1% | 0.100 | 0.044 to 0.164 | 15.4% |
| bm25 | 5 | 18.5% | 10.9% to 29.6% | 0.107 | 0.051 to 0.171 | 18.5% |
| bm25 | 10 | 26.2% | 17.0% to 38.0% | 0.116 | 0.059 to 0.181 | 26.2% |
| hybrid_en | 1 | 7.7% | 3.3% to 16.8% | 0.077 | 0.015 to 0.138 | 7.7% |
| hybrid_en | 3 | 12.3% | 6.4% to 22.5% | 0.095 | 0.036 to 0.167 | 12.3% |
| hybrid_en | 5 | 21.5% | 13.3% to 33.0% | 0.116 | 0.056 to 0.186 | 21.5% |
| hybrid_en | 10 | 32.3% | 22.2% to 44.4% | 0.131 | 0.071 to 0.201 | 32.3% |
| hybrid_multi | 1 | 6.2% | 2.4% to 14.8% | 0.062 | 0.015 to 0.123 | 6.2% |
| hybrid_multi | 3 | 12.3% | 6.4% to 22.5% | 0.085 | 0.028 to 0.149 | 12.3% |
| hybrid_multi | 5 | 23.1% | 14.5% to 34.6% | 0.109 | 0.052 to 0.172 | 23.1% |
| hybrid_multi | 10 | 27.7% | 18.3% to 39.6% | 0.115 | 0.058 to 0.179 | 27.7% |

Seek precision:
- bm25: median |start error| of first hit = 8.0s (n=17)
- hybrid_en: median |start error| of first hit = 9.0s (n=21)
- hybrid_multi: median |start error| of first hit = 15.5s (n=18)

### Hit@3 by query type

| type | n | bm25 | hybrid_en | hybrid_multi |
|---|---:|---:|---:|---:|
| lexical | 13 | 15.4% | 23.1% | 23.1% |
| paraphrase | 21 | 19.0% | 14.3% | 14.3% |
| conceptual | 17 | 17.6% | 11.8% | 11.8% |
| symptom | 14 | 7.1% | 0.0% | 0.0% |

### Missed by every retriever at k=3 (check labels first)

- q002 [paraphrase]: technique with two pointers moving at different speeds to find loop
- q004 [paraphrase]: detect cycle by storing visited node addresses in a set
- q005 [symptom]: my while loop runs forever when checking if linked list has a loop
- q007 [lexical]: reversing singly linked list using recursion
- q009 [conceptual]: time and space complexity of recursive linked list reversal
- q011 [paraphrase]: find a pair that adds up to target without using extra memory
- q013 [symptom]: my hash map returns the same element twice when target is double of it
- q014 [lexical]: worst case time complexity of unordered_map in c++
- q016 [lexical]: sliding window for longest subarray with positive sum
- q017 [conceptual]: why two pointer window fails when array contains negative numbers
- q019 [conceptual]: generating all subarrays brute force time complexity
- q021 [paraphrase]: combining two already sorted halves into a single list
- q023 [symptom]: mid calculation low plus high divided by two overflow
- q024 [conceptual]: recurrence relation for merge sort time complexity
- q028 [symptom]: index out of bounds in quick sort partition pointer crossing
- q031 [paraphrase]: how the computer remembers where to return after a recursive call
- q033 [symptom]: program crashes with stack overflow error
- q034 [lexical]: recursion tree diagram
- q038 [symptom]: large array index throws memory limit exceeded error
- q039 [conceptual]: difference between map and unordered_map in stl
- q041 [lexical]: linear probing collision handling
- q043 [conceptual]: why merge sort is preferred over quicksort for linked lists
- q045 [symptom]: segmentation fault when dereferencing next on null pointer in linked list
- q047 [conceptual]: why can hash function not store negative numbers directly with modulo
- q049 [symptom]: recursive step modifying input node link causes cycle in list
- q051 [conceptual]: quick sort recursion tree depth in best vs worst case
- q054 [conceptual]: why memoization reduces exponential recursion to linear time
- q055 [paraphrase]: top down approach with an array to store already computed states
- q057 [conceptual]: how to convert top down memoization into bottom up tabulation
- q058 [paraphrase]: optimizing dp array to two variables for constant space
- q062 [symptom]: graph traversal causes infinite loop on cyclic graph
- q064 [lexical]: depth first search in graphs
- q065 [paraphrase]: recursive exploration of graph going as deep as possible before backtracking
- q067 [symptom]: getting stack overflow error on deep graph traversal
- q069 [conceptual]: why the search space for integer square root is from 1 to n
- q070 [paraphrase]: finding largest integer whose square is less than or equal to n
- q071 [symptom]: integer overflow when calculating mid times mid in binary search
- q074 [paraphrase]: verifying if every opening symbol has a corresponding closing symbol in order
- q077 [paraphrase]: visiting left subtree then root then right subtree
- q079 [lexical]: preorder traversal sequence
- q081 [conceptual]: why does a standard queue need front and rear pointers
- q082 [paraphrase]: circular array buffer to prevent wasted space in queue implementation
- q083 [symptom]: stack overflow when pushing to fixed size array
- q085 [conceptual]: why keeping track of the minimum price so far gives optimal profit
- q086 [paraphrase]: single pass algorithm to find maximum difference between two elements where second comes after first
- q087 [lexical]: adjacency matrix versus adjacency list
- q089 [paraphrase]: storing neighbor connections as array of lists instead of 2d grid
- q092 [paraphrase]: binary tree where every parent node has either zero or two children
- q097 [lexical]: median of two sorted arrays binary search
- q099 [paraphrase]: finding 50th percentile across two independent ordered collections in logarithmic time
- q100 [symptom]: edge case when all elements from the first array lie on the left side of partition
- q102 [conceptual]: why binary search works on floating point distances between gas stations
- q103 [paraphrase]: placing k extra stations on highway to reduce gaps between consecutive points

### Paired comparison at k=3: hybrid_en vs hybrid_multi

- hybrid_en only: 1 | hybrid_multi only: 1 | both: 7 | neither: 56
- exact McNemar p = 1.0000
- TOST Equivalence (margin delta = +/-10.0%): p_TOST = 0.0000 -> **Equivalent (p < 0.05)**
- Bayesian Posterior P(|diff| < 10.0%): **99.6%** (95% Credible Interval [-5.4%, +5.6%])
- MRR difference (hybrid_en - hybrid_multi) = +0.010 (95% CI -0.010 to +0.033)

Only hybrid_en found:
- q090: full binary tree versus complete binary tree

Only hybrid_multi found:
- q076: inorder traversal of binary tree

## Results: hit definition `overlap`

Hit iff same video and overlap >= min(0.5 x len(gt), 30s).

| retriever | k | Hit@k | 95% CI | MRR@k | 95% CI | span recall@k |
|---|---:|---:|---|---:|---|---:|
| bm25 | 1 | 10.8% | 5.3% to 20.6% | 0.108 | 0.031 to 0.185 | 10.8% |
| bm25 | 3 | 16.9% | 9.7% to 27.8% | 0.136 | 0.062 to 0.221 | 16.9% |
| bm25 | 5 | 20.0% | 12.1% to 31.3% | 0.144 | 0.068 to 0.226 | 20.0% |
| bm25 | 10 | 26.2% | 17.0% to 38.0% | 0.151 | 0.076 to 0.233 | 26.2% |
| hybrid_en | 1 | 13.8% | 7.5% to 24.3% | 0.138 | 0.062 to 0.231 | 13.8% |
| hybrid_en | 3 | 18.5% | 10.9% to 29.6% | 0.156 | 0.074 to 0.246 | 18.5% |
| hybrid_en | 5 | 23.1% | 14.5% to 34.6% | 0.167 | 0.085 to 0.255 | 23.1% |
| hybrid_en | 10 | 32.3% | 22.2% to 44.4% | 0.180 | 0.098 to 0.268 | 32.3% |
| hybrid_multi | 1 | 9.2% | 4.3% to 18.7% | 0.092 | 0.031 to 0.169 | 9.2% |
| hybrid_multi | 3 | 13.8% | 7.5% to 24.3% | 0.110 | 0.044 to 0.187 | 13.8% |
| hybrid_multi | 5 | 23.1% | 14.5% to 34.6% | 0.132 | 0.067 to 0.207 | 23.1% |
| hybrid_multi | 10 | 27.7% | 18.3% to 39.6% | 0.138 | 0.073 to 0.213 | 27.7% |

Seek precision:
- bm25: median |start error| of first hit = 25.0s (n=17)
- hybrid_en: median |start error| of first hit = 11.0s (n=21)
- hybrid_multi: median |start error| of first hit = 23.0s (n=18)

### Hit@3 by query type

| type | n | bm25 | hybrid_en | hybrid_multi |
|---|---:|---:|---:|---:|
| lexical | 13 | 23.1% | 30.8% | 23.1% |
| paraphrase | 21 | 28.6% | 28.6% | 19.0% |
| conceptual | 17 | 11.8% | 11.8% | 11.8% |
| symptom | 14 | 0.0% | 0.0% | 0.0% |

### Missed by every retriever at k=3 (check labels first)

- q002 [paraphrase]: technique with two pointers moving at different speeds to find loop
- q004 [paraphrase]: detect cycle by storing visited node addresses in a set
- q005 [symptom]: my while loop runs forever when checking if linked list has a loop
- q007 [lexical]: reversing singly linked list using recursion
- q009 [conceptual]: time and space complexity of recursive linked list reversal
- q011 [paraphrase]: find a pair that adds up to target without using extra memory
- q013 [symptom]: my hash map returns the same element twice when target is double of it
- q014 [lexical]: worst case time complexity of unordered_map in c++
- q016 [lexical]: sliding window for longest subarray with positive sum
- q017 [conceptual]: why two pointer window fails when array contains negative numbers
- q019 [conceptual]: generating all subarrays brute force time complexity
- q021 [paraphrase]: combining two already sorted halves into a single list
- q023 [symptom]: mid calculation low plus high divided by two overflow
- q024 [conceptual]: recurrence relation for merge sort time complexity
- q028 [symptom]: index out of bounds in quick sort partition pointer crossing
- q029 [conceptual]: why quick sort is preferred over merge sort for arrays
- q031 [paraphrase]: how the computer remembers where to return after a recursive call
- q033 [symptom]: program crashes with stack overflow error
- q034 [lexical]: recursion tree diagram
- q038 [symptom]: large array index throws memory limit exceeded error
- q039 [conceptual]: difference between map and unordered_map in stl
- q041 [lexical]: linear probing collision handling
- q043 [conceptual]: why merge sort is preferred over quicksort for linked lists
- q045 [symptom]: segmentation fault when dereferencing next on null pointer in linked list
- q047 [conceptual]: why can hash function not store negative numbers directly with modulo
- q049 [symptom]: recursive step modifying input node link causes cycle in list
- q051 [conceptual]: quick sort recursion tree depth in best vs worst case
- q054 [conceptual]: why memoization reduces exponential recursion to linear time
- q055 [paraphrase]: top down approach with an array to store already computed states
- q057 [conceptual]: how to convert top down memoization into bottom up tabulation
- q058 [paraphrase]: optimizing dp array to two variables for constant space
- q061 [paraphrase]: exploring graph nodes level by level starting from source
- q062 [symptom]: graph traversal causes infinite loop on cyclic graph
- q064 [lexical]: depth first search in graphs
- q065 [paraphrase]: recursive exploration of graph going as deep as possible before backtracking
- q067 [symptom]: getting stack overflow error on deep graph traversal
- q069 [conceptual]: why the search space for integer square root is from 1 to n
- q070 [paraphrase]: finding largest integer whose square is less than or equal to n
- q071 [symptom]: integer overflow when calculating mid times mid in binary search
- q077 [paraphrase]: visiting left subtree then root then right subtree
- q081 [conceptual]: why does a standard queue need front and rear pointers
- q082 [paraphrase]: circular array buffer to prevent wasted space in queue implementation
- q083 [symptom]: stack overflow when pushing to fixed size array
- q085 [conceptual]: why keeping track of the minimum price so far gives optimal profit
- q086 [paraphrase]: single pass algorithm to find maximum difference between two elements where second comes after first
- q087 [lexical]: adjacency matrix versus adjacency list
- q089 [paraphrase]: storing neighbor connections as array of lists instead of 2d grid
- q096 [symptom]: index out of bounds when looking at i minus two state in frog jump
- q097 [lexical]: median of two sorted arrays binary search
- q099 [paraphrase]: finding 50th percentile across two independent ordered collections in logarithmic time
- q100 [symptom]: edge case when all elements from the first array lie on the left side of partition
- q102 [conceptual]: why binary search works on floating point distances between gas stations

### Paired comparison at k=3: hybrid_en vs hybrid_multi

- hybrid_en only: 4 | hybrid_multi only: 1 | both: 8 | neither: 52
- exact McNemar p = 0.3750
- TOST Equivalence (margin delta = +/-10.0%): p_TOST = 0.0562 -> **Inconclusive / Not Equivalent**
- Bayesian Posterior P(|diff| < 10.0%): **93.0%** (95% Credible Interval [-2.3%, +12.1%])
- MRR difference (hybrid_en - hybrid_multi) = +0.046 (95% CI -0.003 to +0.108)

Only hybrid_en found:
- q079: preorder traversal sequence
- q090: full binary tree versus complete binary tree
- q092: binary tree where every parent node has either zero or two children
- q103: placing k extra stations on highway to reduce gaps between consecutive points

Only hybrid_multi found:
- q076: inorder traversal of binary tree
