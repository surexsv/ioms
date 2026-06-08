from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from accounts.decorators import module_required
from accounts.permissions import MODULE_CLIENTS
from .models import Client
from .forms import ClientForm


@module_required(MODULE_CLIENTS)
def client_list(request):
    clients = Client.objects.all().order_by('name')
    return render(request, 'clients/client_list.html', {'clients': clients})


@module_required(MODULE_CLIENTS)
def create_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client created successfully.')
            return redirect('client_list')
    else:
        form = ClientForm()
    return render(request, 'clients/client_form.html', {'form': form, 'title': 'Add Client'})


@module_required(MODULE_CLIENTS)
def edit_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client updated successfully.')
            return redirect('client_list')
    else:
        form = ClientForm(instance=client)
    return render(request, 'clients/client_form.html', {
        'form': form,
        'title': f'Edit {client.name}',
    })
