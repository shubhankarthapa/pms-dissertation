from django.db import models
from django.conf import settings
from projects.models import Project


class Task(models.Model):
	class Status(models.TextChoices):
		PENDING = "pending", "Pending"
		IN_PROGRESS = "in_progress", "In Progress"
		COMPLETED = "completed", "Completed"

	class Priority(models.TextChoices):
		LOW = "low", "Low"
		MEDIUM = "medium", "Medium"
		HIGH = "high", "High"

	title = models.CharField(max_length=200)
	description = models.TextField(blank=True)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
	priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
	assigned_to = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="assigned_tasks",
	)
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return self.title
