from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

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
    employee_id = forms.CharField(max_length=50, required=False, label='Employee ID (optional)')
    mobile = forms.CharField(max_length=15, label='Mobile Number')
    email = forms.EmailField(label='Email Address')
    department = forms.CharField(max_length=100)
    designation = forms.CharField(max_length=100)
    role_requested = forms.ChoiceField(
        choices=User.ROLE_REQUEST_CHOICES,
        label='Role Requested',
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
        for field in ('username', 'password1', 'password2', 'email', 'mobile'):
            if field in self.fields:
                self.fields[field].required = True

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

    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data['full_name'].strip()
        parts = full_name.split(None, 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data['mobile']
        user.employee_id = self.cleaned_data.get('employee_id', '')
        user.department = self.cleaned_data['department']
        user.designation = self.cleaned_data['designation']
        user.role_requested = self.cleaned_data['role_requested']
        user.role = user.map_requested_role()
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
        return user


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

    class Meta:
        model = User
        fields = [
            'employee_id', 'email', 'department', 'designation',
            'role_requested', 'address', 'city', 'state', 'pin_code', 'profile_photo',
        ]
        labels = {
            'employee_id': 'Employee ID (optional)',
            'role_requested': 'Role Requested',
            'profile_photo': 'Profile Photo (optional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role_requested'].choices = User.ROLE_REQUEST_CHOICES
        self.fields['full_name'].initial = self.instance.full_name_display
        self.fields['mobile'].initial = self.instance.phone

    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data['full_name'].strip()
        parts = full_name.split(None, 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        user.phone = self.cleaned_data['mobile']
        user.role = user.map_requested_role()
        if commit:
            user.save()
        return user


class UserRejectionForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. Incomplete profile'}),
        label='Rejection Reason',
    )
