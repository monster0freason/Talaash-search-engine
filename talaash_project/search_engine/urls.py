from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('search/', views.search_results, name='search_results'),
    path('document/<int:doc_id>/', views.document_detail, name='document_detail'),
    path('refresh-index/', views.refresh_index, name='refresh_index'),
]