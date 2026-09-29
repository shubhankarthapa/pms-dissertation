from django.db import models
from django.conf import settings


class ActivityLog(models.Model):
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="activity_logs",
	)
	activity = models.TextField()
	timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

	class Meta:
		ordering = ["-timestamp", "-pk"]
		verbose_name = "activity log"
		verbose_name_plural = "activity logs"

	def __str__(self):
		return self.activity
