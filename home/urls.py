from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    re_path(r'^tip-api/(?P<path>.+)$', views.tip_api_proxy, name='tip_api_proxy'),
]
