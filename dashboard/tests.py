from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.models import Project
from tasks.models import Task


User = get_user_model()


class DashboardTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="dashboard-user", password="Dash-Password-482!")
		self.other_user = User.objects.create_user(username="other-user", password="Other-Password-482!")
		self.project = Project.objects.create(title="Owned project", created_by=self.user)
		self.assigned_project = Project.objects.create(title="Other project", created_by=self.other_user)

	def test_dashboard_requires_login(self):
		response = self.client.get(reverse("dashboard:home"))

		self.assertRedirects(
			response,
			f"{reverse('accounts:login')}?next={reverse('dashboard:home')}",
		)

	def test_dashboard_shows_user_scoped_counts_and_charts(self):
		Task.objects.create(title="Pending", project=self.project, status=Task.Status.PENDING)
		Task.objects.create(title="Active", project=self.project, status=Task.Status.IN_PROGRESS, priority=Task.Priority.HIGH)
		Task.objects.create(title="Done", project=self.project, status=Task.Status.COMPLETED)
		Task.objects.create(
			title="Assigned elsewhere",
			project=self.assigned_project,
			assigned_to=self.user,
			status=Task.Status.PENDING,
			priority=Task.Priority.LOW,
		)
		Task.objects.create(title="Not visible", project=self.assigned_project, status=Task.Status.COMPLETED)
		self.client.force_login(self.user)

		response = self.client.get(reverse("dashboard:home"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["total_projects"], 1)
		self.assertEqual(response.context["total_users"], 2)
		self.assertEqual(response.context["total_tasks"], 4)
		self.assertEqual(response.context["pending_tasks"], 2)
		self.assertEqual(response.context["in_progress_tasks"], 1)
		self.assertEqual(response.context["completed_tasks"], 1)
		self.assertEqual(response.context["high_priority_tasks"], 1)
		self.assertEqual(response.context["chart_data"]["status"]["values"], [2, 1, 1])
		self.assertEqual(response.context["chart_data"]["priority"]["values"], [1, 2, 1])
		self.assertEqual(response.context["chart_data"]["project_completion"]["values"], [33])
		self.assertEqual(response.context["project_progress"][0]["percentage"], 33)
		self.assertContains(response, "Tasks by status")
		self.assertContains(response, "Tasks by priority")
		self.assertContains(response, "Project completion")
		self.assertContains(response, "Total Users")
		self.assertContains(response, 'role="progressbar"')
		self.assertContains(response, "Assigned elsewhere")
		self.assertNotContains(response, "Not visible")

	def test_dashboard_renders_without_projects_or_tasks(self):
		self.project.delete()
		self.client.force_login(self.user)

		response = self.client.get(reverse("dashboard:home"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["total_projects"], 0)
		self.assertEqual(response.context["total_users"], 2)
		self.assertEqual(response.context["total_tasks"], 0)
		self.assertEqual(response.context["high_priority_tasks"], 0)
		self.assertEqual(response.context["chart_data"]["priority"]["values"], [0, 0, 0])
		self.assertEqual(response.context["chart_data"]["project_completion"]["values"], [])
