from django.db import models

from .profile import ProviderProfile


class ProviderAvailability(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, 'Segunda-feira'
        TUESDAY = 1, 'Terça-feira'
        WEDNESDAY = 2, 'Quarta-feira'
        THURSDAY = 3, 'Quinta-feira'
        FRIDAY = 4, 'Sexta-feira'
        SATURDAY = 5, 'Sábado'
        SUNDAY = 6, 'Domingo'

    provider = models.ForeignKey(
        ProviderProfile,
        on_delete=models.CASCADE,
        related_name='availability',
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['provider', 'weekday', 'start_time']
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_time__lt=models.F('end_time')),
                name='provideravailability_start_before_end',
            ),
            models.UniqueConstraint(
                fields=['provider', 'weekday', 'start_time', 'end_time'],
                name='unique_provider_weekday_interval',
            ),
        ]

    def __str__(self):
        return (
            f'({self.id}) provider: {self.provider.user.email}, '
            f'{self.get_weekday_display()} {self.start_time}-{self.end_time}'
        )
