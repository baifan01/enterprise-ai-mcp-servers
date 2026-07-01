"""SQL composition helpers for trusted Databricks query fragments.

Query modules pass user-controlled values as Databricks parameters. The only
string fragments composed into SQL are trusted table names from Settings and
fixed internal clauses selected by application logic.
"""

from __future__ import annotations


def compose_query_with_trusted_fragments(*parts: str) -> str:
    """Join trusted SQL fragments while keeping value parameters separate."""

    return "".join(parts)
