"""Postgres ltree support: materialised tree paths (decision 3).

A unit's path is its ancestors' labels joined by dots, e.g. u<root>.u<london>.u<soho>.
"Everyone under London" becomes one indexed query:  path <@ 'u<root>.u<london>'
(GiST index), instead of walking the tree level by level.
"""

from django.db import models
from django.db.models import Lookup


class LTreeField(models.TextField):
    description = "Postgres ltree path"

    def db_type(self, connection):
        return "ltree"


@LTreeField.register_lookup
class DescendantOf(Lookup):
    """unit.path__descendant_of=other.path  (includes the node itself)."""

    lookup_name = "descendant_of"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f"{lhs} <@ {rhs}::ltree", [*lhs_params, *rhs_params]


@LTreeField.register_lookup
class AncestorOf(Lookup):
    """unit.path__ancestor_of=other.path  (includes the node itself)."""

    lookup_name = "ancestor_of"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        return f"{lhs} @> {rhs}::ltree", [*lhs_params, *rhs_params]


@LTreeField.register_lookup
class DescendantOfAny(Lookup):
    """unit.path__descendant_of_any=[path1, path2]: inside ANY of these subtrees
    (one GiST-indexed test, e.g. a manager who manages two sites)."""

    lookup_name = "descendant_of_any"
    prepare_rhs = False  # keep the list as a list (a text field would stringify it)

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        return f"{lhs} <@ ANY(%s::ltree[])", [*lhs_params, [str(p) for p in self.rhs]]


def label(pk) -> str:
    """ltree label for a row id: 'u' + hex (labels allow letters, digits, _ only).
    Ids never change, so renaming a unit never rewrites paths."""
    return "u" + pk.hex
