**Derived verdict:** YES  (rule: ≤ 2 retained unclear items and no hedge in the restatement; computed in code)
<!-- yamlgraph-outsider | source: pr-591-v2 | provider: anthropic | model: claude-haiku-4-5 | 2026-09-05T13:52:02.210086+00:00 -->

## 1. In my own words

This PR adds a pipeline that processes 242 software capabilities to determine which user types each serves, whether anything in the codebase uses it, and whether it should be kept or removed. The pipeline has four steps: extracting facts about each capability via code search (no AI), classifying capabilities into ten user types using Claude Haiku, validating that cited evidence actually exists in the search results, and checking against six pre-written correct answers as canaries. A 30-capability trial run found that two capabilities have no codebase usage, about half serve only internal developers, the user-type classification is unreliable (with a catch-all category that migrated between runs and two high-priority business categories receiving zero classifications), and the business-value sentences are not useful for ranking. The text does not state whether the pipeline code itself has been tested beyond the trial run or what the acceptance criteria are for stabilizing the classification before a full 242-capability run.

## 2. Could I decide whether to merge this from the description alone?

YES
(model's non-authoritative opinion) The description clearly states what the pipeline does, what the trial found, what is knowingly incomplete, where to find results and code, and how to run it.

## 3. Words and references I could not understand

- **“Someone writing a graph”** · is this a user type from the ten defined in journeys.yaml, or a description of a problem the model created? · "mercury-2" · is this a different AI model, and if so why was it agreed but not used? · "FR-990 AC-7" · what is the relationship between this FR number and AC number? · "retire" rows · does this mean rows marked for removal, or something else? · "cross-cutting handling" · what does this mean in the context of capability classification?

## 4. What a merge decision would still need

- [ ] Whether the checker validation rules in tools.py are correct or have been reviewed. Whether the six canary capabilities are representative of the full 242. Whether the 30-capability sample was random or selected. Whether the model's temperature-0 setting was chosen deliberately and why. Whether the unreliability in user-type sorting is a blocker for merging or acceptable for a research instrument.

### Set aside by the reducer (not counted)

none
