---
name: pydantic-house-rules
description: Use when writing or reviewing any Python data shape (model, DTO, settings, workflow payload, internal state or value object), alongside the vendored pydantic skill. House precedence: Pydantic v2 models everywhere, no dataclasses, UUIDv7 ids, Temporal payloads through the Pydantic data converter.
license: MIT
---

# Pydantic house rules

The vendored `pydantic` skill is the mechanics reference and stays authoritative on
constraints, validators, type coercion, forward annotations and discriminated unions. This
skill exists for one reason: the house disagrees with its advice on where models belong, and
that disagreement is resolved here rather than by editing a vendored file.

Written against Pydantic v2 (`docs.pydantic.dev/latest`; the current release on PyPI was
2.13.5 when these pages were fetched).

Sources (fetched 2026-09-10, curl, all HTTP 200):
- https://docs.pydantic.dev/latest/concepts/models/ - "Models | Pydantic Docs"
- https://docs.pydantic.dev/latest/concepts/dataclasses/ - "Dataclasses | Pydantic Docs"
- https://docs.pydantic.dev/latest/concepts/serialization/ - "Serialization | Pydantic Docs"
- https://docs.pydantic.dev/latest/api/types/ - "Pydantic Types | Pydantic Docs"

In-repo sources: `skills/python/pydantic/SKILL.md` (the vendored skill, pin `9e9390ee`) and
`skills/temporal/temporal-developer/references/python/data-handling.md` (the vendored
Temporal SDK reference, section "Pydantic Integration").

## What this overrides

`skills/python/pydantic/SKILL.md` lines 8 to 10 say:

> "In a nutshell, Pydantic is dataclasses with runtime validation. It leverages type hints to understand how validation (and serialization) should be performed. It is mostly useful when dealing with external untrusted data, for example when defining an HTTP API."

That paragraph stands, with one correction: "mostly useful" understates it here. Untrusted
external data is the floor, not the ceiling.

Lines 12 to 15 say:

> "It is generally *not* recommended to use Pydantic to define classes that are instantiated within the user code. By doing so, you will lose flexibility (e.g. can't use types not supported by Pydantic, harder to perform post init changes). It is usually better to use vanilla classes (or standard library dataclasses) in this case, as a static type checker will already catch type mismatches."

**That paragraph does not apply here.** The house rule is the opposite: internally
instantiated classes are `BaseModel` subclasses too. Those are the only two passages in the
vendored file that mention dataclasses or vanilla classes.

Precedence, spec 4.5 (`docs/superpowers/specs/2026-08-31-graph-engineering-plugin-design.md`):
**house > vault-generated > community.** The vendored skill is community, so on this one
point it loses. Everything it says that this skill does not contradict is still binding, and
the vendored file is never edited to express the override.

The reason the house takes the other side: one validation and serialization model across
settings, contracts, HTTP boundaries and workflow payloads costs less than two. Static type
checking catches mismatches at the call sites it can see; it does not catch the payload that
crossed a queue, a workflow history replay or a config file.

## When to apply

- Any Python file that declares a data shape: request and response models, service
  contracts, settings, workflow and activity payloads, internal state, value objects.
- Reviewing a diff that adds `@dataclass`, `TypedDict`, `NamedTuple` or a bare `dict` as a
  domain type.
- Wiring a Temporal client, worker or codec.
- Not for: plain functions, protocols and ABCs with no data fields, or third-party types you
  do not own. Those are unaffected.

## Rules

1. **Every data shape is a `BaseModel` subclass, including ones only your own code
   instantiates.** Model methods are the reason: `model_validate`, `model_dump`,
   `model_dump_json`, `model_json_schema` and `model_copy` come with the base class and have
   no stdlib equivalent. https://docs.pydantic.dev/latest/concepts/models/#model-methods-and-properties
2. **Value objects and anything shared across a boundary set
   `model_config = ConfigDict(frozen=True)`.** Assigning to a field of a frozen model raises
   a `ValidationError`; note the docs caution that Python does not enforce immutability, so
   this is a guard, not a proof. https://docs.pydantic.dev/latest/concepts/models/#faux-immutability
3. **Validate at the boundary with `model_validate`, or `model_validate_json` when the input
   is already JSON bytes or text.** The docs call the JSON path generally faster than parsing
   to a dict first. Never construct a model from untrusted input with `__init__` plus manual
   checks. https://docs.pydantic.dev/latest/concepts/models/#validating-data
4. **Leave on the way out with `model_dump` (Python mode) or `model_dump_json` (JSON mode).**
   Python mode output may still contain values that are not JSON serializable, so anything
   crossing the wire uses the JSON mode.
   https://docs.pydantic.dev/latest/concepts/serialization/#serializing-data
5. **`pydantic.dataclasses` is not the compromise.** The docs are explicit that Pydantic
   dataclasses are not a replacement for Pydantic models, and that the validate, dump and
   JSON Schema methods are absent, so every call site has to wrap the type in a `TypeAdapter`
   to get them back. That is the model API with extra steps.
   https://docs.pydantic.dev/latest/concepts/dataclasses/
6. **Identifiers are UUIDv7, typed as `UUID7`** (`from pydantic import UUID7`), which the API
   reference defines as `Annotated[UUID, UuidVersion(7)]` and documents as a UUID that must
   be version 7. A `str` id field validates nothing; a bare `uuid.UUID` field accepts any
   version. https://docs.pydantic.dev/latest/api/types/#pydantic.types.UUID7
7. **Temporal workflow and activity inputs and outputs are `BaseModel` subclasses, and every
   client is constructed with `data_converter=pydantic_data_converter` from
   `temporalio.contrib.pydantic`.** The converter has to be passed on the client, the worker
   and the codec server that share a history, or a replay decodes payloads the workflow code
   cannot read. `skills/temporal/temporal-developer/references/python/data-handling.md`,
   "Pydantic Integration".
8. **Reading from an ORM row or another attribute-bearing object is a model concern, not a
   reason to introduce a plain class.** Enable `from_attributes` in the model config, or pass
   `from_attributes=True` to `model_validate`.
   https://docs.pydantic.dev/latest/concepts/models/#arbitrary-class-instances
9. **Where a field must not be silently coerced, say so.** Pydantic casts input to the
   declared type by design and the docs note this can lose information (`a: int` accepts
   `3.000`); strict mode turns that off for the fields that cannot afford it.
   https://docs.pydantic.dev/latest/concepts/models/#data-conversion
10. **Mechanics are inherited, not restated.** Field constraints and metadata, field and
    model validators, collections and unions, forward annotations, model subclasses and
    discriminated unions: read `skills/python/pydantic/SKILL.md`. This skill deliberately
    does not duplicate them, so there is one place for them to be right.

### If a third-party API operates on your instance as a stdlib dataclass

If a library calls `dataclasses.replace()` or `dataclasses.fields()` on an object you hand
it, that object must be a stdlib dataclass and rule 1 cannot reach it. The vendored
`building-pydantic-ai-agents` skill has a live example: capabilities are declared with
`@dataclass` so that `for_run()` can return `replace(self)`
(`references/CAPABILITIES-AND-HOOKS.md`). In that case the dataclass holds wiring only, which
is clients, per-run counters and configuration primitives. Any domain data it carries is a
`BaseModel` field on it, and the dataclass never crosses a serialization boundary.

## Anti-patterns

- `@dataclass` or `from dataclasses import dataclass` on a domain, contract, settings or
  state type. Fails as soon as the type meets untrusted input or a wire: there is no
  `model_validate` to call, so validation gets hand-rolled at each call site and drifts.
- `TypedDict` for domain state. It is erased at runtime, so a wrong shape reaching it is a
  `KeyError` deep in business logic instead of a `ValidationError` at the boundary.
- A `dict` payload across a workflow, queue or HTTP boundary. Nothing pins the keys, so a
  producer-side rename ships and the consumer fails on replay, which is when the history is
  already written and the fix is a new workflow version.
- Reaching for `pydantic.dataclasses` to satisfy both this skill and the vendored one. It
  satisfies neither: the model methods are gone and every call site grows a `TypeAdapter`.
- `id: str` on a model. Any string validates, so a truncated or v4 id gets stored and the
  time ordering UUIDv7 exists for is quietly gone.
- A Temporal client built without `pydantic_data_converter` while the workflow signatures
  use models. It fails at payload conversion, not at wiring time, so it usually surfaces in
  a worker log rather than a test.

## Verify

```bash
# 1. no stdlib dataclasses in application code. Expect no output.
#    A hit is a finding unless it is the framework adapter case named above.
grep -rn '@dataclass\|from dataclasses' src/

# 2. Pydantic v2 is what is installed. Expect a bound method line, not an ImportError.
uv run python -c 'from pydantic import BaseModel; print(BaseModel.model_validate)'
# <bound method BaseModel.model_validate of <class 'pydantic.main.BaseModel'>>

# 3. the UUIDv7 annotated type resolves. Expect the Annotated alias.
uv run python -c 'from pydantic import UUID7; print(UUID7)'
# typing.Annotated[uuid.UUID, UuidVersion(uuid_version=7)]

# 4. every Temporal client passes the converter. Expect the two counts to be equal.
grep -rc 'Client.connect' src/ | awk -F: '{s+=$2} END {print "clients:", s}'
grep -rc 'pydantic_data_converter' src/ | awk -F: '{s+=$2} END {print "converters:", s}'

# 5. no domain TypedDicts. Expect no output.
grep -rn 'TypedDict' src/
```
