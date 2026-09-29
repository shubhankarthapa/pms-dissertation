from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from projects.models import Project
from tasks.models import Task

from .middleware import get_current_user
from .models import ActivityLog


def _authenticated(user):
    return user if user is not None and getattr(user, "is_authenticated", False) else None


def _record_activity(activity, fallback_user=None):
    user = _authenticated(get_current_user()) or _authenticated(fallback_user)
    ActivityLog.objects.create(user=user, activity=activity)


def _user_from_id(user_id):
    if user_id is None:
        return None
    return get_user_model().objects.filter(pk=user_id).first()


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    _record_activity("User Login", user)


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    _record_activity("User Logout", user)


@receiver(post_save, sender=Project)
def log_project_save(sender, instance, created, **kwargs):
    action = "Project Created" if created else "Project Updated"
    _record_activity(f"{action}: {instance.title}", _user_from_id(instance.created_by_id))


@receiver(post_delete, sender=Project)
def log_project_delete(sender, instance, **kwargs):
    _record_activity(f"Project Deleted: {instance.title}", _user_from_id(instance.created_by_id))


@receiver(pre_save, sender=Task)
def remember_task_status(sender, instance, **kwargs):
    if instance.pk:
        instance._activity_log_previous_status = (
            Task.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
        )
    else:
        instance._activity_log_previous_status = None


@receiver(post_save, sender=Task)
def log_task_save(sender, instance, created, **kwargs):
    actor = get_current_user()
    if not _authenticated(actor):
        actor = _user_from_id(instance.project.created_by_id)

    if created:
        _record_activity(f"Task Created: {instance.title}", actor)
        return

    _record_activity(f"Task Updated: {instance.title}", actor)
    old_status = getattr(instance, "_activity_log_previous_status", None)
    if old_status is not None and old_status != instance.status:
        old_label = Task.Status(old_status).label
        new_label = instance.get_status_display()
        _record_activity(f"Task Status Changed: {instance.title} ({old_label} to {new_label})", actor)


@receiver(post_delete, sender=Task)
def log_task_delete(sender, instance, **kwargs):
    actor = get_current_user()
    if not _authenticated(actor):
        actor = _user_from_id(instance.project.created_by_id)
    _record_activity(f"Task Deleted: {instance.title}", actor)