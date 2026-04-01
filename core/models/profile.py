from django.db import models

from . import ServiceType, User


class ProviderProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    fixed_latitude = models.DecimalField(max_digits=9, decimal_places=6,)
    fixed_longitude = models.DecimalField(max_digits=9, decimal_places=6,)
    last_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE, related_name='providers')
    price_per_hour = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    price_per_day = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f'({self.id}) user: {self.user.email}, {self.service_type.name}'
