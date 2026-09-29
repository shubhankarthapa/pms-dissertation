from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from projects.models import Project

from .forms import TaskForm, TaskStatusForm
from .models import Task


def visible_tasks_for(user):
	return Task.objects.filter(Q(project__created_by=user) | Q(assigned_to=user)).distinct()


def can_manage_task(task, user):
	return task.project.created_by_id == user.pk


@login_required
def task_list(request):
	query = request.GET.get("q", "").strip()
	status = request.GET.get("status", "")
	project_id = request.GET.get("project", "").strip()
	tasks = visible_tasks_for(request.user).select_related("project", "assigned_to")
	available_projects = Project.objects.filter(
		Q(created_by=request.user) | Q(tasks__assigned_to=request.user)
	).distinct().order_by("title")
	selected_project = ""
	if query:
		tasks = tasks.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(project__title__icontains=query))
	if status in Task.Status.values:
		tasks = tasks.filter(status=status)
	if project_id.isdecimal() and available_projects.filter(pk=project_id).exists():
		tasks = tasks.filter(project_id=project_id)
		selected_project = project_id
	return render(
		request,
		"tasks/task_list.html",
		{
			"tasks": tasks,
			"query": query,
			"selected_status": status,
			"status_choices": Task.Status.choices,
			"projects": available_projects,
			"selected_project": selected_project,
		},
	)


@login_required
def task_detail(request, pk):
	task = get_object_or_404(visible_tasks_for(request.user).select_related("project", "assigned_to"), pk=pk)
	return render(
		request,
		"tasks/task_detail.html",
		{"task": task, "can_manage": can_manage_task(task, request.user)},
	)


@login_required
def task_create(request):
	form = TaskForm(request.POST or None, user=request.user)
	if request.method == "GET":
		try:
			project_id = int(request.GET.get("project", ""))
		except (TypeError, ValueError):
			project_id = None
		if project_id and form.fields["project"].queryset.filter(pk=project_id).exists():
			form.initial["project"] = project_id
	if request.method == "POST" and form.is_valid():
		task = form.save()
		messages.success(request, "Task created.")
		return redirect("tasks:detail", pk=task.pk)
	return render(request, "tasks/task_form.html", {"form": form, "is_edit": False})


@login_required
def task_update(request, pk):
	task = get_object_or_404(Task.objects.filter(project__created_by=request.user), pk=pk)
	form = TaskForm(request.POST or None, instance=task, user=request.user)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, "Task updated.")
		return redirect("tasks:detail", pk=task.pk)
	return render(
		request,
		"tasks/task_form.html",
		{"form": form, "task": task, "is_edit": True},
	)


@login_required
@require_http_methods(["GET", "POST"])
def task_delete(request, pk):
	task = get_object_or_404(Task.objects.filter(project__created_by=request.user), pk=pk)
	if request.method == "POST":
		task.delete()
		messages.success(request, "Task deleted.")
		return redirect("tasks:list")
	return render(request, "tasks/task_confirm_delete.html", {"task": task})


@login_required
@require_POST
def task_change_status(request, pk):
	task = get_object_or_404(visible_tasks_for(request.user), pk=pk)
	form = TaskStatusForm(request.POST, instance=task)
	if form.is_valid():
		form.save()
		messages.success(request, "Task status updated.")
	else:
		messages.error(request, "Choose a valid task status.")
	return redirect("tasks:detail", pk=task.pk)
