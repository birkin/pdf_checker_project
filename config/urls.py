from django.contrib import admin
from django.urls import path

from pdf_checker_app import views

urlpatterns = [
    ## main ---------------------------------------------------------
    path('pdf_uploader/', views.upload_pdf, name='pdf_upload_url'),
    path('pdf/report/<uuid:pk>/', views.view_report, name='pdf_report_url'),
    ## htmx fragment endpoints --------------------------------------
    path('pdf/report/<uuid:pk>/status.fragment', views.status_fragment, name='status_fragment_url'),
    path('pdf/report/<uuid:pk>/verapdf.fragment', views.verapdf_fragment, name='verapdf_fragment_url'),
    path('pdf/report/<uuid:pk>/summary.fragment', views.summary_fragment, name='summary_fragment_url'),
    path('info/', views.info, name='info_url'),
    ## other --------------------------------------------------------
    path('', views.root, name='root_url'),
    path('admin/', admin.site.urls),
    path('error_check/', views.error_check, name='error_check_url'),
    path('version/', views.version, name='version_url'),
]
