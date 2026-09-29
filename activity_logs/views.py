from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from .models import ActivityLog


@login_required
def activity_list(request):
	activities = ActivityLog.objects.select_related("user")
	if not request.user.is_staff:
		activities = activities.filter(user=request.user)
	page_obj = Paginator(activities, 25).get_page(request.GET.get("page"))
	return render(
		request,
		"activity_logs/activity_list.html",
		{"page_obj": page_obj, "activities": page_obj.object_list},
	)
