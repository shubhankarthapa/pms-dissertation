from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import render

from projects.models import Project
from tasks.models import Task

@login_required
def home(request):
	user_model = get_user_model()
	user_tasks = Task.objects.filter(
		Q(project__created_by=request.user) | Q(assigned_to=request.user)
	).distinct()
	task_counts = user_tasks.aggregate(
		total=Count("pk"),
		pending=Count("pk", filter=Q(status=Task.Status.PENDING)),
		in_progress=Count("pk", filter=Q(status=Task.Status.IN_PROGRESS)),
		completed=Count("pk", filter=Q(status=Task.Status.COMPLETED)),
		low_priority=Count("pk", filter=Q(priority=Task.Priority.LOW)),
		medium_priority=Count("pk", filter=Q(priority=Task.Priority.MEDIUM)),
		high_priority=Count("pk", filter=Q(priority=Task.Priority.HIGH)),
	)
	projects = Project.objects.filter(created_by=request.user).annotate(
		task_count=Count("tasks", distinct=True),
		completed_task_count=Count(
			"tasks",
			filter=Q(tasks__status=Task.Status.COMPLETED),
			distinct=True,
		),
	).order_by("title")
	project_progress = [
		{
			"project": project,
			"task_count": project.task_count,
			"completed_task_count": project.completed_task_count,
			"percentage": round(project.completed_task_count / project.task_count * 100)
			if project.task_count
			else 0,
		}
		for project in projects
	]

	total_projects = Project.objects.filter(
		created_by=request.user
	).count()

	context = {
		"total_projects": len(project_progress),
		"total_users": user_model.objects.count(),
		"total_tasks": task_counts["total"],
		"pending_tasks": task_counts["pending"],
		"in_progress_tasks": task_counts["in_progress"],
		"completed_tasks": task_counts["completed"],
		"high_priority_tasks": task_counts["high_priority"],
		"project_progress": project_progress,
		"recent_tasks": user_tasks.select_related("project", "assigned_to")[:6],
		"chart_data": {
			"status": {
				"labels": [label for _, label in Task.Status.choices],
				"values": [task_counts["pending"], task_counts["in_progress"], task_counts["completed"]],
			},
			"priority": {
				"labels": [label for _, label in Task.Priority.choices],
				"values": [
					task_counts["low_priority"],
					task_counts["medium_priority"],
					task_counts["high_priority"],
				],
			},
			"project_completion": {
				"labels": [item["project"].title for item in project_progress],
				"values": [item["percentage"] for item in project_progress],
			},
		},
	}
	return render(request, "dashboard/dashboard.html", context)
