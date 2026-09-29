from django import forms
from django.contrib.auth import get_user_model

from projects.models import Project

from .models import Task


User = get_user_model()


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "project", "assigned_to", "status", "priority"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "maxlength": 200}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "project": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(created_by=user)
        self.fields["assigned_to"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["assigned_to"].required = False


class TaskStatusForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["status"]
        widgets = {"status": forms.Select(attrs={"class": "form-select"})}