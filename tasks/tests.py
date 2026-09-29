from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from projects.models import Project

from .models import Task


User = get_user_model()


class TaskManagementTests(TestCase):
	def setUp(self):
		self.owner = User.objects.create_user(username="owner", password="Owner-Password-482!")
		self.assignee = User.objects.create_user(username="assignee", password="Assignee-Password-482!")
		self.stranger = User.objects.create_user(username="stranger", password="Stranger-Password-482!")
		self.project = Project.objects.create(title="Release project", created_by=self.owner)
		self.task = Task.objects.create(
			title="Prepare release",
			description="Write release notes",
			project=self.project,
			assigned_to=self.assignee,
			priority=Task.Priority.HIGH,
		)

	def test_owner_can_create_task_and_assign_user(self):
		self.client.force_login(self.owner)
		form_response = self.client.get(reverse("tasks:create"), {"project": self.project.pk})
		self.assertEqual(form_response.status_code, 200)
		self.assertEqual(form_response.context["form"]["project"].value(), self.project.pk)

		response = self.client.post(
			reverse("tasks:create"),
			{
				"title": "Review design",
				"description": "Check the final screens",
				"project": self.project.pk,
				"assigned_to": self.assignee.pk,
				"status": Task.Status.PENDING,
				"priority": Task.Priority.MEDIUM,
			},
		)

		task = Task.objects.get(title="Review design")
		self.assertEqual(task.project, self.project)
		self.assertEqual(task.assigned_to, self.assignee)
		self.assertRedirects(response, reverse("tasks:detail", args=[task.pk]))

	def test_task_list_supports_search_and_status_filter(self):
		self.client.force_login(self.owner)

		response = self.client.get(reverse("tasks:list"), {"q": "release", "status": Task.Status.PENDING})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Prepare release")
		self.assertEqual(list(response.context["tasks"]), [self.task])

	def test_task_list_filters_by_project(self):
		other_project = Project.objects.create(title="Other release project", created_by=self.owner)
		other_task = Task.objects.create(title="Other project task", project=other_project)
		self.client.force_login(self.owner)

		response = self.client.get(reverse("tasks:list"), {"project": other_project.pk})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(list(response.context["tasks"]), [other_task])
		self.assertEqual(response.context["selected_project"], str(other_project.pk))

	def test_updated_at_changes_when_task_is_saved(self):
		original_updated_at = self.task.updated_at
		self.task.title = "Updated release task"
		self.task.save()
		self.task.refresh_from_db()

		self.assertGreaterEqual(self.task.updated_at, original_updated_at)
		self.assertLessEqual(self.task.updated_at, timezone.now())

	def test_assignee_can_view_task_and_change_status(self):
		self.client.force_login(self.assignee)
		self.assertEqual(self.client.get(reverse("tasks:detail", args=[self.task.pk])).status_code, 200)

		response = self.client.post(
			reverse("tasks:change_status", args=[self.task.pk]),
			{"status": Task.Status.IN_PROGRESS},
		)

		self.task.refresh_from_db()
		self.assertEqual(self.task.status, Task.Status.IN_PROGRESS)
		self.assertRedirects(response, reverse("tasks:detail", args=[self.task.pk]))

	def test_invalid_status_is_rejected(self):
		self.client.force_login(self.assignee)

		self.client.post(reverse("tasks:change_status", args=[self.task.pk]), {"status": "invalid"})

		self.task.refresh_from_db()
		self.assertEqual(self.task.status, Task.Status.PENDING)

	def test_only_project_owner_can_edit_or_delete(self):
		self.client.force_login(self.assignee)

		self.assertEqual(self.client.get(reverse("tasks:update", args=[self.task.pk])).status_code, 404)
		self.assertEqual(self.client.post(reverse("tasks:delete", args=[self.task.pk])).status_code, 404)

		self.client.force_login(self.owner)
		self.assertEqual(self.client.get(reverse("tasks:update", args=[self.task.pk])).status_code, 200)
		response = self.client.post(
			reverse("tasks:update", args=[self.task.pk]),
			{
				"title": "Release notes",
				"description": "Finish release notes",
				"project": self.project.pk,
				"assigned_to": self.assignee.pk,
				"status": Task.Status.COMPLETED,
				"priority": Task.Priority.LOW,
			},
		)
		self.task.refresh_from_db()
		self.assertEqual(self.task.title, "Release notes")
		self.assertEqual(self.task.status, Task.Status.COMPLETED)
		self.assertRedirects(response, reverse("tasks:detail", args=[self.task.pk]))

	def test_task_form_rejects_projects_owned_by_another_user(self):
		other_project = Project.objects.create(title="Other project", created_by=self.stranger)
		self.client.force_login(self.owner)

		response = self.client.post(
			reverse("tasks:create"),
			{
				"title": "Invalid project task",
				"description": "Should not be saved",
				"project": other_project.pk,
				"assigned_to": "",
				"status": Task.Status.PENDING,
				"priority": Task.Priority.LOW,
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertFalse(Task.objects.filter(title="Invalid project task").exists())

	def test_task_delete_requires_post(self):
		self.client.force_login(self.owner)
		self.assertEqual(self.client.get(reverse("tasks:delete", args=[self.task.pk])).status_code, 200)

		response = self.client.post(reverse("tasks:delete", args=[self.task.pk]))

		self.assertRedirects(response, reverse("tasks:list"))
		self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())
