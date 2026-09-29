from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AuthenticationFlowTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="projectmember",
			email="member@example.com",
			password="Old-Project-Password-482!",
		)

	def test_registration_creates_and_authenticates_user(self):
		self.assertEqual(self.client.get(reverse("accounts:register")).status_code, 200)
		response = self.client.post(
			reverse("accounts:register"),
			{
				"username": "newmember",
				"email": "newmember@example.com",
				"password1": "New-Project-Password-739!",
				"password2": "New-Project-Password-739!",
			},
		)

		self.assertRedirects(response, reverse("accounts:profile"))
		self.assertTrue(User.objects.filter(username="newmember").exists())
		self.assertEqual(int(self.client.session["_auth_user_id"]), User.objects.get(username="newmember").pk)

	def test_login_and_post_logout(self):
		self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 200)
		response = self.client.post(
			reverse("accounts:login"),
			{"username": "projectmember", "password": "Old-Project-Password-482!"},
		)
		self.assertRedirects(response, reverse("accounts:profile"))

		response = self.client.post(reverse("accounts:logout"))
		self.assertRedirects(response, reverse("accounts:login"))
		self.assertNotIn("_auth_user_id", self.client.session)

	def test_profile_requires_authentication(self):
		response = self.client.get(reverse("accounts:profile"))

		self.assertRedirects(
			response,
			f"{reverse('accounts:login')}?next={reverse('accounts:profile')}",
		)

	def test_password_change_keeps_user_authenticated(self):
		self.client.force_login(self.user)
		self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
		self.assertEqual(self.client.get(reverse("accounts:password_change")).status_code, 200)
		response = self.client.post(
			reverse("accounts:password_change"),
			{
				"old_password": "Old-Project-Password-482!",
				"new_password1": "Replacement-Password-915!",
				"new_password2": "Replacement-Password-915!",
			},
		)

		self.assertRedirects(response, reverse("accounts:profile"))
		self.user.refresh_from_db()
		self.assertTrue(self.user.check_password("Replacement-Password-915!"))
		self.assertIn("_auth_user_id", self.client.session)
