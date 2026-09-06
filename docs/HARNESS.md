# A harness that preserves quality

Token Trail measures first. It does not silently change models, rewrite global instructions, force compaction, or terminate agents. The first release provides an advisory CLI, launch tracing, and this reusable policy. Automatic enforcement requires outcome checks; a smaller token count alone is not success.

## Short instruction block for either agent

> Keep decisive reasoning, research judgment, security decisions, architecture, and final review with a capable model. Use deterministic code for counting, parsing, transforming, monitoring, and formatting. Read only the relevant resource sections and reuse unchanged results already in context. Put large raw outputs in artifacts and return concise evidence plus paths. Delegate only a bounded independent task with an acceptance criterion; reuse that child for follow-ups. Trace cross-provider launches to the current root conversation. After two failures with the same cause, diagnose before repeating. Checkpoint at milestones; preserve objectives, constraints, decisions, evidence, and open risks. Do not skip verification or lower quality to improve token metrics.

The user decides whether to add this to personal instructions. It is intentionally not installed globally by the service installer.

## Before a child launch

Write a one-sentence purpose, the deliverable, the evidence needed, and the acceptance criterion. Prefer a narrow context packet over copied full history where supported. A heavy document digest can merit a child to protect the main context; a tiny grep does not. Reuse the existing child when continuing the same task. Independent subproblems justify concurrency; token monitoring itself does not.

Cross-provider calls should use `token-trail run --parent provider:id -- command ...` with the optional SessionStart hooks installed. This records ancestry without modifying the requested model or capturing prompts/output. Unwrapped older launches may remain unlinked.

`token-trail advise --session provider:id` reads the cached local record and returns a small JSON advisory. It flags a 150k+ observed input context or multiple recent tool error signals. It never interrupts a provider's tool execution; thresholds are review heuristics. A healthy session does not require any action.

## Decisions about model routing

| Work | First choice | Acceptance check |
|---|---|---|
| Count tokens, parse logs, join topics, poll status | Deterministic code | Invariants and fixtures |
| Extract a bounded field from structured input | Code; consider a lightweight model only if needed | Schema + spot-checks |
| Summarize a large ambiguous source | Capable child with bounded context | Evidence fidelity |
| Choose an identification strategy, resolve a security issue, approve architecture | Capable lead model | Independent evidence and critical review |
| Final synthesis or decisive tradeoff | Capable lead model | Completeness, correctness, unresolved risks |

## An evaluation protocol before enforcement

Create representative tasks covering research, document work, coding and operations. Freeze input data and expected acceptance criteria. Run baseline and proposed policy with the same capable decision model. Record fresh/cache-write input, cache reads, output, latency, tool failures, human corrections, and blinded answer quality. Keep a change only when acceptance and quality hold. Report savings as a distribution over tasks; do not extrapolate a single favorable run to all usage.

Use conservative review triggers rather than hard quotas: two repeated failures, a growing context full of completed work, repeated unchanged large payloads, or a parent spawning many overlapping children. A justified exception should keep working and record why.
