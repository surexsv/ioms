from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .enterprise_models import Branch, Department, Designation, Employee
from .models import User


class ApprovalAuthenticationForm(AuthenticationForm):
    """Login form with approval-status aware error messages."""

    def confirm_login_allowed(self, user):
        if user.approval_status == User.APPROVAL_PENDING:
            raise forms.ValidationError(
                'Your registration is under review. Please wait for administrator approval.',
                code='pending_approval',
            )
        if user.approval_status == User.APPROVAL_REJECTED:
            reason = user.rejection_reason or 'No reason provided.'
            raise forms.ValidationError(
                f'Registration Rejected.\nReason: {reason}\n\n'
                'Your registration has been rejected. Please review the remarks and resubmit.',
                code='rejected_registration',
            )
        super().confirm_login_allowed(user)

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username is not None and password:
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                pass
            else:
                if user.check_password(password):
                    self.confirm_login_allowed(user)
                    self.user_cache = user
                    return self.cleaned_data
        raise forms.ValidationError(
            self.error_messages['invalid_login'],
            code='invalid_login',
            params={'username': self.username_field.verbose_name},
        )


class UserRegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=150, label='Full Name')
    employee_code = forms.CharField(max_length=30, required=False, label='Employee Code (optional)')
    mobile = forms.CharField(max_length=15, label='Mobile Number')
    email = forms.EmailField(label='Email Address')
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        label='Department',
    )
    designation = forms.ModelChoiceField(
        queryset=Designation.objects.filter(is_active=True),
        label='Designation',
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True),
        label='Branch',
        required=False,
    )
    employment_type = forms.ChoiceField(
        choices=Employee.EMPLOYMENT_TYPE_CHOICES,
        initial=Employee.EMPLOYMENT_FULL_TIME,
        label='Employment Type',
    )
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}))
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100)
    pin_code = forms.CharField(max_length=10, label='PIN Code')
    profile_photo = forms.ImageField(required=False, label='Profile Photo (optional)')

    class Meta:
        model = User
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ('username', 'password1', 'password2', 'email', 'mobile', 'department', 'designation'):
            if field in self.fields:
                self.fields[field].required = True
        if not self.fields['branch'].queryset.exists():
            self.fields['branch'].required = False

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_mobile(self):
        mobile = self.cleaned_data['mobile'].strip()
        if User.objects.filter(phone=mobile).exists():
            raise forms.ValidationError('An account with this mobile number already exists.')
        return mobile

    def clean_employee_code(self):
        code = (self.cleaned_data.get('employee_code') or '').strip()
        if code and Employee.objects.filter(employee_code=code).exists():
            raise forms.ValidationError('This employee code is already registered.')
        return code

    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data['full_name'].strip()
        parts = full_name.split(None, 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data['mobile']
        user.employee_id = self.cleaned_data.get('employee_code', '')
        user.department = self.cleaned_data['department'].name
        user.designation = self.cleaned_data['designation'].name
        user.role_requested = ''
        user.role = ''
        user.address = self.cleaned_data['address']
        user.city = self.cleaned_data['city']
        user.state = self.cleaned_data['state']
        user.pin_code = self.cleaned_data['pin_code']
        if self.cleaned_data.get('profile_photo'):
            user.profile_photo = self.cleaned_data['profile_photo']
        user.approval_status = User.APPROVAL_PENDING
        user.is_active = False
        user.is_staff = False
        user.is_active_employee = False
        if commit:
            user.save()
            self._create_pending_employee(user)
        return user

    def _create_pending_employee(self, user):
        branch = self.cleaned_data.get('branch') or Branch.objects.filter(is_head_office=True).first()
        if not branch:
            branch = Branch.objects.filter(is_active=True).first()
        code = (self.cleaned_data.get('employee_code') or '').strip() or f'EMP{user.pk:05d}'
        base = code
        n = 1
        while Employee.objects.filter(employee_code=code).exists():
            code = f'{base}-{n}'
            n += 1
        Employee.objects.update_or_create(
            user=user,
            defaults={
                'employee_code': code,
                'department': self.cleaned_data['department'],
                'designation': self.cleaned_data['designation'],
                'branch': branch,
                'employment_type': self.cleaned_data['employment_type'],
                'mobile': self.cleaned_data['mobile'],
                'status': Employee.STATUS_INACTIVE,
            },
        )


class ProfileResubmitVerifyForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(label='Email Address')

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get('username', '').strip()
        email = cleaned.get('email', '').strip().lower()
        if username and email:
            try:
                user = User.objects.get(username__iexact=username, email__iexact=email)
            except User.DoesNotExist:
                raise forms.ValidationError('No matching registration found. Check username and email.')
            if user.approval_status != User.APPROVAL_REJECTED:
                raise forms.ValidationError(
                    'Resubmission is only available for rejected registrations.',
                )
            cleaned['user'] = user
        return cleaned


class ProfileResubmitForm(forms.ModelForm):
    full_name = forms.CharField(max_length=150, label='Full Name')
    mobile = forms.CharField(max_length=15, label='Mobile Number')
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        label='Department',
        required=False,
    )
    designation = forms.ModelChoiceField(
        queryset=Designation.objects.filter(is_active=True),
        label='Designation',
        required=False,
    )

    class Meta:
        model = User
        fields = [
            'employee_id', 'email', 'address', 'city', 'state', 'pin_code', 'profile_photo',
        ]
        labels = {
            'employee_id': 'Employee Code (optional)',
            'profile_photo': 'Profile Photo (optional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['full_name'].initial = self.instance.full_name_display
        self.fields['mobile'].initial = self.instance.phone
        employee = getattr(self.instance, 'employee_profile', None)
        if employee:
            self.fields['department'].initial = employee.department_id
            self.fields['designation'].initial = employee.designation_id

    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data['full_name'].strip()
        parts = full_name.split(None, 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        user.phone = self.cleaned_data['mobile']
        dept = self.cleaned_data.get('department')
        desig = self.cleaned_data.get('designation')
        if dept:
            user.department = dept.name
        if desig:
            user.designation = desig.name
        if commit:
            user.save()
            employee = getattr(user, 'employee_profile', None)
            if employee and dept and desig:
                employee.department = dept
                employee.designation = desig
                employee.mobile = self.cleaned_data['mobile']
                employee.save()
        return user


class UserRejectionForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. Incomplete profile'}),
        label='Rejection Reason',
    )
