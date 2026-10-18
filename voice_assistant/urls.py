from django.urls import path

from . import views

urlpatterns = [
    path('voice/translate/', views.translate_voice, name='voice_translate'),
    path('<int:pk>/voice/', views.save_voice_note, name='order_voice_note'),
]
