# secure_vision/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from cameras.views import CameraNodeViewSet
from visitors.views import VisitorViewSet
from logs.views import GateLogViewSet
from core.views import analytics_dashboard_view, dashboard_view, analytics_view, footprint_map_view
from core.views import analytics_dashboard_view
from django.contrib.auth import views as auth_views
router = DefaultRouter()
router.register(r'cameras', CameraNodeViewSet)
router.register(r'visitors', VisitorViewSet)
router.register(r'logs', GateLogViewSet)

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('analytics/', analytics_view, name='analytics'),
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    path('cameras/', include('cameras.urls')),
    path('footprint-map/', footprint_map_view, name='footprint_map'),
    path('analytics/', analytics_dashboard_view, name='analytics'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('cameras/', include('cameras.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)