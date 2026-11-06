from django.apps import AppConfig


class ComplianceConfig(AppConfig):
    name = "apps.compliance"
    label = "compliance"
    verbose_name = "Compliance"

    def ready(self) -> None:
        # Listen to lower layers instead of them importing compliance (dependencies point up).
        from apps.learning.signals import course_completed
        from apps.org.signals import structure_changed

        from .tasks import course_completed_task, refresh_org_task

        def on_course_completed(sender, *, org_id, enrollment_id, **_):
            course_completed_task.delay(str(org_id), str(enrollment_id))

        def on_structure_changed(sender, *, org_id, member_ids=None, **_):
            members = [str(m) for m in member_ids] if member_ids is not None else None
            refresh_org_task.delay(str(org_id), member_ids=members)

        course_completed.connect(on_course_completed, dispatch_uid="compliance.course_completed")
        structure_changed.connect(on_structure_changed, dispatch_uid="compliance.structure_changed")
