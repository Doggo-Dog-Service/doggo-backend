from django.db import models


class ServiceType(models.Model):
    name = models.CharField(max_length=20, null=False, blank=False)
    description = models.TextField()

    def __str__(self):
        return f'({self.id}) {self.name}'
