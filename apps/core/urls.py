from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.BookNestLoginView.as_view(), name='login'),
    path('logout/', views.BookNestLogoutView.as_view(), name='logout'),
]
