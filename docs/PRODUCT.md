# Product direction: an intent-level token profiler

The first useful promise is: **“Which task burned my tokens, and what can I change without making the answer worse?”** A token total alone is already a crowded category. The distinct feature should be reconstructing one human task across providers and agents, then explaining overhead with defensible evidence.

## Existing tools and the opportunity

[ccusage](https://github.com/ccusage/ccusage) provides local coding-agent usage reports and cache-aware cost accounting across providers. [CodexBar](https://github.com/steipete/CodexBar) emphasizes convenient provider usage/limits in the menu bar. Token Trail should complement these workflows, not claim that usage counters are new. Its proposed differentiation is human-intent lineage, content recurrence, and quality-preserving decisions. This is a positioning hypothesis, not an exhaustive competitive audit or a uniqueness claim. Sources reviewed September 6, 2026.

## The first three minutes

1. One local command; no API key, signup, telemetry, or upload.
2. See the largest conversation tree and its main/child split.
3. Open the tree to find duplicated context, a failure loop, or an unusually expensive delegated task.
4. Make one small workflow improvement and compare the next similar task.
5. Export an aggregate “my AI work footprint” card without chat names or paths.

The release already implements a local dashboard, lineage editing, transparent accounting, synthetic demo, CSV/aggregate JSON exports, and an advisory harness interface. The launch wrapper + identifier-only hooks supply future cross-provider ancestry. Nothing promises a particular saving.

## What would make people share it

Lead with a concrete story: “I asked one question. My agents opened 17 sessions. Here is the actual tree.” A visually compelling private-safe summary should show how the work branched and where context was carried. The useful emotional payoff is understanding, not shame about spending tokens. Default to private; opt in to exporting.

The current version exports safe JSON. A polished shareable PNG/SVG recap, installer packages, shell integration, and share-preview templates are next-release work. Do not describe them as shipped. Brand and package-name availability should be checked before a public release.

## Release plan

**Source preview:** MIT license, zero runtime dependencies, synthetic fixtures, documented uncertainty, one-command startup, no bundled personal data. Recruit five heavy Claude/Codex users to validate that totals reconcile and their session trees match reality.

**Trust release:** versioned adapters, read-only source provenance, migration tests for older transcripts, byte-tail ingestion with rewrite detection, and support for user-supplied provider cost tables. Expand session tracing to native hooks / OpenTelemetry when the providers expose stable identifiers. Show coverage gaps prominently.

**Efficiency release:** repeated resource identity across tool wrappers, retry-cause grouping, context-epoch modeling, and task-level before/after comparisons. Add policy thresholds only after outcome-based evaluations. Avoid blanket “use a cheaper model” prescriptions.

**Distribution:** signed one-click desktop installer, lightweight menu bar status, VS Code entry point, optional ccusage-compatible exports, and a short synthetic walkthrough GIF. Publish only source + synthetic examples. Keep the working private ledger outside Git and package archives.

## What to measure as a product

- Time from install to first useful finding.
- Percentage of roots with verified ancestry; erroneous merges should be close to zero.
- Usage-accounting discrepancies on fixture and real-log reconciliation tests.
- Weekly retention among people who run agents regularly.
- Number of workflow changes that preserve acceptance criteria and reduce token volume/latency.
- Share-export use with explicit consent; never use private-chat uploads as a growth loop.

An open-source tool earns adoption through trust and a fast first insight. Virality cannot be promised. Start with a sharp wedge for Claude Code/Codex power users; “any AI user” becomes plausible only after adding honest adapters for their products, especially browser chats where request usage is often unavailable.


## v0.2 public beta

The first-run payoff is an integrated Overview plus an actionable handoff: show where context and child work accumulate, then copy a rule or download a personalized memory/skill. Keep installation local and deterministic; no API key and no classification bill. Support a single client as a normal case. Ship explicit adapter coverage instead of claiming to observe every AI product.

Public adoption can start with a fictional demo, a screenshot and a two-command clone/run path. The reusable skill should execute this package, not regenerate a dashboard. Community contributions should begin with anonymized adapter fixtures and accounting invariants; never request full private transcripts in public issues. Publish product demos and aggregate exports only with explicit user choice.

Success measures: time to first useful report, installation completion, percentage of sessions with known lineage, usefulness of the first proposed edit, and retained task quality. A large reported token saving is not evidence of product value unless the same work still passes its checks.
