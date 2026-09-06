# Measurement contract

## Sources and coverage

Read-only JSONL adapters scan Claude Code project transcripts (including `subagents/`) and Codex rollout transcripts. The scanner retains a derived snapshot of each indexed file in local SQLite. No provider API, credential, browser history, or billing endpoint is needed. Source files are never modified. Missing/deleted sources remain represented by their last cached snapshot; this is retained indexed history, not proof the source still exists.

Observed facts: request usage counters, timestamps, model names, native parent IDs, tool names, tool error flags, explicit exit signals, and visible image occurrences. The program stores derived sizes/hashes and local labels, not raw tool arguments or message bodies. Titles and labels can still contain sensitive information.

## Normalization

- Claude: `input = input_tokens + cache_read_input_tokens + cache_creation_input_tokens`.
- Codex: `input = input_tokens`; `cached_input_tokens` and `cache_write_input_tokens` are subsets.
- Both: `total = input + output`; `reasoning` is a subset of output.
- Claude repeated streaming blocks: group by message ID, use maximum reported usage fields. Global duplicates across files count once.
- Modern Codex: stable `response_id` plus per-response `usage`; the matching cumulative snapshots are excluded.
- Legacy Codex: positive increments of cumulative usage; identical snapshots do not add usage. Counter resets use `last_token_usage` and produce a warning.
- Codex child/fork history: the first metadata record owns the file. Subsequent ancestor metadata cannot change ownership. Original `task_started.started_at` identifies copied older turns even when the transcript wrapper timestamps were rewritten during fork. Their counters establish a baseline but do not accrue child usage. Older children lacking an inherited baseline use `last_token_usage` initially and disclose a warning.

These are provider-reported usage observations, not a billing reconciliation. Missing records and version changes can limit completeness. Where a legacy delta covers multiple requests, one record is not necessarily one inference request.

## Attribution

A request activity label describes the emitted or recently handled tool activity. It does **not** identify the marginal tokens caused by a tool. Input still includes the surrounding context. Batched executor calls can contain multiple tools and skills; the collector lists nested names without inventing an exact split.

Visible text estimates use `ceil(characters / 4)`. This is a rough cross-language proxy, especially inaccurate for code, CJK, and compressed/token-dense data. Do not add these estimates to measured totals. Base64 image bodies are excluded from text estimates. No exact vision-token charge is inferred from an image count.

Identical result hashes are compared within a native session, with a 100 estimated-token minimum. Additional occurrences are review candidates. No saved-token claim follows without knowing whether reuse would preserve the answer and whether the earlier content was still retained. Results with timestamps/wrappers may evade exact matching.

The simulator is a scenario: payload size × number of subsequent requests, assuming retention and no pruning/compaction. It is not a reconstruction of actual image/file replay.

## Lineage confidence

1. User-confirmed corrections and instrumented launch traces.
2. Native parent IDs and Claude subagent paths.
3. A child session ID in a recognized cross-provider launch tool result, with plausible ordering and a unique parent candidate.
4. Unresolved ancestry. Working-directory proximity never creates an edge.

Explicit `origin.kind=human` establishes a human root. Interactive source labels suggest human origin but can be inherited by automation. Four or more long identical initial prompt templates mark likely automation, not a proven parent. A provider's `thread_source=user` on a headless run is not treated as proof a person launched it.

## Time and privacy

Rolling windows use the usage record timestamp. Daily buckets follow the server's local timezone. They are independent of subscription reset windows. Native-session lifetime totals in a tree are labeled separately from filtered usage.

Safe export contains only allowlisted aggregate token fields, provider totals, period length, and linked-child share. Exporting creates a local download. Publishing is a separate user action.

Sources: [Claude prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching). Adapter behavior is additionally tested against local synthetic fixtures and observed log schemas.

The Claude hook appends only `TOKEN_TRAIL_CURRENT` to the documented `CLAUDE_ENV_FILE` so future shell launches carry parentage. See the [Claude hooks reference](https://code.claude.com/docs/en/hooks). No prompts are injected.
