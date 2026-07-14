from django.db import models

from uploader.models import Image

from .profile import ClientProfile


class Pet(models.Model):

    class Size(models.TextChoices):
        SMALL = 'p', 'Pequeno'
        MEDIUM = 'm', 'Médio'
        LARGE = 'g', 'Grande'

    class VaccinationStatus(models.TextChoices):
        PENDING = 'p', 'Pendente'
        CURRENT = 'c', 'Atualizado'

    owner = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='pets')
    name = models.CharField(max_length=50)
    breed = models.CharField(max_length=50, null=True, blank=True)
    size = models.CharField(max_length=1, choices=Size.choices)
    weight = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    pet_picture = models.ForeignKey(
        Image,
        related_name='+',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )

    def __str__(self):
        return f'({self.id}) {self.name}, dono: {self.owner.user.email}'
