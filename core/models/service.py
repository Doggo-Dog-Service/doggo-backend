from django.db import models


class ServiceType(models.Model):
    name = models.CharField(max_length=20, null=False, blank=False)
    description = models.TextField()

    def __str__(self):
        return f'({self.id}) {self.name}'


class Service(models.Model):
    class ServiceStatus(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        IN_PROGRESS = 'in_progress', 'Em andamento'
        FINISHED = 'finished', 'Concluído'

    pet = models.ForeignKey('core.Pet', on_delete=models.PROTECT)
    provider = models.ForeignKey('core.ProviderProfile', on_delete=models.PROTECT)
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ServiceStatus.choices, null=False, default=ServiceStatus.PENDING)
    price = models.DecimalField(max_digits=7, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'({self.id}) provedor: {self.provider.user.email}, pet: {self.pet}'
