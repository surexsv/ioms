from django import forms

from accounts.models import User
from orders.models import Order

from .models import TeamTask
from .services import assignable_users


class DateInput(forms.DateInput):
    input_type = 'date'


def user_label(user):
    name = user.get_full_name().strip() or user.username
    role = user.get_role_display() if getattr(user, 'role', '') else ''
    if role:
        return f'{name} ({role})'
    return name


class TaskCreateForm(forms.Form):
    title = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))
    priority = forms.ChoiceField(choices=TeamTask.PRIORITY_CHOICES)
    assignee = forms.ModelChoiceField(queryset=User.objects.none())
    scheduled_on = forms.DateField(required=False, widget=DateInput, label='Scheduled date')
    due_on = forms.DateField(required=False, widget=DateInput, label='Due date')
    remind_after_days = forms.IntegerField(
        min_value=1,
        max_value=365,
        initial=3,
        label='Remind after (days)',
        help_text='If the task is still open after this many days, the system records a reminder.',
    )
    related_order_no = forms.CharField(
        required=False,
        label='Related order number',
        help_text='Optional. Example: the IOMS order number this task belongs to.',
    )
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = assignable_users()
        self.fields['assignee'].label_from_instance = user_label

    def clean(self):
        cleaned = super().clean()
        scheduled = cleaned.get('scheduled_on')
        due = cleaned.get('due_on')
        if scheduled and due and due < scheduled:
            self.add_error('due_on', 'Due date cannot be before the scheduled date.')
        order_no = (cleaned.get('related_order_no') or '').strip()
        cleaned['related_order'] = None
        if order_no:
            order = Order.objects.filter(order_no__iexact=order_no).first()
            if not order:
                self.add_error('related_order_no', 'No order found with that number.')
            else:
                cleaned['related_order'] = order
        return cleaned


class ScheduleForm(forms.Form):
    scheduled_on = forms.DateField(required=False, widget=DateInput, label='Scheduled date')
    due_on = forms.DateField(required=False, widget=DateInput, label='Due date')
    remind_after_days = forms.IntegerField(
        min_value=1,
        max_value=365,
        label='Remind after (days)',
    )
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('scheduled_on') and not cleaned.get('due_on'):
            raise forms.ValidationError('Enter a scheduled date or a due date.')
        scheduled = cleaned.get('scheduled_on')
        due = cleaned.get('due_on')
        if scheduled and due and due < scheduled:
            self.add_error('due_on', 'Due date cannot be before the scheduled date.')
        return cleaned


class RemapForm(forms.Form):
    assignee = forms.ModelChoiceField(queryset=User.objects.none(), label='Forward to')
    remarks = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Why is this being forwarded?',
    )

    def __init__(self, *args, task=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = assignable_users()
        if task is not None:
            qs = qs.exclude(pk=task.assignee_id)
        self.fields['assignee'].queryset = qs
        self.fields['assignee'].label_from_instance = user_label


class HoldForm(forms.Form):
    remarks = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Hold remarks',
        help_text='Say why the task is stuck and what should happen next.',
    )
    remind_after_days = forms.IntegerField(
        min_value=1,
        max_value=365,
        label='Remind after (days)',
        help_text='A reminder is recorded if the task is still open after this many days.',
    )


class CloseForm(forms.Form):
    remarks = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Closing remarks',
    )


class NoteForm(forms.Form):
    remarks = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Update',
    )


class ResumeForm(forms.Form):
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
        label='Resume remarks',
    )


def initial_schedule(task):
    return {
        'scheduled_on': task.scheduled_on,
        'due_on': task.due_on,
        'remind_after_days': task.remind_after_days,
    }
