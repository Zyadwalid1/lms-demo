"""Signals other apps listen to, so org never imports them (dependencies point upward).

structure_changed(org_id, member_ids)
    Sent AFTER COMMIT when people's units or job roles change, or the tree itself
    changes (member_ids=None: re-check everyone). Compliance listens to re-assign
    required training.
"""

from django.db import transaction
from django.dispatch import Signal

structure_changed = Signal()


def notify_structure_changed(org_id, member_ids=None) -> None:
    ids = list(member_ids) if member_ids is not None else None
    transaction.on_commit(lambda: structure_changed.send(sender=None, org_id=org_id, member_ids=ids))
