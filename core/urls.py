from django.urls import path
from . import views

urlpatterns = [
    # Vistas principales
    path('', views.home, name='home'),
    path('sessions/', views.sessions_list, name='sessions'),
    path('reports/', views.reports_list, name='reports'),

    # Vistas de detalle
    path('session/<uuid:session_id>/', views.session_view, name='session'),
    path('report/<uuid:report_id>/', views.report_view, name='report'),

    # Acciones
    path('report/<uuid:report_id>/download/<str:format_type>/',
         views.download_report, name='download_report'),
    path('report/<uuid:report_id>/share/',
         views.share_report, name='share_report'),

    # Utilidades
    path('placeholder-image/', views.placeholder_image, name='placeholder_image'),
]
