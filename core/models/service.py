from django.db import models


class ServiceType(models.Model):
    name = models.CharField(max_length=20, null=False, blank=False)
    description = models.TextField()
