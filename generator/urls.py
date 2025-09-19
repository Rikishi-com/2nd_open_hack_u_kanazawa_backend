from django.urls import path
from .views import generate_question
from . import views

urlpatterns = [
    path('', views.index, name="index"),  # ルートページ
    path('generate_simple/', views.generate_question, name="generate_question"),  # 一問一答生成エンドポイント
    path('generate_4choice/', views.generate_question_4choice, name="generate_question_4choice"),  # 四択問題生成エンドポイント
    path('generate_hole/', views.generate_question_hole, name="generate_question_hole"),  # 穴埋め問題生成エンドポイント
    path('generate_problem/', views.generate_problem, name="generate_problem"),  # 問題生成エンドポイント
    path('generate_question_4choice_api/',views.generate_question_4choice_api, name="generate_question_4choice_api"),
    path('generate_workbook_for_q_and_a/', views.generate_workbook_for_q_and_a, name="generate_workbook_for_q_and_a"),
    path('generate_4_choice_workbook_for_q_and_a/', views.generate_4_choice_workbook_for_q_and_a, name="generate_4_choice_workbook_for_q_and_a"),
]


