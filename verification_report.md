# Label verification report

- original golden `sha256:6acc2e6d4d2b` (104 queries) -> verified `sha256:d183ad389425` (102 queries)

## Counts

- confirm rows: 34 ok, 2 adjusted, 1 dropped
- blind rows: 14 found, 1 dropped (answer not found)
- unverified (left as agent labels): 52

## Blind subset: agreement of agent labels with an independent human

- 15 blind queries; 14 human spans; agent label agreed on **10/14 = 71%** (95% Wilson CI 45% to 88%)
- agent spans with no matching human span: 4
- start difference where they agree: n=10, median agent-minus-human start = +5.0s; agent started >5s early on 0, >5s late on 3
- agreement rule: the agent's start lies within [human.start - 20s, human.start + 0.5 x len(human)]
- WARNING: below the protocol's 85% target. The agent labels are not reliable enough to report unqualified; use the verified file as primary.
- queries to inspect: q009, q018, q024, q026, q043

## Confirm subset: how the agent's starts compare

- adjusted spans: n=2, median agent-minus-human start = -70.0s; agent started >5s early on 1, >5s late on 1

## Errata

17 changes; every one is listed in the errata file with before/after.

## What to do next

1. Re-run the evaluation on BOTH golden files (same run files; query ids are unchanged) and report both.
2. If conclusions differ between them, trust the verified file and say so.
3. Do not edit labels again after seeing test results.