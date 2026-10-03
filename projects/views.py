from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ProjectForm
from .models import Project


# @login_required
# def project_list(request):
# 	query = request.GET.get("q", "").strip()
# 	projects = Project.objects.filter(created_by=request.user)
# 	if query:
# 		projects = projects.filter(Q(title__icontains=query) | Q(description__icontains=query))
# 	return render(request, "projects/project_list.html", {"projects": projects, "query": query})

@login_required
def project_list(request):
    query = request.GET.get("q", "").strip()
    projects = Project.objects.filter(created_by=request.user)

    if query:
        projects = projects.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )

    project_count = projects.count()

    return render(
        request,
        "projects/project_list.html",
        {
            "projects": projects,
            "query": query,
            "project_count": project_count,
        },
    )

@login_required
def project_detail(request, pk):
	project = get_object_or_404(Project, pk=pk, created_by=request.user)
	return render(
		request,
		"projects/project_detail.html",
		{"project": project, "tasks": project.tasks.select_related("assigned_to")},
	)


@login_required
def project_create(request):
	form = ProjectForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		project = form.save(commit=False)
		project.created_by = request.user
		project.save()
		messages.success(request, "Project created.")
		return redirect("projects:detail", pk=project.pk)
	return render(request, "projects/project_form.html", {"form": form, "is_edit": False})


@login_required
def project_update(request, pk):
	project = get_object_or_404(Project, pk=pk, created_by=request.user)
	form = ProjectForm(request.POST or None, instance=project)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, "Project updated.")
		return redirect("projects:detail", pk=project.pk)
	return render(
		request,
		"projects/project_form.html",
		{"form": form, "project": project, "is_edit": True},
	)


@login_required
@require_http_methods(["GET", "POST"])
def project_delete(request, pk):
	project = get_object_or_404(Project, pk=pk, created_by=request.user)
	if request.method == "POST":
		project.delete()
		messages.success(request, "Project deleted.")
		return redirect("projects:list")
	return render(request, "projects/project_confirm_delete.html", {"project": project})
