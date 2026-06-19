from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ProviderProfile(models.Model):
    user = models.OneToOneField('core.User', on_delete=models.CASCADE, related_name='provider_profile')
    fixed_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    fixed_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    last_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        null=True,
        blank=True,
    )
    last_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        null=True,
        blank=True,
    )
    service_type = models.ForeignKey('core.ServiceType', on_delete=models.CASCADE, related_name='providers')
    price_per_hour = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    price_per_day = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'({self.id}) user: {self.user.email}, {self.service_type.name}'


class ClientProfile(models.Model):
    user = models.OneToOneField('core.User', on_delete=models.CASCADE, related_name='client_profile')
    last_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        null=True,
        blank=True,
    )
    last_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'({self.id}) user: {self.user.email}'
