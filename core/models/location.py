from django.db import models

from .service import Service


class ServiceLocation(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='locations')
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'({self.id}) {self.service.provider.user.email}: {self.latitude}, {self.longitude}'
