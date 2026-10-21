"""literals: a fact listed under hygiene.literals has one owner; its pattern in any other text file is a
stray copy, reported by path, line and row id only, never the matched text. Owner and allow globs exempt
a path whatever the scope, as do test paths. The pattern is compiled the way risk `re:` keywords are: a
regex that does not compile or matches an empty line is an error, a nested quantifier warns, and lines
over risk.LONG_LINE characters are not searched. Owner globs that match no file are not reported."""

from . import Context, Finding, Row
from .config import Literal
from .scope import read_text
from ..risk import LONG_LINE, REGEX, BadPattern, Row as Keywords, matcher, nested

ID = "literals"
MODES = frozenset({"staged", "base", "tracked", "doctor"})
QUICK = True
SKIP = ("**/fixtures/**", "**/tests/**", "**/test_*", "**/*.test.*")
REGEX_FIX = "write a pattern that compiles as a Python regex and cannot match an empty line"
NESTED_FIX = "rewrite the pattern without a quantified group that holds a quantifier"


def _keywords(item: Literal) -> Keywords | None:
    try:
        return Keywords(item.id, (), (REGEX + item.pattern,))
    except BadPattern:
        return None


def _broken(item: Literal) -> Row:
    return ("error", "hygiene-literal-regex",
            f"hygiene.literals row {item.id}: pattern is not a valid regex or matches an empty line", REGEX_FIX)


def _stray(item: Literal, path: str, number: int) -> Finding:
    owners = ", ".join(item.owner)
    return Finding("error", "literal-stray", f"{path}:{number} repeats literal {item.id}, owned by {owners}",
                   f"read the value from its owner ({owners}), or add the path to the row's allow globs",
                   path, number)


def _scan(ctx: Context, item: Literal, keywords: Keywords) -> list[Finding]:
    [pattern] = keywords.regexes
    skip, exempt = matcher(SKIP), matcher((*item.owner, *item.allow))
    found = []
    for file in ctx.files:
        text = None if skip.match(file.path) or exempt.match(file.path) else read_text(ctx.root, file)
        for number, line in enumerate((text or "").split("\n"), 1):
            if len(line) <= LONG_LINE and pattern.search(line):
                found.append(_stray(item, file.path, number))
    return found


def run(ctx: Context) -> list[Finding]:
    found = []
    for item in ctx.config.literals:
        keywords = _keywords(item)
        found.extend(_scan(ctx, item, keywords) if keywords else [Finding(*_broken(item))])
    return found


def doctor(ctx: Context) -> list[Row]:
    rows = []
    for item in ctx.config.literals:
        keywords = _keywords(item)
        if keywords is None:
            rows.append(_broken(item))
        elif nested([keywords]):
            rows.append(("warn", "hygiene-literal-nested",
                         f"hygiene.literals row {item.id}: pattern has a nested quantifier and can backtrack "
                         "exponentially", NESTED_FIX))
    return rows
