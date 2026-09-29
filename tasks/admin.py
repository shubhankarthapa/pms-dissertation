from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
	list_display = ("title", "project", "assigned_to", "status", "priority", "created_at", "updated_at")
	list_filter = ("status", "priority", "created_at")
	search_fields = ("title", "description", "project__title", "assigned_to__username")
