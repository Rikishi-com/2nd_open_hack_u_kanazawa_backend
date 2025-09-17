from django.urls import path
from .views import generate_question
from . import views

urlpatterns = [
    path('', views.index, name="index"),  # ルートページ
    path('generate/', views.generate_question, name="generate_question"),
]


