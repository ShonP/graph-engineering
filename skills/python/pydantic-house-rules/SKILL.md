---
name: pydantic-house-rules
description: "Use when writing or reviewing any Python data shape (model, DTO, settings, workflow payload, internal state or value object), alongside the vendored pydantic skill. House precedence: Pydantic v2 models everywhere, no dataclasses, UUIDv7 ids, Temporal payloads through the Pydantic data converter."
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
- https://docs.pydantic.dev/latest/concepts/fields/ - "Fields | Pydantic Docs"
- https://docs.pydantic.dev/latest/api/types/ - "Pydantic Types | Pydantic Docs"
- https://docs.python.org/3.14/library/uuid.html - "uuid - UUID objects according to RFC 9562 - Python 3.14.7 documentation"
- https://github.com/aminalaee/uuid-utils - "GitHub - aminalaee/uuid-utils: Fast, drop-in replacement for Python's uuid module, powered by Rust."
- https://github.com/oittaa/uuid6-python - "GitHub - oittaa/uuid6-python: New time-based UUID formats which are suited for use as a database key"

The Python title is recorded with hyphens where the page uses em dashes, which this repo's files
do not carry. The two packages are cited by repository because `pypi.org/project/<name>/` served a
bot challenge that day; PyPI JSON read `uuid-utils` 1.0.0 and `uuid6` 2025.0.1 (Python >=3.10 and
>=3.9).

In-repo sources: `skills/python/pydantic/SKILL.md` (the vendored skill, pin `9e9390ee`) and
`skills/temporal/temporal-developer/references/python/data-handling.md`, "Pydantic Integration".

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

The reason: one validation and serialization model across settings, contracts, HTTP boundaries
and workflow payloads costs less than two. Static type checking catches mismatches at call sites
it can see, not the payload that crossed a queue, a workflow history replay or a config file.

## When to apply

- Any Python file that declares a data shape: request and response models, service contracts,
  settings, workflow and activity payloads, internal state, value objects.
- Reviewing a diff that adds `@dataclass`, `TypedDict`, `NamedTuple` or a bare `dict` as a domain
  type.
- Wiring a Temporal client, worker or codec.
- Not for: plain functions, protocols and ABCs with no data fields, or third-party types you do
  not own.

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
7. **Name the generator, because the annotation does not produce values and the Pydantic docs
   are silent on generation.** `uuid.uuid7()` is stdlib only from Python 3.14 ("Added in
   version 3.14"); below that the stdlib offers no v7 generator at all, and `uuid.uuid4` is
   the thing a hurried hand reaches for.
   https://docs.python.org/3.14/library/uuid.html#uuid.uuid7
   - Python 3.14 and up: `from uuid import uuid7`.
   - Below 3.14: `from uuid_utils.compat import uuid7` (https://github.com/aminalaee/uuid-utils)
     or `from uuid6 import uuid7` (https://github.com/oittaa/uuid6-python). Use the
     `uuid_utils.compat` module, not `uuid_utils` itself: the top-level `uuid7()` returns a
     `uuid_utils.UUID`, which Pydantic rejects with `UUID input should be a string, bytes or
     UUID object`, while `uuid_utils.compat.uuid7()` returns a stdlib `uuid.UUID`.
   - One project module exports `uuid7` behind that version check; models import it from there.
8. **Pydantic does not validate defaults, so a v7 field with a v4 default is silently wrong.**
   The docs say it plainly: "By default, Pydantic will not validate default values." Every
   `UUID7` field carries `validate_default=True` beside its `default_factory`, as does any
   other constrained field with a default.
   https://docs.pydantic.dev/latest/concepts/fields/#validate-default-values
   ```python
   id: UUID7 = Field(default_factory=uuid7, validate_default=True)
   ```
   Without it, `Field(default_factory=uuid.uuid4)` on a `UUID7` field stores a version 4 id
   with no error; with it, construction raises `UUID version 7 expected [type=uuid_version]`.
9. **Temporal workflow and activity inputs and outputs are `BaseModel` subclasses, and every
   client is constructed with `data_converter=pydantic_data_converter` from
   `temporalio.contrib.pydantic`.** The converter has to be passed on the client, the worker
   and the codec server that share a history, or a replay decodes payloads the workflow code
   cannot read. `skills/temporal/temporal-developer/references/python/data-handling.md`,
   "Pydantic Integration".
10. **Reading from an ORM row or another attribute-bearing object is a model concern, not a
   reason to introduce a plain class.** Enable `from_attributes` in the model config, or pass
   `from_attributes=True` to `model_validate`.
   https://docs.pydantic.dev/latest/concepts/models/#arbitrary-class-instances
11. **Where a field must not be silently coerced, say so.** Pydantic casts input to the
   declared type by design and the docs note this can lose information (`a: int` accepts
   `3.000`); strict mode turns that off for the fields that cannot afford it.
   https://docs.pydantic.dev/latest/concepts/models/#data-conversion
12. **Mechanics are inherited, not restated.** Field constraints and metadata, field and
    model validators, collections and unions, forward annotations, model subclasses and
    discriminated unions: read `skills/python/pydantic/SKILL.md`. This skill deliberately
    does not duplicate them, so there is one place for them to be right.

### The framework adapter exception

The only exemption from rule 1. It carries this name here, in the code comment it requires and
in `Verify` check 4, so a grep for the phrase lands on all three.

If a library calls `dataclasses.replace()` or `dataclasses.fields()` on an object you hand
it, that object must be a stdlib dataclass and rule 1 cannot reach it. The vendored
`building-pydantic-ai-agents` skill has a live example: capabilities are declared with
`@dataclass` so that `for_run()` can return `replace(self)`
(`references/CAPABILITIES-AND-HOOKS.md`). In that case the dataclass holds wiring only, which
is clients, per-run counters and configuration primitives. Any domain data it carries is a
`BaseModel` field on it, and the dataclass never crosses a serialization boundary.

An exempt `@dataclass` carries a comment naming the library call that forces it, on the line
above the decorator, so the exemption is checkable in a diff rather than judged by eye:

```python
# framework adapter exception: pydantic_ai calls dataclasses.replace() in for_run()
@dataclass
class RequestCounter(AbstractCapability[Any]): ...
```

A `@dataclass` with no such comment is a finding, whatever its author intended.

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
- `id: UUID7 = Field(default_factory=uuid.uuid4)`. The same failure through the front door:
  defaults skip validation, so the annotation never runs and a v4 id is stored without an
  error. `validate_default=True` plus a v7 factory is what makes the annotation bite.
- A Temporal client built without `pydantic_data_converter` while the workflow signatures
  use models. It fails at payload conversion, not at wiring time, so it usually surfaces in
  a worker log rather than a test.

## Verify

```bash
# 1. Pydantic v2 is what is installed. Expect a bound method line, not an ImportError.
uv run python -c 'from pydantic import BaseModel; print(BaseModel.model_validate)'
# <bound method BaseModel.model_validate of <class 'pydantic.main.BaseModel'>>

# 2. the UUIDv7 annotated type resolves. Expect the Annotated alias.
uv run python -c 'from pydantic import UUID7; print(UUID7)'
# typing.Annotated[uuid.UUID, UuidVersion(uuid_version=7)]

# 3. no domain TypedDicts. Expect no output.
grep -rn 'TypedDict' src/

# 4. no stdlib dataclasses outside the framework adapter exception. Expect no output;
#    a @dataclass whose preceding line carries the comment is skipped, one without is printed.
python3 - src <<'PY'
import pathlib, sys
bad = []
for f in pathlib.Path(sys.argv[1]).rglob('*.py'):
    lines = f.read_text().splitlines()
    for i, line in enumerate(lines):
        if not line.lstrip().startswith('@dataclass'):
            continue
        if 'framework adapter exception:' not in (lines[i - 1] if i else ''):
            bad.append(f'{f}:{i + 1}')
if bad:
    print('@dataclass without the framework adapter exception comment:', *bad, sep='\n  ')
    sys.exit(1)
PY
```

5. Every id default really produces a v7. One assertion per model with an id, in the test
   suite rather than a shell, since it has to construct the model:

```python
def test_id_default_is_v7() -> None:
    assert Order().id.version == 7   # fails loudly on a uuid4 default_factory
```

6. Every Temporal client passes the converter. Counting symbols does not work: a wired file
   mentions `pydantic_data_converter` twice (import plus keyword) against one `Client.connect`,
   so a count comparison false-alarms on correct code and passes when one of two clients omits
   the keyword. Check the call site instead:

```bash
python3 - src <<'PY'
import ast, pathlib, sys
bad = []
for f in pathlib.Path(sys.argv[1]).rglob('*.py'):
    for node in ast.walk(ast.parse(f.read_text())):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if ast.unparse(node.func) != 'Client.connect':
            continue
        kw = next((k.value for k in node.keywords if k.arg == 'data_converter'), None)
        if kw is None or not ast.unparse(kw).endswith('pydantic_data_converter'):
            bad.append(f'{f}:{node.lineno}')
if bad:
    print('Client.connect without data_converter=pydantic_data_converter:', *bad, sep='\n  ')
    sys.exit(1)
print('all Temporal clients pass pydantic_data_converter')
PY
# correct wiring  -> "all Temporal clients pass pydantic_data_converter", exit 0
# one bare client -> "Client.connect without data_converter=...: src/bad/client.py:8", exit 1
```
