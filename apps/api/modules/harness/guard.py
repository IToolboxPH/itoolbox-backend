"""Read-only SQL guard.

Zetaris's query endpoint already refuses anything but SELECT; this check runs
first so a model-written statement is rejected with a message the model can act
on, and so the rule holds even if the endpoint ever changes. It is a guard, not a
parser: it strips literals and comments, then looks at what is left.
"""
from __future__ import annotations

import re

# String literals, quoted identifiers and comments, blanked before inspection so
# a keyword inside them is not mistaken for a statement.
_LITERALS = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|`[^`]*`", re.S)
_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)

# Statements that change data, schema or grants. Word-bounded, so columns such
# as updated_at or created_at do not match. REPLACE is deliberately absent: it is
# also a string function, and CREATE OR REPLACE is caught by CREATE.
_WRITE_VERBS = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|truncate|grant|revoke|register)\b",
    re.I,
)


class SqlRejected(ValueError):
    """A statement the guard will not send; the message says why, for the model to act on."""


def check_read_only(sql: str) -> str:
    """Return the statement without its trailing semicolon, or raise SqlRejected."""
    statement = sql.strip().rstrip(";").strip()
    if not statement:
        raise SqlRejected("The query is empty.")

    bare = _COMMENTS.sub(" ", _LITERALS.sub("''", statement))
    if ";" in bare:
        raise SqlRejected("Send one statement at a time, without semicolons between statements.")

    words = bare.lstrip("( \t\r\n").split(None, 1)
    if not words or words[0].lower() not in ("select", "with"):
        raise SqlRejected("Only read-only SELECT (or WITH ... SELECT) queries are allowed.")

    verb = _WRITE_VERBS.search(bare)
    if verb:
        raise SqlRejected(f"'{verb.group(1).upper()}' is not allowed: this connection is read-only.")
    return statement
