from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Django REST Framework Router
router = DefaultRouter()
router.register(r'nodes', views.CameraNodeViewSet)

urlpatterns = [
    # 1. REST Framework Router & Live Video Stream
    path('api/', include(router.urls)),
    path('stream/<int:camera_id>/', views.live_video_feed, name='live_feed'),
    
    # 2. Core Dashboard & Navigation Views
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('grid/', views.camera_grid_view, name='camera_grid'),
    
    # 3. Camera Management & CP Plus / Network Integration
    path('manage/', views.camera_management_view, name='camera_management'),
    path('add/', views.add_camera_view, name='add_camera'),
    path('add-cpplus/', views.add_cpplus_camera_view, name='add_cpplus_camera'),
    path('scanner/', views.network_scanner_view, name='network_scanner'),
    
    # 4. Vehicle Management & ANPR Hub
    path('vehicles/', views.vehicle_anpr_view, name='vehicle_anpr'),
    path('vehicle-movement/', views.vehicle_movement_view, name='vehicle_movement'),
    path('anpr-logs/', views.anpr_logs_view, name='anpr_logs'),
    path('vehicle/<str:plate_number>/', views.vehicle_profile_view, name='vehicle_profile'),
    
    # 5. Advanced AI Features, Fences & Analytics
    path('zones/', views.zones_fences_view, name='zones_fences'),
    path('analytics/', views.ai_analytics_view, name='ai_analytics'),
    path('footprint-map/', views.footprint_map_view, name='footprint_map'),
    
    # 6. Reports & Alerts Hub
    path('alerts/', views.alerts_buzzer_view, name='alerts_buzzer'),
    path('analytics/report/', views.analytics_report_view, name='analytics_report'),
    path('vehicles/report/', views.vehicle_report_view, name='vehicle_report'),
    
    # 7. System Settings & Authentication
    path('settings/', views.settings_view, name='settings'),
    path('login/', views.custom_login_view, name='login'),
    path('logout/', views.custom_logout_view, name='logout'),
    
    # 8. AJAX & Background JSON APIs
    path('api/scan/', views.scan_network_cameras, name='api_scan_network'),
    path('api/toggle-ai/<int:camera_id>/', views.toggle_camera_ai, name='toggle_camera_ai'),
    path('api/trigger-alarm/<int:camera_id>/', views.trigger_manual_alarm, name='trigger_manual_alarm'),
    path('api/recent-alerts/', views.get_recent_alerts_api, name='recent_alerts_api'),
    path('api/v1/', views.api_endpoints_view, name='api_endpoints'),
]