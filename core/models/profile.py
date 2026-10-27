from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count

LATITUDE_VALIDATORS = [MinValueValidator(-90), MaxValueValidator(90)]
LONGITUDE_VALIDATORS = [MinValueValidator(-180), MaxValueValidator(180)]


class ProviderProfileQuerySet(models.QuerySet):
    def with_rating(self):
        """Anota a média (`rating_avg`) e a quantidade (`rating_count`) de avaliações do prestador."""
        return self.annotate(rating_avg=Avg('reviews__rating'), rating_count=Count('reviews'))


class ProviderProfile(models.Model):
    user = models.OneToOneField('core.User', on_delete=models.CASCADE, related_name='provider_profile')
    fixed_latitude = models.DecimalField(max_digits=9, decimal_places=6, validators=LATITUDE_VALIDATORS)
    fixed_longitude = models.DecimalField(max_digits=9, decimal_places=6, validators=LONGITUDE_VALIDATORS)
    last_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=LATITUDE_VALIDATORS,
        null=True,
        blank=True,
    )
    last_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=LONGITUDE_VALIDATORS,
        null=True,
        blank=True,
    )
    service_type = models.ForeignKey('core.ServiceType', on_delete=models.CASCADE, related_name='providers')
    price_per_hour = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    price_per_day = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProviderProfileQuerySet.as_manager()

    def __str__(self):
        return f'({self.id}) user: {self.user.email}, {self.service_type.name}'


class ClientProfile(models.Model):
    user = models.OneToOneField('core.User', on_delete=models.CASCADE, related_name='client_profile')
    last_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=LATITUDE_VALIDATORS,
        null=True,
        blank=True,
    )
    last_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=LONGITUDE_VALIDATORS,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'({self.id}) user: {self.user.email}'
