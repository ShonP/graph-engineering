# Measure cost per accepted task

Keep the coordinator's model/effort stable during a task. Route bounded mechanical
implementation to the smaller configured tier; keep independent review and QA.
Load only required skills and use artifact paths for detailed logs. Removing a
review, a real acceptance case or a required framework skill is not a saving.

Aggregate local metadata (no prompts, response text, secrets or absolute session
paths in output):

```sh
python3 scripts/session_usage.py --start 2026-09-27T00:00:00+03:00 \
  --end 2026-09-30T00:00:00+03:00 > usage.json
```

The tool deduplicates repeated streamed message IDs using maximum cumulative
usage. It separates main/worker requests, reports cache-write TTLs and context
sizes, and flags malformed/conflicting records. This is token evidence, not a
bill. Reconcile invoice/request IDs and actual provider rates before reporting
currency savings; do not assume model aliases imply public prices.

Compare equal task classes before/after: accepted cases, completed tasks, review
escapes, failed attempts, wall time, requests, cache reads/writes and total spend.
Use run IDs and exact candidate receipts to avoid counting partial tasks as wins.

## Coordinator-only TTL trial

Claude Code >=2.1.242 supports `promptCacheTtl: "1h"` for the main conversation
and `subagentPromptCacheTtl: "5m"` for other requests. Apply this in the host's
provider settings, not plugin code. A custom gateway must forward cache markers
and the extended TTL header. Confirm `usage.cache_creation.ephemeral_1h_input_tokens`
is nonzero in a bounded provider probe before enabling the trial. If rejected or
unreported, retain current settings and record the missing capability.

Longer TTL writes cost more. A workload with no five-minute gaps can become more
expensive, particularly workers. Keep worker TTL at five minutes; compare actual
main-conversation cache writes and spend over matched completed tasks. Roll back
by removing the two settings (restore previous values if they existed).

Source: [Claude Code prompt caching](https://code.claude.com/docs/en/prompt-caching).
This controls a client request; the provider's returned usage is the evidence.
