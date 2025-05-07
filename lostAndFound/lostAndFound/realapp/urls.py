# urls.py in your Django app
from django.conf import settings
from django.conf.urls.static import static

from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('', views.all_complaints_view, name='home'),
    path('add-complaint/', views.add_complaint_view, name='add_complaint'),
    path('delete-complaint/<int:complaint_id>/', views.delete_complaint_view, name='delete_complaint'),
    path('complaints/<int:complaint_id>/update/', views.update_complaint_view, name='update_complaint'),
    path('complaint/<int:complaint_id>/', views.view_complaint_view, name='view_complaint'),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
