# Native call graph SVG

Approved scope: extend the existing graph POST with Ddg,Cg and dot,svg; save the returned Cg SVG as source-bound evidence. No model calls or snapshot mutation.

1. Test current-response artifact retrieval, same-origin restriction, bounded download, query redaction and independent failure.
2. Persist immutable SVG and provenance with source, analysis and original observation digests; verify before reading/exporting.
3. Add session/bound analysis routes and UI links. Preserve original tool statuses and clear links on source changes.
4. Verify Python/Node suites, real sample and upload scans, browser display/download, independent review, documentation and release archive.

Acceptance: links refer only to verified saved bytes; no upstream authorization query in persisted evidence or frontend; old snapshots show unavailable; SVG failure leaves successful DDG intact.

Completed: client, immutable evidence, standalone and bound routes, UI links, regression tests, real sample/upload scan and download checks, independent review, documentation and release packaging. Final automated checks: Python 360 passed / 1 deselected; Node 62 passed. Evidence: docs/demo/callgraph-svg-verification.md.
