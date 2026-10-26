# visitors/admin.py
from django.contrib import admin
from .models import Visitor

@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'is_vip', 'registered_at')
    list_filter = ('is_vip',)
    search_fields = ('name', 'phone')