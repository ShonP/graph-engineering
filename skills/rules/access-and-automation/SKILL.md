---
name: access-and-automation
description: Apply for .github/workflows, infra, scripts calling cloud or vendor CLIs, new tooling that needs a credential, or repetitive manual work. Rules for centralized access (OIDC, groups, no personal keys), the access matrix and onboarding, and pipelines never on a schedule.
---

# Access and automation

Bootstrap snippets: `references/bootstrap.md`. Templates: `templates/access.yaml`, `templates/onboarding.md`.

## 1. Centralized access

No task may depend on one person's laptop login or key. In order of preference:

1. A pipeline identity holds the access: GitHub Actions OIDC federation to the cloud, no stored secret, subject pinned to the default branch ref, workflow dispatched from the default branch.
2. A group-based role a person joins (a security group plus RBAC at the narrowest scope). Onboarding is adding to the group, offboarding is removing.
3. One central secret store with group access (a vault with RBAC), only for secrets no identity federation can replace.

- Prefer token auth over API keys where the vendor supports it (Azure AI Foundry takes Entra bearer tokens: no key at all).
- A secret moves only by stdin or env injection into one process, never argv, logs, chat, agent prompts or the repo in plaintext. A SOPS-encrypted file committed to git stays allowed (`sops-age`).
- A paid API has a vendor-side spend cap, recorded in its matrix row: `paid: true` and `spend_cap` (the doctor rejects a paid row without one).
- Store, signing and infra rows may be `owner_only`.
- GitHub Free private repos have no environments, required reviewers or rulesets: gates there are scope-based (narrow role, default-branch-only subject). Upgrade trigger: the first job that signs or publishes to a store.
- Credential-touching jobs run on ephemeral hosted runners, never a person's machine. Third-party actions are pinned by SHA. Workflow inputs reach scripts through `env`, never interpolated into `run`.

## 2. Access matrix and onboarding, decided at repo start

- Every repo has `docs/ops/access.yaml` (one row per capability: `id`, `what`, `holds`, `role`, `who`, `owner_only`, `check`, `request`, `pipeline`, `status`, plus `paid` and `spend_cap` for a paid API) and `docs/ops/onboarding.md` (day-0 steps for a new person, what they can do, what goes through pipelines, what is owner-only, offboarding).
- A doctor command validates the matrix statically and probes each `check` with `--live`; the profile's `access.doctor` names it.
- New tooling that needs access adds its matrix row in the same PR. A task that needs access with no row is blocked: report `BLOCKED` naming the missing row, never work around it with a personal credential.

## 3. Automation is on demand, never scheduled

- Repeatable manual work becomes a pipeline run by `workflow_dispatch` or by CI/CD triggers (push, PR, release).
- Never automate repeatable work on a timer: no `on: schedule` workflow, no cron job or CronJob that runs a task, no cloud scheduler, no agent routine, unless the owner lifts it for that repo in writing, recorded as `access.schedule_allowed: true` in the profile.
- Exempt: operator-native data-protection schedules, such as a CNPG `ScheduledBackup` (`cloudnativepg`) or certificate renewal run by cert-manager. They are not automation of manual work. A retention-expiry deletion job (`gdpr-erasure-retention`) is not exempt: it runs work, so it waits for the owner's `access.schedule_allowed` lift.

## Review flags

Raise each as Important, Blocking when a secret is exposed:

- A stored cloud key or secret in repo secrets where OIDC is possible.
- A `schedule` trigger, a cron job or CronJob running a task, a cloud scheduler or a scheduled routine (not a CNPG `ScheduledBackup` or cert-manager renewal).
- A plaintext secret in argv, a log line, a prompt or a committed file; an input interpolated into a `run` script.
- An unpinned third-party action in a credential-touching job.
- New access with no `access.yaml` row, or a paid API row with no spend cap.
