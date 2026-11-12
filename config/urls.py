"""
Root URL configuration for BookNest project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls', namespace='core')),
    path('library/', include('apps.library.urls', namespace='library')),
]
