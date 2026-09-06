---
name: token-trail
description: Inspect local AI token usage, cache reuse, repeated skill/file reads and child-session overhead. Run the existing Token Trail dashboard and generate an actionable memory or skill handoff without uploading chats or spending model tokens on raw-log analysis. Use when asked to monitor tokens, diagnose context growth or optimize a Claude, Codex, Kimi or supported imported workflow.
---

# Token Trail

Use the packaged dashboard and deterministic collector. Do not rebuild the UI, read whole transcripts into context, or call a model to classify every chat.

Run commands through `python scripts/trail.py` **relative to this skill directory**. The installed runner selects the correct Python environment. In a source checkout, use `python3 -m token_trail` from the repository root instead.

1. Run `doctor`. Inspect detected sources and existing configuration; absent providers are normal. Reuse the user's running dashboard/configuration if one exists.
2. Run `scan` once, then `report --hours 168` or `coach --hours 168`. Add `--config /absolute/config.json` **before** the subcommand for a custom ledger. Read the small generated report, not source implementations.
3. For the dashboard, run `serve` using an available background-process facility and open the printed loopback URL. Reuse the existing server on that URL instead of spawning another. The app polls files itself; never schedule repeated model calls to monitor it.
4. Give three prioritized changes tied to measured evidence. `coach --format memory` and `coach --format skill` generate reviewable handoffs; redirect to a new private file. The Opportunities page also provides copy buttons and downloads. Inspect existing owned instructions before applying patches; preserve their critical requirements and back them up. Do not auto-install generated advice into always-loaded memory.
5. For new providers or missing usage, read only `references/providers.md`. Report unknown coverage; never invent usage from text lengths or a provider's subscription limits.

Cached input is reused prefix computation, not automatically waste. Each model request can carry active history; stored history may have been compacted or pruned. Preserve stable useful context; remove obsolete material at milestones. Keep capable models for decisive work and final review. Reuse bounded child sessions for follow-ups; do not fan out merely to analyze these logs.

Never alter source transcripts, credentials, client model selection or existing hooks to perform a diagnosis. Share only the dashboard's allowlisted aggregate export; personal reports contain paths and chat labels. Do not commit them.
