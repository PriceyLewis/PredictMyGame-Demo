from django import forms
from .models import Module

class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = [
            "level", "name", "year", "assessment_type",
            "grade_percent", "grade_letter", "credits", "weight"
        ]
        widgets = {
            "level": forms.Select(attrs={"onchange": "toggleHelp()"}),
            "grade_percent": forms.NumberInput(attrs={"step": "0.1", "min": "0", "max": "100"}),
            "weight": forms.NumberInput(attrs={"step": "0.1", "min": "0"}),
        }
