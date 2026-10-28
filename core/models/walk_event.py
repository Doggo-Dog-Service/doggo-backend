from django.db import models

from .service import Service


class WalkEvent(models.Model):
    class Kind(models.TextChoices):
        PEE = 'pee', 'Xixi'
        POOP = 'poop', 'Cocô'
        WATER = 'water', 'Água'
        PHOTO = 'photo', 'Foto'

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='events')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    image = models.ForeignKey('uploader.Image', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']

    def __str__(self):
        return f'({self.id}) serviço {self.service_id}: {self.kind}'
