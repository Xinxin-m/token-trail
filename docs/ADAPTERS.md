# Bring your own client

A provider filter identifies the **log source/client**, not necessarily the company serving the model. The Model table preserves the model reported by that client. Claude Code used through a compatible endpoint still appears as Claude Code.

| Adapter | Automatic discovery | Coverage |
| --- | --- | --- |
| `claude` | `~/.claude/projects/**/*.jsonl` | Usage, cache splits, tools, skill/file labels, image occurrences, native subagents |
| `codex` | `~/.codex/sessions/**/*.jsonl` | Usage, cache splits, tools, native parents, fork-history deduplication |
| `kimi` | `~/.kimi/sessions/**/wire.jsonl` | Python Kimi CLI per-step usage, compactions, nested subagent lineage |
| `usage-jsonl` | Explicit path required | Other clients through the contract below; measured usage and explicit ancestry |

One provider is sufficient. Absent default directories are not errors. Explicit `sources` replaces discovery; an empty list collects nothing. Imported history already in a database is retained when source configuration changes. Use filters or a separate database to isolate datasets. This is not a deletion mechanism.

Kimi is covered by synthetic regression fixtures matching the official [wire record](https://github.com/MoonshotAI/kimi-cli/blob/main/src/kimi_cli/wire/file.py) and [event types](https://github.com/MoonshotAI/kimi-cli/blob/main/src/kimi_cli/wire/types.py). It has not been validated against this developer's personal Kimi history. Missing model names remain unknown. Human/headless origin cannot be determined from TurnBegin alone. Tool/file/image attribution, native Kimi hooks and the newer TypeScript Kimi Code wire format are not supported. Unsupported usage fields produce warnings rather than invented zero usage.

Browser-only ChatGPT/Claude conversations, provider web dashboards, credentials and remote machines are not auto-collected. Token Trail is not a universal interception proxy. Other providers need an adapter or a local exporter with actual usage counters.

## A portable export contract

Write one JSON object per completed model response, ending every record with a newline:

```json
{
  "schema": "token-trail.usage.v1",
  "provider": "my-client",
  "session_id": "task-1",
  "request_id": "response-1",
  "timestamp": "2026-09-01T12:00:00Z",
  "model": "reported-model-name",
  "title": "Fictional research task",
  "topic": "Research",
  "origin": "human",
  "usage": {
    "fresh": 120,
    "cache_read": 900,
    "cache_write": 80,
    "output": 75,
    "reasoning": 20
  }
}
```

Input is 1,100; total is 1,175. Reasoning is already inside output. The four required usage fields are mutually exclusive nonnegative integers. Supply zero only when known. `reasoning` is optional. No prompt bodies or tool arguments are required.

`provider`, `session_id`, `request_id`, `timestamp`, `usage` and `schema` are required. Other fields are optional. Timestamp accepts ISO 8601 or Unix **seconds**. A `request_id` must be stable and unique across that provider, including sessions and machines. Identical rows are deduplicated; conflicting duplicates within a file are warned and rejected. Multiple files describing the same response must use the same ID and counters. Do not import native responses again using a second namespace.

A child supplies `parent_id: "my-client:task-1"` and its own session ID. Cross-provider parents use the same `provider:session-id` format. Omitting a parent does not prove a person started the session. Supply `origin: "human"` only when your instrumentation establishes it.

Convert cumulative snapshots to deltas in your exporter before writing these records. For inclusive input counters, subtract known cache reads/writes to get `fresh`. Never infer absent usage from character counts. If a client does not expose counters, report that gap.

```sh
python3 -m token_trail init --output /private/path/config.json \
  --source usage-jsonl=/absolute/path/to/exports
python3 -m token_trail --config /private/path/config.json serve
```

Repeat `--source adapter=path` for several sources. A source may be a single file or a directory. Discovery never opens credential files.

## Add a native adapter

Implement a read-only parser returning normalized bundles, register the source in `adapters.sources`, and add fixtures for cache accounting, streaming duplicates, missing fields, partial trailing lines and ancestry. Keep unsupported fields explicitly unknown. The dashboard's provider selectors and histograms adapt without a new page.
