# Provider coverage

Native sources: Claude Code `~/.claude/projects/**/*.jsonl`; Codex `~/.codex/sessions/**/*.jsonl`; Python Kimi CLI `~/.kimi/sessions/**/wire.jsonl`. Override roots with a private JSON config. Detection reads log paths, never credentials.

Only one client is needed. Provider filters follow observed data. Here provider means the transcript client/source, while Model identifies the model reported by that source; compatible endpoints can run other models behind a client.

Kimi coverage is per-step usage, compactions and nested `SubagentEvent` lineage. Missing model is `unknown`; human-vs-headless origin remains unresolved. Tool/file/image attribution and the newer TypeScript Kimi Code wire format are not implemented. Older logs without usage cannot be reconstructed. Do not label missing cache counters as zero.

Other clients can export newline-delimited records with schema `token-trail.usage.v1`, one row per completed model response. Required: `provider`, `session_id`, globally stable `request_id` within that provider, ISO or Unix-seconds `timestamp`, and `usage` with **mutually exclusive** `fresh`, `cache_read`, `cache_write`, `output` nonnegative integers. `reasoning` is optional and is a subset of output. Optional: `model`, `title`, `topic`, `origin` (`human`, `agent`, `automation`, `unresolved`) and namespaced `parent_id` (`provider:session-id`). Values must be actual usage counters; never estimate missing totals.

Configure `sources: [{"adapter":"usage-jsonl","path":"/absolute/export-folder"}]`. Do not import the same native responses through two adapters under different IDs. Reject cumulative snapshots unless a producer first converts them into per-response deltas. Normalize inclusive OpenAI-style input by subtracting known cache reads/writes; Claude-style fresh input is already exclusive. See repository `docs/ADAPTERS.md` for a complete example.

Cross-provider lineage needs explicit evidence. `run --parent provider:session -- command ...` propagates parent identity, but the receiving client must emit a supported SessionStart hook or the producer must export `parent_id`. The wrapper alone cannot infer an opaque child ID. Built-in hooks support Claude and Codex; do not claim Kimi hook installation.
