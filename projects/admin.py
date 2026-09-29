from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
	list_display = ("title", "created_by", "created_at")
	search_fields = ("title", "description", "created_by__username")
	list_filter = ("created_at",)
