from django.db import models

from core.models import Service, User


class Payment(models.Model):
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='payments')
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(decimal_places=2, max_digits=7, null=False, blank=False)
    paid_at = models.DateTimeField(null=False, blank=False)
    created_at = models.DateField(null=False, blank=False, auto_now_add=True)

    def __str__(self):
        return f'({self.id}) {self.service} - valor: {self.amount}'
