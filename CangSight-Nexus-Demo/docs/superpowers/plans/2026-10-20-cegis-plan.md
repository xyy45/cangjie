# CEGIS implementation ledger

Approved scope: up to three DeepSeek proposals, real MCP verification feedback,
isolated baseline-based candidates, round history UI, existing human review.

1. Persist one model reservation per task/round; only attributable previous failure
   permits a next round. Preserve legacy one-call reservations and uncertain outcomes.
2. Send explicit round/budget and baseline semantics; record useful stop reasons.
3. Show selectable round summaries, advice, diff, checks and diagnostic feedback;
   prevent review of historical/stale candidates and async selection races.
4. Verify protocol tests, deterministic actual SDK/MCP two-round test, full suites,
   bounded real DeepSeek/MCP run, browser checks, refreshed source archive.

Ruling: no Git repository exists here; edit the approved project in place and
deliver a source ZIP rather than creating a branch or PR.

Progress: all four implementation steps complete.

Verification:
- Focused DeepSeek/controller: 24 passed; frontend race/round tests: 12 passed.
- Actual SDK/MCP + deterministic model HTTP: 2 candidates, first failed and second passed;
  immutable baseline retained, zero acceptance. 1 test passed in 18.63s.
- Full non-live Python: 272 passed, 1 deselected in 253.19s.
- Frontend Node: 46 passed.
- Actual DeepSeek + remote static MCP + local verification MCP/SDK: task
  bc41e269129f42a3a0cfd498a2030f21, first candidate passed 9 tests in 31.13s,
  1 model request / 6912 total tokens, REVIEW_PENDING, zero acceptance.
- Read-only fresh reviewer found no P1/P2 issues; browser refresh restored the
  candidate and round selection without any new model requests.

Ruling: do not force the real model to fail to manufacture multi-round live
performance. The deterministic model HTTP test covers the two-round branch;
actual model result is reported as one round.
