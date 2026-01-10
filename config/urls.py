from django.contrib import admin
from django.urls import path
from pdf_checker_app import views


urlpatterns = [
    ## main ---------------------------------------------------------
    path('pdf_uploader/', views.upload_pdf, name='pdf_upload_url'),
    path('pdf/report/<int:pk>/', views.view_report, name='pdf_report_url'),
    path('info/', views.info, name='info_url'),
    ## other --------------------------------------------------------
    path('', views.root, name='root_url'),
    path('admin/', admin.site.urls),
    path('error_check/', views.error_check, name='error_check_url'),
    path('version/', views.version, name='version_url'),
]
