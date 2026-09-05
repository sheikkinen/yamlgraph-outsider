**Derived verdict:** YES  (rule: ≤ 2 retained unclear items and no hedge in the restatement; computed in code)
<!-- input: README.md | sha256: 7fbcc2d60664966bdde120a764f368fb14f1a5c1895999e6d49013b868d49fc3 | source commit: ee5ea00 (README uncommitted at run time; committed in the next commit) -->
<!-- yamlgraph-outsider | source: README | provider: anthropic | model: claude-haiku-4-5 | 2026-09-05T14:29:15.901416+00:00 -->

## 1. In my own words

This pull request introduces yamlgraph-outsider, a tool that shows a pull request's title and description to a language model that has never seen the project and reports what phrases or concepts the model could not understand. The tool is designed to help authors identify insider language before human review, by running the PR text through a configurable LLM (tested with Anthropic's claude-haiku-4-5) and producing a report with four sections: the model's restatement, the model's opinion on whether the PR is mergeable from the description alone, a list of phrases the model could not understand, and a list of information a merge decision would still need. The tool includes a "reducer" that filters out bare identifiers, file paths, and self-explained phrases before computing a verdict. The text does not state what repository this is being merged into, whether this is a new tool or an enhancement to an existing one, or who the intended users are beyond "authors" and "reviewers."

## 2. Could I decide whether to merge this from the description alone?

YES
(model's non-authoritative opinion) The description clearly states what the tool does, how to install and use it, what the output contains, how it was tested, and what its known limits are.

## 3. Words and references I could not understand

- **“the reducer”** · what specific rules does it apply beyond the three examples given?

## 4. What a merge decision would still need

- [ ] Whether this is a new repository or a feature added to an existing one.
- [ ] What the fixture mismatch means for reliability and whether it is acceptable.
- [ ] Whether the tool is production-ready or still experimental.
- [ ] Cost estimate for running the live tests or typical usage.

### Set aside by the reducer (not counted)

- **“sheikkinen/yamlgraph”** · is this the parent project or an unrelated project? — reason: path
- **“FR-1001”** · what is this identifier and why is it relevant? — reason: identifier
- **“FR-995”** · what is this identifier and why is it relevant? — reason: identifier
