from django import forms
from django.contrib.auth import get_user_model

from .enterprise_models import (
    Branch,
    Department,
    Designation,
    Employee,
    EmployeePermissionGrant,
    ModulePermission,
)

User = get_user_model()


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['code', 'name', 'description', 'is_active', 'sort_order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class DesignationForm(forms.ModelForm):
    class Meta:
        model = Designation
        fields = ['code', 'name', 'description', 'is_active', 'sort_order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['code', 'name', 'city', 'state', 'address', 'is_head_office', 'is_active']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
        }


class ModulePermissionForm(forms.ModelForm):
    class Meta:
        model = ModulePermission
        fields = [
            'codename', 'name', 'category', 'description',
            'menu_url_name', 'menu_icon', 'sort_order', 'is_active',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class EmployeeForm(forms.ModelForm):
    """Employee master form — links to login user."""

    class Meta:
        model = Employee
        fields = [
            'user', 'employee_code', 'department', 'designation',
            'reporting_manager', 'branch', 'employment_type',
            'mobile', 'joining_date', 'status',
        ]
        widgets = {
            'joining_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = User.objects.order_by('username')
        self.fields['reporting_manager'].queryset = User.objects.filter(
            is_active=True,
        ).order_by('first_name', 'username')
        self.fields['department'].queryset = Department.objects.filter(is_active=True)
        self.fields['designation'].queryset = Designation.objects.filter(is_active=True)
        self.fields['branch'].queryset = Branch.objects.filter(is_active=True)


class EmployeePermissionGrantForm(forms.ModelForm):
    class Meta:
        model = EmployeePermissionGrant
        fields = ['permission', 'is_active', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['permission'].queryset = ModulePermission.objects.filter(
            is_active=True,
        ).order_by('sort_order', 'name')


class EmployeePermissionBulkForm(forms.Form):
    """Assign multiple permissions to one employee (admin helper)."""

    permissions = forms.ModelMultipleChoiceField(
        queryset=ModulePermission.objects.filter(is_active=True).order_by('sort_order', 'name'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Module Permissions',
    )
