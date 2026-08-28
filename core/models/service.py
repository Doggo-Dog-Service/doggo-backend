from django.db import models

from .pet import Pet
from .profile import ClientProfile, ProviderProfile


class ServiceType(models.Model):
    name = models.CharField(max_length=20, null=False, blank=False)
    description = models.TextField()

    def __str__(self):
        return f'({self.id}) {self.name}'


class Service(models.Model):
    class Status(models.IntegerChoices):
        IN_REVIEW = 1, 'Em análise'
        CONFIRMED = 2, 'Confirmado'
        IN_PROGRESS = 3, 'Em andamento'
        COMPLETED = 4, 'Concluído'
        CANCELLED = 5, 'Cancelado'
        REJECTED = 6, 'Recusado'

    pets = models.ManyToManyField(Pet, related_name='services')
    provider = models.ForeignKey(ProviderProfile, on_delete=models.PROTECT, related_name='services')
    client = models.ForeignKey(ClientProfile, on_delete=models.PROTECT, related_name='services')
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name='services')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, null=False, default=Status.IN_REVIEW)
    price = models.DecimalField(max_digits=7, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'({self.id}) provedor: {self.provider.user.email}, cliente: {self.client.user.email}'
