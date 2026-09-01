---
name: security-review
description: Review a diff for security defects - injection, authz, secrets, unsafe deserialization, SSRF, path traversal and dependency risk. Use on every code review pass, whatever the stack.
---

# Security review

Cross-cutting, so it runs on every diff. Most diffs have nothing; say so and move
on rather than manufacturing a finding.

## What to look for

**Authorization, not just authentication.** Logged in is not permitted. For each
new endpoint, query or mutation: who may call it, and is that enforced server
side? A check in the UI is not a check. Row-level policy for a new table is part
of the change, not a follow-up.

**Injection.** Interpolated SQL, shell strings built from input, template
injection. Parameterised queries and argument arrays, always.

**Secrets.** Keys, tokens and connection strings in source, fixtures, logs or
error messages. A secret in git history stays there after the delete commit; say
so plainly and treat it as rotation, not removal.

**Untrusted input crossing a boundary.** Deserialization, dynamic imports,
`eval`, path joins from user input (traversal), URLs fetched server side (SSRF).

**Dependencies.** New ones: what do they pull in, and is the version pinned?

**Error and log output.** Stack traces, internal paths, user records or tokens
leaking to a client or a log sink.

## Judgement

Report what this diff introduces. Pre-existing issues go in a note, not the
blocking list, unless the diff makes one materially worse.

Severity is about exploitability and blast radius, not about how alarming the
category sounds. A hardcoded credential in a test fixture for a local demo
service is not the same finding as one in production config, and calling both
blocking teaches people to ignore you.
