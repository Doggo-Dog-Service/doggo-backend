from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.models import ProviderAvailability, Service

BLOCKING_STATUSES = [
    Service.Status.IN_REVIEW,
    Service.Status.CONFIRMED,
    Service.Status.IN_PROGRESS,
]

IN_REVIEW_STATUS = str(Service.Status.IN_REVIEW)
CONFIRMED_STATUS = str(Service.Status.CONFIRMED)
IN_PROGRESS_STATUS = str(Service.Status.IN_PROGRESS)
COMPLETED_STATUS = str(Service.Status.COMPLETED)
CANCELLED_STATUS = str(Service.Status.CANCELLED)
REJECTED_STATUS = str(Service.Status.REJECTED)


def local_now():
    return timezone.localtime(timezone.now())


def combine_local(date, time_of_day):
    tz = timezone.get_current_timezone()
    return datetime.combine(date, time_of_day, tzinfo=tz)


def availability_intervals(provider, date):
    intervals = (
        ProviderAvailability.objects.filter(provider=provider, weekday=date.weekday())
        .order_by('start_time')
    )
    return [
        (combine_local(date, interval.start_time), combine_local(date, interval.end_time))
        for interval in intervals
    ]


def generate_slots(provider, date, duration):
    intervals = availability_intervals(provider, date)
    if not intervals:
        return []

    now = local_now()
    day_start = intervals[0][0]
    day_end = intervals[-1][1]
    blockers = conflicting_services(provider, day_start, day_end)

    slots = []
    for start, end in intervals:
        candidate = start
        while candidate + duration <= end:
            if candidate > now and not _overlaps(candidate, candidate + duration, blockers):
                slots.append(candidate)
            candidate += duration
    return slots


def _overlaps(window_start, window_end, services):
    for service in services:
        if service.start_datetime < window_end and service.end_datetime > window_start:
            return True
    return False


def format_slot(dt):
    """Formata um slot como HH:MM no horário local."""
    return timezone.localtime(dt).strftime('%H:%M')


def fits_in_availability(provider, start, end):
    local_start = timezone.localtime(start)
    local_end = timezone.localtime(end)

    if local_start.date() != local_end.date():
        return False

    for interval_start, interval_end in availability_intervals(provider, local_start.date()):
        if interval_start <= local_start and local_end <= interval_end:
            return True
    return False


def conflicting_services(provider, start, end, exclude_pk=None):
    queryset = Service.objects.filter(
        provider=provider,
        status__in=BLOCKING_STATUSES,
        start_datetime__lt=end,
        end_datetime__isnull=False,
        end_datetime__gt=start,
    )
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset


def has_conflict(provider, start, end, exclude_pk=None):
    return conflicting_services(provider, start, end, exclude_pk=exclude_pk).exists()


def compute_price(provider, start, end):
    duration = end - start
    if duration <= timedelta(0):
        raise ValidationError('O horário final tem que ser maior que o inicial')

    if provider.price_per_hour:
        seconds = Decimal(duration.total_seconds())
        price = provider.price_per_hour * (seconds / Decimal(3600))
    elif provider.price_per_day:
        days = duration.days or 1
        price = provider.price_per_day * Decimal(days)
    else:
        raise ValidationError('O Provedor não possui preço definido')

    return price.quantize(Decimal('0.01'))
