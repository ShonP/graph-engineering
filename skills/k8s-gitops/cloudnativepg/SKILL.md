---
name: cloudnativepg
description: Use when writing or reviewing any postgresql.cnpg.io resource - Cluster, Database, DatabaseRole, Pooler, ScheduledBackup - or an Argo CD health check that gates on one. Covers superuser posture, backups through the Barman Cloud plugin, poolers per consumer, and the Database-before-DatabaseRole race that crash-loops consumers.
license: MIT
---

# CloudNativePG

Written for CloudNativePG **1.30.0**. Version confirmed from the running operator's image tag,
not from the chart: the operator Deployment in `cnpg-system` reports
`ghcr.io/cloudnative-pg/cloudnative-pg:1.30.0`, while the `cloudnative-pg` chart pinned in the
same repo (0.29.0) declares `appVersion: 1.29.1`. **The image wins.** Confirm on any cluster with
`kubectl get deploy -n <operator-ns> -o jsonpath='{.items[*].spec.template.spec.containers[0].image}'`.

`cloudnative-pg.io/documentation/current/*` is a meta-refresh to the development docs, so every
citation below uses the versioned `/docs/1.30/` path, which showed a `Version: 1.30` banner.

Sources (fetched 2026-09-10, CNPG 1.30.0):
- https://cloudnative-pg.io/docs/1.30/ - "CloudNativePG"
- https://cloudnative-pg.io/docs/1.30/bootstrap - "Bootstrap | CloudNativePG"
- https://cloudnative-pg.io/docs/1.30/storage - "Storage | CloudNativePG"
- https://cloudnative-pg.io/docs/1.30/security - "Security | CloudNativePG"
- https://cloudnative-pg.io/docs/1.30/backup - "Backup | CloudNativePG"
- https://cloudnative-pg.io/docs/1.30/connection_pooling - "Connection Pooling | CloudNativePG"
- https://cloudnative-pg.io/docs/1.30/declarative_database_management - "PostgreSQL Database management | CloudNativePG"
- https://cloudnative-pg.io/docs/1.30/declarative_role_management - "PostgreSQL Role management | CloudNativePG"
- https://cloudnative-pg.io/docs/1.30/kubectl-plugin - "Kubectl Plugin | CloudNativePG"
- https://cloudnative-pg.io/docs/1.30/cloudnative-pg.v1 - "API Reference | CloudNativePG"
- https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/ - "Resource Health - Argo CD - Declarative GitOps CD for Kubernetes"

## When to apply

- Any `postgresql.cnpg.io` resource: `Cluster`, `Database`, `DatabaseRole`, `Pooler`, `Backup`,
  `ScheduledBackup`, and the `ObjectStore` the Barman Cloud plugin adds.
- An Argo CD health customization for `Cluster`, `Database` or `DatabaseRole`, or a sync wave
  whose ordering depends on one.
- Wiring an application to a CNPG database: credentials, TLS, pooler, `pg_hba`.

## Rules

### Cluster essentials

- A `Cluster` is one primary plus optional replicas in one namespace; failover and switchover are
  the operator's job, and applications connect through the operator-managed `-rw`, `-ro` and `-r`
  services rather than to a pod. https://cloudnative-pg.io/docs/1.30/
- Set `spec.storage.size` and `storageClass` explicitly, and give WAL its own volume with
  `spec.walStorage` on anything that matters. Note the one-way door: **removing `walStorage` is
  not supported** once added. https://cloudnative-pg.io/docs/1.30/storage
- Leave `enableSuperuserAccess` at its default `false`. The operator sets it false for a
  security-by-default posture: changes go through the `Cluster` spec declaratively, and the
  database owner is the account developers get. Turning it on materialises a `postgres` password
  Secret and a `.pgpass`. https://cloudnative-pg.io/docs/1.30/security
- Toggling it off on a running cluster is supported and it does clean up: the operator ignores the
  Secret, removes the one it generated, and sets the `postgres` password to NULL.
  https://cloudnative-pg.io/docs/1.30/security
- If you supply your own bootstrap credentials, the Secret must be `kubernetes.io/basic-auth` and
  its `username` must match the owner (application Secret) or be `postgres` (superuser Secret);
  otherwise let the operator generate them. https://cloudnative-pg.io/docs/1.30/bootstrap
- The application user is not used by the operator: the operator reconciles the cluster as the
  superuser regardless, which is why an app credential problem never shows up as an operator
  problem. https://cloudnative-pg.io/docs/1.30/bootstrap

### Declarative Database and DatabaseRole

- A `Database` needs `metadata.name`, `spec.name`, `spec.owner` and `spec.cluster.name`.
  `spec.cluster` is immutable: to move a database to another Cluster you create a new resource.
  https://cloudnative-pg.io/docs/1.30/declarative_database_management
- A reconciled `Database` sets `status.applied: true` and `status.observedGeneration` equal to
  `metadata.generation`; on failure `status.applied` is `false` and `status.message` carries the
  error. That pair is the only honest readiness signal the CRD offers.
  https://cloudnative-pg.io/docs/1.30/declarative_database_management
- **CNPG does not order `Database` after the `DatabaseRole` that owns it, and the docs never
  claim it does.** Both pages describe independent reconciliation with no cross-resource
  dependency, and neither states any ordering guarantee. Measured instead, rung 1, on a live
  1.30 cluster: the instance manager ran `CREATE DATABASE "<db>" OWNER "<role>"` for three
  databases and all three failed with `role "<role>" does not exist`; consumers then crash-looped
  or retried in-process until both resources landed. It is self-healing, but it is not ordered.
  https://cloudnative-pg.io/docs/1.30/declarative_database_management and
  https://cloudnative-pg.io/docs/1.30/declarative_role_management
- Consequence for the manifest author: **a consumer of a declaratively managed database must be
  gated on both `Database` and `DatabaseRole` being applied**, not on the `Cluster` being
  healthy, and the consumer's own startup must tolerate a database that briefly does not exist.
  Do not detect this by restart count: one consumer exits and restarts, another retries in
  process and restarts zero times. The instance manager log line is the reliable detector.
  https://cloudnative-pg.io/docs/1.30/declarative_database_management
- `DatabaseRole` is the recommended shape over the inline `managed.roles` stanza for GitOps, but
  when the same role name appears in both, **the `Cluster` spec always wins**: the `DatabaseRole`
  is not reconciled and reports the conflict with `applied: false` and
  `database role is already managed by the CNPG cluster`.
  https://cloudnative-pg.io/docs/1.30/declarative_role_management
- A `DatabaseRole` is applied when its spec or its password Secret changes; a manual `ALTER ROLE`
  is not detected or reverted. Inline `managed.roles` are reconciled against the catalog
  periodically. Pick per role which drift behaviour you want.
  https://cloudnative-pg.io/docs/1.30/declarative_role_management
- A `DatabaseRole`, the `Cluster` it references and its `passwordSecret` must all live in the same
  namespace. https://cloudnative-pg.io/docs/1.30/declarative_role_management
- Creating a `DatabaseRole` for a role that already exists **adopts and rewrites it**: omitted
  attributes are forced back to defaults, memberships not in `inRoles` are revoked,
  `connectionLimit` resets to -1, `validUntil` becomes infinity. Read the live role before
  adopting. https://cloudnative-pg.io/docs/1.30/declarative_role_management
- Reclaim policies are the deletion contract and default to the safe side:
  `databaseReclaimPolicy` and `databaseRoleReclaimPolicy` both default to `retain`. Choose
  `delete` only where the data is genuinely ephemeral, and know that `DROP ROLE` fails while the
  role owns objects, leaving the resource `Terminating`.
  https://cloudnative-pg.io/docs/1.30/declarative_database_management and
  https://cloudnative-pg.io/docs/1.30/declarative_role_management
- Certificate roles over password roles where you can: `clientCertificate` issues a
  `<databaserole-name>-client-cert` Secret signed by **the cluster's own client CA**, with nothing
  to rotate by hand. Two constraints follow: `login: true` is required and validated, and the CA
  is that cluster's, in that namespace, not a cluster-wide issuer, so a consumer in another
  namespace cannot verify against it without you copying the CA there.
  https://cloudnative-pg.io/docs/1.30/declarative_role_management
- The operator issues the certificate but **does not touch `pg_hba.conf`**. Add the
  `hostssl <db> <role> all cert` rule to `spec.postgresql.pg_hba` yourself or the role cannot
  authenticate. https://cloudnative-pg.io/docs/1.30/declarative_role_management
- Client certificates are 90 days by default and renew inside 7 days of expiry, both operator-wide
  (`CERTIFICATE_DURATION`, `EXPIRING_CHECK_THRESHOLD`), not per role. Do not design a per-role
  rotation policy the operator cannot express.
  https://cloudnative-pg.io/docs/1.30/declarative_role_management

### Argo CD health for CNPG resources

- Argo CD has no built-in health for `postgresql.cnpg.io` kinds, so an Application containing a
  `Cluster` or a `Database` reports on the pods and PVCs alone unless you add a Lua check. A sync
  wave drawn across an ungated CNPG resource orders nothing.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- Gate `Database` on `status.applied == true`, with a nil-status guard: a freshly created
  `Database` has no `status` key, which must read as `Progressing`, not as a Lua abort.
  https://cloudnative-pg.io/docs/1.30/declarative_database_management and
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- Before writing one of these, check whether the repository already has it. A correct
  `Database` gate is a dozen lines and a second, subtly different copy is worse than none.
  https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/
- A password-backed `DatabaseRole` is only usable once the instance manager has applied the
  password, and the `PasswordSecretChange` condition is how you can see that: its `message`
  carries the `resourceVersion` of the password Secret the operator last observed. Comparing it
  to what the instance manager recorded is a workable gate, **but the docs call this condition an
  internal signal for the instance manager**, not an API contract. Anything built on it is
  re-verified on every CNPG bump, and the failure mode if the operator stops writing that value
  is a role stuck Progressing forever, which deadlocks whatever wave waits on it.
  https://cloudnative-pg.io/docs/1.30/declarative_role_management
- `status.applied` on a `DatabaseRole` is left **unset (nil)** on a replica cluster, which is
  neither true nor false. A gate that tests `applied == false` for Degraded must not catch that
  case. https://cloudnative-pg.io/docs/1.30/declarative_role_management

### Backups

- Native `barmanObjectStore` is deprecated from 1.26 in favour of the CNPG-I **Barman Cloud
  plugin**, though it remains the default `method` for backward compatibility. New clusters use
  the plugin and set `method: plugin` explicitly rather than inheriting the deprecated default.
  https://cloudnative-pg.io/docs/1.30/backup
- WAL archive plus base backup, always both. The docs are blunt: a WAL archive alone is useless,
  you cannot restore without a physical base backup. Configure the archive in production; it is
  what buys RPO under 5 minutes. https://cloudnative-pg.io/docs/1.30/backup
- `ScheduledBackup.spec.schedule` is a **six-field** cron with a leading seconds field, not a Unix
  crontab. `0 0 0 * * *` is daily midnight; the same string read as a Unix crontab is wrong.
  https://cloudnative-pg.io/docs/1.30/backup
- `ScheduledBackup.spec.cluster` is immutable, same as `Database` and `Pooler`: point it at a new
  cluster by creating a new resource. https://cloudnative-pg.io/docs/1.30/backup
- Backup frequency sets your RTO, and an untested backup is not a backup: restore regularly and
  measure how long a full recovery takes. https://cloudnative-pg.io/docs/1.30/backup

### Poolers

- A `Pooler` is a PgBouncer Deployment in front of one service of one `Cluster`, in the same
  namespace, and its name must differ from every cluster name in that namespace.
  https://cloudnative-pg.io/docs/1.30/connection_pooling
- **Poolers are not managed automatically and their lifecycle is independent of the Cluster's.**
  Deleting a cluster leaves its poolers; you can run several, and the docs explicitly suggest one
  per application. Give each consumer its own `Pooler` so one consumer's `default_pool_size` or
  `poolMode` cannot starve another. https://cloudnative-pg.io/docs/1.30/connection_pooling
- Choose `poolMode` per consumer, not globally: `session` is the safe default, and transaction
  mode is the one that actually multiplexes but forbids session state (prepared statements,
  advisory locks, `SET`). https://cloudnative-pg.io/docs/1.30/connection_pooling
- `spec.cluster` on a `Pooler` is immutable.
  https://cloudnative-pg.io/docs/1.30/connection_pooling
- Leave the certificate integration alone unless you must change it: by default the pooler reuses
  the cluster's certificates and its TLS client cert to run `auth_query`. Supplying your own
  Secrets **disables the built-in integration** and hands you the whole authentication problem.
  https://cloudnative-pg.io/docs/1.30/connection_pooling
- PgBouncer image 1.19 or higher is required, for `auth_dbname`.
  https://cloudnative-pg.io/docs/1.30/connection_pooling

## Anti-patterns

- **A plain-text superuser or owner password in git, or `enableSuperuserAccess: true` with no
  stated reason.** The default is false precisely so no `postgres` password exists to leak.
  https://cloudnative-pg.io/docs/1.30/security
- **A `Database` whose owning `DatabaseRole` may land after it, with a consumer that treats the
  database as present at startup.** There is no ordering; `CREATE DATABASE ... OWNER` fails and
  the consumer crash-loops (measured, see the rule above).
  https://cloudnative-pg.io/docs/1.30/declarative_database_management
- **Using restart count to detect that race.** One consumer exits and restarts, another retries
  in process at zero restarts. Read the instance manager log.
  https://cloudnative-pg.io/docs/1.30/declarative_database_management
- **One `Pooler` shared by every consumer.** Independent lifecycle, one pool size, one pool mode:
  the first consumer that needs transaction mode or a bigger pool changes it for all of them.
  https://cloudnative-pg.io/docs/1.30/connection_pooling
- **Assuming the client CA behind `clientCertificate` is a cluster-wide issuer.** It is that
  Cluster's client CA, and the `DatabaseRole`, Cluster and Secret are all namespace-scoped.
  https://cloudnative-pg.io/docs/1.30/declarative_role_management
- **Issuing a client certificate and forgetting `pg_hba`.** The operator does not edit
  `pg_hba.conf`; without a `hostssl ... cert` line the role still cannot connect.
  https://cloudnative-pg.io/docs/1.30/declarative_role_management
- **Pointing a `DatabaseRole` at an existing role to tidy it up, or to drop it.** Adoption
  rewrites every omitted attribute back to its default first.
  https://cloudnative-pg.io/docs/1.30/declarative_role_management
- **A five-field cron in a `ScheduledBackup`.** The field you think is minutes is seconds.
  https://cloudnative-pg.io/docs/1.30/backup
- **A sync wave that depends on a CNPG resource with no Argo health check.** Nothing is waited
  for. https://argo-cd.readthedocs.io/en/release-3.5/operator-manual/health/

## Verify

```bash
# 0. Which operator version are the docs you are reading supposed to match?
kubectl get deploy -n <operator-ns> \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.template.spec.containers[0].image}{"\n"}{end}'
# expect: ghcr.io/cloudnative-pg/cloudnative-pg:<the version you cited>

# 1. Cluster overview: instances, roles, continuous backup, replication.
kubectl cnpg status <cluster> -n <ns>
# expect: Status: Cluster in healthy state
kubectl get cluster <cluster> -n <ns> -o jsonpath='{.status.phase}'
# expect: Cluster in healthy state

# 2. Every declarative Database reconciled.
kubectl get database -n <ns> \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.applied}{"\t"}{.status.message}{"\n"}{end}'
# expect: applied=true on every row, no message

# 3. Every DatabaseRole reconciled, and the password the instance manager actually applied
#    matching the Secret the operator last saw (re-check this on every CNPG bump: the docs call
#    PasswordSecretChange an internal signal, not an API contract).
kubectl get databaserole -n <ns> \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.applied}{"\t"}{.status.secretResourceVersion}{"\t"}{.status.conditions[?(@.type=="PasswordSecretChange")].message}{"\n"}{end}'
# expect: applied=true, and the last two columns equal on every password-backed role

# 4. The ordering race, caught in the log rather than in restart counts.
kubectl logs -n <ns> <cluster>-1 -c postgres | grep -i 'does not exist'
# expect: empty on a settled cluster; hits here are the Database-before-DatabaseRole race

# 5. Diagnostic bundle for anything you cannot explain from the above.
kubectl cnpg report cluster <cluster> -n <ns>
```

If the `cnpg` plugin is not installed, `kubectl cnpg` fails with
`unknown command "cnpg" for "kubectl"`; steps 1 and 5 need it, the rest are plain kubectl.
