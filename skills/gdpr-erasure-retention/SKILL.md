---
name: gdpr-erasure-retention
description: Implement retention limits and the Article 17 right to erasure - automated deletion workflows, cascading deletes across dependent systems, and the backup and archive problem. Use when adding a table or data store, building a delete path, or reviewing whether data actually goes away.
---

# GDPR erasure and retention

Two obligations that code usually forgets in the same place: data must not be
kept longer than needed (Art. 5(1)(e)), and a user can demand it be deleted
(Art. 17).

**The rule worth internalising: a new table needs an answer to "how long, and
what deletes it" before it ships.** A store with no deletion path silently
breaks an erasure guarantee that already exists elsewhere in the system, and
nobody notices until a request arrives.

## Automated deletion

Deletion is triggered by retention expiry or by an erasure request. Both need
the same machinery: a dependency map, cascading deletes that respect
referential integrity, confirmation logging, and an audit trail.

The hard part is never the row itself. It is the copies: search indexes,
caches, analytics warehouses, event logs, exports, and any third party you
sent it to. A delete that clears the primary table and leaves the index is
not an erasure.

Read `references/automated-deletion.md` for the architecture, the three
workflows (scheduled expiry, on-demand erasure, cascading logic) and a
dependency map template.

## Backups and archives

Backups are the standard exception and the standard excuse. Deleting one
record from an immutable backup set is often technically infeasible, and
regulators accept that - but only with conditions.

What is actually required: align backup cycles with the retention schedule so
deleted data ages out; put the data "beyond use" in the interim, meaning it is
not accessed or restored into production; and if you do restore, re-apply the
outstanding deletions as part of the restore procedure.

"It is in a backup" is not an answer on its own. It is an answer plus a
documented restore-and-delete procedure.

Read `references/backups-and-archives.md` for Recital 66, the ICO and EDPB
positions, erasure strategy by backup type, and the beyond-use controls.

## Reviewing

- Does this new store have a stated retention period and something that enforces it?
- Does the delete path reach every copy, including indexes, caches and analytics?
- Is deletion logged in a way that could evidence compliance later?
- Does a restore re-apply outstanding deletions?

## Attribution

The references adapt Agent Skills by mukul975, Apache-2.0.
