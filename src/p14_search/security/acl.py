"""Access-control filter, built once from the principal and applied INSIDE both retrievers.

Rules: public -> everyone; internal -> principals with level >= internal; restricted -> principals with
level restricted whose offices include the document's office (or all offices for admins).
The same rules produce a SQL clause (FTS5/BM25) and a Qdrant payload filter (dense), so the two
retrievers cannot disagree, and unauthorised passages never enter ranking, counts or scores.
"""

from __future__ import annotations

from qdrant_client import models as qm

from p14_search.models import AccessLevel, SearchFilters
from p14_search.security.principals import Principal


def allows(principal: Principal, access_level: str, office: str) -> bool:
    level = AccessLevel(access_level)
    if level == AccessLevel.public:
        return True
    if level == AccessLevel.internal:
        return principal.level in (AccessLevel.internal, AccessLevel.restricted)
    return principal.level == AccessLevel.restricted and (principal.all_offices or office in principal.offices)


def sql_clause(principal: Principal, filters: SearchFilters | None, doc_alias: str = "d") -> tuple[str, list]:
    """WHERE fragment over the documents table (alias `doc_alias`)."""
    d = doc_alias
    params: list = []
    if principal.level == AccessLevel.public:
        acl = f"{d}.access_level = 'public'"
    elif principal.level == AccessLevel.internal:
        acl = f"{d}.access_level IN ('public','internal')"
    elif principal.all_offices:
        acl = "1 = 1"
    elif principal.offices:
        marks = ",".join("?" * len(principal.offices))
        acl = f"({d}.access_level IN ('public','internal') OR ({d}.access_level = 'restricted' AND {d}.office IN ({marks})))"
        params += list(principal.offices)
    else:
        acl = f"{d}.access_level IN ('public','internal')"
    clauses = [acl]
    for column, values in _filter_items(filters):
        clauses.append(f"{d}.{column} IN ({','.join('?' * len(values))})")
        params += values
    return " AND ".join(clauses), params


def qdrant_filter(principal: Principal, filters: SearchFilters | None) -> qm.Filter:
    must: list = []
    if principal.level == AccessLevel.public:
        must.append(_match("access_level", ["public"]))
    elif principal.level == AccessLevel.internal or (not principal.all_offices and not principal.offices):
        must.append(_match("access_level", ["public", "internal"]))
    elif not principal.all_offices:
        must.append(
            qm.Filter(
                should=[
                    _match("access_level", ["public", "internal"]),
                    qm.Filter(must=[_match("access_level", ["restricted"]), _match("office", list(principal.offices))]),
                ]
            )
        )
    for column, values in _filter_items(filters):
        must.append(_match(column, values))
    return qm.Filter(must=must)


def _match(key: str, values: list[str]) -> qm.FieldCondition:
    return qm.FieldCondition(key=key, match=qm.MatchAny(any=values))


def _filter_items(filters: SearchFilters | None):
    if not filters:
        return []
    return [(col, vals) for col, vals in (("office", filters.office), ("type", filters.type), ("source_id", filters.source_id)) if vals]
