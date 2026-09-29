from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.models import Project
from tasks.models import Task

from .models import ActivityLog


User = get_user_model()


class ActivityLogTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="activity-owner", password="Activity-Password-482!")

	def test_login_and_logout_are_logged(self):
		self.client.post(
			reverse("accounts:login"),
			{"username": "activity-owner", "password": "Activity-Password-482!"},
		)
		self.client.post(reverse("accounts:logout"))

		self.assertTrue(ActivityLog.objects.filter(user=self.user, activity="User Login").exists())
		self.assertTrue(ActivityLog.objects.filter(user=self.user, activity="User Logout").exists())

	def test_project_create_update_delete_are_logged_with_actor(self):
		self.client.force_login(self.user)
		response = self.client.post(
			reverse("projects:create"),
			{"title": "Activity project", "description": "Initial details"},
		)
		project = Project.objects.get(title="Activity project")
		self.assertRedirects(response, reverse("projects:detail", args=[project.pk]))

		self.client.post(
			reverse("projects:update", args=[project.pk]),
			{"title": "Updated activity project", "description": "Changed details"},
		)
		self.client.post(reverse("projects:delete", args=[project.pk]))

		entries = ActivityLog.objects.filter(user=self.user).values_list("activity", flat=True)
		self.assertIn("Project Created: Activity project", entries)
		self.assertIn("Project Updated: Updated activity project", entries)
		self.assertIn("Project Deleted: Updated activity project", entries)

	def test_task_create_update_status_change_and_delete_are_logged(self):
		project = Project.objects.create(title="Task activity project", created_by=self.user)
		self.client.force_login(self.user)
		response = self.client.post(
			reverse("tasks:create"),
			{
				"title": "Activity task",
				"description": "Initial task",
				"project": project.pk,
				"assigned_to": "",
				"status": Task.Status.PENDING,
				"priority": Task.Priority.MEDIUM,
			},
		)
		task = Task.objects.get(title="Activity task")
		self.assertRedirects(response, reverse("tasks:detail", args=[task.pk]))

		self.client.post(
			reverse("tasks:update", args=[task.pk]),
			{
				"title": "Updated activity task",
				"description": "Updated task",
				"project": project.pk,
				"assigned_to": "",
				"status": Task.Status.IN_PROGRESS,
				"priority": Task.Priority.HIGH,
			},
		)
		self.client.post(reverse("tasks:delete", args=[task.pk]))

		entries = list(ActivityLog.objects.filter(user=self.user).values_list("activity", flat=True))
		self.assertIn("Task Created: Activity task", entries)
		self.assertIn("Task Updated: Updated activity task", entries)
		self.assertIn(
			"Task Status Changed: Updated activity task (Pending to In Progress)",
			entries,
		)
		self.assertIn("Task Deleted: Updated activity task", entries)

	def test_activity_list_is_user_scoped_and_staff_can_view_all(self):
		other_user = User.objects.create_user(username="activity-other", password="Other-Password-482!")
		own_log = ActivityLog.objects.create(user=self.user, activity="Own entry")
		other_log = ActivityLog.objects.create(user=other_user, activity="Other entry")
		self.client.force_login(self.user)

		response = self.client.get(reverse("activity_logs:list"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Own entry")
		self.assertNotContains(response, "Other entry")
		self.assertIn(own_log, response.context["activities"])
		self.assertNotIn(other_log, response.context["activities"])

		staff_user = User.objects.create_superuser(
			username="activity-admin",
			email="admin@example.com",
			password="Admin-Password-482!",
		)
		self.client.force_login(staff_user)
		response = self.client.get(reverse("activity_logs:list"))
		self.assertContains(response, "Own entry")
		self.assertContains(response, "Other entry")
