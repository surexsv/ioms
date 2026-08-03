from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

DEPRECATION_MSG = (
    'The Enquiries module has been retired. Create and manage all work directly from Orders.'
)


@login_required
def _deprecated_redirect(request, *args, **kwargs):
    messages.info(request, DEPRECATION_MSG)
    return redirect('order_list')


enquiry_list = _deprecated_redirect
create_enquiry = _deprecated_redirect
enquiry_detail = _deprecated_redirect
edit_enquiry = _deprecated_redirect
convert_enquiry_order = _deprecated_redirect
site_progress_create = _deprecated_redirect
