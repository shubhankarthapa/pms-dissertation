from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import JsonResponse

from .forms import RegistrationForm

def health_check(request):
	return JsonResponse({"status": "ok"})

def register(request):
	if request.user.is_authenticated:
		return redirect("accounts:profile")

	form = RegistrationForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		user = form.save()
		login(request, user)
		messages.success(request, "Your account has been created.")
		return redirect("accounts:profile")

	return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
	return render(request, "accounts/profile.html")
