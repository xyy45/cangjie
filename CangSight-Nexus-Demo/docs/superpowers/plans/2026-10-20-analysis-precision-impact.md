# Approved implementation ledger: selected-line slicing and candidate impact

Scope: select a source line for backward slicing, persist/restore criteria, and
explicitly generate before/after impact reports for isolated registered candidates.
No uploaded-program repair, model calls, or automatic candidate acceptance.

1. Tests first: strict slice-line validation and request binding; preserve legacy
   default-line records and original bytes. UI separates selected target from the
   criteria of displayed results.
2. Candidate impact: deterministic source diff/function text ranges; optional real
   MCP analyses bound to each side's exact source and selected changed line.
   Persist one job per candidate, no replay, conservative restart, exact evidence
   copies. Reuse only matching source/name/criteria records.
3. UI: candidate-specific impact preview, explicit generate action, per-side
   graph/diagnostic/source links, download, late-response guards.
4. Verify focused/full suites, actual MCP selected-line requests and a real
   existing candidate comparison, browser flows, docs and updated source ZIP.

Rulings: no Git repository exists; edit this approved directory in place. Function
locations are source-text observations, not compiler AST claims. Graph nodes are
never matched across versions by opaque node ID. Existing test/verification and
model budgets are unchanged.

Progress: implemented and verified.

- Selected-line API validation, immutable criteria and history: focused tests pass.
- Explicit candidate impact, per-side exact bytes, cache criteria, lease and atomic
  archive event: 13 impact regressions pass; independent review confirms fixes.
- Full Python: 302 passed, 1 deselected, 251.82s; Node: 52 passed.
- Real upload L7/L43: 6 MCP calls, correctly bound PARTIAL observations, native
  DDG valid, original slice failures retained with display-only text recovery.
- Existing real candidate: 12 MCP calls / 31.641s, PARTIAL with empty DDGs honestly
  labelled, original source and 22-entry downloaded archive hashes verified.
- No additional model calls, no acceptance, baseline and candidate unchanged.
- Pure readonly target hint wording received final focused UI verification.

Ruling: the upstream service's parameter/semantic precision is outside our control;
we verify transmitted criteria and preserve warnings rather than claiming every
selected line produces an exact semantic slice. Registered package fragments
currently produce empty DDGs; valid nonempty graph neighborhoods are separately
covered by deterministic tests, not fabricated in the actual comparison.
