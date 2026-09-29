from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Project


User = get_user_model()


class ProjectManagementTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="owner", password="Owner-Password-482!")
		self.other_user = User.objects.create_user(username="other", password="Other-Password-482!")
		self.client.force_login(self.user)
		self.project = Project.objects.create(
			title="Website refresh",
			description="Update the product site",
			created_by=self.user,
		)

	def test_list_and_search_only_show_current_users_projects(self):
		Project.objects.create(title="Private plan", created_by=self.other_user)

		response = self.client.get(reverse("projects:list"), {"q": "website"})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Website refresh")
		self.assertNotContains(response, "Private plan")
		self.assertEqual(list(response.context["projects"]), [self.project])

	def test_create_assigns_current_user(self):
		response = self.client.post(
			reverse("projects:create"),
			{"title": "Launch plan", "description": "Prepare the release"},
		)

		created = Project.objects.get(title="Launch plan")
		self.assertEqual(created.created_by, self.user)
		self.assertRedirects(response, reverse("projects:detail", args=[created.pk]))

	def test_owner_can_view_and_update_project(self):
		self.assertEqual(
			self.client.get(reverse("projects:detail", args=[self.project.pk])).status_code,
			200,
		)
		response = self.client.post(
			reverse("projects:update", args=[self.project.pk]),
			{"title": "Updated website", "description": "New scope"},
		)

		self.project.refresh_from_db()
		self.assertEqual(self.project.title, "Updated website")
		self.assertRedirects(response, reverse("projects:detail", args=[self.project.pk]))

	def test_non_owner_cannot_view_or_delete_project(self):
		self.client.force_login(self.other_user)

		self.assertEqual(
			self.client.get(reverse("projects:detail", args=[self.project.pk])).status_code,
			404,
		)
		self.assertEqual(
			self.client.post(reverse("projects:delete", args=[self.project.pk])).status_code,
			404,
		)
		self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

	def test_delete_requires_post_and_removes_project(self):
		response = self.client.get(reverse("projects:delete", args=[self.project.pk]))
		self.assertEqual(response.status_code, 200)

		response = self.client.post(reverse("projects:delete", args=[self.project.pk]))

		self.assertRedirects(response, reverse("projects:list"))
		self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())
