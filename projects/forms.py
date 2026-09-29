from django import forms

from .models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "maxlength": 200}),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 6, "placeholder": "What is this project about?"}
            ),
        }