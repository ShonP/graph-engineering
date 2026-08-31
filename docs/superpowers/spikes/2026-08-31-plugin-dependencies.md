# Spike: can plugin.json declare dependencies on other plugins?

Date: 2026-08-31
Status: **ANSWERED - yes, natively supported**

## Question

The spec chose "depend on community skills, do not vendor them". Can
`plugin.json` declare those dependencies, or must `/graph-doctor` plus the
README carry the whole contract?

## What was run

1. Enumerated every installed manifest on this machine:

```bash
find ~/.claude/plugins/cache -name plugin.json -maxdepth 5
```

15 manifests across 8 plugins. None declares dependencies. This establishes a
baseline only: no installed plugin happens to use the field. It does not show
the field is unavailable.

2. Fetched `https://code.claude.com/schemas/plugin.json` - 302 redirect to a
marketing page. There is no schema served at that URL, so the `$schema` value
in existing marketplace files does not resolve to anything fetchable.

3. Read the official plugins reference at
`https://code.claude.com/docs/en/plugins-reference`.

## Answer

`plugin.json` supports a `dependencies` array:

```json
{
  "dependencies": [
    "helper-lib",
    { "name": "secrets-vault", "version": "~2.1.0" }
  ]
}
```

Entries are either a bare plugin name string, or an object with `name` and an
optional semver `version` constraint.

The same reference lists more manifest fields than the design assumed:
`displayName`, `metadata`, `defaultEnabled`, `userConfig` (values prompted at
enable time), `channels`, and component-path fields `skills`, `commands`,
`agents`, `workflows`, `hooks`, `mcpServers`, `outputStyles`, `lspServers`.

Note the older reference in the `anthropics/claude-code` repo
(`plugins/plugin-dev/skills/plugin-structure/references/manifest-reference.md`)
documents a narrower field list with no `dependencies`. Where the two disagree,
the plugins-reference doc is the current one.

## Recommendation

1. Declare the adopted community plugins in `dependencies` with semver
   constraints. This is stronger than the spec's fallback: version pinning
   answers the "external maintainers can change agent behavior on update"
   risk that section 4.2 accepted without a mitigation.
2. Keep `/graph-doctor` anyway. `dependencies` states what is required; the
   doctor reports what is actually installed and which graph legs degrade
   without it. They answer different questions.
3. Consider `userConfig` for the board project name, which is per-install
   rather than per-repo.

## Spec impact

Section 4.2 gains the `dependencies` mechanism and drops the "if declaration is
unsupported" fallback. Section 11's question 3 is closed.
