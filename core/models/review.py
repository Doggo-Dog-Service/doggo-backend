from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .profile import ClientProfile, ProviderProfile


class Review(models.Model):
    provider = models.ForeignKey(
        ProviderProfile,
        on_delete=models.PROTECT,
        related_name='reviews',
    )
    client = models.ForeignKey(
        ClientProfile,
        on_delete=models.PROTECT,
        related_name='reviews',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ]
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'({self.id}) cliente: {self.client.user.email}'
