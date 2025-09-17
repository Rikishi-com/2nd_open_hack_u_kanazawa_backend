from django.contrib import admin
from django.urls import path, include
from generator import views  # 👈 追加

urlpatterns = [
    path('admin/', admin.site.urls),
    path('generator/', include('generator.urls')),
    path('', views.index, name="home"),  # 👈 ルートURLを直でビューに割り当て
]
