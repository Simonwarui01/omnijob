from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('companies/', views.companies, name='companies'),
    path('jobs/', views.jobs, name='jobs'),
    path('taxonomy/', views.taxonomy, name='taxonomy'),
    path('crawl-logs/', views.crawl_logs, name='crawl_logs'),
    path('sources/', views.sources, name='sources'),
    path('my-applications/', views.my_applications, name='my_applications'),
    path('jobs/<int:job_id>/apply/', views.track_application, name='track_application'),
    path('jobs/<int:job_id>/applications/', views.get_applications, name='get_applications'),
    path('my-applications/', views.my_applications, name='my_applications'),
    path('notifications/', views.notifications, name='notifications'),
    path('jobs/<int:job_id>/viewed/', views.mark_viewed, name='mark_viewed'),
    path('jobs/<int:job_id>/queue/', views.toggle_queue, name='toggle_queue'),
    path('apply-queue/', views.apply_queue, name='apply_queue'),
]