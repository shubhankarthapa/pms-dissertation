from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
	list_display = ("timestamp", "user", "activity")
	list_filter = ("timestamp",)
	search_fields = ("user__username", "activity")
	readonly_fields = ("user", "activity", "timestamp")
	ordering = ("-timestamp", "-pk")
