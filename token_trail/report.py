from datetime import datetime

def markdown(ledger,s):
    t=s['totals'];c=s['coverage'];o=s['observed'];fmt=lambda n:f'{n:,}';pct=lambda a,b:f'{100*a/max(1,b):.1f}%'
    out=['# Token Trail — usage diagnosis','',f'Generated {datetime.fromtimestamp(s["as_of"]).astimezone().isoformat(timespec="seconds")}. Window: '+(f'last {s["hours"]} hours' if s['hours'] is not None else 'all indexed history')+'.','',
         f'Provider-reported volume is **{fmt(t["total"])} tokens** across **{fmt(t["requests"])} usage records**. **{pct(t["cache_read"],t["input"])} of input came from cache**. These are token counters, not an invoice or a waste estimate.','',
         '| Provider | Input | Cache reads | Cache writes | Output | Total |','|---|---:|---:|---:|---:|---:|']
    for r in s['providers']:out.append('| '+r['name']+' | '+' | '.join(fmt(r[k]) for k in ('input','cache_read','cache_write','output','total'))+' |')
    out+=['','## Concentration and delegation','',f'Linked children account for {fmt(c["child_tokens"])} tokens ({pct(c["child_tokens"],t["total"])}). There are {c["human_roots"]} explicitly human roots, {c["likely_human_roots"]} likely-human roots, and {c["unresolved_roots"]} roots whose human origin is unconfirmed.',
          '', '| Root conversation | Tokens | Linked children | Child share |','|---|---:|---:|---:|']
    for r in s['roots'][:12]:out.append(f'| {r["title"].replace("|","/")} | {fmt(r["total"])} | {r["child_count"]} | {pct(r["child_tokens"],r["total"])} |')
    out+=['','## Observable optimization opportunities','']
    for i in s['insights']:out+=[f'### {i["title"]} ({i["kind"]})','',i['evidence'],i['action'],'']
    out+=['## Topic allocation','','| Topic | Tokens | Share |','|---|---:|---:|']
    for r in s['topics']:out.append(f'| {r["name"]} | {fmt(r["total"])} | {pct(r["total"],t["total"])} |')
    out+=['','## Tool-result context','','Visible text size uses characters ÷ 4. Tool-result text is not the tool’s full causal token cost.','', '| Tool | Calls | Error signals | Result text ≈ tokens |','|---|---:|---:|---:|']
    for r in s['tools'][:12]:out.append(f'| {r["name"]} | {r["calls"]:,} | {r["failures"]:,} | {r["result_tokens"]:,} |')
    out+=['','## Quality-preserving policy','',
          '1. Read only the relevant section; save raw large results to an artifact and return the evidence needed for the next decision.',
          '2. Track which resources were already read in the current context epoch. Reuse them unless the file changed, the question changed, or compaction removed essential details.',
          '3. Delegate a bounded, independent task with a clear acceptance criterion. Reuse the same child for follow-ups. Do not launch a model merely to poll, grep, parse JSON, or format a table.',
          '4. Keep decisive research, security, architecture, and final validation with a capable model. Change model routing only after quality checks on representative tasks.',
          '5. After two failures with the same cause, diagnose before repeating. Do not skip validation or suppress failures to improve the dashboard.',
          '6. Summarize at a milestone when old context is no longer useful. Preserve the objective, constraints, decisions, evidence links, and unresolved risks.',
          '', '## Measurement limits','',
          f'{c["warning_sessions"]} indexed sessions have adapter warnings. {c["deduplicated_records"]} duplicate usage records were removed across files. {c["cycles"]} lineage cycles remain.',
          'Images are counted as occurrences; exact image tokens and whether each later request reused them are unknown. The tool text estimates omit base64. Hidden instructions and schemas, remote logs, missing/deleted history, browser-only chats, and provider-side charges may be absent. Old cumulative usage deltas can cover more than one request. Cached reuse is often useful; no percentage saving is proven by these observations.',
          '', 'Sources: [Claude cache accounting](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [OpenAI caching](https://developers.openai.com/api/docs/guides/prompt-caching).', '']
    return '\n'.join(out)
