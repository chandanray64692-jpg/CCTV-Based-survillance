# visitors/models.py
from django.db import models

class Visitor(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    photo = models.ImageField(upload_to='visitors_photos/')
    vector_embedding = models.TextField(blank=True, null=True) # Vector data for AI matching
    is_vip = models.BooleanField(default=False)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name